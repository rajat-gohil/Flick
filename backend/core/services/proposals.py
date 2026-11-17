import logging
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple, Union
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.utils import timezone

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    ProposalOutboxMessage,
    Session,
)

logger = logging.getLogger(__name__)
User = get_user_model()

PROPOSAL_EXPIRY_MINUTES = 10


class ProposalError(Exception):
    """Base exception for proposal operations."""
    pass


class ProposalNotFoundError(ProposalError):
    """Raised when a proposal cannot be found."""
    pass


class ProposalPermissionDeniedError(ProposalError):
    """Raised when a user is unauthorized to initiate or decide on a proposal."""
    pass


class ProposalExpiredError(ProposalError):
    """Raised when an operation is attempted on an expired proposal."""
    pass


class ProposalInvalidStateError(ProposalError):
    """Raised when a proposal is not in an acceptable state for an operation."""
    pass


class ProposalSupersededError(ProposalError):
    """Raised when an operation is attempted on a superseded proposal."""
    pass


class ProposalService:
    """
    Core service for managing the lifecycle of ConstraintExpansionProposal records.
    
    Guarantees:
    - Explicit, attributable participant consent tracking (never inferred from initiation or silence).
    - 10-minute authoritative expiry (lazy evaluation + periodic reaper).
    - Proposal supersession: newer proposals supersede older pending proposals.
    - Transactional outbox creation upon mutual approval.
    """

    @classmethod
    def get_session_membership(cls, session: Session, user: Any) -> Optional[str]:
        """
        Returns 'host' if user is session host, 'guest' if user is session guest, else None.
        """
        if session.host_id and session.host_id == user.id:
            return "host"
        if session.guest_id and session.guest_id == user.id:
            return "guest"
        return None

    @classmethod
    def create_proposal(
        cls,
        session: Session,
        user: Any,
        proposed_constraints: Optional[Dict[str, Any]] = None,
        auto_approve: bool = False,
    ) -> ConstraintExpansionProposal:
        """
        Initiates a formal constraint expansion proposal.
        
        Rules:
        - User must be the host or guest of the session.
        - Session must be active (ended_at is None).
        - Any existing pending proposals for the session are superseded.
        - Attributable consent: if auto_approve is False, initiator's decision starts pending;
          if auto_approve is True, initiator's decision is explicitly recorded with timestamp.
        """
        role = cls.get_session_membership(session, user)
        if not role:
            raise ProposalPermissionDeniedError("You are not an authorized participant in this session.")

        if session.ended_at:
            raise ProposalInvalidStateError("Cannot initiate proposal for an ended session.")

        # Resolve CollaborativeAgreement
        agreement, _ = CollaborativeAgreement.objects.get_or_create(session=session)

        # Snapshot original constraints
        exclusions = agreement.mutual_hard_exclusions or {}
        original_constraints = {
            "shared_min_rating": str(agreement.shared_min_rating) if agreement.shared_min_rating is not None else None,
            "shared_max_runtime": agreement.shared_max_runtime,
            "shared_eras": list(agreement.shared_eras or []),
            "shared_languages": list(agreement.shared_languages or []),
            "excluded_genre_ids": list(exclusions.get("excluded_genre_ids", [])),
            "required_genre_ids": list(exclusions.get("required_genre_ids", [])),
        }

        # If proposed constraints not provided, generate intelligent defaults
        if not proposed_constraints:
            proposed = dict(original_constraints)
            if agreement.shared_min_rating is not None:
                # Relax rating by 0.5 (floor at 6.0)
                relaxed_r = max(6.0, float(agreement.shared_min_rating) - 0.5)
                proposed["shared_min_rating"] = f"{relaxed_r:.2f}"
            if agreement.shared_max_runtime is not None:
                # Expand runtime by 20 minutes
                proposed["shared_max_runtime"] = agreement.shared_max_runtime + 20
            proposed_constraints = proposed

        now = timezone.now()
        now_iso = now.isoformat()
        expires_at = now + timedelta(minutes=PROPOSAL_EXPIRY_MINUTES)

        # Attributable consent tracking: explicit record
        host_decision = {"decision": "pending", "decided_at": None}
        guest_decision = {"decision": "pending", "decided_at": None}

        if auto_approve:
            if role == "host":
                host_decision = {"decision": "approve", "decided_at": now_iso}
            elif role == "guest":
                guest_decision = {"decision": "approve", "decided_at": now_iso}

        with transaction.atomic():
            # Supersede any existing pending proposals for this session (Specification L6)
            ConstraintExpansionProposal.objects.filter(
                session=session,
                status=ConstraintExpansionProposal.STATUS_PENDING,
            ).update(status=ConstraintExpansionProposal.STATUS_SUPERSEDED)

            proposal = ConstraintExpansionProposal.objects.create(
                session=session,
                initiated_by_user=user,
                status=ConstraintExpansionProposal.STATUS_PENDING,
                original_constraints=original_constraints,
                proposed_constraints=proposed_constraints,
                host_decision=host_decision,
                guest_decision=guest_decision,
                expires_at=expires_at,
            )

            agreement.active_proposal = proposal
            agreement.save(update_fields=["active_proposal", "updated_at"])

        logger.info(
            f"Created constraint expansion proposal {proposal.id} for session {session.code} by {user.username} "
            f"(auto_approve={auto_approve})"
        )
        return proposal

    @classmethod
    def record_decision(
        cls,
        session: Session,
        user: Any,
        proposal_id: Union[str, UUID],
        decision: str,
    ) -> Tuple[ConstraintExpansionProposal, bool]:
        """
        Records an explicit, attributable approval or decline from a participant.
        
        Returns:
            Tuple[ConstraintExpansionProposal, bool]: (proposal, is_queued_for_replenishment)
        
        Guarantees:
        - 10-minute expiry strictly enforced (raises ProposalExpiredError -> 409).
        - Superseded proposals strictly rejected (raises ProposalSupersededError -> 409).
        - Mutual approval transitions status to 'approved_queued' and creates a ProposalOutboxMessage
          inside the same database transaction.
        """
        role = cls.get_session_membership(session, user)
        if not role:
            raise ProposalPermissionDeniedError("You are not an authorized participant in this session.")

        if decision not in ("approve", "decline"):
            raise ValueError(f"Invalid decision '{decision}'. Must be 'approve' or 'decline'.")

        try:
            proposal = ConstraintExpansionProposal.objects.get(id=proposal_id, session=session)
        except ConstraintExpansionProposal.DoesNotExist:
            raise ProposalNotFoundError(f"Proposal {proposal_id} does not exist for session {session.code}.")

        # 1. Authoritative Lazy Expiry Validation (Specification L4)
        if proposal.is_expired or proposal.status == ConstraintExpansionProposal.STATUS_EXPIRED:
            if proposal.status != ConstraintExpansionProposal.STATUS_EXPIRED:
                proposal.status = ConstraintExpansionProposal.STATUS_EXPIRED
                proposal.save(update_fields=["status"])
                CollaborativeAgreement.objects.filter(session=session, active_proposal=proposal).update(active_proposal=None)
            raise ProposalExpiredError("Proposal has expired. 10-minute decision window exceeded.")

        # 2. Superseded proposal check (Specification L7)
        if proposal.status == ConstraintExpansionProposal.STATUS_SUPERSEDED:
            raise ProposalSupersededError("Proposal has been superseded by a newer proposal.")

        # 3. Valid pending status check
        if proposal.status != ConstraintExpansionProposal.STATUS_PENDING:
            raise ProposalInvalidStateError(
                f"Proposal is in '{proposal.status}' state and can no longer accept decisions."
            )

        now = timezone.now()
        now_iso = now.isoformat()

        # Database mutation under atomic transaction
        with transaction.atomic():
            if connection.vendor == "postgresql":
                locked_proposal = ConstraintExpansionProposal.objects.select_for_update().get(id=proposal.id)
            else:
                locked_proposal = ConstraintExpansionProposal.objects.get(id=proposal.id)

            # Re-check expiry and status under lock
            if locked_proposal.is_expired or locked_proposal.status == ConstraintExpansionProposal.STATUS_EXPIRED:
                locked_proposal.status = ConstraintExpansionProposal.STATUS_EXPIRED
                locked_proposal.save(update_fields=["status"])
                CollaborativeAgreement.objects.filter(session=session, active_proposal=locked_proposal).update(active_proposal=None)
                raise ProposalExpiredError("Proposal has expired under concurrent evaluation.")

            if locked_proposal.status != ConstraintExpansionProposal.STATUS_PENDING:
                raise ProposalInvalidStateError(
                    f"Proposal changed to '{locked_proposal.status}' state concurrently."
                )

            # Record attributable participant decision
            if role == "host":
                locked_proposal.host_decision = {"decision": decision, "decided_at": now_iso}
            elif role == "guest":
                locked_proposal.guest_decision = {"decision": decision, "decided_at": now_iso}

            # If declined by either participant
            if decision == "decline":
                locked_proposal.status = ConstraintExpansionProposal.STATUS_DECLINED
                locked_proposal.completed_at = now
                locked_proposal.save(update_fields=["host_decision", "guest_decision", "status", "completed_at"])
                CollaborativeAgreement.objects.filter(session=session, active_proposal=locked_proposal).update(active_proposal=None)
                logger.info(f"Proposal {locked_proposal.id} declined by {role} ({user.username}).")
                return locked_proposal, False

            # If approved, check if both participants have approved (Specification L3)
            h_approved = (
                locked_proposal.host_decision
                and locked_proposal.host_decision.get("decision") == "approve"
            )
            g_approved = (
                locked_proposal.guest_decision
                and locked_proposal.guest_decision.get("decision") == "approve"
            )

            if h_approved and g_approved:
                locked_proposal.status = ConstraintExpansionProposal.STATUS_APPROVED_QUEUED
                locked_proposal.save(update_fields=["host_decision", "guest_decision", "status"])

                # Create outbox message transactionally in the same DB transaction!
                ProposalOutboxMessage.objects.create(
                    proposal=locked_proposal,
                    session=session,
                    topic="proposal.replenishment",
                    payload={
                        "proposal_id": str(locked_proposal.id),
                        "session_id": session.id,
                        "proposed_constraints": locked_proposal.proposed_constraints,
                        "approved_at": now_iso,
                    },
                    status=ProposalOutboxMessage.STATUS_PENDING,
                    scheduled_at=now,
                )
                logger.info(
                    f"Proposal {locked_proposal.id} mutually approved! Dispatched ProposalOutboxMessage."
                )
                return locked_proposal, True
            else:
                locked_proposal.save(update_fields=["host_decision", "guest_decision"])
                logger.info(
                    f"Proposal {locked_proposal.id} approval recorded from {role} ({user.username}). Awaiting partner."
                )
                return locked_proposal, False

    @classmethod
    def reap_expired_proposals(cls) -> int:
        """
        Background periodic reaper to transition abandoned pending proposals past their
        10-minute expiry window to 'expired' status.
        """
        now = timezone.now()
        expired_qs = ConstraintExpansionProposal.objects.filter(
            status=ConstraintExpansionProposal.STATUS_PENDING,
            expires_at__lte=now,
        )
        reaped_count = 0
        for proposal in expired_qs:
            with transaction.atomic():
                proposal.status = ConstraintExpansionProposal.STATUS_EXPIRED
                proposal.save(update_fields=["status"])
                CollaborativeAgreement.objects.filter(session=proposal.session, active_proposal=proposal).update(active_proposal=None)
                reaped_count += 1

        if reaped_count > 0:
            logger.info(f"Reaped {reaped_count} expired constraint expansion proposals.")
        return reaped_count
