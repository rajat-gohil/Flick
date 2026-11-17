"""
Permanent 90-Day Catalogue Staleness Sweep Service.

Iterates across eligible catalogue movies using keyset cursor pagination,
detecting movies that either have never been enriched or whose enrichment
is older than 90 days, and enqueuing them into the low-priority queue (priority 200)
for enrichment without starving interactive/high-priority sync operations.
"""

from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import CatalogueJob, Movie, StalenessSweepCheckpoint
from core.services.catalogue_queue import CatalogueQueueService

logger = logging.getLogger(__name__)

DEFAULT_SWEEP_NAME = "90_day_movie_staleness"
DEFAULT_STALENESS_DAYS = 90
DEFAULT_BATCH_SIZE = 50
STALENESS_ENQUEUE_PRIORITY = 200

# Provenance values eligible for staleness sweeps
ELIGIBLE_PROVENANCE_VALUES = ("tmdb_catalogue", "manual_curated")

# Provenance values strictly excluded from staleness sweeps
STRICT_EXCLUDED_PROVENANCE_VALUES = ("synthetic_fixture", "needs_review")


class StalenessSweepService:
    """
    Permanent 90-day staleness sweep service with cursor-based keyset pagination.
    """

    DEFAULT_SWEEP_NAME = DEFAULT_SWEEP_NAME
    DEFAULT_STALENESS_DAYS = DEFAULT_STALENESS_DAYS
    DEFAULT_BATCH_SIZE = DEFAULT_BATCH_SIZE
    STALENESS_ENQUEUE_PRIORITY = STALENESS_ENQUEUE_PRIORITY
    ELIGIBLE_PROVENANCE_VALUES = ELIGIBLE_PROVENANCE_VALUES
    STRICT_EXCLUDED_PROVENANCE_VALUES = STRICT_EXCLUDED_PROVENANCE_VALUES

    @classmethod
    def get_or_create_checkpoint(
        cls, sweep_name: str = DEFAULT_SWEEP_NAME, select_for_update: bool = False
    ) -> StalenessSweepCheckpoint:
        """
        Retrieves or creates the StalenessSweepCheckpoint for the given sweep name.
        """
        qs = StalenessSweepCheckpoint.objects.all()
        if select_for_update:
            qs = qs.select_for_update()
        checkpoint, _ = qs.get_or_create(sweep_name=sweep_name)
        return checkpoint

    @classmethod
    def reset_checkpoint(
        cls, sweep_name: str = DEFAULT_SWEEP_NAME, dry_run: bool = False
    ) -> StalenessSweepCheckpoint:
        """
        Resets last_scanned_id to 0 and resets sweep metrics.
        """
        with transaction.atomic():
            checkpoint = cls.get_or_create_checkpoint(sweep_name=sweep_name, select_for_update=True)
            checkpoint.last_scanned_id = 0
            checkpoint.records_scanned = 0
            checkpoint.records_enqueued = 0
            checkpoint.records_skipped = 0
            checkpoint.is_in_progress = False
            checkpoint.last_error = ""
            if not dry_run:
                checkpoint.save()
            return checkpoint

    @classmethod
    def run_sweep(
        cls,
        batch_size: int = DEFAULT_BATCH_SIZE,
        limit: Optional[int] = None,
        dry_run: bool = False,
        force_reset: bool = False,
        staleness_days: int = DEFAULT_STALENESS_DAYS,
        sweep_name: str = DEFAULT_SWEEP_NAME,
    ) -> Dict[str, Any]:
        """
        Executes a staleness sweep over eligible movies.

        Args:
            batch_size: Number of records to query and advance per cursor batch.
            limit: Maximum total records to process in this run. If None, sweeps to completion.
            dry_run: If True, simulates enqueueing without DB modifications.
            force_reset: If True, resets cursor last_scanned_id to 0 before running.
            staleness_days: Age threshold in days (default: 90 days).
            sweep_name: Checkpoint identifier (default: '90_day_movie_staleness').

        Returns:
            Dict containing execution summary metrics.
        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        if limit is not None and limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")

        if force_reset:
            cls.reset_checkpoint(sweep_name=sweep_name, dry_run=dry_run)

        total_scanned = 0
        total_enqueued = 0
        total_skipped = 0
        sweep_completed = False

        try:
            # If dry_run, maintain simulated cursor in memory without modifying DB checkpoint
            simulated_cursor_id: Optional[int] = None
            if dry_run:
                initial_cp = cls.get_or_create_checkpoint(sweep_name=sweep_name, select_for_update=False)
                simulated_cursor_id = initial_cp.last_scanned_id

            while True:
                # Determine current batch limit if total limit specified
                if limit is not None:
                    remaining = limit - total_scanned
                    if remaining <= 0:
                        break
                    current_batch_size = min(batch_size, remaining)
                else:
                    current_batch_size = batch_size

                if dry_run:
                    cutoff = timezone.now() - timedelta(days=staleness_days)
                    batch_qs = (
                        Movie.objects.filter(
                            id__gt=simulated_cursor_id,
                            provenance__in=ELIGIBLE_PROVENANCE_VALUES,
                        )
                        .filter(
                            Q(last_enriched_at__lt=cutoff) | Q(last_enriched_at__isnull=True)
                        )
                        .order_by("id")[:current_batch_size]
                    )
                    movies = list(batch_qs)

                    if not movies:
                        sweep_completed = True
                        break

                    simulated_cursor_id = max(m.id for m in movies)
                    total_scanned += len(movies)
                    total_enqueued += len(movies)

                    if limit is not None and total_scanned >= limit:
                        break
                    continue

                # Live Execution with atomic transaction per batch
                with transaction.atomic():
                    checkpoint = cls.get_or_create_checkpoint(sweep_name=sweep_name, select_for_update=True)

                    if not checkpoint.is_in_progress:
                        checkpoint.is_in_progress = True
                        checkpoint.save(update_fields=["is_in_progress", "updated_at"])

                    cutoff = timezone.now() - timedelta(days=staleness_days)

                    batch_qs = (
                        Movie.objects.filter(
                            id__gt=checkpoint.last_scanned_id,
                            provenance__in=ELIGIBLE_PROVENANCE_VALUES,
                        )
                        .filter(
                            Q(last_enriched_at__lt=cutoff) | Q(last_enriched_at__isnull=True)
                        )
                        .order_by("id")[:current_batch_size]
                    )
                    movies = list(batch_qs)

                    if not movies:
                        sweep_completed = True
                        checkpoint.last_scanned_id = 0
                        checkpoint.last_sweep_completed_at = timezone.now()
                        checkpoint.is_in_progress = False
                        checkpoint.save()
                        break

                    # If starting fresh cycle from id 0, reset sweep cycle counters
                    if checkpoint.last_scanned_id == 0 and total_scanned == 0:
                        checkpoint.records_scanned = 0
                        checkpoint.records_enqueued = 0
                        checkpoint.records_skipped = 0

                    batch_enqueued = 0
                    batch_skipped = 0

                    for movie in movies:
                        job, created = CatalogueQueueService.enqueue(
                            job_type="catalogue_enrichment",
                            entity_type="movie",
                            entity_id=str(movie.id),
                            external_id=str(movie.tmdb_id) if movie.tmdb_id is not None else "",
                            priority=STALENESS_ENQUEUE_PRIORITY,
                        )
                        if created:
                            batch_enqueued += 1
                        else:
                            batch_skipped += 1

                    max_id = max(m.id for m in movies)
                    checkpoint.last_scanned_id = max_id
                    checkpoint.records_scanned += len(movies)
                    checkpoint.records_enqueued += batch_enqueued
                    checkpoint.records_skipped += batch_skipped
                    checkpoint.save()

                    total_scanned += len(movies)
                    total_enqueued += batch_enqueued
                    total_skipped += batch_skipped

                if limit is not None and total_scanned >= limit:
                    break

        except Exception as exc:
            logger.exception("Error during staleness sweep '%s': %s", sweep_name, exc)
            if not dry_run:
                try:
                    with transaction.atomic():
                        cp = cls.get_or_create_checkpoint(sweep_name=sweep_name, select_for_update=True)
                        cp.last_error = str(exc)
                        cp.save(update_fields=["last_error", "updated_at"])
                except Exception:
                    pass
            raise

        checkpoint = StalenessSweepCheckpoint.objects.get(sweep_name=sweep_name)
        final_last_scanned_id = (
            simulated_cursor_id if dry_run and simulated_cursor_id is not None else checkpoint.last_scanned_id
        )

        return {
            "sweep_name": sweep_name,
            "records_scanned": total_scanned,
            "records_enqueued": total_enqueued,
            "records_skipped": total_skipped,
            "sweep_completed": sweep_completed,
            "last_scanned_id": final_last_scanned_id,
            "dry_run": dry_run,
            "checkpoint": {
                "sweep_name": checkpoint.sweep_name,
                "last_scanned_id": checkpoint.last_scanned_id,
                "is_in_progress": checkpoint.is_in_progress,
                "records_scanned": checkpoint.records_scanned,
                "records_enqueued": checkpoint.records_enqueued,
                "records_skipped": checkpoint.records_skipped,
                "last_sweep_completed_at": checkpoint.last_sweep_completed_at,
                "last_error": checkpoint.last_error,
            },
        }


def run_staleness_sweep(
    batch_size: int = DEFAULT_BATCH_SIZE,
    limit: Optional[int] = None,
    dry_run: bool = False,
    force_reset: bool = False,
    staleness_days: int = DEFAULT_STALENESS_DAYS,
    sweep_name: str = DEFAULT_SWEEP_NAME,
) -> Dict[str, Any]:
    """
    Convenience functional wrapper for StalenessSweepService.run_sweep.
    """
    return StalenessSweepService.run_sweep(
        batch_size=batch_size,
        limit=limit,
        dry_run=dry_run,
        force_reset=force_reset,
        staleness_days=staleness_days,
        sweep_name=sweep_name,
    )
