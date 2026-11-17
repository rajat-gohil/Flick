import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import connection, transaction
from django.utils import timezone

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    ProposalOutboxMessage,
    Session,
)
from core.services.manifest import ManifestCompilerService
from core.services.proposals import ProposalService
from core.services.retrieval import CandidateRetrievalService, EligibilityPolicyEngine

logger = logging.getLogger(__name__)


class ProposalExecutionWorker:
    """
    Durable Background Outbox Worker for Constraint Expansion Replenishment.
    
    Guarantees:
    - Zero external network calls inside database transactions (TMDB retrieval executed strictly outside DB locks).
    - Database row locks held for < 10ms for atomic state transitions.
    - Safe concurrency claiming using SKIP LOCKED on PostgreSQL.
    - Worker crash recovery for stale claims exceeding timeout.
    - Exponential backoff and bounded retry limits.
    - Strict non-negotiable hard-constraint guarantee: original constraints maintained if pool < 16.
    """

    def __init__(self, worker_id: Optional[str] = None, claim_timeout_seconds: int = 300):
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.claim_timeout_seconds = claim_timeout_seconds

    def _broadcast_event(self, session_id: int, event_data: Dict[str, Any]) -> None:
        """Best-effort WebSocket broadcast via Channels channel layer."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f"session_{session_id}",
                    event_data
                )
        except Exception as e:
            logger.debug(f"Channels broadcast skipped or failed: {e}")

    def claim_next_message(self) -> Optional[ProposalOutboxMessage]:
        """
        Atomically claims the next pending message whose scheduled_at <= now.
        Uses PostgreSQL SKIP LOCKED for concurrent worker safety.
        """
        now = timezone.now()
        with transaction.atomic():
            qs = ProposalOutboxMessage.objects.filter(
                status=ProposalOutboxMessage.STATUS_PENDING,
                scheduled_at__lte=now,
            ).select_related("proposal", "session")

            if connection.vendor == "postgresql":
                msg = qs.select_for_update(skip_locked=True).first()
            else:
                msg = qs.first()

            if not msg:
                return None

            msg.status = ProposalOutboxMessage.STATUS_PROCESSING
            msg.attempts += 1
            payload = dict(msg.payload or {})
            payload["worker_id"] = self.worker_id
            payload["claimed_at"] = now.isoformat()
            msg.payload = payload
            msg.save(update_fields=["status", "attempts", "payload"])
            return msg

    def recover_stale_claims(self, timeout_seconds: Optional[int] = None) -> int:
        """
        Detects processing messages abandoned due to worker crash or process termination.
        Resets them to PENDING with exponential backoff if attempts < max_attempts,
        or marks them FAILED if retries exhausted.
        """
        timeout = timeout_seconds if timeout_seconds is not None else self.claim_timeout_seconds
        cutoff = timezone.now() - timedelta(seconds=timeout)

        stale_qs = ProposalOutboxMessage.objects.filter(
            status=ProposalOutboxMessage.STATUS_PROCESSING,
        ).select_related("proposal")

        recovered_count = 0
        now = timezone.now()

        for msg in stale_qs:
            payload = msg.payload or {}
            claimed_str = payload.get("claimed_at")
            is_stale = False

            if claimed_str:
                try:
                    claimed_dt = datetime.fromisoformat(claimed_str)
                    if timezone.is_naive(claimed_dt):
                        claimed_dt = timezone.make_aware(claimed_dt)
                    if claimed_dt < cutoff:
                        is_stale = True
                except Exception:
                    is_stale = True
            elif msg.scheduled_at and msg.scheduled_at < cutoff:
                is_stale = True

            if is_stale:
                with transaction.atomic():
                    recovered_count += 1
                    if msg.attempts < msg.max_attempts:
                        msg.status = ProposalOutboxMessage.STATUS_PENDING
                        backoff = min(300, (2 ** msg.attempts) * 5)
                        msg.scheduled_at = now + timedelta(seconds=backoff)
                        msg.error_message = f"Recovered stale claim (attempt {msg.attempts}/{msg.max_attempts})"
                        msg.save(update_fields=["status", "scheduled_at", "error_message"])
                        logger.warning(
                            f"Worker recovered stale outbox message {msg.id}; scheduled retry in {backoff}s."
                        )
                    else:
                        msg.status = ProposalOutboxMessage.STATUS_FAILED
                        msg.error_message = f"Stale claim exceeded max retry attempts ({msg.max_attempts})"
                        msg.processed_at = now
                        msg.save(update_fields=["status", "error_message", "processed_at"])

                        if msg.proposal:
                            msg.proposal.status = ConstraintExpansionProposal.STATUS_REPLENISHMENT_FAILED
                            msg.proposal.error_message = msg.error_message
                            msg.proposal.completed_at = now
                            msg.proposal.save(update_fields=["status", "error_message", "completed_at"])
                        logger.error(f"Outbox message {msg.id} permanently failed after exceeding max attempts.")

        return recovered_count

    def execute_message(self, message: ProposalOutboxMessage) -> bool:
        """
        Executes candidate replenishment for a claimed outbox message.
        
        Execution steps:
        1. Pre-execution 10-minute expiry validation.
        2. Set proposal status to 'replenishment_running'.
        3. TMDB Candidate Retrieval (executed strictly OUTSIDE database transaction).
        4. Final database transaction:
           - If candidates >= 16: apply proposed constraints, compile/append manifest, mark completed.
           - If candidates < 16: maintain original constraints, mark replenishment_insufficient.
        """
        proposal = message.proposal
        session = message.session
        now = timezone.now()

        # Step 1: Pre-execution validation & idempotency checks
        # 1A. Idempotency guard: If proposal is already completed, do not re-process
        if proposal.status == ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED:
            message.status = ProposalOutboxMessage.STATUS_COMPLETED
            message.processed_at = proposal.completed_at or now
            message.error_message = ""
            message.save(update_fields=["status", "processed_at", "error_message"])
            logger.info(
                f"Proposal {proposal.id} is already completed. "
                "Idempotently marked outbox message completed without duplicate effects."
            )
            return True

        # 1B. 10-minute expiry validation
        if proposal.is_expired or proposal.status == ConstraintExpansionProposal.STATUS_EXPIRED:
            proposal.status = ConstraintExpansionProposal.STATUS_EXPIRED
            proposal.save(update_fields=["status"])
            CollaborativeAgreement.objects.filter(session=session, active_proposal=proposal).update(active_proposal=None)

            message.status = ProposalOutboxMessage.STATUS_FAILED
            message.error_message = "Proposal expired before replenishment execution."
            message.processed_at = now
            message.save(update_fields=["status", "error_message", "processed_at"])
            logger.info(f"Skipping expired proposal {proposal.id} in outbox worker.")
            return False

        # 1C. Terminal state guard: declined, superseded, failed, or insufficient
        if proposal.status in (
            ConstraintExpansionProposal.STATUS_DECLINED,
            ConstraintExpansionProposal.STATUS_SUPERSEDED,
            ConstraintExpansionProposal.STATUS_REPLENISHMENT_FAILED,
            ConstraintExpansionProposal.STATUS_REPLENISHMENT_INSUFFICIENT,
        ):
            message.status = ProposalOutboxMessage.STATUS_FAILED
            message.error_message = f"Proposal is in terminal state '{proposal.status}'."
            message.processed_at = now
            message.save(update_fields=["status", "error_message", "processed_at"])
            logger.warning(
                f"Proposal {proposal.id} is in terminal state '{proposal.status}'. Outbox message marked failed."
            )
            return False

        # Step 2: Set status to replenishment_running
        proposal.status = ConstraintExpansionProposal.STATUS_REPLENISHMENT_RUNNING
        proposal.save(update_fields=["status"])

        proposed_constraints = (
            message.payload.get("proposed_constraints")
            or proposal.proposed_constraints
            or {}
        )

        # Step 3: TMDB Candidate Retrieval (STRICTLY OUTSIDE DB TRANSACTIONS)
        try:
            candidate_pool = CandidateRetrievalService.retrieve_candidates(
                session=session,
                experience_type=EligibilityPolicyEngine.EXPERIENCE_SCREENING,
                constraints=proposed_constraints,
                auto_replenish=True,
                max_tmdb_pages=3,
            )
        except Exception as exc:
            logger.exception(f"TMDB retrieval failed during replenishment for session {session.code}: {exc}")
            now = timezone.now()
            if message.attempts < message.max_attempts:
                # Bounded retry with exponential backoff
                backoff = min(300, (2 ** message.attempts) * 5)
                message.status = ProposalOutboxMessage.STATUS_PENDING
                message.scheduled_at = now + timedelta(seconds=backoff)
                message.error_message = f"TMDB retrieval error: {exc}"
                message.save(update_fields=["status", "scheduled_at", "error_message"])
            else:
                # Exhausted retries
                message.status = ProposalOutboxMessage.STATUS_FAILED
                message.error_message = f"Exhausted retries: {exc}"
                message.processed_at = now
                message.save(update_fields=["status", "error_message", "processed_at"])

                proposal.status = ConstraintExpansionProposal.STATUS_REPLENISHMENT_FAILED
                proposal.error_message = str(exc)
                proposal.completed_at = now
                proposal.save(update_fields=["status", "error_message", "completed_at"])
            return False

        # Step 4: Final Database Transaction (Lock CollaborativeAgreement, Proposal & OutboxMessage)
        with transaction.atomic():
            if connection.vendor == "postgresql":
                agreement = CollaborativeAgreement.objects.select_for_update().get(session=session)
                locked_prop = ConstraintExpansionProposal.objects.select_for_update().get(id=proposal.id)
                locked_msg = ProposalOutboxMessage.objects.select_for_update().get(id=message.id)
            else:
                agreement, _ = CollaborativeAgreement.objects.get_or_create(session=session)
                locked_prop = ConstraintExpansionProposal.objects.get(id=proposal.id)
                locked_msg = message

            now = timezone.now()

            # Candidate pool evaluation
            if candidate_pool.total_count >= 16:
                # 4A. Sufficient Candidates: Apply proposed constraints
                for key in (
                    "shared_min_rating",
                    "shared_max_runtime",
                    "shared_eras",
                    "shared_languages",
                ):
                    if key in proposed_constraints:
                        val = proposed_constraints[key]
                        if key == "shared_min_rating" and val is not None:
                            val = Decimal(str(val))
                        setattr(agreement, key, val)

                # Update mutual_hard_exclusions if present
                if "excluded_genre_ids" in proposed_constraints or "required_genre_ids" in proposed_constraints:
                    exclusions = dict(agreement.mutual_hard_exclusions or {})
                    if "excluded_genre_ids" in proposed_constraints:
                        exclusions["excluded_genre_ids"] = proposed_constraints["excluded_genre_ids"]
                    if "required_genre_ids" in proposed_constraints:
                        exclusions["required_genre_ids"] = proposed_constraints["required_genre_ids"]
                    agreement.mutual_hard_exclusions = exclusions

                # Append newly qualified candidates to manifest (immutability preserved)
                ManifestCompilerService.replenish_and_append_manifest(
                    session=session,
                    agreement=agreement,
                    candidate_pool=candidate_pool,
                )

                agreement.active_proposal = None
                agreement.save()

                locked_prop.status = ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED
                locked_prop.completed_at = now
                locked_prop.save(update_fields=["status", "completed_at"])

                locked_msg.status = ProposalOutboxMessage.STATUS_COMPLETED
                locked_msg.processed_at = now
                locked_msg.error_message = ""
                locked_msg.save(update_fields=["status", "processed_at", "error_message"])

                logger.info(
                    f"Proposal {locked_prop.id} successfully completed. Manifest replenished "
                    f"({len(agreement.deck_manifest or [])} cards)."
                )

                self._broadcast_event(session.id, {
                    "type": "proposal_event",
                    "event": "constraints_updated",
                    "session_id": session.id,
                    "proposal_id": str(locked_prop.id),
                    "manifest_count": len(agreement.deck_manifest or []),
                })
                return True
            else:
                # 4B. Pool < 16 candidates: Strict non-negotiable rule: maintain original constraints!
                agreement.active_proposal = None
                agreement.save(update_fields=["active_proposal", "updated_at"])

                err_msg = (
                    f"Insufficient candidates after replenishment: {candidate_pool.total_count} (< 16). "
                    "Original constraints maintained without relaxation."
                )
                locked_prop.status = ConstraintExpansionProposal.STATUS_REPLENISHMENT_INSUFFICIENT
                locked_prop.completed_at = now
                locked_prop.error_message = err_msg
                locked_prop.save(update_fields=["status", "completed_at", "error_message"])

                locked_msg.status = ProposalOutboxMessage.STATUS_FAILED
                locked_msg.processed_at = now
                locked_msg.error_message = err_msg
                locked_msg.save(update_fields=["status", "processed_at", "error_message"])

                logger.warning(
                    f"Proposal {locked_prop.id} replenishment yielded {candidate_pool.total_count} (< 16). "
                    "Constraints unrelaxed."
                )

                self._broadcast_event(session.id, {
                    "type": "proposal_event",
                    "event": "replenishment_exhausted",
                    "session_id": session.id,
                    "proposal_id": str(locked_prop.id),
                    "candidate_count": candidate_pool.total_count,
                })
                return False

    def process_batch(self, max_messages: int = 10) -> Dict[str, int]:
        """
        Runs one cycle of background outbox processing:
        1. Reaps expired proposals.
        2. Recovers stale claims.
        3. Claims and processes up to max_messages.
        """
        reaped = ProposalService.reap_expired_proposals()
        recovered = self.recover_stale_claims()

        processed = 0
        succeeded = 0
        failed = 0

        for _ in range(max_messages):
            msg = self.claim_next_message()
            if not msg:
                break
            processed += 1
            ok = self.execute_message(msg)
            if ok:
                succeeded += 1
            else:
                failed += 1

        return {
            "reaped_expired": reaped,
            "recovered_stale": recovered,
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
        }
