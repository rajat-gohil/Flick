"""
TMDB Changes Feed polling service for Flick Batch 3.

Features & Invariants:
1. Strict 14-Day Date Window Clamp:
   - TMDB rejects intervals > 14 days. If end_date - start_date >= 14 days, clamp end_date = start_date + 13 days.
2. Cold Start:
   - If no checkpoint exists or dates are null, default start_date = today - 13 days, end_date = today.
3. Concurrency Safety:
   - If checkpoint.is_in_progress is True and lock was updated recently (< 5 minutes), abort/skip.
4. Token Acquisition & Rate Limiting:
   - acquire_tmdb_token("background").
   - Handle HTTP 429 via record_tmdb_429 and abort/pause.
5. Ingestion & Filtering:
   - Filters TMDB change results against local Movie records where
     provenance in ('tmdb_catalogue', 'manual_curated').
   - For matching movies, enqueues durable enrichment job via:
     CatalogueQueueService.enqueue(
         job_type='catalogue_enrichment',
         entity_type='movie',
         entity_id=str(movie.id),
         external_id=str(movie.tmdb_id),
         priority=100
     )
6. Transactional Checkpoint Advancement:
   - Checkpoint current_page and metrics advance ONLY inside an atomic transaction
     AFTER all matching jobs for that page are enqueued.
7. Window Completion:
   - Advances window_start_date = window_end_date (with optional overlap), resets page counters,
     and clears is_in_progress.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import Movie, TmdbChangesCheckpoint
from core.services.catalogue_queue import CatalogueQueueService
from core.services.tmdb_rate_limiter import acquire_tmdb_token, record_tmdb_429

logger = logging.getLogger(__name__)

TMDB_CHANGES_URL = "https://api.themoviedb.org/3/movie/changes"
DEFAULT_LOCK_TIMEOUT_SECONDS = 300  # 5 minutes
MAX_WINDOW_DAYS = 14  # Max allowed window by TMDB API is 14 days (< 14 days difference)


class PollerLockedError(Exception):
    """Raised when another TMDB changes poller instance currently holds an active lock."""
    pass


class StalePollerOwnershipError(Exception):
    """Raised when a poller attempts to advance or finalize checkpoint after its lock was overridden."""
    pass


class TmdbConfigError(Exception):
    """Raised when TMDB API configuration is missing or invalid."""
    pass


class RateLimitBackoffError(Exception):
    """Raised when a TMDB HTTP 429 rate limit is encountered."""
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


class TmdbChangesService:
    """Service to safely poll TMDB Movie Changes Feed and enqueue enrichment jobs."""

    def __init__(self, feed_name: str = "movie_changes", lock_timeout_seconds: int = DEFAULT_LOCK_TIMEOUT_SECONDS):
        self.feed_name = feed_name
        self.lock_timeout_seconds = lock_timeout_seconds
        self.lock_token: Optional[uuid.UUID] = None
        self.lock_generation: int = 0

    @staticmethod
    def clamp_date_window(
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Tuple[datetime.date, datetime.date]:
        """
        Clamp date window to strict TMDB rules.
        TMDB rejects intervals >= 14 days (i.e. end_date - start_date >= 14 days).
        If end_date - start_date >= 14 days:
            end_date = start_date + 13 days (14 total calendar days inclusive).
        If end_date < start_date:
            end_date = start_date
        """
        if end_date < start_date:
            end_date = start_date

        delta = (end_date - start_date).days
        if delta >= MAX_WINDOW_DAYS:
            end_date = start_date + datetime.timedelta(days=MAX_WINDOW_DAYS - 1)

        return start_date, end_date

    def get_or_init_checkpoint(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        force_reset: bool = False,
        dry_run: bool = False,
    ) -> TmdbChangesCheckpoint:
        """
        Loads or initializes the checkpoint within atomic transaction with row lock.
        Validates lock freshness and concurrency, issuing generation fencing token.
        When dry_run=True, creates/loads in-memory checkpoint without persisting lock or state to DB.
        """
        now = timezone.now()
        today = now.date()

        if dry_run:
            checkpoint = TmdbChangesCheckpoint.objects.filter(feed_name=self.feed_name).first()
            if not checkpoint:
                checkpoint = TmdbChangesCheckpoint(
                    feed_name=self.feed_name,
                    window_start_date=today - datetime.timedelta(days=13),
                    window_end_date=today,
                    current_page=1,
                    total_pages=1,
                    is_in_progress=False,
                )
            if start_date is not None:
                checkpoint.window_start_date = start_date
            elif checkpoint.window_start_date is None:
                checkpoint.window_start_date = today - datetime.timedelta(days=13)

            if end_date is not None:
                checkpoint.window_end_date = end_date
            elif checkpoint.window_end_date is None:
                checkpoint.window_end_date = today

            c_start, c_end = self.clamp_date_window(checkpoint.window_start_date, checkpoint.window_end_date)
            checkpoint.window_start_date = c_start
            checkpoint.window_end_date = c_end
            self.lock_token = checkpoint.lock_token or uuid.uuid4()
            self.lock_generation = checkpoint.lock_generation or 1
            return checkpoint

        with transaction.atomic():
            checkpoint, created = TmdbChangesCheckpoint.objects.select_for_update().get_or_create(
                feed_name=self.feed_name,
                defaults={
                    "window_start_date": today - datetime.timedelta(days=13),
                    "window_end_date": today,
                    "current_page": 1,
                    "total_pages": 1,
                    "is_in_progress": False,
                    "lock_generation": 0,
                },
            )

            # Concurrency check if already in progress and not expired
            if checkpoint.is_in_progress and not force_reset:
                if checkpoint.updated_at:
                    elapsed = (now - checkpoint.updated_at).total_seconds()
                    if elapsed < self.lock_timeout_seconds:
                        raise PollerLockedError(
                            f"TMDB Changes feed '{self.feed_name}' is locked by another worker (updated {elapsed:.1f}s ago)."
                        )
                    else:
                        logger.warning(
                            f"Overriding stale TMDB changes poller lock for '{self.feed_name}' (held for {elapsed:.1f}s)."
                        )

            # If force reset requested or dates manually provided
            if force_reset:
                checkpoint.current_page = 1
                checkpoint.total_pages = 1
                checkpoint.changes_detected_count = 0
                checkpoint.changes_enqueued_count = 0
                checkpoint.is_in_progress = False
                checkpoint.last_error = ""

            if start_date is not None:
                checkpoint.window_start_date = start_date
            elif checkpoint.window_start_date is None:
                checkpoint.window_start_date = today - datetime.timedelta(days=13)

            if end_date is not None:
                checkpoint.window_end_date = end_date
            elif checkpoint.window_end_date is None:
                checkpoint.window_end_date = today

            # Clamp window dates
            c_start, c_end = self.clamp_date_window(
                checkpoint.window_start_date, checkpoint.window_end_date
            )
            checkpoint.window_start_date = c_start
            checkpoint.window_end_date = c_end

            # Fencing tokens
            self.lock_token = uuid.uuid4()
            self.lock_generation = (checkpoint.lock_generation or 0) + 1

            checkpoint.lock_token = self.lock_token
            checkpoint.lock_generation = self.lock_generation
            checkpoint.is_in_progress = True
            checkpoint.save(update_fields=[
                "window_start_date", "window_end_date", "current_page",
                "total_pages", "changes_detected_count", "changes_enqueued_count",
                "is_in_progress", "lock_token", "lock_generation", "last_error", "updated_at",
            ])
            return checkpoint

    def fetch_changes_page(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        page: int,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Acquires rate limit token and fetches one page from TMDB movie changes endpoint.
        In dry-run mode, safely simulates changes discovery from local catalogue sample
        without making any external network requests or consuming live rate-limit budget.
        """
        if dry_run:
            logger.info(
                f"[DRY-RUN] Simulating TMDB changes page {page} for window {start_date} -> {end_date} (no external HTTP calls)."
            )
            sample_ids = list(
                Movie.objects.filter(
                    provenance__in=["tmdb_catalogue", "manual_curated"],
                    tmdb_id__isnull=False,
                ).values_list("tmdb_id", flat=True)[:10]
            )
            simulated_results = [{"id": tid, "adult": False} for tid in sample_ids]
            return {
                "page": page,
                "total_pages": 1,
                "results": simulated_results,
                "total_results": len(simulated_results),
            }

        api_key = getattr(settings, "TMDB_API_KEY", "")
        if not api_key:
            raise TmdbConfigError("TMDB_API_KEY is not configured in Django settings.")

        token_ok = acquire_tmdb_token("background")
        if not token_ok:
            raise RateLimitBackoffError("TMDB rate limit budget exhausted; rate limiter denied token", 5.0)

        params = {
            "api_key": api_key,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "page": page,
        }

        try:
            resp = requests.get(TMDB_CHANGES_URL, params=params, timeout=(3.05, 12.0))
        except requests.RequestException as exc:
            logger.error(f"HTTP request failed while fetching TMDB changes: {exc}")
            raise

        if resp.status_code == 429:
            retry_after_header = resp.headers.get("Retry-After")
            cooldown = record_tmdb_429(retry_after_header)
            raise RateLimitBackoffError(f"TMDB returned HTTP 429 rate limit. Cooldown: {cooldown}s", cooldown)

        resp.raise_for_status()
        return resp.json()

    def process_page_results(
        self,
        results: List[Dict[str, Any]],
        page: int,
        total_pages: int,
        dry_run: bool = False,
    ) -> Tuple[int, int]:
        """
        Processes a page of results:
        1. Extracts tmdb_ids.
        2. Filters for local movies with tmdb_id in ids and provenance in ('tmdb_catalogue', 'manual_curated').
        3. Fencing check: verifies lock_token and lock_generation under row-lock.
        4. Enqueues durable enrichment jobs for matching movies.
        5. Transactionally updates the checkpoint cursor ONLY in the same atomic transaction!
        
        Returns (detected_count, enqueued_count).
        """
        detected_count = len(results)
        tmdb_ids = [item.get("id") for item in results if item.get("id") is not None]

        matching_movies = list(
            Movie.objects.filter(
                tmdb_id__in=tmdb_ids,
                provenance__in=["tmdb_catalogue", "manual_curated"],
            ).only("id", "tmdb_id")
        )

        enqueued_count = 0
        if not dry_run:
            with transaction.atomic():
                # Check generation and lock_token fencing BEFORE mutating any state!
                chk = TmdbChangesCheckpoint.objects.select_for_update().get(feed_name=self.feed_name)
                if chk.lock_token != self.lock_token or chk.lock_generation != self.lock_generation:
                    raise StalePollerOwnershipError(
                        f"Poller lost lock ownership for '{self.feed_name}'. "
                        f"Current (gen={chk.lock_generation}, token={chk.lock_token}) vs "
                        f"poller (gen={self.lock_generation}, token={self.lock_token}). "
                        f"Checkpoint advancement and enqueueing rejected."
                    )

                # Enqueue durable catalogue_enrichment jobs
                for movie in matching_movies:
                    CatalogueQueueService.enqueue(
                        job_type="catalogue_enrichment",
                        entity_type="movie",
                        entity_id=str(movie.id),
                        external_id=str(movie.tmdb_id),
                        priority=100,
                    )
                    enqueued_count += 1

                # Checkpoint advancement invariant: MUST advance current_page atomically
                # in the exact same transaction as enqueueing
                chk.current_page = page + 1
                chk.total_pages = total_pages
                chk.changes_detected_count += detected_count
                chk.changes_enqueued_count += enqueued_count
                chk.last_polled_at = timezone.now()
                chk.last_error = ""
                chk.save(update_fields=[
                    "current_page", "total_pages", "changes_detected_count",
                    "changes_enqueued_count", "last_polled_at", "last_error", "updated_at",
                ])
        else:
            enqueued_count = len(matching_movies)

        return detected_count, enqueued_count

    def finalize_window(self, dry_run: bool = False, overlap_days: int = 1) -> None:
        """
        Called when all pages for the current window have been processed.
        Advances window_start_date = window_end_date (or window_end_date - overlap_days),
        resets current_page = 1, total_pages = 1, and clears is_in_progress.
        Guarded by generation fencing.
        """
        if dry_run:
            return

        with transaction.atomic():
            chk = TmdbChangesCheckpoint.objects.select_for_update().get(feed_name=self.feed_name)
            if chk.lock_token != self.lock_token or chk.lock_generation != self.lock_generation:
                raise StalePollerOwnershipError(
                    f"Poller lost lock ownership for '{self.feed_name}' before window finalization."
                )

            next_start = chk.window_end_date
            if overlap_days > 0 and next_start:
                next_start = next_start - datetime.timedelta(days=overlap_days)
            today = timezone.now().date()
            next_end = today

            # Clamp window
            if next_start and next_end:
                next_start, next_end = self.clamp_date_window(next_start, next_end)

            chk.window_start_date = next_start
            chk.window_end_date = next_end
            chk.current_page = 1
            chk.total_pages = 1
            chk.is_in_progress = False
            chk.lock_token = None
            chk.last_polled_at = timezone.now()
            chk.save(update_fields=[
                "window_start_date", "window_end_date", "current_page",
                "total_pages", "is_in_progress", "lock_token", "last_polled_at", "updated_at",
            ])

    def poll(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        limit_pages: Optional[int] = None,
        dry_run: bool = False,
        force_reset: bool = False,
    ) -> Dict[str, Any]:
        """
        Polls TMDB changes feed for the window.
        Returns summary metrics dictionary.
        """
        checkpoint = self.get_or_init_checkpoint(
            start_date=start_date,
            end_date=end_date,
            force_reset=force_reset,
            dry_run=dry_run,
        )

        metrics = {
            "feed_name": self.feed_name,
            "window_start_date": checkpoint.window_start_date,
            "window_end_date": checkpoint.window_end_date,
            "pages_processed": 0,
            "changes_detected": 0,
            "changes_enqueued": 0,
            "completed_window": False,
            "dry_run": dry_run,
        }

        try:
            curr_page = checkpoint.current_page
            # Fetch first target page to discover total_pages
            page_data = self.fetch_changes_page(
                start_date=checkpoint.window_start_date,
                end_date=checkpoint.window_end_date,
                page=curr_page,
                dry_run=dry_run,
            )

            total_pages = int(page_data.get("total_pages", 1))
            # Persist discovered total_pages immediately if needed
            if not dry_run and checkpoint.total_pages != total_pages:
                with transaction.atomic():
                    chk = TmdbChangesCheckpoint.objects.select_for_update().get(feed_name=self.feed_name)
                    if chk.lock_token == self.lock_token and chk.lock_generation == self.lock_generation:
                        chk.total_pages = total_pages
                        chk.save(update_fields=["total_pages", "updated_at"])

            pages_to_process = 0
            while curr_page <= total_pages:
                if limit_pages is not None and pages_to_process >= limit_pages:
                    logger.info(f"Reached page limit ({limit_pages}); halting poll.")
                    break

                if pages_to_process > 0:
                    page_data = self.fetch_changes_page(
                        start_date=checkpoint.window_start_date,
                        end_date=checkpoint.window_end_date,
                        page=curr_page,
                        dry_run=dry_run,
                    )
                    total_pages = int(page_data.get("total_pages", total_pages))

                results = page_data.get("results", [])
                detected, enqueued = self.process_page_results(
                    results=results,
                    page=curr_page,
                    total_pages=total_pages,
                    dry_run=dry_run,
                )

                metrics["pages_processed"] += 1
                metrics["changes_detected"] += detected
                metrics["changes_enqueued"] += enqueued
                pages_to_process += 1
                curr_page += 1

            if curr_page > total_pages:
                self.finalize_window(dry_run=dry_run)
                metrics["completed_window"] = True
            else:
                # Still pages remaining in window, release in_progress lock so next run resumes
                if not dry_run:
                    with transaction.atomic():
                        chk = TmdbChangesCheckpoint.objects.select_for_update().get(feed_name=self.feed_name)
                        if chk.lock_token == self.lock_token and chk.lock_generation == self.lock_generation:
                            chk.is_in_progress = False
                            chk.lock_token = None
                            chk.save(update_fields=["is_in_progress", "lock_token", "updated_at"])

            return metrics

        except Exception as exc:
            logger.exception(f"Error during TMDB changes polling: {exc}")
            if not dry_run:
                try:
                    with transaction.atomic():
                        chk = TmdbChangesCheckpoint.objects.select_for_update().get(feed_name=self.feed_name)
                        if chk.lock_token == self.lock_token and chk.lock_generation == self.lock_generation:
                            chk.is_in_progress = False
                            chk.lock_token = None
                            chk.last_error = str(exc)
                            chk.save(update_fields=["is_in_progress", "lock_token", "last_error", "updated_at"])
                except Exception as inner_exc:
                    logger.error(f"Failed to clear in_progress lock after error: {inner_exc}")
            raise


def poll_tmdb_changes(
    feed_name: str = "movie_changes",
    start_date: Optional[datetime.date] = None,
    end_date: Optional[datetime.date] = None,
    limit_pages: Optional[int] = None,
    dry_run: bool = False,
    force_reset: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Convenience functional entrypoint for polling TMDB Movie Changes Feed.
    Delegates to TmdbChangesService.poll().
    """
    service = TmdbChangesService(feed_name=feed_name)
    return service.poll(
        start_date=start_date,
        end_date=end_date,
        limit_pages=limit_pages,
        dry_run=dry_run,
        force_reset=force_reset,
    )

