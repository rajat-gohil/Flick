"""
Historical Interaction Reconciliation Service.

Inspects historical `core_swipe` records against `core_interactionlog` using
`source_swipe_id` and composite keys to reconstruct missing InteractionLog
events idempotently and without mutating existing interaction logs.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from django.db import transaction
from django.db.models import Case, DateTimeField, Value, When
from django.utils import timezone

from core.models import InteractionLog, Swipe

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100


def map_swipe_reaction(reaction: str) -> Tuple[str, float]:
    """
    Maps a Swipe reaction string to (event_type, weight).

    Reaction choices in core.models.Swipe:
        - 'like': event_type='swipe_like', weight=1.0
        - 'dislike': event_type='swipe_dislike', weight=-1.2
        - 'superlike': event_type='superlike', weight=3.0
    """
    r = (reaction or "").strip().lower()
    if r == "superlike":
        return "superlike", 3.0
    elif r == "dislike":
        return "swipe_dislike", -1.2
    elif r == "like":
        return "swipe_like", 1.0
    else:
        return f"swipe_{r}", 1.0


class HistoricalReconciliationService:
    """
    Reconciles historical Swipe interactions into the unified InteractionLog audit ledger.

    Guarantees:
        - Idempotency: Duplicate runs detect existing source_swipe_id or composite keys
          and skip already-reconciled swipes with zero duplicates.
        - Non-mutating: Existing InteractionLog records are never modified or deleted.
        - Backdating: Preserves historical swipe.created_at by overriding auto_now_add.
        - Dry-run safety: dry_run=True executes inspection and reporting with zero DB mutations.
        - Keyset cursor pagination: Resumable and bounded memory usage across arbitrarily large tables.
    """

    DEFAULT_BATCH_SIZE = DEFAULT_BATCH_SIZE

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE):
        self.batch_size = batch_size

    @classmethod
    def reconcile(
        cls,
        dry_run: bool = False,
        limit: Optional[int] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        start_after_id: int = 0,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Executes historical swipe reconciliation.

        Args:
            dry_run: If True, inspects and counts missing records without writing to the database.
            limit: Maximum total swipes to inspect in this invocation (None for all).
            batch_size: Number of Swipe rows to fetch and inspect per batch.
            start_after_id: Keyset cursor starting point (scans Swipe.id > start_after_id).
            progress_callback: Optional callback receiving per-batch metrics dict.

        Returns:
            Dict containing execution summary metrics.
        """
        total_scanned = 0
        total_reconciled = 0
        total_skipped = 0
        batches_processed = 0
        last_id = start_after_id
        completed = False

        logger.info(
            "Starting HistoricalReconciliationService (dry_run=%s, limit=%s, batch_size=%s, start_after_id=%s)",
            dry_run,
            limit,
            batch_size,
            start_after_id,
        )

        while True:
            current_batch_size = batch_size
            if limit is not None:
                remaining = limit - total_scanned
                if remaining <= 0:
                    completed = False
                    break
                current_batch_size = min(current_batch_size, remaining)

            swipes: List[Swipe] = list(
                Swipe.objects.filter(id__gt=last_id).order_by("id")[:current_batch_size]
            )

            if not swipes:
                completed = True
                break

            batch_count = len(swipes)
            last_id = swipes[-1].id
            total_scanned += batch_count
            batches_processed += 1

            batch_swipe_ids = [s.id for s in swipes]
            user_ids = {s.user_id for s in swipes}
            session_ids = {s.session_id for s in swipes}
            movie_ids = {s.movie_id for s in swipes}

            # 1. Inspect existing logs by source_swipe_id
            existing_source_ids: Set[int] = set(
                InteractionLog.objects.filter(
                    source_swipe_id__in=batch_swipe_ids
                ).values_list("source_swipe_id", flat=True)
            )

            # 2. Inspect existing logs by composite key (user, session, movie) with swipe event types
            existing_composite_keys: Set[Tuple[int, Optional[int], int]] = set(
                InteractionLog.objects.filter(
                    user_id__in=user_ids,
                    session_id__in=session_ids,
                    movie_id__in=movie_ids,
                    event_type__in=["swipe_like", "swipe_dislike", "superlike"],
                ).values_list("user_id", "session_id", "movie_id")
            )

            # In-memory deduplication set to avoid duplicates within the same batch
            seen_composite_keys: Set[Tuple[int, Optional[int], int]] = set(existing_composite_keys)

            unreconciled_swipes: List[Swipe] = []
            new_logs: List[InteractionLog] = []

            for swipe in swipes:
                composite_key = (swipe.user_id, swipe.session_id, swipe.movie_id)

                # Skip if already reconciled via source_swipe_id or matching composite key
                if swipe.id in existing_source_ids:
                    continue
                if composite_key in seen_composite_keys:
                    continue

                seen_composite_keys.add(composite_key)
                unreconciled_swipes.append(swipe)

                event_type, weight = map_swipe_reaction(swipe.reaction)
                log_id = uuid.uuid4()

                log_entry = InteractionLog(
                    id=log_id,
                    user_id=swipe.user_id,
                    session_id=swipe.session_id,
                    movie_id=swipe.movie_id,
                    event_type=event_type,
                    weight=weight,
                    source_swipe_id=swipe.id,
                    processing_status="pending",
                    metadata={
                        "reconciled": True,
                        "source": "historical_swipe",
                        "original_swipe_id": swipe.id,
                    },
                )
                new_logs.append(log_entry)

            batch_reconciled = len(unreconciled_swipes)
            batch_skipped = batch_count - batch_reconciled
            total_reconciled += batch_reconciled
            total_skipped += batch_skipped

            if not dry_run and new_logs:
                with transaction.atomic():
                    InteractionLog.objects.bulk_create(new_logs)
                    # Override auto_now_add on created_at to preserve original swipe timestamp
                    try:
                        when_clauses = [
                            When(
                                id=log.id,
                                then=Value(swipe.created_at or timezone.now()),
                            )
                            for log, swipe in zip(new_logs, unreconciled_swipes)
                        ]
                        InteractionLog.objects.filter(
                            id__in=[log.id for log in new_logs]
                        ).update(
                            created_at=Case(*when_clauses, output_field=DateTimeField())
                        )
                    except Exception as err:
                        logger.warning(
                            "Case/When created_at update fallback to per-item update: %s",
                            err,
                        )
                        for log, swipe in zip(new_logs, unreconciled_swipes):
                            InteractionLog.objects.filter(id=log.id).update(
                                created_at=swipe.created_at or timezone.now()
                            )

            batch_summary = {
                "batch_number": batches_processed,
                "batch_scanned": batch_count,
                "batch_reconciled": batch_reconciled,
                "batch_skipped": batch_skipped,
                "total_scanned": total_scanned,
                "total_reconciled": total_reconciled,
                "total_skipped": total_skipped,
                "last_scanned_id": last_id,
            }

            if progress_callback is not None:
                try:
                    progress_callback(batch_summary)
                except Exception as cb_err:
                    logger.warning("Error in progress callback: %s", cb_err)

            logger.debug(
                "Batch %d complete: %d scanned, %d reconciled, %d skipped",
                batches_processed,
                batch_count,
                batch_reconciled,
                batch_skipped,
            )

        summary = {
            "swipes_scanned": total_scanned,
            "swipes_reconciled": total_reconciled,
            "swipes_skipped": total_skipped,
            "reconciled_count": total_reconciled,
            "scanned_count": total_scanned,
            "skipped_count": total_skipped,
            "batches_processed": batches_processed,
            "dry_run": dry_run,
            "limit": limit,
            "last_scanned_id": last_id,
            "completed": completed,
        }

        logger.info(
            "Historical reconciliation finished: scanned=%d, reconciled=%d, skipped=%d, dry_run=%s, completed=%s",
            total_scanned,
            total_reconciled,
            total_skipped,
            dry_run,
            completed,
        )

        return summary


def reconcile_historical_interactions(
    dry_run: bool = False,
    limit: Optional[int] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    start_after_id: int = 0,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Convenience function executing HistoricalReconciliationService.reconcile.
    """
    return HistoricalReconciliationService.reconcile(
        dry_run=dry_run,
        limit=limit,
        batch_size=batch_size,
        start_after_id=start_after_id,
        progress_callback=progress_callback,
    )
