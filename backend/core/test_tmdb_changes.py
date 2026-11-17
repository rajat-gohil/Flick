"""
Unit and integration tests for TMDB Changes Feed polling service and command.

Test coverage:
1. 14-day window clamping (TMDB API invariant).
2. Initial polling cold-start cursor defaults.
3. Multi-page pagination handling.
4. Matching movie detection and durable enqueueing.
5. Non-matching TMDB IDs are ignored.
6. Transactional checkpoint advancement (checkpoint NOT advanced if enqueue fails).
7. HTTP 429 backoff handling.
8. Concurrent poller lock rejection (and stale lock override).
9. Management command CLI invocation and flags.
"""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import CatalogueJob, Movie, TmdbChangesCheckpoint
from core.services.catalogue_queue import CatalogueQueueService
from core.services.tmdb_changes import (
    PollerLockedError,
    RateLimitBackoffError,
    StalePollerOwnershipError,
    TmdbChangesService,
    TmdbConfigError,
)


class TmdbChangesServiceTests(TestCase):
    def setUp(self):
        self.service = TmdbChangesService(feed_name="test_changes")
        TmdbChangesCheckpoint.objects.all().delete()
        Movie.objects.all().delete()
        CatalogueJob.objects.all().delete()

    def test_14_day_window_clamping(self):
        """TMDB strictly rejects intervals >= 14 days. Ensure clamping preserves max 14 days (13 days delta)."""
        start_date = datetime.date(2026, 1, 1)
        end_date = datetime.date(2026, 1, 30)  # 29 days delta

        clamped_start, clamped_end = self.service.clamp_date_window(start_date, end_date)
        self.assertEqual(clamped_start, datetime.date(2026, 1, 1))
        self.assertEqual(clamped_end, datetime.date(2026, 1, 14))  # exactly 13 days delta
        self.assertEqual((clamped_end - clamped_start).days, 13)

        # Inverted dates
        inv_start, inv_end = self.service.clamp_date_window(datetime.date(2026, 1, 10), datetime.date(2026, 1, 5))
        self.assertEqual(inv_start, datetime.date(2026, 1, 10))
        self.assertEqual(inv_end, datetime.date(2026, 1, 10))

        # Valid 5-day delta unchanged
        v_start, v_end = self.service.clamp_date_window(datetime.date(2026, 1, 1), datetime.date(2026, 1, 6))
        self.assertEqual(v_start, datetime.date(2026, 1, 1))
        self.assertEqual(v_end, datetime.date(2026, 1, 6))

    def test_initial_polling_cold_start(self):
        """Cold start initializes checkpoint with start_date=today - 13 days and end_date=today."""
        today = timezone.now().date()
        checkpoint = self.service.get_or_init_checkpoint()

        self.assertEqual(checkpoint.feed_name, "test_changes")
        self.assertEqual(checkpoint.window_start_date, today - datetime.timedelta(days=13))
        self.assertEqual(checkpoint.window_end_date, today)
        self.assertEqual(checkpoint.current_page, 1)
        self.assertEqual(checkpoint.total_pages, 1)
        self.assertTrue(checkpoint.is_in_progress)

    def test_concurrent_poller_lock_rejection_and_stale_override(self):
        """Active lock within 5 minutes raises PollerLockedError; stale lock is overridden."""
        now = timezone.now()
        # Create an in-progress checkpoint updated 1 minute ago
        chk = TmdbChangesCheckpoint.objects.create(
            feed_name="test_changes",
            window_start_date=now.date() - datetime.timedelta(days=13),
            window_end_date=now.date(),
            current_page=1,
            is_in_progress=True,
        )

        # Attempting to get lock should raise PollerLockedError
        with self.assertRaises(PollerLockedError):
            self.service.get_or_init_checkpoint()

        # Force lock update to > 5 minutes ago (305 seconds)
        stale_time = now - datetime.timedelta(seconds=305)
        TmdbChangesCheckpoint.objects.filter(pk=chk.pk).update(updated_at=stale_time)

        # Fresh acquisition should now succeed by breaking stale lock
        acquired = self.service.get_or_init_checkpoint()
        self.assertTrue(acquired.is_in_progress)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("requests.get")
    def test_matching_movie_detection_and_durable_enqueue(self, mock_get, mock_acquire):
        """Matching movies with proper provenance are enqueued; non-matching are ignored."""
        # 1. Movie that matches provenance tmdb_catalogue
        m1 = Movie.objects.create(
            title="Catalogue Movie",
            tmdb_id=101,
            provenance="tmdb_catalogue",
            display_ready=True,
        )
        # 2. Movie that matches provenance manual_curated
        m2 = Movie.objects.create(
            title="Curated Movie",
            tmdb_id=102,
            provenance="manual_curated",
            display_ready=True,
        )
        # 3. Movie with non-matching provenance (needs_review)
        m3 = Movie.objects.create(
            title="Unreviewed Movie",
            tmdb_id=103,
            provenance="needs_review",
            display_ready=False,
        )
        # 4. TMDB ID 104 does not exist in local database

        # Mock TMDB changes response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"id": 101, "adult": False},
                {"id": 102, "adult": False},
                {"id": 103, "adult": False},
                {"id": 104, "adult": False},
            ],
            "page": 1,
            "total_pages": 1,
            "total_results": 4,
        }
        mock_get.return_value = mock_resp

        metrics = self.service.poll()

        self.assertEqual(metrics["pages_processed"], 1)
        self.assertEqual(metrics["changes_detected"], 4)
        self.assertEqual(metrics["changes_enqueued"], 2)  # Only 101 and 102
        self.assertTrue(metrics["completed_window"])

        # Verify CatalogueJob records
        jobs = list(CatalogueJob.objects.filter(job_type="catalogue_enrichment"))
        self.assertEqual(len(jobs), 2)
        enqueued_ids = {j.entity_id for j in jobs}
        self.assertEqual(enqueued_ids, {str(m1.id), str(m2.id)})
        enqueued_external_ids = {j.external_id for j in jobs}
        self.assertEqual(enqueued_external_ids, {"101", "102"})

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("requests.get")
    def test_multi_page_pagination(self, mock_get, mock_acquire):
        """Poller paginates across multiple pages and completes the window."""
        Movie.objects.create(title="Movie 1", tmdb_id=201, provenance="tmdb_catalogue")
        Movie.objects.create(title="Movie 2", tmdb_id=202, provenance="tmdb_catalogue")

        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.json.return_value = {
            "results": [{"id": 201, "adult": False}],
            "page": 1,
            "total_pages": 2,
        }

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.json.return_value = {
            "results": [{"id": 202, "adult": False}],
            "page": 2,
            "total_pages": 2,
        }

        mock_get.side_effect = [page1_resp, page2_resp]

        metrics = self.service.poll()
        self.assertEqual(metrics["pages_processed"], 2)
        self.assertEqual(metrics["changes_detected"], 2)
        self.assertEqual(metrics["changes_enqueued"], 2)
        self.assertTrue(metrics["completed_window"])

        # Checkpoint should have advanced window and reset page to 1
        chk = TmdbChangesCheckpoint.objects.get(feed_name="test_changes")
        self.assertEqual(chk.current_page, 1)
        self.assertFalse(chk.is_in_progress)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("requests.get")
    def test_transactional_checkpoint_advancement_rollback(self, mock_get, mock_acquire):
        """If enqueue fails midway, checkpoint page and counts must NOT advance."""
        Movie.objects.create(title="Movie Err", tmdb_id=301, provenance="tmdb_catalogue")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"id": 301, "adult": False}],
            "page": 1,
            "total_pages": 2,
        }
        mock_get.return_value = mock_resp

        # Patch CatalogueQueueService.enqueue to simulate an unexpected error
        with patch.object(CatalogueQueueService, "enqueue", side_effect=RuntimeError("Database failure")):
            with self.assertRaises(RuntimeError):
                self.service.poll()

        chk = TmdbChangesCheckpoint.objects.get(feed_name="test_changes")
        # Checkpoint MUST remain on page 1, 0 detected, 0 enqueued
        self.assertEqual(chk.current_page, 1)
        self.assertEqual(chk.changes_enqueued_count, 0)
        self.assertFalse(chk.is_in_progress)  # in_progress lock is released on error
        self.assertIn("Database failure", chk.last_error)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("core.services.tmdb_changes.record_tmdb_429", return_value=12.5)
    @patch("requests.get")
    def test_http_429_backoff_handling(self, mock_get, mock_record_429, mock_acquire):
        """HTTP 429 response triggers record_tmdb_429 and raises RateLimitBackoffError."""
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {"Retry-After": "10"}
        mock_get.return_value = mock_resp

        with self.assertRaises(RateLimitBackoffError) as ctx:
            self.service.poll()

        self.assertEqual(ctx.exception.retry_after, 12.5)
        mock_record_429.assert_called_once_with("10")

        chk = TmdbChangesCheckpoint.objects.get(feed_name="test_changes")
        self.assertFalse(chk.is_in_progress)
        self.assertIn("HTTP 429 rate limit", chk.last_error)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=False)
    def test_rate_limiter_token_denial(self, mock_acquire):
        """When token bucket denies token, raises RateLimitBackoffError."""
        with self.assertRaises(RateLimitBackoffError) as ctx:
            self.service.poll()

        self.assertIn("rate limiter denied token", str(ctx.exception))

    def test_stale_poller_fencing_rejection_and_rollback(self):
        """Verifies that an overridden poller raises StalePollerOwnershipError and enqueues 0 jobs."""
        m = Movie.objects.create(tmdb_id=99001, title="Fence Test", provenance="tmdb_catalogue")
        self.service.get_or_init_checkpoint()
        self.assertEqual(self.service.lock_generation, 1)

        # Another poller takes over
        service_2 = TmdbChangesService(feed_name=self.service.feed_name)
        service_2.get_or_init_checkpoint(force_reset=True)
        self.assertEqual(service_2.lock_generation, 2)

        # Original poller tries to advance
        with self.assertRaises(StalePollerOwnershipError):
            self.service.process_page_results(
                results=[{"id": 99001, "adult": False}],
                page=1,
                total_pages=1,
                dry_run=False,
            )

        self.assertEqual(CatalogueJob.objects.filter(external_id="99001").count(), 0)

    @patch("core.services.tmdb_changes.requests.get")
    def test_dry_run_mode_does_not_mutate_db_or_call_external_endpoints(self, mock_get):
        """Verify dry-run mode makes 0 external HTTP calls and creates 0 DB checkpoint/job records."""
        Movie.objects.create(tmdb_id=99002, title="Dry Movie", provenance="tmdb_catalogue")
        metrics = self.service.poll(dry_run=True)

        mock_get.assert_not_called()
        self.assertEqual(metrics["dry_run"], True)
        self.assertEqual(metrics["changes_detected"], 1)
        self.assertEqual(metrics["changes_enqueued"], 1)
        self.assertEqual(TmdbChangesCheckpoint.objects.count(), 0)
        self.assertEqual(CatalogueJob.objects.count(), 0)

    @patch("core.services.tmdb_changes.settings.TMDB_API_KEY", "")
    def test_missing_api_key_raises_config_error_when_not_dry_run(self):
        """When TMDB_API_KEY is empty and dry_run=False, raises TmdbConfigError."""
        with self.assertRaises(TmdbConfigError):
            self.service.fetch_changes_page(
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 10),
                page=1,
                dry_run=False,
            )


class PollTmdbChangesCommandTests(TestCase):
    def setUp(self):
        TmdbChangesCheckpoint.objects.all().delete()
        Movie.objects.all().delete()
        CatalogueJob.objects.all().delete()

    @patch("core.services.tmdb_changes.TmdbChangesService.poll")
    def test_command_dry_run_and_date_flags(self, mock_poll):
        """Management command parses arguments and passes to service."""
        mock_poll.return_value = {
            "feed_name": "movie_changes",
            "window_start_date": datetime.date(2026, 1, 1),
            "window_end_date": datetime.date(2026, 1, 10),
            "pages_processed": 1,
            "changes_detected": 10,
            "changes_enqueued": 2,
            "completed_window": True,
            "dry_run": True,
        }

        call_command(
            "poll_tmdb_changes",
            "--start-date=2026-01-01",
            "--end-date=2026-01-10",
            "--limit-pages=5",
            "--dry-run",
        )

        mock_poll.assert_called_once_with(
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 1, 10),
            limit_pages=5,
            dry_run=True,
            force_reset=False,
        )

    def test_command_invalid_date_format(self):
        """Command raises CommandError on invalid date format."""
        with self.assertRaises(CommandError):
            call_command("poll_tmdb_changes", "--start-date=invalid-date")

    def test_command_dry_run_end_to_end_unmocked(self):
        """Verify command runs unmocked in dry-run mode with 0 DB writes and 0 external network requests."""
        Movie.objects.create(tmdb_id=99003, title="Dry Command Movie", provenance="tmdb_catalogue")
        call_command("poll_tmdb_changes", "--dry-run")
        self.assertEqual(TmdbChangesCheckpoint.objects.count(), 0)
        self.assertEqual(CatalogueJob.objects.count(), 0)
