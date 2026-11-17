"""
Management command to poll the TMDB Movie Changes Feed.

CLI flags:
  --start-date: Optional window start date (YYYY-MM-DD)
  --end-date: Optional window end date (YYYY-MM-DD)
  --limit-pages: Maximum number of pages to process in this run
  --dry-run: Simulate polling and matching without enqueuing jobs or mutating checkpoints
  --force-reset: Force reset of the cursor and clear in_progress lock
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from core.services.tmdb_changes import (
    PollerLockedError,
    RateLimitBackoffError,
    StalePollerOwnershipError,
    TmdbChangesService,
    TmdbConfigError,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Polls the TMDB Movie Changes Feed and enqueues durable enrichment jobs for matching movies."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--start-date",
            type=str,
            default=None,
            help="Window start date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=None,
            help="Window end date in YYYY-MM-DD format.",
        )
        parser.add_argument(
            "--limit-pages",
            type=int,
            default=None,
            help="Maximum number of pages to poll in this run.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate polling without enqueuing jobs or updating the checkpoint.",
        )
        parser.add_argument(
            "--force-reset",
            action="store_true",
            default=False,
            help="Reset the checkpoint cursor and override any existing lock.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        limit_pages = options.get("limit_pages")
        dry_run = options.get("dry_run", False)
        force_reset = options.get("force_reset", False)

        start_date = None
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except ValueError:
                raise CommandError(f"Invalid --start-date format '{start_date_str}'. Expected YYYY-MM-DD.")

        end_date = None
        if end_date_str:
            try:
                end_date = datetime.date.fromisoformat(end_date_str)
            except ValueError:
                raise CommandError(f"Invalid --end-date format '{end_date_str}'. Expected YYYY-MM-DD.")

        self.stdout.write(
            self.style.NOTICE(
                f"Starting TMDB Changes Feed Poller (dry_run={dry_run}, force_reset={force_reset}, limit_pages={limit_pages})..."
            )
        )

        service = TmdbChangesService()

        try:
            metrics = service.poll(
                start_date=start_date,
                end_date=end_date,
                limit_pages=limit_pages,
                dry_run=dry_run,
                force_reset=force_reset,
            )
        except PollerLockedError as exc:
            self.stdout.write(self.style.WARNING(f"Skipped polling: {exc}"))
            return
        except StalePollerOwnershipError as exc:
            self.stdout.write(self.style.WARNING(f"Poller ownership lost: {exc}"))
            return
        except RateLimitBackoffError as exc:
            self.stdout.write(self.style.WARNING(f"Rate limited: {exc}"))
            return
        except TmdbConfigError as exc:
            self.stderr.write(self.style.ERROR(f"Configuration error: {exc}"))
            raise CommandError(str(exc))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Poller encountered an error: {exc}"))
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS("TMDB Changes Feed polling completed successfully."))
        self.stdout.write(
            f"Metrics: Window: {metrics['window_start_date']} -> {metrics['window_end_date']} | "
            f"Pages Processed: {metrics['pages_processed']} | "
            f"Changes Detected: {metrics['changes_detected']} | "
            f"Changes Enqueued: {metrics['changes_enqueued']} | "
            f"Window Completed: {metrics['completed_window']}"
        )
