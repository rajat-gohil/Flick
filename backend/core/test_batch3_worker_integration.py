"""
Worker Integration Tests for Flick Batch 3.

Validates end-to-end integration of Batch 3 handlers into the Render Background Worker:
1. Registration of 'sync_changes_feed' and 'full_reconciliation' in worker handler registry.
2. Worker claiming, lease fencing, execution, and completion of 'sync_changes_feed' jobs.
3. Worker claiming, lease fencing, execution, and completion of 'full_reconciliation' jobs.
4. Generation fencing / lease token enforcement: stale lease ownership prevents worker commit.
5. End-to-end batch processing via IntelligenceWorkerProcess.run_loop(once=True).
6. Robust error handling for invalid payloads and handler exceptions.
"""

from __future__ import annotations

import datetime
from datetime import timedelta
from unittest.mock import MagicMock, patch
import uuid

from django.test import TestCase
from django.utils import timezone

from core.models import CatalogueJob, Movie, StalenessSweepCheckpoint, TmdbChangesCheckpoint
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.services.batch3_handlers import (
    handle_full_reconciliation,
    handle_sync_changes_feed,
)
from core.management.commands.run_intelligence_worker import (
    DEFAULT_JOB_HANDLERS,
    JOB_HANDLERS,
    IntelligenceWorkerProcess,
    reset_handlers,
)


class Batch3WorkerIntegrationTests(TestCase):
    def setUp(self):
        super().setUp()
        reset_handlers()
        CatalogueJob.objects.all().delete()
        Movie.objects.all().delete()
        TmdbChangesCheckpoint.objects.all().delete()
        StalenessSweepCheckpoint.objects.all().delete()

    def tearDown(self):
        reset_handlers()
        super().tearDown()

    def test_01_handler_registry(self):
        """Verify Batch 3 handlers are registered in DEFAULT_JOB_HANDLERS and JOB_HANDLERS."""
        self.assertIn("sync_changes_feed", DEFAULT_JOB_HANDLERS)
        self.assertIn("full_reconciliation", DEFAULT_JOB_HANDLERS)
        self.assertEqual(DEFAULT_JOB_HANDLERS["sync_changes_feed"], handle_sync_changes_feed)
        self.assertEqual(DEFAULT_JOB_HANDLERS["full_reconciliation"], handle_full_reconciliation)

        self.assertIn("sync_changes_feed", JOB_HANDLERS)
        self.assertIn("full_reconciliation", JOB_HANDLERS)

        # Verify reset_handlers restores them
        JOB_HANDLERS.clear()
        self.assertEqual(len(JOB_HANDLERS), 0)
        reset_handlers()
        self.assertIn("sync_changes_feed", JOB_HANDLERS)
        self.assertIn("full_reconciliation", JOB_HANDLERS)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("core.services.tmdb_changes.requests.get")
    def test_02_worker_claims_and_executes_sync_changes_feed_success(
        self, mock_get: MagicMock, mock_acquire: MagicMock
    ):
        """
        Verify worker claims and successfully executes a sync_changes_feed job under lease fencing.
        """
        # Seed matching movie in database
        movie = Movie.objects.create(
            title="Dune Part Two",
            tmdb_id=693134,
            provenance="tmdb_catalogue",
        )

        # Mock TMDB changes API response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {"id": 693134, "adult": False},
                {"id": 999999, "adult": False},  # Non-matching
            ],
            "page": 1,
            "total_pages": 1,
        }
        mock_get.return_value = mock_resp

        # Enqueue sync_changes_feed job
        job, created = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="tmdb_changes",
            priority=50,
            payload={"limit_pages": 1, "dry_run": False},
        )
        self.assertTrue(created)
        self.assertEqual(job.status, CatalogueJob.Status.PENDING)

        worker = IntelligenceWorkerProcess(worker_id="test-worker-batch3-sync", lease_duration=60)
        claimed_jobs = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        self.assertEqual(len(claimed_jobs), 1)
        claimed_job = claimed_jobs[0]
        self.assertEqual(claimed_job.id, job.id)
        self.assertEqual(claimed_job.status, CatalogueJob.Status.IN_PROGRESS)

        # Process the job
        success = worker.process_one_job(claimed_job)
        self.assertTrue(success)

        # Verify job marked as succeeded under generation fencing
        job.refresh_from_db()
        self.assertEqual(job.status, CatalogueJob.Status.SUCCEEDED)
        self.assertIsNone(job.lease_expires_at)

        # Verify TMDB changes checkpoint recorded processed metrics
        checkpoint = TmdbChangesCheckpoint.objects.first()
        self.assertIsNotNone(checkpoint)
        self.assertEqual(checkpoint.changes_detected_count, 2)
        self.assertEqual(checkpoint.changes_enqueued_count, 1)

        # Verify downstream catalogue_enrichment job was enqueued for the matching movie
        downstream = CatalogueJob.objects.filter(
            job_type="catalogue_enrichment",
            entity_type="movie",
            entity_id=str(movie.id),
        ).first()
        self.assertIsNotNone(downstream)
        self.assertEqual(downstream.priority, 100)
        self.assertEqual(downstream.status, CatalogueJob.Status.PENDING)

    def test_03_worker_claims_and_executes_full_reconciliation_success(self):
        """
        Verify worker claims and successfully executes a full_reconciliation job under lease fencing.
        """
        now = timezone.now()
        # Seed movies:
        # 1. Stale movie (> 90 days) -> should be enqueued
        m1 = Movie.objects.create(
            title="Interstellar",
            tmdb_id=157336,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=95),
        )
        # 2. Never enriched movie -> should be enqueued
        m2 = Movie.objects.create(
            title="Inception",
            tmdb_id=27205,
            provenance="manual_curated",
            last_enriched_at=None,
        )
        # 3. Fresh movie (< 90 days) -> should be skipped
        m3 = Movie.objects.create(
            title="Oppenheimer",
            tmdb_id=872585,
            provenance="tmdb_catalogue",
            last_enriched_at=now - timedelta(days=10),
        )
        # 4. Synthetic fixture -> strictly excluded
        m4 = Movie.objects.create(
            title="Synthetic Movie",
            tmdb_id=999901,
            provenance="synthetic_fixture",
            last_enriched_at=now - timedelta(days=120),
        )

        # Enqueue full_reconciliation job
        job, created = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
            entity_type="system",
            entity_id="staleness_sweep",
            priority=150,
            payload={"batch_size": 50, "limit": 100, "dry_run": False},
        )
        self.assertTrue(created)

        worker = IntelligenceWorkerProcess(worker_id="test-worker-batch3-recon", lease_duration=60)
        claimed_jobs = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        self.assertEqual(len(claimed_jobs), 1)
        claimed_job = claimed_jobs[0]

        # Execute
        success = worker.process_one_job(claimed_job)
        self.assertTrue(success)

        # Check job completion
        job.refresh_from_db()
        self.assertEqual(job.status, CatalogueJob.Status.SUCCEEDED)
        self.assertIsNone(job.lease_expires_at)

        # Check StalenessSweepCheckpoint recorded metrics
        sweep_checkpoint = StalenessSweepCheckpoint.objects.get(sweep_name="90_day_movie_staleness")
        self.assertEqual(sweep_checkpoint.records_scanned, 2)
        self.assertEqual(sweep_checkpoint.records_enqueued, 2)

        # Check enrichment jobs were enqueued with priority 200 (staleness low priority)
        enqueued_m1 = CatalogueJob.objects.filter(
            job_type="catalogue_enrichment", entity_id=str(m1.id)
        ).first()
        self.assertIsNotNone(enqueued_m1)
        self.assertEqual(enqueued_m1.priority, 200)

        enqueued_m2 = CatalogueJob.objects.filter(
            job_type="catalogue_enrichment", entity_id=str(m2.id)
        ).first()
        self.assertIsNotNone(enqueued_m2)
        self.assertEqual(enqueued_m2.priority, 200)

        # m3 and m4 should NOT have enrichment jobs
        self.assertFalse(CatalogueJob.objects.filter(job_type="catalogue_enrichment", entity_id=str(m3.id)).exists())
        self.assertFalse(CatalogueJob.objects.filter(job_type="catalogue_enrichment", entity_id=str(m4.id)).exists())

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("core.services.tmdb_changes.requests.get")
    def test_04_stale_lease_ownership_prevents_worker_commit_sync_changes(
        self, mock_get: MagicMock, mock_acquire: MagicMock
    ):
        """
        Verify that if lease token or claim generation changes (e.g. lease reclaimed),
        the worker's completion attempt is rejected with StaleLeaseOwnershipError,
        process_one_job returns False, and the database record is not corrupted.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [],
            "page": 1,
            "total_pages": 1,
        }
        mock_get.return_value = mock_resp

        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="tmdb_changes",
            priority=50,
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-original", lease_duration=60)
        claimed = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        claimed_job = claimed[0]

        # Simulate lease theft / reclamation by bumping generation and lease token
        new_token = uuid.uuid4()
        CatalogueJob.objects.filter(id=claimed_job.id).update(
            claimed_by_worker_id="worker-thief",
            lease_token=new_token,
            claim_generation=claimed_job.claim_generation + 1,
        )

        # Original worker attempts to finish job
        success = worker.process_one_job(claimed_job)
        self.assertFalse(success)

        # Verify job in database still belongs to worker-thief and was NOT marked succeeded by worker-original
        refreshed = CatalogueJob.objects.get(id=claimed_job.id)
        self.assertEqual(refreshed.claimed_by_worker_id, "worker-thief")
        self.assertEqual(refreshed.lease_token, new_token)
        self.assertEqual(refreshed.status, CatalogueJob.Status.IN_PROGRESS)

    def test_05_stale_lease_ownership_prevents_worker_commit_full_reconciliation(self):
        """
        Verify that expired lease timestamp prevents worker completion for full_reconciliation job.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
            entity_type="system",
            entity_id="staleness_sweep",
            priority=150,
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-reconciliation", lease_duration=60)
        claimed = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        claimed_job = claimed[0]

        # Artificially expire the lease in the past
        past_time = timezone.now() - timedelta(minutes=15)
        CatalogueJob.objects.filter(id=claimed_job.id).update(
            lease_expires_at=past_time,
        )

        # Attempt to process
        success = worker.process_one_job(claimed_job)
        self.assertFalse(success)

        # Verify job is NOT marked succeeded
        refreshed = CatalogueJob.objects.get(id=claimed_job.id)
        self.assertNotEqual(refreshed.status, CatalogueJob.Status.SUCCEEDED)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("core.services.tmdb_changes.requests.get")
    def test_06_worker_run_loop_once_processes_batch3_jobs(
        self, mock_get: MagicMock, mock_acquire: MagicMock
    ):
        """
        Verify IntelligenceWorkerProcess.run_loop(once=True) processes multiple Batch 3 jobs.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [],
            "page": 1,
            "total_pages": 1,
        }
        mock_get.return_value = mock_resp

        # Enqueue both Batch 3 job types
        job1, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="feed1",
            priority=50,
            payload={"limit_pages": 1},
        )
        job2, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
            entity_type="system",
            entity_id="sweep1",
            priority=50,
            payload={"limit": 5},
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-batch-runner", batch_size=10)
        summary = worker.run_loop(once=True)

        self.assertEqual(summary["batches"], 1)
        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["failed"], 0)

        job1.refresh_from_db()
        job2.refresh_from_db()
        self.assertEqual(job1.status, CatalogueJob.Status.SUCCEEDED)
        self.assertEqual(job2.status, CatalogueJob.Status.SUCCEEDED)

    def test_07_invalid_payload_fails_cleanly(self):
        """Verify non-dict payload fails permanently without crashing worker."""
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="test_invalid",
            priority=50,
        )
        # Update to non-dict payload directly in DB
        CatalogueJob.objects.filter(id=job.id).update(payload="invalid-string-payload")

        worker = IntelligenceWorkerProcess(worker_id="worker-invalid-test")
        claimed = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        self.assertEqual(len(claimed), 1)
        claimed_job = claimed[0]

        success = worker.process_one_job(claimed_job)
        self.assertFalse(success)

        claimed_job.refresh_from_db()
        self.assertEqual(claimed_job.status, CatalogueJob.Status.FAILED_PERMANENT)
        self.assertIn("InvalidPayloadError", claimed_job.last_error)

    @patch("core.services.tmdb_changes.acquire_tmdb_token", return_value=True)
    @patch("core.services.tmdb_changes.requests.get")
    def test_08_handler_direct_invocation_sync_changes(self, mock_get: MagicMock, mock_acquire: MagicMock):
        """Test direct invocation of handle_sync_changes_feed with date string and dry_run."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [],
            "page": 1,
            "total_pages": 1,
        }
        mock_get.return_value = mock_resp

        job = CatalogueJob(
            id=991,
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            payload={"dry_run": True, "limit_pages": 2},
        )
        res = handle_sync_changes_feed(job, "worker-direct", uuid.uuid4(), 1)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("pages_processed"), 1)
        self.assertTrue(res.get("dry_run"))

    def test_09_handler_direct_invocation_full_reconciliation(self):
        """Test direct invocation of handle_full_reconciliation with dry_run and limit."""
        job = CatalogueJob(
            id=992,
            job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
            payload={"dry_run": True, "limit": 10, "batch_size": 5},
        )
        res = handle_full_reconciliation(job, "worker-direct", uuid.uuid4(), 1)
        self.assertIsInstance(res, dict)
        self.assertTrue(res.get("dry_run"))
        self.assertIn("records_scanned", res)

    @patch("core.services.tmdb_changes.poll_tmdb_changes", side_effect=ConnectionError("TMDB host unreachable"))
    def test_10_worker_handles_transient_handler_exception(self, mock_poll: MagicMock):
        """Verify worker handles transient exceptions by calling fail_job gracefully."""
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="test_fail",
            priority=50,
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-fail-test")
        claimed = CatalogueQueueService.claim_jobs(worker_id=worker.worker_id, batch_size=1)
        claimed_job = claimed[0]

        success = worker.process_one_job(claimed_job)
        self.assertFalse(success)

        claimed_job.refresh_from_db()
        self.assertEqual(claimed_job.status, CatalogueJob.Status.RETRY_WAIT)
        self.assertIn("ConnectionError: TMDB host unreachable", claimed_job.last_error)

    def test_11_worker_releases_unstarted_jobs_on_shutdown(self):
        """Verify that on shutdown_requested, remaining unstarted jobs in batch are released."""
        job1, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.SYNC_CHANGES_FEED,
            entity_type="system",
            entity_id="s1",
            priority=50,
            payload={"limit_pages": 1, "dry_run": True},
        )
        job2, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
            entity_type="system",
            entity_id="r1",
            priority=50,
            payload={"limit": 1, "dry_run": True},
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-shutdown-test", batch_size=10)
        # Simulate shutdown requested right after claiming
        with patch.object(worker, "process_one_job", side_effect=lambda j: setattr(worker, "shutdown_requested", True) or True):
            summary = worker.run_loop(once=True)

        self.assertEqual(summary["completed"], 1)

        # Job 2 should have been gracefully released back to PENDING
        job2.refresh_from_db()
        self.assertEqual(job2.status, CatalogueJob.Status.PENDING)
        self.assertIsNone(job2.lease_token)
        self.assertIsNone(job2.claimed_by_worker_id)

