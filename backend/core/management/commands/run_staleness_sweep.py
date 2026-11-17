"""
Management command to run the 90-day catalogue staleness sweep.

Executes keyset cursor pagination to identify and enqueue stale catalogue movies
for background enrichment at low priority (priority 200).
"""

from datetime import timedelta
import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.services.staleness_sweep import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_STALENESS_DAYS,
    DEFAULT_SWEEP_NAME,
    run_staleness_sweep,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Runs the permanent 90-day catalogue staleness sweep. "
        "Iterates over eligible movies (tmdb_catalogue, manual_curated) using cursor keyset pagination "
        "and enqueues stale or unenriched movies for low-priority background enrichment."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Number of records per keyset cursor batch (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum records to process in this invocation (default: process until sweep completion).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate the sweep without creating jobs or advancing database checkpoints.",
        )
        parser.add_argument(
            "--force-reset",
            action="store_true",
            default=False,
            help="Reset the sweep cursor (last_scanned_id) to 0 before running.",
        )
        parser.add_argument(
            "--staleness-days",
            type=int,
            default=DEFAULT_STALENESS_DAYS,
            help=f"Staleness threshold in days (default: {DEFAULT_STALENESS_DAYS}).",
        )
        parser.add_argument(
            "--sweep-name",
            type=str,
            default=DEFAULT_SWEEP_NAME,
            help=f"Sweep checkpoint identifier (default: '{DEFAULT_SWEEP_NAME}').",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        batch_size: int = options["batch_size"]
        limit: int | None = options["limit"]
        dry_run: bool = options["dry_run"]
        force_reset: bool = options["force_reset"]
        staleness_days: int = options["staleness_days"]
        sweep_name: str = options["sweep_name"]

        cutoff_date = timezone.now() - timedelta(days=staleness_days)

        mode_str = "[DRY-RUN] " if dry_run else ""
        self.stdout.write(
            self.style.NOTICE(
                f"{mode_str}Starting 90-Day Staleness Sweep ('{sweep_name}')\n"
                f"  Staleness Cutoff: < {cutoff_date.isoformat()} ({staleness_days} days ago)\n"
                f"  Batch Size:       {batch_size}\n"
                f"  Limit:            {limit if limit is not None else 'None (sweep to completion)'}\n"
                f"  Force Reset:      {force_reset}\n"
            )
        )

        try:
            result = run_staleness_sweep(
                batch_size=batch_size,
                limit=limit,
                dry_run=dry_run,
                force_reset=force_reset,
                staleness_days=staleness_days,
                sweep_name=sweep_name,
            )
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Staleness sweep failed with error: {exc}"))
            raise

        records_scanned = result["records_scanned"]
        records_enqueued = result["records_enqueued"]
        records_skipped = result["records_skipped"]
        sweep_completed = result["sweep_completed"]
        last_scanned_id = result["last_scanned_id"]
        cp_info = result["checkpoint"]

        status_text = "COMPLETED" if sweep_completed else "IN PROGRESS (resumable)"
        status_style = self.style.SUCCESS if sweep_completed else self.style.WARNING

        self.stdout.write(
            status_style(
                f"\nStaleness Sweep Result: {status_text}\n"
                f"  Run Scanned:            {records_scanned}\n"
                f"  Run Enqueued:           {records_enqueued}\n"
                f"  Run Skipped / Deduped:  {records_skipped}\n"
                f"  Final Cursor ID:        {last_scanned_id}\n"
                f"  Checkpoint In Progress: {cp_info.get('is_in_progress')}\n"
                f"  Cumulative Scanned:     {cp_info.get('records_scanned')}\n"
                f"  Cumulative Enqueued:    {cp_info.get('records_enqueued')}\n"
                f"  Last Completed At:      {cp_info.get('last_sweep_completed_at')}\n"
            )
        )
