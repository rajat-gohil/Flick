"""
Management command to reconcile historical Swipe records into InteractionLog.

Iterates across historical core_swipe records using keyset cursor pagination,
detecting swipes that lack an InteractionLog entry, and backfills InteractionLog
records with source_swipe_id, processing_status='pending', and backdated created_at.
"""

import logging
from typing import Any, Dict, Optional

from django.core.management.base import BaseCommand

from core.services.historical_reconciliation import (
    DEFAULT_BATCH_SIZE,
    HistoricalReconciliationService,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Reconciles historical core_swipe records into core_interactionlog audit ledger. "
        "Inspects swipes against existing interaction logs using source_swipe_id and composite keys. "
        "Creates missing InteractionLog entries with processing_status='pending' and historical created_at. "
        "Safe to retry idempotently; never modifies or deletes existing InteractionLogs."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Number of Swipe records to inspect per keyset batch (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum total Swipe records to inspect in this invocation (default: process until finished).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate reconciliation without making any database modifications (0 DB mutations).",
        )
        parser.add_argument(
            "--start-after-id",
            type=int,
            default=0,
            help="Swipe ID to resume scanning after for keyset pagination (default: 0).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        batch_size: int = options["batch_size"]
        limit: Optional[int] = options["limit"]
        dry_run: bool = options["dry_run"]
        start_after_id: int = options["start_after_id"]

        mode_str = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.NOTICE(
                f"{mode_str}Starting Historical Interaction Reconciliation\n"
                f"  Batch Size:     {batch_size}\n"
                f"  Limit:          {limit if limit is not None else 'None (all unreconciled swipes)'}\n"
                f"  Dry Run:        {dry_run}\n"
                f"  Start After ID: {start_after_id}\n"
            )
        )

        def on_batch_progress(batch_metrics: Dict[str, Any]) -> None:
            self.stdout.write(
                f"  Batch {batch_metrics['batch_number']}: "
                f"Scanned {batch_metrics['batch_scanned']} (Total Scanned: {batch_metrics['total_scanned']}), "
                f"Reconciled: {batch_metrics['batch_reconciled']} (Total Reconciled: {batch_metrics['total_reconciled']}), "
                f"Skipped: {batch_metrics['batch_skipped']} (Total Skipped: {batch_metrics['total_skipped']}), "
                f"Last ID: {batch_metrics['last_scanned_id']}"
            )

        try:
            result = HistoricalReconciliationService.reconcile(
                dry_run=dry_run,
                limit=limit,
                batch_size=batch_size,
                start_after_id=start_after_id,
                progress_callback=on_batch_progress,
            )
        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(f"Historical reconciliation failed with error: {exc}")
            )
            raise

        swipes_scanned = result["swipes_scanned"]
        swipes_reconciled = result["swipes_reconciled"]
        swipes_skipped = result["swipes_skipped"]
        batches_processed = result["batches_processed"]
        last_scanned_id = result["last_scanned_id"]
        completed = result["completed"]

        status_text = "COMPLETED" if completed else "INCOMPLETE (resumable)"
        status_style = self.style.SUCCESS if completed else self.style.WARNING

        self.stdout.write(
            status_style(
                f"\nHistorical Reconciliation Result: {status_text}\n"
                f"  Swipes Scanned:     {swipes_scanned}\n"
                f"  Swipes Reconciled:  {swipes_reconciled}\n"
                f"  Swipes Skipped:     {swipes_skipped}\n"
                f"  Batches Processed:  {batches_processed}\n"
                f"  Last Scanned ID:    {last_scanned_id}\n"
                f"  Dry Run:            {dry_run}\n"
            )
        )
