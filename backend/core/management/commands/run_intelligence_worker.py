import logging
import os
import signal
import socket
import sys
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

from core.models import CatalogueJob
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.services.batch3_handlers import (
    handle_full_reconciliation,
    handle_sync_changes_feed,
)
from core.services.enrichment_handlers import (
    handle_catalogue_classification,
    handle_catalogue_enrichment,
)
from core.services.taste_engine import handle_recompute_taste_profile

logger = logging.getLogger(__name__)


# Default registry of job handlers
DEFAULT_JOB_HANDLERS: Dict[str, Callable[[CatalogueJob, str, uuid.UUID, int], Optional[Dict[str, Any]]]] = {
    "catalogue_classification": handle_catalogue_classification,
    "catalogue_enrichment": handle_catalogue_enrichment,
    "sync_changes_feed": handle_sync_changes_feed,
    "full_reconciliation": handle_full_reconciliation,
    "recompute_taste_profile": handle_recompute_taste_profile,
}

JOB_HANDLERS: Dict[str, Callable[[CatalogueJob, str, uuid.UUID, int], Optional[Dict[str, Any]]]] = dict(DEFAULT_JOB_HANDLERS)


def reset_handlers() -> None:
    """Restores JOB_HANDLERS to default state."""
    JOB_HANDLERS.clear()
    JOB_HANDLERS.update(DEFAULT_JOB_HANDLERS)


def register_handler(job_type: str):
    """Decorator to register a callable handler for a specific job_type."""
    def decorator(fn: Callable[[CatalogueJob, str, uuid.UUID, int], Optional[Dict[str, Any]]]):
        JOB_HANDLERS[job_type] = fn
        return fn
    return decorator


class IntelligenceWorkerProcess:
    """
    Dedicated Render Background Worker for Catalogue Intelligence and Taste Processing.
    
    Guarantees:
    - Traps SIGTERM and SIGINT for graceful worker shutdown.
    - Maintains heartbeat renewal for long-running tasks.
    - Releases unstarted claimed jobs back to PENDING on shutdown.
    - Strictly checks generation fencing tokens and lease validity before marking jobs complete.
    - Emits structured log events for operational observability.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        batch_size: int = 10,
        lease_duration: int = 60,
        empty_interval: float = 2.0,
    ):
        hostname = socket.gethostname().split(".")[0]
        self.worker_id = worker_id or f"worker-{hostname}-{uuid.uuid4().hex[:8]}"
        self.batch_size = batch_size
        self.lease_duration = lease_duration
        self.empty_interval = empty_interval

        self.shutdown_requested = False
        self.current_job: Optional[CatalogueJob] = None
        self._heartbeat_timer: Optional[threading.Timer] = None
        self._active_lease_token: Optional[uuid.UUID] = None
        self._active_generation: Optional[int] = None
        self._lease_lost: bool = False

    def register_signal_handlers(self) -> None:
        """Attaches signal listeners for graceful process termination."""
        signal.signal(signal.SIGTERM, self._on_termination_signal)
        signal.signal(signal.SIGINT, self._on_termination_signal)

    def _on_termination_signal(self, signum: int, frame: Any) -> None:
        signame = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
        logger.info(f"[{self.worker_id}] Received {signame}. Initiating graceful shutdown...")
        self.shutdown_requested = True

    def _start_heartbeat(self, job_id: int, lease_token: uuid.UUID, generation: int) -> None:
        """Schedules recurring heartbeat lease extension every lease_duration / 3 seconds."""
        interval = max(5, self.lease_duration // 3)
        self._lease_lost = False

        def _beat():
            if self.shutdown_requested:
                return
            try:
                extended = CatalogueQueueService.renew_lease(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    generation=generation,
                    extension_seconds=self.lease_duration,
                )
                if extended:
                    logger.debug(f"[{self.worker_id}] Renewed lease for Job {job_id} (gen={generation})")
                    self._heartbeat_timer = threading.Timer(interval, _beat)
                    self._heartbeat_timer.daemon = True
                    self._heartbeat_timer.start()
                else:
                    logger.warning(f"[{self.worker_id}] Heartbeat renewal failed for Job {job_id}: lease lost.")
                    self._lease_lost = True
            except Exception as exc:
                logger.warning(f"[{self.worker_id}] Exception during heartbeat for Job {job_id}: {exc}")
            finally:
                # Close the thread-local database connection to prevent pool leaks
                connection.close()

        self._heartbeat_timer = threading.Timer(interval, _beat)
        self._heartbeat_timer.daemon = True
        self._heartbeat_timer.start()

    def _stop_heartbeat(self) -> None:
        """Cancels any running heartbeat timer."""
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None
        self._lease_lost = False

    def process_one_job(self, job: CatalogueJob) -> bool:
        """
        Executes a single claimed job under generation fencing protection.
        Returns True on success; False on failure or stale ownership.
        """
        self.current_job = job
        self._active_lease_token = job.lease_token
        self._active_generation = job.claim_generation
        job_id = job.id
        job_type = job.job_type
        token = job.lease_token
        gen = job.claim_generation
        start_time = time.time()

        logger.info(
            f"[{self.worker_id}] Starting Job {job_id} "
            f"(type={job_type}, entity={job.entity_type}:{job.entity_id}, gen={gen})"
        )

        self._start_heartbeat(job_id, token, gen)

        try:
            handler = JOB_HANDLERS.get(job_type)
            if not handler:
                error_msg = f"UnknownJobHandlerError: No registered handler for job_type='{job_type}'"
                logger.error(f"[{self.worker_id}] {error_msg}")
                CatalogueQueueService.fail_job(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_token=token,
                    generation=gen,
                    error_message=error_msg,
                    is_permanent=True,
                )
                return False

            if not isinstance(job.payload, dict):
                error_msg = f"InvalidPayloadError: Payload for Job {job.id} is not a valid JSON dictionary"
                logger.error(f"[{self.worker_id}] {error_msg}")
                CatalogueQueueService.fail_job(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_token=token,
                    generation=gen,
                    error_message=error_msg,
                    is_permanent=True,
                )
                return False

            result_payload = handler(job, self.worker_id, token, gen) or {}

            # Mark job complete under generation fencing check
            CatalogueQueueService.complete_job(
                job_id=job_id,
                worker_id=self.worker_id,
                lease_token=token,
                generation=gen,
                result_payload=result_payload,
            )
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"[{self.worker_id}] Completed Job {job_id} (type={job_type}) in {duration_ms}ms"
            )
            return True

        except StaleLeaseOwnershipError as stale_exc:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(
                f"[{self.worker_id}] Stale ownership for Job {job_id} after {duration_ms}ms: {stale_exc}"
            )
            return False

        except Exception as exc:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = f"{type(exc).__name__}: {str(exc)}"
            logger.exception(
                f"[{self.worker_id}] Error executing Job {job_id} after {duration_ms}ms: {error_msg}"
            )
            # Permanent errors: ValueError, TypeError, KeyError, AssertionError, etc.
            # Transient errors: ConnectionError, Timeout, TMDB 429 rate limit, operational errors
            is_permanent = isinstance(exc, (ValueError, TypeError, KeyError, AssertionError))
            try:
                CatalogueQueueService.fail_job(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    lease_token=token,
                    generation=gen,
                    error_message=error_msg,
                    is_permanent=is_permanent,
                )
            except StaleLeaseOwnershipError:
                logger.warning(
                    f"[{self.worker_id}] Could not record failure for Job {job_id}: lease expired."
                )
            return False

        finally:
            self._stop_heartbeat()
            self.current_job = None
            self._active_lease_token = None
            self._active_generation = None

    def run_loop(self, once: bool = False, max_batches: Optional[int] = None) -> Dict[str, int]:
        """Main worker loop."""
        self.register_signal_handlers()
        logger.info(
            f"[{self.worker_id}] Worker started. Batch size: {self.batch_size}, "
            f"Lease duration: {self.lease_duration}s"
        )

        batches_processed = 0
        total_jobs_completed = 0
        total_jobs_failed = 0

        while not self.shutdown_requested:
            claimed_jobs = CatalogueQueueService.claim_jobs(
                worker_id=self.worker_id,
                batch_size=self.batch_size,
                lease_duration_seconds=self.lease_duration,
            )

            if not claimed_jobs:
                if once:
                    break
                time.sleep(self.empty_interval)
                continue

            batches_processed += 1
            logger.info(f"[{self.worker_id}] Claimed {len(claimed_jobs)} job(s) in batch #{batches_processed}")

            for i, job in enumerate(claimed_jobs):
                if self.shutdown_requested:
                    # Gracefully release remaining unstarted jobs in this batch back to PENDING
                    logger.info(
                        f"[{self.worker_id}] Shutdown requested; releasing remaining {len(claimed_jobs) - i} job(s)..."
                    )
                    for remaining_job in claimed_jobs[i:]:
                        CatalogueQueueService.release_job(
                            job_id=remaining_job.id,
                            worker_id=self.worker_id,
                            lease_token=remaining_job.lease_token,
                            generation=remaining_job.claim_generation,
                        )
                    break

                success = self.process_one_job(job)
                if success:
                    total_jobs_completed += 1
                else:
                    total_jobs_failed += 1

            if once:
                break

            if max_batches and batches_processed >= max_batches:
                logger.info(f"[{self.worker_id}] Reached max_batches limit ({max_batches}). Exiting.")
                break

        logger.info(
            f"[{self.worker_id}] Worker stopped. Total batches: {batches_processed}, "
            f"Completed: {total_jobs_completed}, Failed: {total_jobs_failed}"
        )
        return {
            "batches": batches_processed,
            "completed": total_jobs_completed,
            "failed": total_jobs_failed,
        }


class Command(BaseCommand):
    help = "Starts the dedicated Render Background Worker for Catalogue Intelligence."

    def add_arguments(self, parser):
        parser.add_argument(
            "--worker-id",
            type=str,
            default=None,
            help="Unique identifier for this worker instance (default: worker-{hostname}-{uuid}).",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Maximum jobs to claim and process per batch (default: 10).",
        )
        parser.add_argument(
            "--lease-duration",
            type=int,
            default=60,
            help="Lease duration in seconds (default: 60).",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="Sleep interval in seconds when queue is empty (default: 2.0).",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process a single batch and exit immediately.",
        )
        parser.add_argument(
            "--max-batches",
            type=int,
            default=None,
            help="Exit after processing this number of batches (default: run indefinitely).",
        )

    def handle(self, *args, **options):
        batch_size = options.get("batch_size")
        if batch_size is not None and (batch_size < 1 or batch_size > 500):
            raise CommandError(f"--batch-size must be between 1 and 500 (got {batch_size})")

        lease_duration = options.get("lease_duration")
        if lease_duration is not None and (lease_duration < 5 or lease_duration > 3600):
            raise CommandError(f"--lease-duration must be between 5 and 3600 seconds (got {lease_duration})")

        interval = options.get("interval")
        if interval is not None and (interval < 0.1 or interval > 60.0):
            raise CommandError(f"--interval must be between 0.1 and 60.0 seconds (got {interval})")

        max_batches = options.get("max_batches")
        if max_batches is not None and max_batches < 1:
            raise CommandError(f"--max-batches must be at least 1 (got {max_batches})")

        worker = IntelligenceWorkerProcess(
            worker_id=options.get("worker_id"),
            batch_size=batch_size or 10,
            lease_duration=lease_duration or 60,
            empty_interval=interval if interval is not None else 2.0,
        )
        summary = worker.run_loop(
            once=options.get("once", False),
            max_batches=max_batches,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Intelligence worker finished. "
                f"Batches: {summary['batches']}, Completed: {summary['completed']}, Failed: {summary['failed']}"
            )
        )
