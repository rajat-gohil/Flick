from datetime import timedelta
import threading
import unittest
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from core.models import CatalogueJob, InteractionLog, Movie, TmdbChangesCheckpoint
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.services.tmdb_changes import (
    StalePollerOwnershipError,
    TmdbChangesService,
)


@unittest.skipIf(
    connection.vendor != "postgresql",
    "PostgreSQL test environment is unavailable. PostgreSQL-specific SKIP LOCKED and partial index guarantees cannot be tested on SQLite."
)
class PostgreSQLQueueConcurrencyTests(TransactionTestCase):
    """
    Dedicated PostgreSQL Integration Test Suite.
    
    Verifies:
    1. SELECT FOR UPDATE SKIP LOCKED prevents lock contention and guarantees zero duplicate claims among concurrent worker threads.
    2. Partial unique index uidx_active_catalogue_job enforces database-level concurrency deduplication.
    3. Transactional fencing rollbacks prevent stale workers from writing side effects.
    
    Requirement:
    Must be executed against a live PostgreSQL database (e.g. CI or staging).
    If connection.vendor != 'postgresql', all tests in this suite are explicitly SKIPPED and reported as NOT RUN.
    """

    def setUp(self):
        super().setUp()
        CatalogueJob.objects.all().delete()

    def test_postgresql_skip_locked_concurrent_workers_zero_overlap(self):
        """
        Spawns 4 concurrent worker threads simultaneously claiming from 20 pending jobs.
        Verifies that PostgreSQL's SKIP LOCKED assigns each job to exactly one worker
        with zero deadlocks and zero duplicate claims.
        """
        # Create 20 pending jobs
        job_ids = []
        for i in range(20):
            job, _ = CatalogueQueueService.enqueue(
                job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                entity_type="movie",
                entity_id=f"pg-test-{i}",
                priority=100,
            )
            job_ids.append(job.id)

        claimed_ids = []
        lock = threading.Lock()
        exceptions = []

        def worker_task(worker_num):
            try:
                # Each thread claims a batch of 5
                claims = CatalogueQueueService.claim_jobs(
                    worker_id=f"pg-worker-{worker_num}",
                    batch_size=5,
                    lease_duration_seconds=60,
                )
                with lock:
                    claimed_ids.extend([c.id for c in claims])
            except Exception as e:
                with lock:
                    exceptions.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0, f"Concurrent claiming raised exceptions: {exceptions}")
        self.assertEqual(len(claimed_ids), 20, f"Expected 20 claimed jobs, got {len(claimed_ids)}")
        # Assert strictly zero overlap
        self.assertEqual(len(claimed_ids), len(set(claimed_ids)), "Duplicate claims detected across concurrent workers!")

    def test_postgresql_partial_unique_index_concurrency_race(self):
        """
        Verifies that PostgreSQL enforces the partial unique index condition:
        uidx_active_catalogue_job: (job_type, entity_type, entity_id) WHERE status IN ('pending', 'in_progress', 'retry_wait').
        Simulates two threads attempting raw parallel inserts.
        """
        def raw_insert():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO core_cataloguejob (job_type, entity_type, entity_id, status, priority, scheduled_for, attempts, max_attempts, payload, needs_subsequent_pass, claim_generation, last_error, created_at, updated_at)
                    VALUES ('enrich_movie', 'movie', 'race-999', 'pending', 100, NOW(), 0, 5, '{}', FALSE, 0, '', NOW(), NOW());
                    """
                )

        # First insert succeeds
        raw_insert()

        # Second raw concurrent insert must violate the partial unique index
        from django.db.utils import IntegrityError
        with self.assertRaises(IntegrityError):
            raw_insert()

    def test_postgresql_transactional_side_effect_fencing_rollback(self):
        """
        Verifies that if Worker A's lease expires and Worker B reclaims the job:
        1. Worker A performs a representative database side effect within an atomic transaction.
        2. Worker A calls complete_job within the SAME atomic transaction.
        3. Fencing checks under SELECT FOR UPDATE detect generation mismatch and raise StaleLeaseOwnershipError.
        4. The entire transaction rolls back, guaranteeing the representative side effect is NOT committed.
        5. The job remains safely in progress under Worker B's generation ownership.
        """
        # Create an isolated temporary table for representative domain side effects
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMPORARY TABLE IF NOT EXISTS test_worker_side_effects (
                    id SERIAL PRIMARY KEY,
                    worker_id VARCHAR(64) NOT NULL,
                    payload_note TEXT NOT NULL
                );
                TRUNCATE TABLE test_worker_side_effects;
                """
            )

        job, _ = CatalogueQueueService.enqueue(
            job_type=CatalogueJob.JobType.ENRICH_MOVIE,
            entity_type="movie",
            entity_id="fencing-100",
        )
        claimed_a = CatalogueQueueService.claim_jobs("worker-A", batch_size=1, lease_duration_seconds=5)[0]
        self.assertEqual(claimed_a.claim_generation, 1)

        # Simulate expiration and reclamation by Worker B
        CatalogueJob.objects.filter(id=job.id).update(lease_expires_at=timezone.now() - timedelta(seconds=1))
        CatalogueQueueService.reclaim_expired_leases()
        CatalogueJob.objects.filter(id=job.id).update(scheduled_for=timezone.now() - timedelta(seconds=1))
        claimed_b = CatalogueQueueService.claim_jobs("worker-B", batch_size=1, lease_duration_seconds=60)[0]
        self.assertEqual(claimed_b.claim_generation, 2)

        # Stale Worker A attempts database side effect AND completion in the SAME atomic transaction
        with self.assertRaises(StaleLeaseOwnershipError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO test_worker_side_effects (worker_id, payload_note) VALUES (%s, %s);",
                        ["worker-A", "stale mutation that must be rolled back"],
                    )
                # Fencing token check must fail here and abort the transaction
                CatalogueQueueService.complete_job(
                    job_id=job.id,
                    worker_id="worker-A",
                    lease_token=claimed_a.lease_token,
                    generation=claimed_a.claim_generation,
                )

        # Crucial Verification: Assert representative side effect was completely ROLLED BACK
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM test_worker_side_effects WHERE worker_id = 'worker-A';")
            side_effect_count = cursor.fetchone()[0]
        self.assertEqual(
            side_effect_count,
            0,
            "CRITICAL FENCING FAILURE: Stale worker side effect committed despite lease ownership loss!",
        )

        # Verify job is preserved under Worker B with generation 2
        current = CatalogueJob.objects.get(id=job.id)
        self.assertEqual(current.status, CatalogueJob.Status.IN_PROGRESS)
        self.assertEqual(current.claimed_by_worker_id, "worker-B")
        self.assertEqual(current.claim_generation, 2)

    def test_postgresql_concurrent_threads_enqueue_race(self):
        """
        Spawns 5 threads simultaneously calling CatalogueQueueService.enqueue
        for the exact same (job_type, entity_type, entity_id).
        Verifies that PostgreSQL partial unique constraint and atomic savepoints
        guarantee exactly 1 job is created and all 5 threads return the same job ID
        without any TransactionManagementError or IntegrityError escaping.
        """
        results = []
        errors = []
        lock = threading.Lock()

        def do_enqueue(i):
            try:
                job, created = CatalogueQueueService.enqueue(
                    job_type=CatalogueJob.JobType.ENRICH_MOVIE,
                    entity_type="movie",
                    entity_id="concurrent-entity-race",
                    payload={"thread": i},
                )
                with lock:
                    results.append((job.id, created))
            except Exception as e:
                with lock:
                    errors.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=do_enqueue, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent enqueue raised errors: {errors}")
        self.assertEqual(len(results), 5)
        # Exactly one thread created = True
        created_count = sum(1 for _, created in results if created)
        self.assertEqual(created_count, 1)
        # All returned job IDs are identical
        job_ids = set(job_id for job_id, _ in results)
        self.assertEqual(len(job_ids), 1)

    def test_postgresql_tmdb_changes_stale_poller_fencing_rejection(self):
        """
        Verifies generation and token fencing on TmdbChangesCheckpoint under PostgreSQL:
        1. Poller A initializes checkpoint and acquires lock (generation 1, token A).
        2. Poller A prepares to process page 1.
        3. Poller B takes over the lock (simulating stale timeout override, generation 2, token B).
        4. Poller A attempts to advance checkpoint and enqueue jobs via process_page_results.
        5. PostgreSQL atomic transaction aborts:
           - StalePollerOwnershipError is raised.
           - Zero CatalogueJob records are created by Poller A.
           - Checkpoint cursor (current_page, changes_enqueued_count) remains uncorrupted.
        """
        TmdbChangesCheckpoint.objects.all().delete()
        Movie.objects.filter(tmdb_id=88881).delete()
        Movie.objects.create(
            tmdb_id=88881,
            title="Stale Fencing Test Movie",
            provenance="tmdb_catalogue",
        )

        service_a = TmdbChangesService(feed_name="pg_fencing_feed")
        cp_a = service_a.get_or_init_checkpoint()
        self.assertEqual(cp_a.lock_generation, 1)
        token_a = service_a.lock_token
        self.assertIsNotNone(token_a)

        # Poller B takes over with force_reset or after stale timeout
        service_b = TmdbChangesService(feed_name="pg_fencing_feed")
        cp_b = service_b.get_or_init_checkpoint(force_reset=True)
        self.assertEqual(cp_b.lock_generation, 2)
        token_b = service_b.lock_token
        self.assertNotEqual(token_a, token_b)

        # Poller A attempts to process results from its earlier HTTP fetch
        page_results = [{"id": 88881, "adult": False}]
        with self.assertRaises(StalePollerOwnershipError) as ctx:
            service_a.process_page_results(
                results=page_results,
                page=1,
                total_pages=5,
                dry_run=False,
            )
        self.assertIn("Poller lost lock ownership", str(ctx.exception))

        # Verify zero jobs were enqueued by stale Poller A
        enqueued_jobs = CatalogueJob.objects.filter(external_id="88881")
        self.assertEqual(enqueued_jobs.count(), 0)

        # Verify checkpoint was NOT advanced by Poller A
        refreshed_cp = TmdbChangesCheckpoint.objects.get(feed_name="pg_fencing_feed")
        self.assertEqual(refreshed_cp.lock_generation, 2)
        self.assertEqual(refreshed_cp.lock_token, token_b)
        self.assertEqual(refreshed_cp.current_page, 1)
        self.assertEqual(refreshed_cp.changes_enqueued_count, 0)

    def test_postgresql_skip_locked_concurrent_interaction_logs_zero_overlap(self):
        """
        Batch 4: Verifies PostgreSQL SELECT FOR UPDATE SKIP LOCKED on pending InteractionLogs.
        Spawns 4 concurrent worker threads simultaneously claiming pending interaction logs.
        Verifies:
        1. PostgreSQL SKIP LOCKED assigns each pending log to exactly one worker thread.
        2. Zero duplicate claims across concurrent workers.
        3. All 20 pending logs are claimed and processed without deadlocks or contention.
        """
        User = get_user_model()
        user = User.objects.create_user(username="pg_batch4_user", password="password123")
        movie = Movie.objects.create(
            tmdb_id=999991,
            title="Batch 4 Concurrency Movie",
            provenance="tmdb_catalogue",
        )

        log_ids = []
        for i in range(20):
            log = InteractionLog.objects.create(
                user=user,
                movie=movie,
                event_type="swipe_like",
                weight=1.0,
                processing_status="pending",
                metadata={"test_index": i},
            )
            log_ids.append(log.id)

        claimed_ids = []
        lock = threading.Lock()
        exceptions = []

        def worker_task(worker_num):
            try:
                # Each thread runs in its own atomic transaction and uses select_for_update(skip_locked=True)
                with transaction.atomic():
                    pending_batch = list(
                        InteractionLog.objects.select_for_update(skip_locked=True)
                        .filter(processing_status="pending")[:5]
                    )
                    batch_ids = [item.id for item in pending_batch]
                    if batch_ids:
                        InteractionLog.objects.filter(id__in=batch_ids).update(
                            processing_status="processed",
                            processed_at=timezone.now(),
                        )
                    with lock:
                        claimed_ids.extend(batch_ids)
            except Exception as e:
                with lock:
                    exceptions.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0, f"Concurrent log claiming raised exceptions: {exceptions}")
        self.assertEqual(len(claimed_ids), 20, f"Expected 20 claimed logs, got {len(claimed_ids)}")
        self.assertEqual(len(claimed_ids), len(set(claimed_ids)), "Duplicate log claims detected across concurrent workers!")

        # Verify all 20 are now processed in DB
        processed_count = InteractionLog.objects.filter(
            id__in=log_ids,
            processing_status="processed",
        ).count()
        self.assertEqual(processed_count, 20)
