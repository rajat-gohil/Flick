"""
Unit and integration tests for Flick 90-Day Catalogue Staleness Sweep.

Tests verify:
1. 90-day boundary condition:
   - enriched 89 days ago: skipped (< 90 days)
   - enriched 91 days ago: enqueued (> 90 days)
   - last_enriched_at is None: enqueued
2. Synthetic fixture exclusion:
   - synthetic_fixture movies are never enqueued regardless of staleness
3. Needs review exclusion:
   - unverified needs_review movies are never enqueued
4. Manual curated inclusion:
   - manual_curated movies are eligible and enqueued when stale
5. Cursor keyset pagination:
   - batching advances last_scanned_id across multiple batches without loading all records into memory
   - finishes with last_scanned_id=0, is_in_progress=False, last_sweep_completed_at set
6. Duplicate prevention:
   - repeated sweep against already enqueued active jobs does not create duplicate CatalogueJobs
   - records_skipped is incremented
7. Crash and resume:
   - interrupted sweep resumes execution cleanly from checkpoint.last_scanned_id
   - exception stores last_error on the checkpoint
8. Dry-run mode:
   - simulates counts without creating DB jobs or updating checkpoint
9. CLI management command:
   - run_staleness_sweep command operates correctly with --batch-size, --limit, --dry-run, --force-reset
"""

from datetime import timedelta
import io
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import CatalogueJob, Movie, StalenessSweepCheckpoint
from core.services.catalogue_queue import CatalogueQueueService
from core.services.staleness_sweep import (
    DEFAULT_SWEEP_NAME,
    StalenessSweepService,
    run_staleness_sweep,
)


@override_settings(DEBUG=True)
class StalenessSweepTests(TestCase):
    def setUp(self):
        super().setUp()
        # Clean up existing test data
        CatalogueJob.objects.all().delete()
        Movie.objects.all().delete()
        StalenessSweepCheckpoint.objects.all().delete()

    def test_90_day_boundary(self):
        """
        Movies enriched 89 days ago are skipped (< 90 days).
        Movies enriched 91 days ago are enqueued (> 90 days).
        Movies with last_enriched_at=None are enqueued.
        Enqueued jobs must have priority=200 and job_type='catalogue_enrichment'.
        """
        now = timezone.now()

        # Movie 1: enriched 89 days ago (fresh)
        m_fresh = Movie.objects.create(
            title="Fresh Movie",
            tmdb_id=101,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=89),
        )

        # Movie 2: enriched 91 days ago (stale)
        m_stale = Movie.objects.create(
            title="Stale Movie",
            tmdb_id=102,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=91),
        )

        # Movie 3: never enriched (stale)
        m_never = Movie.objects.create(
            title="Never Enriched Movie",
            tmdb_id=103,
            provenance="tmdb_catalogue",
            last_enriched_at=None,
        )

        result = run_staleness_sweep(batch_size=50)

        self.assertEqual(result["records_scanned"], 2)
        self.assertEqual(result["records_enqueued"], 2)
        self.assertEqual(result["records_skipped"], 0)
        self.assertTrue(result["sweep_completed"])

        # Verify CatalogueJob entries in queue
        jobs = CatalogueJob.objects.all()
        self.assertEqual(jobs.count(), 2)

        enqueued_entity_ids = set(jobs.values_list("entity_id", flat=True))
        self.assertNotIn(str(m_fresh.id), enqueued_entity_ids)
        self.assertIn(str(m_stale.id), enqueued_entity_ids)
        self.assertIn(str(m_never.id), enqueued_entity_ids)

        for job in jobs:
            self.assertEqual(job.job_type, "catalogue_enrichment")
            self.assertEqual(job.entity_type, "movie")
            self.assertEqual(job.priority, 200)

    def test_synthetic_fixture_exclusion(self):
        """Synthetic fixture movies must NEVER be enqueued by staleness sweeps."""
        now = timezone.now()

        Movie.objects.create(
            title="Synthetic Stale",
            tmdb_id=201,
            provenance="synthetic_fixture",
            last_enriched_at=now - timedelta(days=120),
        )
        Movie.objects.create(
            title="Synthetic Never",
            tmdb_id=202,
            provenance="synthetic_fixture",
            last_enriched_at=None,
        )

        result = run_staleness_sweep()

        self.assertEqual(result["records_scanned"], 0)
        self.assertEqual(result["records_enqueued"], 0)
        self.assertTrue(result["sweep_completed"])
        self.assertEqual(CatalogueJob.objects.count(), 0)

    def test_needs_review_exclusion(self):
        """Unverified needs_review movies must NEVER be enqueued by staleness sweeps."""
        now = timezone.now()

        Movie.objects.create(
            title="Needs Review Stale",
            tmdb_id=301,
            provenance="needs_review",
            last_enriched_at=now - timedelta(days=120),
        )
        Movie.objects.create(
            title="Needs Review Never",
            tmdb_id=302,
            provenance="needs_review",
            last_enriched_at=None,
        )

        result = run_staleness_sweep()

        self.assertEqual(result["records_scanned"], 0)
        self.assertEqual(result["records_enqueued"], 0)
        self.assertTrue(result["sweep_completed"])
        self.assertEqual(CatalogueJob.objects.count(), 0)

    def test_manual_curated_inclusion(self):
        """Manually curated movies are catalogue-eligible and must be enqueued when stale."""
        now = timezone.now()

        m_curated = Movie.objects.create(
            title="Curated Classic",
            tmdb_id=401,
            provenance="manual_curated",
            last_enriched_at=now - timedelta(days=95),
        )

        result = run_staleness_sweep()

        self.assertEqual(result["records_scanned"], 1)
        self.assertEqual(result["records_enqueued"], 1)
        self.assertEqual(CatalogueJob.objects.count(), 1)
        job = CatalogueJob.objects.first()
        self.assertEqual(job.entity_id, str(m_curated.id))
        self.assertEqual(job.external_id, str(m_curated.tmdb_id))
        self.assertEqual(job.priority, 200)

    def test_cursor_keyset_pagination(self):
        """
        Test cursor keyset pagination: batching advances last_scanned_id
        without loading all records into memory at once.
        """
        now = timezone.now()
        movies = []
        for i in range(1, 6):
            m = Movie.objects.create(
                title=f"Movie {i}",
                tmdb_id=500 + i,
                provenance="tmdb_catalogue",
                last_enriched_at=now - timedelta(days=100),
            )
            movies.append(m)

        # Pass 1: batch_size=2, limit=2 -> processes first 2 movies
        res1 = run_staleness_sweep(batch_size=2, limit=2)
        self.assertEqual(res1["records_scanned"], 2)
        self.assertEqual(res1["records_enqueued"], 2)
        self.assertFalse(res1["sweep_completed"])
        self.assertEqual(res1["last_scanned_id"], movies[1].id)

        cp1 = StalenessSweepCheckpoint.objects.get(sweep_name=DEFAULT_SWEEP_NAME)
        self.assertEqual(cp1.last_scanned_id, movies[1].id)
        self.assertTrue(cp1.is_in_progress)

        # Pass 2: batch_size=2, limit=2 -> resumes from movies[1].id, processes movies 3 and 4
        res2 = run_staleness_sweep(batch_size=2, limit=2)
        self.assertEqual(res2["records_scanned"], 2)
        self.assertEqual(res2["records_enqueued"], 2)
        self.assertFalse(res2["sweep_completed"])
        self.assertEqual(res2["last_scanned_id"], movies[3].id)

        cp2 = StalenessSweepCheckpoint.objects.get(sweep_name=DEFAULT_SWEEP_NAME)
        self.assertEqual(cp2.last_scanned_id, movies[3].id)
        self.assertTrue(cp2.is_in_progress)

        # Pass 3: batch_size=2, no limit -> processes movie 5, reaches end, marks sweep complete
        res3 = run_staleness_sweep(batch_size=2)
        self.assertEqual(res3["records_scanned"], 1)
        self.assertEqual(res3["records_enqueued"], 1)
        self.assertTrue(res3["sweep_completed"])
        self.assertEqual(res3["last_scanned_id"], 0)

        cp3 = StalenessSweepCheckpoint.objects.get(sweep_name=DEFAULT_SWEEP_NAME)
        self.assertEqual(cp3.last_scanned_id, 0)
        self.assertFalse(cp3.is_in_progress)
        self.assertIsNotNone(cp3.last_sweep_completed_at)
        self.assertEqual(cp3.records_scanned, 5)
        self.assertEqual(cp3.records_enqueued, 5)

        self.assertEqual(CatalogueJob.objects.count(), 5)

    def test_duplicate_prevention(self):
        """Repeated sweeps do not duplicate active jobs in CatalogueJob."""
        now = timezone.now()

        m = Movie.objects.create(
            title="Deduplication Target",
            tmdb_id=601,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=100),
        )

        # First sweep enqueues 1 job
        res1 = run_staleness_sweep()
        self.assertEqual(res1["records_enqueued"], 1)
        self.assertEqual(res1["records_skipped"], 0)
        self.assertEqual(CatalogueJob.objects.count(), 1)

        # Force cursor reset to 0 to simulate re-evaluating the same movie while job is still pending
        res2 = run_staleness_sweep(force_reset=True)
        self.assertEqual(res2["records_scanned"], 1)
        self.assertEqual(res2["records_enqueued"], 0)
        self.assertEqual(res2["records_skipped"], 1)
        # Total jobs in table remains 1
        self.assertEqual(CatalogueJob.objects.count(), 1)

    def test_crash_and_resume(self):
        """If a sweep crashes or is interrupted, the next invocation picks up from checkpoint.last_scanned_id."""
        now = timezone.now()
        movies = []
        for i in range(1, 5):
            m = Movie.objects.create(
                title=f"Crash Movie {i}",
                tmdb_id=700 + i,
                provenance="tmdb_catalogue",
                last_enriched_at=now - timedelta(days=100),
            )
            movies.append(m)

        # Run first batch of 2
        res1 = run_staleness_sweep(batch_size=2, limit=2)
        self.assertEqual(res1["last_scanned_id"], movies[1].id)

        # Simulate exception during next batch
        with patch.object(
            CatalogueQueueService,
            "enqueue",
            side_effect=RuntimeError("Simulated TMDB Queue DB Lockup"),
        ):
            with self.assertRaises(RuntimeError):
                run_staleness_sweep(batch_size=2)

        # Verify last_error saved on checkpoint
        cp = StalenessSweepCheckpoint.objects.get(sweep_name=DEFAULT_SWEEP_NAME)
        self.assertIn("Simulated TMDB Queue DB Lockup", cp.last_error)
        # Cursor remained at movies[1].id (end of last successful batch)
        self.assertEqual(cp.last_scanned_id, movies[1].id)

        # Resume sweep after fixing crash: finishes remaining movies
        res3 = run_staleness_sweep(batch_size=2)
        self.assertEqual(res3["records_scanned"], 2)
        self.assertEqual(res3["records_enqueued"], 2)
        self.assertTrue(res3["sweep_completed"])
        self.assertEqual(res3["last_scanned_id"], 0)

        # All 4 movies enqueued exactly once
        self.assertEqual(CatalogueJob.objects.count(), 4)

    def test_dry_run_mode(self):
        """Dry-run mode calculates counts without creating jobs or modifying the checkpoint in DB."""
        now = timezone.now()
        Movie.objects.create(
            title="Dry Run Movie 1",
            tmdb_id=801,
            provenance="tmdb_catalogue",
            last_enriched_at=None,
        )
        Movie.objects.create(
            title="Dry Run Movie 2",
            tmdb_id=802,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=100),
        )

        res = run_staleness_sweep(dry_run=True)
        self.assertEqual(res["records_scanned"], 2)
        self.assertEqual(res["records_enqueued"], 2)
        self.assertTrue(res["dry_run"])

        # No jobs enqueued in database
        self.assertEqual(CatalogueJob.objects.count(), 0)

        # Checkpoint does not exist or has last_scanned_id=0 and is_in_progress=False
        if StalenessSweepCheckpoint.objects.filter(sweep_name=DEFAULT_SWEEP_NAME).exists():
            cp = StalenessSweepCheckpoint.objects.get(sweep_name=DEFAULT_SWEEP_NAME)
            self.assertEqual(cp.records_enqueued, 0)
            self.assertFalse(cp.is_in_progress)

    def test_management_command(self):
        """Verify the run_staleness_sweep management command CLI interface."""
        now = timezone.now()
        for i in range(3):
            Movie.objects.create(
                title=f"CLI Movie {i}",
                tmdb_id=900 + i,
                provenance="tmdb_catalogue",
                last_enriched_at=None,
            )

        # Test dry-run CLI
        out = io.StringIO()
        call_command("run_staleness_sweep", "--batch-size=2", "--dry-run", stdout=out)
        output = out.getvalue()
        self.assertIn("[DRY-RUN]", output)
        self.assertEqual(CatalogueJob.objects.count(), 0)

        # Test live CLI
        out = io.StringIO()
        call_command("run_staleness_sweep", "--batch-size=2", stdout=out)
        output = out.getvalue()
        self.assertIn("COMPLETED", output)
        self.assertEqual(CatalogueJob.objects.count(), 3)

        # Test force-reset CLI
        out = io.StringIO()
        call_command("run_staleness_sweep", "--force-reset", stdout=out)
        output = out.getvalue()
        self.assertIn("Run Skipped / Deduped:  3", output)
