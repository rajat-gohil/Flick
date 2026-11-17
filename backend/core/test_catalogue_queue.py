import time
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from core.models import CatalogueJob
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.management.commands.run_intelligence_worker import (
    IntelligenceWorkerProcess,
    register_handler,
    JOB_HANDLERS,
)


class CatalogueQueueUnitTests(TestCase):
    """
    Focused unit tests for Batch 1: CatalogueJob model, Queue Service,
    lease fencing, generation tokens, reclamation, deduplication, and worker lifecycle.
    """

    def setUp(self):
        super().setUp()
        CatalogueJob.objects.all().delete()
        JOB_HANDLERS.clear()

    def tearDown(self):
        JOB_HANDLERS.clear()
        super().tearDown()

    def test_01_job_creation_and_attributes(self):
        """Verify clean job creation with defaults and entity targeting."""
        job, created = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="367",
            external_id="550",
            payload={"source": "test"},
            priority=50,
        )
        self.assertTrue(created)
        self.assertEqual(job.status, CatalogueJob.Status.PENDING)
        self.assertEqual(job.priority, 50)
        self.assertEqual(job.entity_type, "movie")
        self.assertEqual(job.entity_id, "367")
        self.assertEqual(job.external_id, "550")
        self.assertEqual(job.claim_generation, 0)
        self.assertIsNone(job.lease_token)
        self.assertFalse(job.needs_subsequent_pass)

    def test_02_active_job_deduplication_pending(self):
        """
        Submitting a second enqueue for the same (job_type, entity_type, entity_id)
        while the first is PENDING returns the existing job and elevates priority if higher.
        """
        job1, created1 = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="367",
            priority=100,
        )
        self.assertTrue(created1)

        job2, created2 = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="367",
            priority=40,  # Higher priority (lower integer)
            payload={"updated": True},
        )
        self.assertFalse(created2)
        self.assertEqual(job1.id, job2.id)
        self.assertEqual(job2.priority, 40)
        self.assertTrue(job2.payload.get("updated"))
        self.assertEqual(CatalogueJob.objects.count(), 1)

    def test_03_active_job_deduplication_in_progress_dirty_flag(self):
        """
        Submitting an enqueue while a job is IN_PROGRESS marks needs_subsequent_pass=True.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.RECOMPUTE_TASTE,
            entity_type="user",
            entity_id="5",
            priority=50,
        )
        claims = CatalogueQueueService.claim_jobs(worker_id="worker-test-1", batch_size=1)
        self.assertEqual(len(claims), 1)
        claimed_job = claims[0]
        self.assertEqual(claimed_job.status, CatalogueJob.Status.IN_PROGRESS)
        self.assertFalse(claimed_job.needs_subsequent_pass)

        # Enqueue new work while in-flight
        dup_job, created = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.RECOMPUTE_TASTE,
            entity_type="user",
            entity_id="5",
            priority=30,
        )
        self.assertFalse(created)
        self.assertEqual(dup_job.id, claimed_job.id)
        self.assertTrue(dup_job.needs_subsequent_pass)
        self.assertEqual(dup_job.priority, 30)

    def test_04_completion_clears_or_reschedules_on_dirty_flag(self):
        """
        Completing an in_progress job:
        - If needs_subsequent_pass is False -> transitions to SUCCEEDED.
        - If needs_subsequent_pass is True -> resets to PENDING for immediate follow-up pass.
        """
        # Case A: Normal completion
        job_a, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="101",
        )
        claimed_a = CatalogueQueueService.claim_jobs("worker-A", batch_size=1)[0]
        completed_a = CatalogueQueueService.complete_job(
            job_id=claimed_a.id,
            worker_id="worker-A",
            lease_token=claimed_a.lease_token,
            generation=claimed_a.claim_generation,
            result_payload={"done": True},
        )
        self.assertEqual(completed_a.status, CatalogueJob.Status.SUCCEEDED)
        self.assertIsNone(completed_a.lease_expires_at)
        self.assertTrue(completed_a.payload.get("done"))

        # Case B: Completion with dirty flag set
        job_b, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="102",
        )
        claimed_b = CatalogueQueueService.claim_jobs("worker-B", batch_size=1)[0]
        # Set dirty flag via concurrent enqueue
        CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="102",
        )
        completed_b = CatalogueQueueService.complete_job(
            job_id=claimed_b.id,
            worker_id="worker-B",
            lease_token=claimed_b.lease_token,
            generation=claimed_b.claim_generation,
        )
        # Rescheduled for another pass
        self.assertEqual(completed_b.status, CatalogueJob.Status.PENDING)
        self.assertFalse(completed_b.needs_subsequent_pass)
        self.assertIsNone(completed_b.claimed_by_worker_id)
        self.assertIsNone(completed_b.lease_token)

    def test_05_claim_generation_and_fencing_token(self):
        """
        Every claim increments claim_generation monotonically and assigns a unique lease_token.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="200",
        )
        self.assertEqual(job.claim_generation, 0)

        claims_1 = CatalogueQueueService.claim_jobs("worker-1", batch_size=1)
        job_1 = claims_1[0]
        self.assertEqual(job_1.claim_generation, 1)
        self.assertIsNotNone(job_1.lease_token)
        self.assertEqual(job_1.attempts, 1)

        # Fail with retry wait
        CatalogueQueueService.fail_job(
            job_id=job_1.id,
            worker_id="worker-1",
            lease_token=job_1.lease_token,
            generation=job_1.claim_generation,
            error_message="Simulated network glitch",
        )
        # Advance scheduled_for to allow reclaim
        CatalogueJob.objects.filter(id=job_1.id).update(scheduled_for=timezone.now() - timedelta(seconds=1))

        claims_2 = CatalogueQueueService.claim_jobs("worker-2", batch_size=1)
        job_2 = claims_2[0]
        self.assertEqual(job_2.claim_generation, 2)
        self.assertNotEqual(job_1.lease_token, job_2.lease_token)
        self.assertEqual(job_2.attempts, 2)

    def test_06_stale_worker_completion_rejected(self):
        """
        A stale worker whose lease expired or was reclaimed cannot complete the job.
        Raises StaleLeaseOwnershipError and aborts without modifying the job.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="300",
        )
        # Worker A claims job
        claimed_a = CatalogueQueueService.claim_jobs("worker-A", batch_size=1, lease_duration_seconds=10)[0]
        old_token = claimed_a.lease_token
        old_gen = claimed_a.claim_generation

        # Scenario 1: Worker A resumes after lease expiration but before reclamation
        # Simulate lease expiration in DB
        CatalogueJob.objects.filter(id=job.id).update(
            lease_expires_at=timezone.now() - timedelta(seconds=5)
        )
        with self.assertRaises(StaleLeaseOwnershipError):
            CatalogueQueueService.complete_job(
                job_id=job.id,
                worker_id="worker-A",
                lease_token=old_token,
                generation=old_gen,
            )

        # Scenario 2: Expired job is reclaimed and Worker B claims it after backoff
        CatalogueQueueService.reclaim_expired_leases()
        # Set scheduled_for in the past so Worker B can claim immediately
        CatalogueJob.objects.filter(id=job.id).update(
            scheduled_for=timezone.now() - timedelta(seconds=1)
        )

        reclaimed_b = CatalogueQueueService.claim_jobs("worker-B", batch_size=1, lease_duration_seconds=60)[0]
        self.assertEqual(reclaimed_b.claim_generation, 2)
        self.assertEqual(reclaimed_b.claimed_by_worker_id, "worker-B")

        # Worker A now attempts to complete with stale generation 1
        with self.assertRaises(StaleLeaseOwnershipError):
            CatalogueQueueService.complete_job(
                job_id=job.id,
                worker_id="worker-A",
                lease_token=old_token,
                generation=old_gen,
            )

        # Verify job remains active under Worker B
        current = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(current.status, CatalogueJob.Status.IN_PROGRESS)
        self.assertEqual(current.claimed_by_worker_id, "worker-B")
        self.assertEqual(current.claim_generation, 2)

    def test_07_lease_renewal_heartbeat(self):
        """
        renew_lease extends lease_expires_at if caller still holds ownership.
        Returns False if generation changed or lease already expired.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="400",
        )
        claimed = CatalogueQueueService.claim_jobs("worker-hb", batch_size=1, lease_duration_seconds=30)[0]
        initial_expires = claimed.lease_expires_at

        # Successful renewal
        time.sleep(0.01)
        success = CatalogueQueueService.renew_lease(
            job_id=claimed.id,
            worker_id="worker-hb",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
            extension_seconds=60,
        )
        self.assertTrue(success)
        refreshed = CatalogueJob.objects.get(id=claimed.id)
        self.assertGreater(refreshed.lease_expires_at, initial_expires)

        # Failed renewal: wrong generation
        failed = CatalogueQueueService.renew_lease(
            job_id=claimed.id,
            worker_id="worker-hb",
            lease_token=claimed.lease_token,
            generation=999,
            extension_seconds=60,
        )
        self.assertFalse(failed)

    def test_08_reclamation_exponential_backoff_and_terminal_failure(self):
        """
        Expired leases are reclaimed into RETRY_WAIT with backoff.
        When max_attempts is reached, transitions to FAILED_PERMANENT.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="500",
        )
        # Set max_attempts to 2 for quick terminal testing
        CatalogueJob.objects.filter(id=job.id).update(max_attempts=2)

        # Attempt 1: claim and expire
        claimed_1 = CatalogueQueueService.claim_jobs("worker-1", batch_size=1, lease_duration_seconds=10)[0]
        self.assertEqual(claimed_1.attempts, 1)
        CatalogueJob.objects.filter(id=job.id).update(lease_expires_at=timezone.now() - timedelta(seconds=1))

        # Reclaim attempt 1 -> RETRY_WAIT
        count = CatalogueQueueService.reclaim_expired_leases()
        self.assertEqual(count, 1)
        j1 = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(j1.status, CatalogueJob.Status.RETRY_WAIT)
        self.assertGreater(j1.scheduled_for, timezone.now())

        # Pull scheduled_for forward and claim attempt 2
        CatalogueJob.objects.filter(id=job.id).update(scheduled_for=timezone.now() - timedelta(seconds=1))
        claimed_2 = CatalogueQueueService.claim_jobs("worker-2", batch_size=1, lease_duration_seconds=10)[0]
        self.assertEqual(claimed_2.attempts, 2)
        CatalogueJob.objects.filter(id=job.id).update(lease_expires_at=timezone.now() - timedelta(seconds=1))

        # Reclaim attempt 2 -> FAILED_PERMANENT (attempts >= max_attempts)
        count_terminal = CatalogueQueueService.reclaim_expired_leases()
        self.assertEqual(count_terminal, 1)
        j2 = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(j2.status, CatalogueJob.Status.FAILED_PERMANENT)
        self.assertIn("max attempts", j2.last_error)

    def test_09_quota_fairness_across_priority_classes(self):
        """
        Claiming allocates quotas: 60% High (<=50), 30% Normal (51-150), 10% Low (>150).
        Low-priority jobs are guaranteed at least 1 slot even when high-priority jobs are queued.
        """
        # Create 10 High-priority jobs
        for i in range(10):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.RECOMPUTE_TASTE,
                entity_type="user",
                entity_id=f"user-high-{i}",
                priority=20,
            )

        # Create 5 Normal-priority jobs
        for i in range(5):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                entity_type="movie",
                entity_id=f"movie-norm-{i}",
                priority=100,
            )

        # Create 3 Low-priority jobs
        for i in range(3):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
                entity_type="system",
                entity_id=f"sys-low-{i}",
                priority=200,
            )

        # Claim batch of 10
        claims = CatalogueQueueService.claim_jobs("worker-fair", batch_size=10)
        self.assertEqual(len(claims), 10)

        high_count = sum(1 for c in claims if c.priority <= 50)
        normal_count = sum(1 for c in claims if 50 < c.priority <= 150)
        low_count = sum(1 for c in claims if c.priority > 150)

        # High quota was 6, normal target was 3, low quota was 1
        self.assertEqual(high_count, 6)
        self.assertEqual(normal_count, 3)
        self.assertEqual(low_count, 1)
        # Confirms low-priority sweep was NOT starved by 10 pending high-priority jobs!

    def test_10_graceful_shutdown_releases_uncompleted_jobs(self):
        """
        Calling release_job returns an in_progress job to PENDING without increasing attempts.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="600",
        )
        claimed = CatalogueQueueService.claim_jobs("worker-term", batch_size=1)[0]
        self.assertEqual(claimed.status, CatalogueJob.Status.IN_PROGRESS)

        released = CatalogueQueueService.release_job(
            job_id=claimed.id,
            worker_id="worker-term",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )
        self.assertTrue(released)
        j = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(j.status, CatalogueJob.Status.PENDING)
        self.assertIsNone(j.claimed_by_worker_id)
        self.assertIsNone(j.lease_token)
        # Attempts remains 1 (did not increment)
        self.assertEqual(j.attempts, 1)

    def test_11_worker_process_loop_execution(self):
        """
        IntelligenceWorkerProcess executes a batch of jobs via registered handlers,
        records results, and gracefully terminates with once=True.
        """
        handled_entities = []

        @register_handler(CatalogueJob.JobType.ENRICH_MOVIE)
        def mock_enrich_handler(job, worker_id, token, gen):
            handled_entities.append(job.entity_id)
            return {"enrichment_verified": True}

        # Enqueue two jobs
        CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="701",
        )
        CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="702",
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-proc-test", batch_size=5)
        summary = worker.run_loop(once=True)

        self.assertEqual(summary["completed"], 2)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(handled_entities, ["701", "702"])

        j1 = CatalogueJob.objects.get(entity_id="701")
        self.assertEqual(j1.status, CatalogueJob.Status.SUCCEEDED)
        self.assertTrue(j1.payload.get("enrichment_verified"))

    def test_12_concurrent_duplicate_enqueue_race_handling(self):
        """
        Simulates concurrent enqueue where an IntegrityError occurs during insert
        because another process inserted the row first.
        Verifies that the inner savepoint absorbs the IntegrityError cleanly without
        dirtying the transaction, and returns the existing active job.
        """
        # Create initial active job
        initial_job, created = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="race-entity-1",
            priority=100,
        )
        self.assertTrue(created)

        # Mock CatalogueJob.objects.create to raise IntegrityError inside the atomic savepoint
        with patch.object(CatalogueJob.objects, "create", side_effect=IntegrityError("Duplicate key simulated")):
            dedup_job, newly_created = CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                entity_type="movie",
                entity_id="race-entity-1",
                priority=40,
            )
            self.assertFalse(newly_created)
            self.assertEqual(dedup_job.id, initial_job.id)

    def test_13_completion_racing_with_reclamation(self):
        """
        Simulates the race where reclaim_expired_leases acquires the row lock before
        complete_job. When complete_job acquires the lock, it must observe the reclamation,
        raise StaleLeaseOwnershipError, and preserve the job in RETRY_WAIT.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="race-reclaim-1",
        )
        claimed = CatalogueQueueService.claim_jobs("worker-race", batch_size=1, lease_duration_seconds=5)[0]

        # Simulate expiration
        CatalogueJob.objects.filter(id=job.id).update(
            lease_expires_at=timezone.now() - timedelta(seconds=1)
        )

        # Reclamation runs first
        reclaimed_count = CatalogueQueueService.reclaim_expired_leases()
        self.assertEqual(reclaimed_count, 1)

        # Worker attempts to complete with its stale lease
        with self.assertRaises(StaleLeaseOwnershipError):
            CatalogueQueueService.complete_job(
                job_id=job.id,
                worker_id="worker-race",
                lease_token=claimed.lease_token,
                generation=claimed.claim_generation,
            )

        refreshed = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(refreshed.status, CatalogueJob.Status.RETRY_WAIT)

    def test_14_sustained_high_priority_load_fairness(self):
        """
        Under sustained heavy high-priority load (50 High jobs, 20 Normal, 10 Low),
        across 5 consecutive batch claims of size 10, low and normal priority jobs
        are guaranteed progress in EVERY batch, proving zero starvation.
        """
        # Create 50 High (priority=20)
        for i in range(50):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.RECOMPUTE_TASTE,
                entity_type="user",
                entity_id=f"high-{i}",
                priority=20,
            )
        # Create 20 Normal (priority=100)
        for i in range(20):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                entity_type="movie",
                entity_id=f"norm-{i}",
                priority=100,
            )
        # Create 10 Low (priority=200)
        for i in range(10):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.FULL_RECONCILIATION,
                entity_type="system",
                entity_id=f"low-{i}",
                priority=200,
            )

        total_low_claimed = 0
        total_normal_claimed = 0

        for batch_num in range(5):
            claims = CatalogueQueueService.claim_jobs(
                worker_id=f"worker-sustained-{batch_num}",
                batch_size=10,
                lease_duration_seconds=60,
            )
            self.assertEqual(len(claims), 10)

            high_in_batch = sum(1 for c in claims if c.priority <= 50)
            norm_in_batch = sum(1 for c in claims if 50 < c.priority <= 150)
            low_in_batch = sum(1 for c in claims if c.priority > 150)

            # High claims max 6, reserving at least 3 for normal and 1 for low
            self.assertEqual(high_in_batch, 6)
            self.assertEqual(norm_in_batch, 3)
            self.assertEqual(low_in_batch, 1)

            total_normal_claimed += norm_in_batch
            total_low_claimed += low_in_batch

        self.assertEqual(total_normal_claimed, 15)
        self.assertEqual(total_low_claimed, 5)

    def test_15_graceful_shutdown_with_unstarted_jobs_in_batch(self):
        """
        Simulates a batch of 4 claimed jobs where SIGTERM arrives during the second job.
        The worker finishes the second job, then cleanly releases jobs 3 and 4 back
        to PENDING with attempts preserved.
        """
        for i in range(4):
            CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                entity_type="movie",
                entity_id=f"shutdown-movie-{i}",
            )

        worker = IntelligenceWorkerProcess(worker_id="worker-shutdown-test", batch_size=4)
        processed_count = 0

        @register_handler(CatalogueJob.JobType.ENRICH_MOVIE)
        def handler_with_shutdown(job, worker_id, token, gen):
            nonlocal processed_count
            processed_count += 1
            if processed_count == 2:
                # Simulate SIGTERM arrival during job 2
                worker.shutdown_requested = True
            return {"job_num": processed_count}

        summary = worker.run_loop(once=False)

        self.assertEqual(summary["completed"], 2)
        self.assertEqual(processed_count, 2)

        # Verify jobs 1 and 2 succeeded
        j0 = CatalogueJob.objects.get(entity_id="shutdown-movie-0")
        j1 = CatalogueJob.objects.get(entity_id="shutdown-movie-1")
        self.assertEqual(j0.status, CatalogueJob.Status.SUCCEEDED)
        self.assertEqual(j1.status, CatalogueJob.Status.SUCCEEDED)

        # Verify jobs 3 and 4 were released back to PENDING
        j2 = CatalogueJob.objects.get(entity_id="shutdown-movie-2")
        j3 = CatalogueJob.objects.get(entity_id="shutdown-movie-3")
        self.assertEqual(j2.status, CatalogueJob.Status.PENDING)
        self.assertEqual(j3.status, CatalogueJob.Status.PENDING)
        self.assertIsNone(j2.claimed_by_worker_id)
        self.assertIsNone(j3.claimed_by_worker_id)
        # Attempt count was incremented on claim to 1, preserved on release
        self.assertEqual(j2.attempts, 1)
        self.assertEqual(j3.attempts, 1)

    def test_16_transaction_rollback_and_error_handling(self):
        """
        Simulates an unhandled exception inside a job handler.
        Verifies that process_one_job catches it, marks the job RETRY_WAIT,
        sets last_error, schedules retry with backoff, and does not crash the worker.
        """
        CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="error-movie-1",
        )

        @register_handler(CatalogueJob.JobType.ENRICH_MOVIE)
        def failing_handler(job, worker_id, token, gen):
            raise RuntimeError("TMDB service 503 Service Unavailable")

        worker = IntelligenceWorkerProcess(worker_id="worker-err-test", batch_size=1)
        summary = worker.run_loop(once=True)

        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["failed"], 1)

        failed_job = CatalogueJob.objects.get(entity_id="error-movie-1")
        self.assertEqual(failed_job.status, CatalogueJob.Status.RETRY_WAIT)
        self.assertIn("RuntimeError: TMDB service 503 Service Unavailable", failed_job.last_error)
        self.assertGreater(failed_job.scheduled_for, timezone.now())

    def test_17_worker_cli_arguments_validation(self):
        """
        Validates CLI argument bounds checking:
        --batch-size, --lease-duration, --interval, --max-batches
        must reject invalid values with CommandError.
        """
        with self.assertRaises(CommandError) as cm:
            call_command("run_intelligence_worker", "--batch-size=0", "--once")
        self.assertIn("--batch-size must be between 1 and 500", str(cm.exception))

        with self.assertRaises(CommandError) as cm:
            call_command("run_intelligence_worker", "--lease-duration=2", "--once")
        self.assertIn("--lease-duration must be between 5 and 3600", str(cm.exception))

        with self.assertRaises(CommandError) as cm:
            call_command("run_intelligence_worker", "--interval=0.01", "--once")
        self.assertIn("--interval must be between 0.1 and 60.0", str(cm.exception))

        with self.assertRaises(CommandError) as cm:
            call_command("run_intelligence_worker", "--max-batches=0", "--once")
        self.assertIn("--max-batches must be at least 1", str(cm.exception))

    def test_18_database_clock_authority(self):
        """
        Verifies that CatalogueQueueService.get_db_now() queries the database clock,
        returns a valid timezone-aware datetime, and is utilized for claim timestamps.
        """
        db_now = CatalogueQueueService.get_db_now()
        self.assertIsNotNone(db_now)
        self.assertFalse(timezone.is_naive(db_now))

        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="clock-test-1",
        )
        claimed = CatalogueQueueService.claim_jobs("worker-clock", batch_size=1, lease_duration_seconds=30)[0]
        self.assertIsNotNone(claimed.claimed_at)
        self.assertIsNotNone(claimed.lease_expires_at)
        self.assertGreater(claimed.lease_expires_at, claimed.claimed_at)
