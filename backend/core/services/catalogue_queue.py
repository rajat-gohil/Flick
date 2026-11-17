import logging
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Dict, List, Optional, Tuple

from django.db import IntegrityError, connection, models, transaction
from django.utils import timezone

from core.models import CatalogueJob

logger = logging.getLogger(__name__)


class CatalogueQueueError(Exception):
    """Base exception for catalogue queue operations."""
    pass


class StaleLeaseOwnershipError(CatalogueQueueError):
    """
    Raised when a worker attempts to update, complete, or fail a job whose lease
    has expired, whose generation token has incremented, or whose ownership
    has been reclaimed by another worker.
    """
    pass


class JobNotFoundError(CatalogueQueueError):
    """Raised when a specified job does not exist."""
    pass


class CatalogueQueueService:
    """
    Durable, PostgreSQL-backed queue service for asynchronous intelligence jobs.
    
    Guarantees:
    - At-least-once processing with generation fencing tokens.
    - Transactional side-effect protection under row-level locks.
    - Active-job uniqueness and deduplication via conditional constraints.
    - Atomic job claiming via SELECT FOR UPDATE SKIP LOCKED.
    - Quota-partitioned fair scheduling (60% High / 30% Normal / 10% Low) preventing priority starvation.
    - Expired-job reclamation with exponential backoff and terminal failure handling.
    - Database server clock authority for all lease operations.
    """

    @classmethod
    def get_db_now(cls) -> datetime:
        """
        Retrieves current database server time.
        In PostgreSQL: executes clock_timestamp() for exact database wall-clock time,
        preventing application-host clock skew and transaction-start staleness.
        In SQLite/other: executes CURRENT_TIMESTAMP.
        Guarantees that all lease decisions (claiming, expiry, renewal, reclamation,
        fencing checks) rely strictly on the authoritative database clock.
        """
        try:
            with connection.cursor() as cursor:
                sql = "SELECT clock_timestamp()" if connection.vendor == "postgresql" else "SELECT CURRENT_TIMESTAMP"
                cursor.execute(sql)
                val = cursor.fetchone()[0]
                if isinstance(val, str):
                    dt = datetime.fromisoformat(val)
                    if timezone.is_naive(dt):
                        dt = dt.replace(tzinfo=dt_timezone.utc)
                    return dt
                elif isinstance(val, datetime):
                    if timezone.is_naive(val):
                        return timezone.make_aware(val, dt_timezone.utc)
                    return val
        except Exception as exc:
            logger.warning(f"Failed to query database clock ({exc}); falling back to application timezone.now().")
        return timezone.now()

    @classmethod
    def enqueue(
        cls,
        job_type: str,
        entity_type: str,
        entity_id: str,
        external_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        priority: int = 100,
        scheduled_for: Optional[datetime] = None,
    ) -> Tuple[CatalogueJob, bool]:
        """
        Durable enqueue with active-job deduplication.
        
        If an active job (pending, in_progress, retry_wait) already exists for
        (job_type, entity_type, entity_id):
          - If in_progress: sets needs_subsequent_pass=True so a follow-up pass runs immediately upon completion.
          - If pending/retry_wait: elevates priority if new priority is higher (lower integer).
          - Returns (existing_job, False).
        Otherwise creates a new pending job and returns (new_job, True).
        """
        now = cls.get_db_now()
        scheduled = scheduled_for or now
        payload_data = payload or {}

        # 1. Check for existing active job under row lock
        with transaction.atomic():
            active_job = (
                CatalogueJob.objects.select_for_update()
                .filter(
                    job_type=job_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status__in=[
                        CatalogueJob.Status.PENDING,
                        CatalogueJob.Status.IN_PROGRESS,
                        CatalogueJob.Status.RETRY_WAIT,
                    ],
                )
                .first()
            )

            if active_job:
                updated_fields = []
                # Elevate priority if new request has higher priority (lower integer)
                if priority < active_job.priority:
                    active_job.priority = priority
                    updated_fields.append("priority")

                # If external_id provided and missing on job, store it
                if external_id and not active_job.external_id:
                    active_job.external_id = external_id
                    updated_fields.append("external_id")

                # If in_progress, flag dirty for another pass
                if active_job.status == CatalogueJob.Status.IN_PROGRESS:
                    if not active_job.needs_subsequent_pass:
                        active_job.needs_subsequent_pass = True
                        updated_fields.append("needs_subsequent_pass")

                # If pending/retry_wait and new scheduled_for is earlier, pull forward
                elif active_job.status in (CatalogueJob.Status.PENDING, CatalogueJob.Status.RETRY_WAIT):
                    if scheduled < active_job.scheduled_for:
                        active_job.scheduled_for = scheduled
                        updated_fields.append("scheduled_for")

                # Merge payload if provided
                if payload_data:
                    merged = dict(active_job.payload or {})
                    merged.update(payload_data)
                    active_job.payload = merged
                    updated_fields.append("payload")

                if updated_fields:
                    updated_fields.append("updated_at")
                    active_job.save(update_fields=updated_fields)

                return active_job, False

            # 2. No active job found; create new one in isolated savepoint
            try:
                with transaction.atomic():
                    new_job = CatalogueJob.objects.create(
                        job_type=job_type,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        external_id=external_id,
                        payload=payload_data,
                        priority=priority,
                        scheduled_for=scheduled,
                        status=CatalogueJob.Status.PENDING,
                    )
                    return new_job, True
            except IntegrityError:
                # Concurrent race condition: another process created the active job
                active_job = CatalogueJob.objects.get(
                    job_type=job_type,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    status__in=[
                        CatalogueJob.Status.PENDING,
                        CatalogueJob.Status.IN_PROGRESS,
                        CatalogueJob.Status.RETRY_WAIT,
                    ],
                )
                return active_job, False

    @classmethod
    def reclaim_expired_leases(cls, now: Optional[datetime] = None, batch_size: int = 50) -> int:
        """
        Scans for abandoned in_progress jobs whose lease_expires_at < database time.
        Resets them to RETRY_WAIT with exponential backoff if attempts < max_attempts,
        or marks them FAILED_PERMANENT if attempts exhausted.
        Uses database clock authority.
        """
        check_time = now or cls.get_db_now()
        reclaimed_count = 0

        with transaction.atomic():
            qs = CatalogueJob.objects.filter(
                status=CatalogueJob.Status.IN_PROGRESS,
                lease_expires_at__lt=check_time,
            )

            if connection.vendor == "postgresql":
                expired_jobs = list(qs.select_for_update(skip_locked=True)[:batch_size])
            else:
                expired_jobs = list(qs.select_for_update()[:batch_size])

            for job in expired_jobs:
                if job.attempts < job.max_attempts:
                    backoff_sec = min(300, 10 * (2 ** max(0, job.attempts - 1)))
                    job.status = CatalogueJob.Status.RETRY_WAIT
                    job.scheduled_for = check_time + timedelta(seconds=backoff_sec)
                    job.last_error = (
                        f"Lease expired (worker={job.claimed_by_worker_id}, gen={job.claim_generation}); "
                        f"rescheduled for retry {job.attempts}/{job.max_attempts}."
                    )
                else:
                    job.status = CatalogueJob.Status.FAILED_PERMANENT
                    job.last_error = (
                        f"Lease expired (worker={job.claimed_by_worker_id}, gen={job.claim_generation}); "
                        f"max attempts ({job.max_attempts}) exhausted."
                    )

                job.claimed_by_worker_id = None
                job.lease_token = None
                job.lease_expires_at = None
                job.save(
                    update_fields=[
                        "status",
                        "scheduled_for",
                        "claimed_by_worker_id",
                        "lease_token",
                        "lease_expires_at",
                        "last_error",
                        "updated_at",
                    ]
                )
                reclaimed_count += 1

        return reclaimed_count

    @classmethod
    def claim_jobs(
        cls,
        worker_id: str,
        batch_size: int = 10,
        lease_duration_seconds: int = 60,
        now: Optional[datetime] = None,
    ) -> List[CatalogueJob]:
        """
        Atomically claims available jobs using PostgreSQL SELECT FOR UPDATE SKIP LOCKED
        with Quota-Partitioned Fair Scheduling (60% High / 30% Normal / 10% Low)
        and dynamic redistribution of unused quota to prevent starvation.
        All timestamps are derived strictly from database clock.
        """
        check_time = now or cls.get_db_now()
        lease_until = check_time + timedelta(seconds=lease_duration_seconds)

        with transaction.atomic():
            # 1. First reclaim any expired leases under database time
            cls.reclaim_expired_leases(now=check_time, batch_size=batch_size)

            base_qs = CatalogueJob.objects.filter(
                status__in=[CatalogueJob.Status.PENDING, CatalogueJob.Status.RETRY_WAIT],
                scheduled_for__lte=check_time,
            )

            # 2. Quota allocation: 60% High (<=50), 30% Normal (51-150), 10% Low (>150)
            if batch_size >= 10:
                low_quota = max(1, int(batch_size * 0.1))
                normal_target = max(1, int(batch_size * 0.3))
                high_quota = max(1, batch_size - low_quota - normal_target)
            elif batch_size >= 3:
                low_quota = 1
                normal_target = 1
                high_quota = batch_size - 2
            elif batch_size == 2:
                low_quota = 0
                normal_target = 1
                high_quota = 1
            else:  # batch_size == 1
                low_quota = 0
                normal_target = 0
                high_quota = 1

            # Helper for conditional locking query
            def _select_slice(qs_slice, limit):
                if limit <= 0:
                    return []
                ordered = qs_slice.order_by("priority", "scheduled_for")
                if connection.vendor == "postgresql":
                    return list(ordered.select_for_update(skip_locked=True).values_list("id", flat=True)[:limit])
                else:
                    return list(ordered.select_for_update().values_list("id", flat=True)[:limit])

            # High priority claim
            high_ids = _select_slice(base_qs.filter(priority__lte=50), high_quota)

            # Normal priority claim: absorbs unused high quota
            normal_quota = normal_target + (high_quota - len(high_ids))
            normal_ids = _select_slice(base_qs.filter(priority__gt=50, priority__lte=150), normal_quota)

            # Low priority claim: absorbs remaining batch capacity
            remaining_capacity = max(0, batch_size - len(high_ids) - len(normal_ids))
            low_ids = _select_slice(base_qs.filter(priority__gt=150), remaining_capacity)

            # If low doesn't consume all remaining capacity, backfill from remaining pending jobs
            unfilled = remaining_capacity - len(low_ids)
            backfill_ids = []
            if unfilled > 0:
                already_selected = set(high_ids + normal_ids + low_ids)
                backfill_ids = _select_slice(base_qs.exclude(id__in=already_selected), unfilled)

            selected_ids = high_ids + normal_ids + low_ids + backfill_ids
            if not selected_ids:
                return []

            # 3. Apply atomic claim attributes
            token = uuid.uuid4()
            CatalogueJob.objects.filter(id__in=selected_ids).update(
                status=CatalogueJob.Status.IN_PROGRESS,
                claimed_by_worker_id=worker_id,
                lease_token=token,
                claim_generation=models.F("claim_generation") + 1,
                claimed_at=check_time,
                heartbeat_at=check_time,
                lease_expires_at=lease_until,
                attempts=models.F("attempts") + 1,
                updated_at=check_time,
            )

            # Return in-memory refreshed instances with new generation/token
            claimed_jobs = list(CatalogueJob.objects.filter(id__in=selected_ids).order_by("priority", "scheduled_for"))
            return claimed_jobs

    @classmethod
    def renew_lease(
        cls,
        job_id: int,
        worker_id: str,
        lease_token: uuid.UUID,
        generation: int,
        extension_seconds: int = 60,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Renews an active lease during long-running tasks (heartbeat).
        Verifies worker_id, lease_token, generation, in_progress status, and that lease has not already expired.
        Returns True if extended; False if ownership was lost or expired.
        Uses database clock authority.
        """
        check_time = now or cls.get_db_now()
        new_lease_until = check_time + timedelta(seconds=extension_seconds)

        with transaction.atomic():
            rows_updated = CatalogueJob.objects.filter(
                id=job_id,
                claimed_by_worker_id=worker_id,
                lease_token=lease_token,
                claim_generation=generation,
                status=CatalogueJob.Status.IN_PROGRESS,
                lease_expires_at__gte=check_time,
            ).update(
                lease_expires_at=new_lease_until,
                heartbeat_at=check_time,
                updated_at=check_time,
            )
            return rows_updated == 1

    @classmethod
    def complete_job(
        cls,
        job_id: int,
        worker_id: str,
        lease_token: uuid.UUID,
        generation: int,
        result_payload: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> CatalogueJob:
        """
        Atomically marks a job as SUCCEEDED, verifying lease ownership and validity.
        If needs_subsequent_pass is True, resets status to PENDING for an immediate follow-up pass.
        Raises StaleLeaseOwnershipError if lease expired, generation changed, or reclaimed.
        Uses database clock authority.
        """
        check_time = now or cls.get_db_now()

        with transaction.atomic():
            job = (
                CatalogueJob.objects.select_for_update()
                .filter(
                    id=job_id,
                    claimed_by_worker_id=worker_id,
                    lease_token=lease_token,
                    claim_generation=generation,
                    status=CatalogueJob.Status.IN_PROGRESS,
                    lease_expires_at__gte=check_time,
                )
                .first()
            )

            if not job:
                logger.warning(
                    f"Completion rejected for Job {job_id}: worker {worker_id} gen {generation} "
                    f"lost lease ownership or lease expired."
                )
                raise StaleLeaseOwnershipError(
                    f"Cannot complete Job {job_id}: worker {worker_id} (gen={generation}) "
                    f"lost lease ownership or lease expired before completion."
                )

            if result_payload:
                merged = dict(job.payload or {})
                merged.update(result_payload)
                job.payload = merged

            if job.needs_subsequent_pass:
                # Reset to pending for immediate follow-up pass
                job.status = CatalogueJob.Status.PENDING
                job.needs_subsequent_pass = False
                job.claimed_by_worker_id = None
                job.lease_token = None
                job.lease_expires_at = None
                job.scheduled_for = check_time
            else:
                job.status = CatalogueJob.Status.SUCCEEDED
                job.lease_expires_at = None

            job.save()
            return job

    @classmethod
    def fail_job(
        cls,
        job_id: int,
        worker_id: str,
        lease_token: uuid.UUID,
        generation: int,
        error_message: str,
        is_permanent: bool = False,
        now: Optional[datetime] = None,
    ) -> CatalogueJob:
        """
        Atomically transitions a job to RETRY_WAIT with exponential backoff,
        or FAILED_PERMANENT if max_attempts reached or is_permanent is True.
        Raises StaleLeaseOwnershipError if worker no longer owns the active lease.
        Uses database clock authority.
        """
        check_time = now or cls.get_db_now()

        with transaction.atomic():
            job = (
                CatalogueJob.objects.select_for_update()
                .filter(
                    id=job_id,
                    claimed_by_worker_id=worker_id,
                    lease_token=lease_token,
                    claim_generation=generation,
                    status=CatalogueJob.Status.IN_PROGRESS,
                    lease_expires_at__gte=check_time,
                )
                .first()
            )

            if not job:
                logger.warning(
                    f"Failure transition rejected for Job {job_id}: worker {worker_id} gen {generation} "
                    f"lost lease ownership."
                )
                raise StaleLeaseOwnershipError(
                    f"Cannot record failure for Job {job_id}: worker {worker_id} (gen={generation}) "
                    f"lost lease ownership or lease expired."
                )

            job.last_error = error_message[:2000]

            if is_permanent or job.attempts >= job.max_attempts:
                job.status = CatalogueJob.Status.FAILED_PERMANENT
                job.claimed_by_worker_id = None
                job.lease_token = None
                job.lease_expires_at = None
            else:
                backoff_sec = min(300, 10 * (2 ** max(0, job.attempts - 1)))
                job.status = CatalogueJob.Status.RETRY_WAIT
                job.scheduled_for = check_time + timedelta(seconds=backoff_sec)
                job.claimed_by_worker_id = None
                job.lease_token = None
                job.lease_expires_at = None

            job.save()
            return job

    @classmethod
    def release_job(
        cls,
        job_id: int,
        worker_id: str,
        lease_token: uuid.UUID,
        generation: int,
        now: Optional[datetime] = None,
    ) -> bool:
        """
        Cleanly releases an in-flight job back to PENDING during graceful worker shutdown.
        Does not increment attempts or record failure.
        Uses database clock authority.
        """
        check_time = now or cls.get_db_now()
        with transaction.atomic():
            rows_updated = CatalogueJob.objects.filter(
                id=job_id,
                claimed_by_worker_id=worker_id,
                lease_token=lease_token,
                claim_generation=generation,
                status=CatalogueJob.Status.IN_PROGRESS,
            ).update(
                status=CatalogueJob.Status.PENDING,
                claimed_by_worker_id=None,
                lease_token=None,
                lease_expires_at=None,
                updated_at=check_time,
            )
            return rows_updated == 1
