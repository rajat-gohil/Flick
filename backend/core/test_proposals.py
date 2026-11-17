import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    Genre,
    Movie,
    ProposalOutboxMessage,
    Session,
)
from core.services.outbox import ProposalExecutionWorker
from core.services.proposals import (
    ProposalError,
    ProposalExpiredError,
    ProposalInvalidStateError,
    ProposalNotFoundError,
    ProposalPermissionDeniedError,
    ProposalService,
    ProposalSupersededError,
)
from core.services.retrieval import CandidatePool, HardConstraints

User = get_user_model()


class ProposalServiceTestCase(TestCase):
    """
    Unit and integration tests for ProposalService lifecycle and consent tracking.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")
        self.stranger = User.objects.create_user(username="stranger_user", password="password123")

        self.session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="PROP01",
        )

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_min_rating=Decimal("8.00"),
            shared_max_runtime=110,
            shared_eras=["modern"],
            shared_languages=["en"],
            mutual_hard_exclusions={
                "excluded_genre_ids": [27],
                "required_genre_ids": [28, 12],
            },
        )

    def test_proposal_creation_with_snapshots_spec_l1(self):
        """Specification L1: Proposal creation with snapshots of original and proposed constraints."""
        proposed = {
            "shared_min_rating": "7.50",
            "shared_max_runtime": 130,
        }

        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints=proposed,
            auto_approve=False,
        )

        self.assertIsNotNone(proposal.id)
        self.assertEqual(proposal.session, self.session)
        self.assertEqual(proposal.initiated_by_user, self.host)
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_PENDING)

        # Snapshot assertions
        self.assertEqual(proposal.original_constraints["shared_min_rating"], "8.00")
        self.assertEqual(proposal.original_constraints["shared_max_runtime"], 110)
        self.assertEqual(proposal.original_constraints["shared_eras"], ["modern"])
        self.assertEqual(proposal.proposed_constraints["shared_min_rating"], "7.50")
        self.assertEqual(proposal.proposed_constraints["shared_max_runtime"], 130)

        # Consent tracking: Both decisions start pending when auto_approve=False
        self.assertEqual(proposal.host_decision["decision"], "pending")
        self.assertIsNone(proposal.host_decision["decided_at"])
        self.assertEqual(proposal.guest_decision["decision"], "pending")

        # 10-minute validity
        self.assertFalse(proposal.is_expired)
        self.assertGreater(proposal.expires_at, timezone.now() + timedelta(minutes=9))

        # Attached to agreement
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.active_proposal, proposal)

    def test_single_approval_leaves_status_pending_spec_l2(self):
        """Specification L2: Single approval leaves status pending; consent is explicit and attributable."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=False,
        )

        updated_proposal, is_queued = ProposalService.record_decision(
            session=self.session,
            user=self.host,
            proposal_id=proposal.id,
            decision="approve",
        )

        self.assertFalse(is_queued)
        self.assertEqual(updated_proposal.status, ConstraintExpansionProposal.STATUS_PENDING)
        self.assertEqual(updated_proposal.host_decision["decision"], "approve")
        self.assertIsNotNone(updated_proposal.host_decision["decided_at"])
        self.assertEqual(updated_proposal.guest_decision["decision"], "pending")

        # Outbox message NOT yet created
        self.assertFalse(ProposalOutboxMessage.objects.filter(proposal=proposal).exists())

    def test_dual_approval_transitions_to_approved_queued_spec_l3(self):
        """Specification L3: Dual approval transitions to approved_queued and creates outbox message."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,  # Host explicitly approves upon creation
        )

        self.assertEqual(proposal.host_decision["decision"], "approve")
        self.assertEqual(proposal.guest_decision["decision"], "pending")

        # Guest approves
        updated_proposal, is_queued = ProposalService.record_decision(
            session=self.session,
            user=self.guest,
            proposal_id=proposal.id,
            decision="approve",
        )

        self.assertTrue(is_queued)
        self.assertEqual(updated_proposal.status, ConstraintExpansionProposal.STATUS_APPROVED_QUEUED)
        self.assertEqual(updated_proposal.guest_decision["decision"], "approve")
        self.assertIsNotNone(updated_proposal.guest_decision["decided_at"])
        self.assertTrue(updated_proposal.is_mutually_approved)

        # Durable Outbox Message created transactionally
        outbox_msg = ProposalOutboxMessage.objects.filter(proposal=proposal).first()
        self.assertIsNotNone(outbox_msg)
        self.assertEqual(outbox_msg.session, self.session)
        self.assertEqual(outbox_msg.status, ProposalOutboxMessage.STATUS_PENDING)
        self.assertEqual(outbox_msg.topic, "proposal.replenishment")
        self.assertEqual(outbox_msg.payload["proposal_id"], str(proposal.id))
        self.assertEqual(outbox_msg.payload["proposed_constraints"], {"shared_min_rating": "7.00"})

    def test_decline_by_either_participant_marks_declined(self):
        """Either participant declining immediately transitions status to declined."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )

        updated_proposal, is_queued = ProposalService.record_decision(
            session=self.session,
            user=self.guest,
            proposal_id=proposal.id,
            decision="decline",
        )

        self.assertFalse(is_queued)
        self.assertEqual(updated_proposal.status, ConstraintExpansionProposal.STATUS_DECLINED)
        self.assertEqual(updated_proposal.guest_decision["decision"], "decline")
        self.assertIsNotNone(updated_proposal.completed_at)

        # Active proposal cleared from agreement
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.active_proposal)

        # Outbox message never created
        self.assertFalse(ProposalOutboxMessage.objects.filter(proposal=proposal).exists())

    def test_ten_minute_lazy_expiry_spec_l4(self):
        """Specification L4: 10-Minute Lazy Expiry Enforcement."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )

        # Simulate 11 minutes elapsed
        proposal.expires_at = timezone.now() - timedelta(minutes=1)
        proposal.save(update_fields=["expires_at"])

        with self.assertRaises(ProposalExpiredError):
            ProposalService.record_decision(
                session=self.session,
                user=self.guest,
                proposal_id=proposal.id,
                decision="approve",
            )

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_EXPIRED)

    def test_periodic_reaper(self):
        """Periodic reaper transitions abandoned expired pending proposals."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=False,
        )
        proposal.expires_at = timezone.now() - timedelta(seconds=10)
        proposal.save(update_fields=["expires_at"])

        reaped = ProposalService.reap_expired_proposals()
        self.assertEqual(reaped, 1)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_EXPIRED)

    def test_proposal_supersession_spec_l6_and_l7(self):
        """Specification L6 & L7: Proposal supersession and stale approval rejection."""
        # Proposal A
        prop_a = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.50"},
            auto_approve=False,
        )

        # Proposal B initiated while Proposal A pending
        prop_b = ProposalService.create_proposal(
            session=self.session,
            user=self.guest,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=False,
        )

        prop_a.refresh_from_db()
        prop_b.refresh_from_db()
        self.assertEqual(prop_a.status, ConstraintExpansionProposal.STATUS_SUPERSEDED)
        self.assertEqual(prop_b.status, ConstraintExpansionProposal.STATUS_PENDING)

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.active_proposal, prop_b)

        # Stale approval on superseded proposal A rejected with ProposalSupersededError
        with self.assertRaises(ProposalSupersededError):
            ProposalService.record_decision(
                session=self.session,
                user=self.guest,
                proposal_id=prop_a.id,
                decision="approve",
            )

    def test_unauthorized_user_blocked(self):
        """Unauthorized non-member rejected with ProposalPermissionDeniedError."""
        with self.assertRaises(ProposalPermissionDeniedError):
            ProposalService.create_proposal(
                session=self.session,
                user=self.stranger,
                proposed_constraints={"shared_min_rating": "7.00"},
            )


class ProposalOutboxWorkerTestCase(TestCase):
    """
    Unit and integration tests for ProposalExecutionWorker outbox processing,
    stale claim recovery, and candidate replenishment.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="worker_host", password="password123")
        self.guest = User.objects.create_user(username="worker_guest", password="password123")

        self.session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="WORK01",
        )

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_min_rating=Decimal("8.00"),
            shared_max_runtime=100,
            shared_eras=["modern"],
            deck_manifest=[
                {"card_index": 0, "movie_id": 999, "tmdb_id": 999, "title": "Served Movie", "slot_type": "consensus", "turn": "joint"}
            ],
            host_card_index=1,
            guest_card_index=1,
            resolved_card_index=1,
        )

        self.proposal = ConstraintExpansionProposal.objects.create(
            session=self.session,
            initiated_by_user=self.host,
            status=ConstraintExpansionProposal.STATUS_APPROVED_QUEUED,
            original_constraints={"shared_min_rating": "8.00", "shared_max_runtime": 100},
            proposed_constraints={"shared_min_rating": "7.00", "shared_max_runtime": 130},
            host_decision={"decision": "approve", "decided_at": timezone.now().isoformat()},
            guest_decision={"decision": "approve", "decided_at": timezone.now().isoformat()},
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        self.agreement.active_proposal = self.proposal
        self.agreement.save()

        self.outbox_msg = ProposalOutboxMessage.objects.create(
            proposal=self.proposal,
            session=self.session,
            topic="proposal.replenishment",
            payload={
                "proposal_id": str(self.proposal.id),
                "session_id": self.session.id,
                "proposed_constraints": self.proposal.proposed_constraints,
            },
            status=ProposalOutboxMessage.STATUS_PENDING,
            scheduled_at=timezone.now(),
        )

    def _create_mock_candidates(self, count):
        movies = []
        for i in range(1, count + 1):
            m, _ = Movie.objects.get_or_create(
                tmdb_id=1000 + i,
                defaults={
                    "title": f"Candidate Movie {i}",
                    "rating": 7.5,
                    "release_date": "2020-01-01",
                    "vote_count": 500,
                }
            )
            movies.append(m)
        return movies

    @patch("core.services.retrieval.CandidateRetrievalService.retrieve_candidates")
    def test_worker_replenishment_success_with_sufficient_candidates(self, mock_retrieve):
        """Worker successfully replenishes manifest and updates constraints when candidates >= 16."""
        candidates = self._create_mock_candidates(25)
        mock_retrieve.return_value = CandidatePool(
            pool_type="boutique",
            candidates=candidates,
            total_count=25,
            local_count=10,
            replenished_count=15,
            hard_constraints=HardConstraints(min_rating=7.0, max_runtime=130),
            experience_type="screening",
        )

        worker = ProposalExecutionWorker(worker_id="test-worker-1")
        claimed = worker.claim_next_message()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, self.outbox_msg.id)
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_PROCESSING)
        self.assertEqual(claimed.attempts, 1)
        self.assertEqual(claimed.payload["worker_id"], "test-worker-1")

        success = worker.execute_message(claimed)
        self.assertTrue(success)

        # Refresh objects
        claimed.refresh_from_db()
        self.proposal.refresh_from_db()
        self.agreement.refresh_from_db()

        # Proposal and Outbox completed
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_COMPLETED)
        self.assertIsNotNone(claimed.processed_at)
        self.assertEqual(self.proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED)
        self.assertIsNotNone(self.proposal.completed_at)

        # Proposed constraints applied to CollaborativeAgreement
        self.assertEqual(self.agreement.shared_min_rating, Decimal("7.00"))
        self.assertEqual(self.agreement.shared_max_runtime, 130)
        self.assertIsNone(self.agreement.active_proposal)

        # Immutability preserved: first card (index 0) remains unchanged
        self.assertEqual(self.agreement.deck_manifest[0]["movie_id"], 999)
        # New cards appended
        self.assertGreater(len(self.agreement.deck_manifest), 1)

    @patch("core.services.retrieval.CandidateRetrievalService.retrieve_candidates")
    def test_candidate_shortage_preserves_original_constraints(self, mock_retrieve):
        """Candidate shortage (< 16): Original constraints strictly maintained without relaxation."""
        candidates = self._create_mock_candidates(8)
        mock_retrieve.return_value = CandidatePool(
            pool_type="exhausted",
            candidates=candidates,
            total_count=8,
            local_count=4,
            replenished_count=4,
            hard_constraints=HardConstraints(min_rating=7.0, max_runtime=130),
            experience_type="screening",
        )

        worker = ProposalExecutionWorker(worker_id="test-worker-2")
        claimed = worker.claim_next_message()
        success = worker.execute_message(claimed)

        self.assertFalse(success)

        claimed.refresh_from_db()
        self.proposal.refresh_from_db()
        self.agreement.refresh_from_db()

        # Proposal status is replenishment_insufficient
        self.assertEqual(self.proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_INSUFFICIENT)
        self.assertIn("Insufficient candidates", self.proposal.error_message)

        # Outbox message failed
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_FAILED)

        # STRICT NON-NEGOTIABLE GUARANTEE: Original constraints maintained!
        self.assertEqual(self.agreement.shared_min_rating, Decimal("8.00"))
        self.assertEqual(self.agreement.shared_max_runtime, 100)
        self.assertEqual(self.agreement.shared_eras, ["modern"])

    def test_worker_pre_execution_expired_proposal_handling(self):
        """Worker rejects expired proposal before calling retrieval."""
        self.proposal.expires_at = timezone.now() - timedelta(minutes=1)
        self.proposal.save(update_fields=["expires_at"])

        worker = ProposalExecutionWorker()
        claimed = worker.claim_next_message()
        success = worker.execute_message(claimed)

        self.assertFalse(success)

        claimed.refresh_from_db()
        self.proposal.refresh_from_db()

        self.assertEqual(self.proposal.status, ConstraintExpansionProposal.STATUS_EXPIRED)
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_FAILED)
        self.assertIn("Proposal expired", claimed.error_message)

    def test_stale_claim_recovery(self):
        """Stale processing claims exceeding timeout are reset to pending with backoff."""
        # Message stuck in processing
        self.outbox_msg.status = ProposalOutboxMessage.STATUS_PROCESSING
        self.outbox_msg.attempts = 1
        self.outbox_msg.payload = {
            "worker_id": "crashed-worker",
            "claimed_at": (timezone.now() - timedelta(seconds=400)).isoformat(),
        }
        self.outbox_msg.save()

        worker = ProposalExecutionWorker(claim_timeout_seconds=300)
        recovered = worker.recover_stale_claims()

        self.assertEqual(recovered, 1)

        self.outbox_msg.refresh_from_db()
        self.assertEqual(self.outbox_msg.status, ProposalOutboxMessage.STATUS_PENDING)
        self.assertGreater(self.outbox_msg.scheduled_at, timezone.now())
        self.assertIn("Recovered stale claim", self.outbox_msg.error_message)

    def test_stale_claim_exceeding_max_attempts_permanently_fails(self):
        """Stale claim exceeding max_attempts is permanently marked failed."""
        self.outbox_msg.status = ProposalOutboxMessage.STATUS_PROCESSING
        self.outbox_msg.attempts = 3
        self.outbox_msg.max_attempts = 3
        self.outbox_msg.payload = {
            "worker_id": "crashed-worker",
            "claimed_at": (timezone.now() - timedelta(seconds=400)).isoformat(),
        }
        self.outbox_msg.save()

        worker = ProposalExecutionWorker(claim_timeout_seconds=300)
        recovered = worker.recover_stale_claims()

        self.assertEqual(recovered, 1)

        self.outbox_msg.refresh_from_db()
        self.proposal.refresh_from_db()

        self.assertEqual(self.outbox_msg.status, ProposalOutboxMessage.STATUS_FAILED)
        self.assertEqual(self.proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_FAILED)


class ProposalAPITestCase(TestCase):
    """
    Integration tests for Proposal REST API endpoints.
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="api_host", password="password123")
        self.guest = User.objects.create_user(username="api_guest", password="password123")
        self.stranger = User.objects.create_user(username="api_stranger", password="password123")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="API001",
        )

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_min_rating=Decimal("8.50"),
            shared_max_runtime=105,
        )

    def test_unified_expand_constraints_propose_and_respond(self):
        """Unified endpoint: POST /api/sessions/<id>/expand-constraints/"""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        # 1. Host proposes
        propose_resp = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {
                "action": "propose",
                "proposed_constraints": {
                    "shared_min_rating": "7.50",
                    "shared_max_runtime": 125,
                },
                "auto_approve": True,
            },
            format="json",
        )
        self.assertEqual(propose_resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(propose_resp.data["success"])
        proposal_id = propose_resp.data["proposal_id"]
        self.assertEqual(propose_resp.data["status"], "pending")

        # 2. GET endpoint returns active proposal
        get_resp = self.client.get(f"/api/sessions/{self.session.id}/expand-constraints/")
        self.assertEqual(get_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(get_resp.data["active_proposal"]["id"], proposal_id)

        # 3. Guest responds with approval
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        respond_resp = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {
                "action": "respond",
                "proposal_id": proposal_id,
                "decision": "approve",
            },
            format="json",
        )
        self.assertEqual(respond_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(respond_resp.data["status"], "approved_queued")

    def test_restful_proposal_approve_and_reject_shortcuts(self):
        """RESTful endpoints: approve and reject shortcuts."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        create_resp = self.client.post(
            f"/api/sessions/{self.session.id}/proposals/",
            {
                "proposed_constraints": {"shared_min_rating": "7.00"},
                "auto_approve": False,
            },
            format="json",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        proposal_id = create_resp.data["proposal"]["id"]

        # Host approves via /approve/
        approve_resp = self.client.post(
            f"/api/sessions/{self.session.id}/proposals/{proposal_id}/approve/",
            {},
            format="json",
        )
        self.assertEqual(approve_resp.status_code, status.HTTP_200_OK)
        self.assertFalse(approve_resp.data["is_queued"])

        # Guest rejects via /reject/
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        reject_resp = self.client.post(
            f"/api/sessions/{self.session.id}/proposals/{proposal_id}/reject/",
            {},
            format="json",
        )
        self.assertEqual(reject_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(reject_resp.data["proposal"]["status"], "declined")

    def test_api_rejection_of_expired_proposal(self):
        """API returns 409 Conflict when decision submitted for expired proposal."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )
        proposal.expires_at = timezone.now() - timedelta(minutes=1)
        proposal.save(update_fields=["expires_at"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        resp = self.client.post(
            f"/api/sessions/{self.session.id}/proposals/{proposal.id}/decide/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(resp.data["status"], "expired")

    def test_management_command_process_proposal_outbox(self):
        """Django management command executes batch cleanly without errors."""
        call_command("process_proposal_outbox", max_messages=5, timeout=300)

    def test_administrative_worker_endpoint_authorization(self):
        """Ordinary participants cannot invoke administrative worker processing (403 Forbidden)."""
        # 1. Host (ordinary participant) cannot invoke
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        resp = self.client.post(f"/api/sessions/{self.session.id}/proposals/process-outbox/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # 2. Guest (ordinary participant) cannot invoke
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        resp = self.client.post(f"/api/sessions/{self.session.id}/proposals/process-outbox/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Stranger cannot invoke
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        resp = self.client.post(f"/api/sessions/{self.session.id}/proposals/process-outbox/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # 4. Staff/Admin user CAN invoke
        admin_user = User.objects.create_user(username="admin_user", password="password123", is_staff=True)
        admin_token = Token.objects.create(user=admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {admin_token.key}")
        resp = self.client.post(f"/api/sessions/{self.session.id}/proposals/process-outbox/", {}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])

    def test_stranger_cannot_propose_or_decide(self):
        """Stranger (non-session participant) cannot propose or decide on proposals."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")

        # Propose attempt
        resp = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {"action": "propose", "proposed_constraints": {"shared_min_rating": "7.00"}},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        # Decide attempt on valid proposal
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )
        resp = self.client.post(
            f"/api/sessions/{self.session.id}/proposals/{proposal.id}/decide/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_cross_session_proposal_id_isolation(self):
        """Proposal IDs cannot be accessed or manipulated across unrelated sessions."""
        session_two = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="SESS02",
        )
        CollaborativeAgreement.objects.create(session=session_two)

        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )

        # Attempt to decide proposal from session_one using session_two URL
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        resp = self.client.post(
            f"/api/sessions/{session_two.id}/proposals/{proposal.id}/decide/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


class ProposalLifecycleAndIdempotencyTestCase(TestCase):
    """
    Exhaustive tests for outbox idempotency, crash recovery, atomic completion,
    and terminal lifecycle consistency.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="life_host", password="password123")
        self.guest = User.objects.create_user(username="life_guest", password="password123")

        self.session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="LIFE01",
        )

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_min_rating=Decimal("8.00"),
            shared_max_runtime=100,
            shared_eras=["modern"],
            deck_manifest=[
                {"card_index": 0, "movie_id": 888, "tmdb_id": 888, "title": "Card 0", "slot_type": "consensus", "turn": "joint"}
            ],
            host_card_index=1,
            guest_card_index=1,
            resolved_card_index=1,
        )

    def _create_candidates(self, count, start_id=2000):
        candidates = []
        for i in range(count):
            m, _ = Movie.objects.get_or_create(
                tmdb_id=start_id + i,
                defaults={
                    "title": f"Candidate Film {i}",
                    "rating": 7.8,
                    "release_date": "2021-05-01",
                    "vote_count": 250,
                }
            )
            candidates.append(m)
        return candidates

    @patch("core.services.retrieval.CandidateRetrievalService.retrieve_candidates")
    def test_outbox_idempotency_and_crash_recovery_prevents_duplicate_effects(self, mock_retrieve):
        """
        Simulate crash recovery failure sequence:
        1. An outbox message is claimed.
        2. TMDB replenishment succeeds.
        3. The manifest append succeeds.
        4. The worker crashes before marking the message completed.
        5. The message is recovered and processed again.
        Verify that retry cannot duplicate manifest cards, candidate records, or constraint changes.
        """
        candidates = self._create_candidates(25, start_id=3000)
        mock_retrieve.return_value = CandidatePool(
            pool_type="boutique",
            candidates=candidates,
            total_count=25,
            local_count=10,
            replenished_count=15,
            hard_constraints=HardConstraints(min_rating=7.0, max_runtime=120),
            experience_type="screening",
        )

        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00", "shared_max_runtime": 120},
            auto_approve=True,
        )
        ProposalService.record_decision(
            session=self.session,
            user=self.guest,
            proposal_id=proposal.id,
            decision="approve",
        )
        outbox_msg = ProposalOutboxMessage.objects.get(proposal=proposal)

        # Worker 1 claims message and executes
        worker1 = ProposalExecutionWorker(worker_id="crashed-worker-1")
        claimed = worker1.claim_next_message()
        self.assertEqual(claimed.id, outbox_msg.id)

        # Worker 1 successfully finishes execution
        worker1.execute_message(claimed)

        self.agreement.refresh_from_db()
        manifest_len_after_run1 = len(self.agreement.deck_manifest)
        self.assertEqual(self.agreement.shared_min_rating, Decimal("7.00"))
        movie_ids_run1 = [c["movie_id"] for c in self.agreement.deck_manifest]
        self.assertEqual(len(movie_ids_run1), len(set(movie_ids_run1)), "Zero duplicates in run 1")

        # SIMULATE CRASH: Outbox message was somehow left or reset to PROCESSING due to crash right after commit
        outbox_msg.refresh_from_db()
        outbox_msg.status = ProposalOutboxMessage.STATUS_PROCESSING
        outbox_msg.payload["claimed_at"] = (timezone.now() - timedelta(seconds=400)).isoformat()
        outbox_msg.save()

        # Step 4: Worker 2 recovers stale claim
        worker2 = ProposalExecutionWorker(worker_id="recovering-worker-2", claim_timeout_seconds=300)
        recovered = worker2.recover_stale_claims()
        self.assertEqual(recovered, 1)

        outbox_msg.refresh_from_db()
        self.assertEqual(outbox_msg.status, ProposalOutboxMessage.STATUS_PENDING)
        self.assertGreater(outbox_msg.scheduled_at, timezone.now(), "Exponential backoff set scheduled_at in future")

        # Advance scheduled_at to simulate backoff window elapsed
        outbox_msg.scheduled_at = timezone.now() - timedelta(seconds=1)
        outbox_msg.save(update_fields=["scheduled_at"])

        # Step 5: Worker 2 claims and executes retry
        claimed2 = worker2.claim_next_message()
        self.assertIsNotNone(claimed2)
        self.assertEqual(claimed2.id, outbox_msg.id)

        success2 = worker2.execute_message(claimed2)
        self.assertTrue(success2)

        # VERIFICATIONS:
        self.agreement.refresh_from_db()
        claimed2.refresh_from_db()
        proposal.refresh_from_db()

        # 1. No duplicate manifest cards
        manifest_len_after_run2 = len(self.agreement.deck_manifest)
        self.assertEqual(manifest_len_after_run1, manifest_len_after_run2)
        movie_ids_run2 = [c["movie_id"] for c in self.agreement.deck_manifest]
        self.assertEqual(len(movie_ids_run2), len(set(movie_ids_run2)), "Zero duplicate movie cards after retry")

        # 2. No duplicated candidate records in Movie table
        tmdb_ids = [m.tmdb_id for m in Movie.objects.filter(tmdb_id__gte=3000, tmdb_id__lt=3025)]
        self.assertEqual(len(tmdb_ids), 25)

        # 3. Constraints match proposed exactly
        self.assertEqual(self.agreement.shared_min_rating, Decimal("7.00"))
        self.assertEqual(self.agreement.shared_max_runtime, 120)

        # 4. Outbox status and proposal status are completed
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED)
        self.assertEqual(claimed2.status, ProposalOutboxMessage.STATUS_COMPLETED)

    @patch("core.services.retrieval.CandidateRetrievalService.retrieve_candidates")
    def test_atomic_completion_rolls_back_entirely_on_database_error(self, mock_retrieve):
        """
        Verify atomic completion: If a database error occurs during the final atomic transaction,
        no constraint changes, manifest changes, or proposal status changes are persisted.
        """
        candidates = self._create_candidates(20, start_id=4000)
        mock_retrieve.return_value = CandidatePool(
            pool_type="boutique",
            candidates=candidates,
            total_count=20,
            local_count=10,
            replenished_count=10,
            hard_constraints=HardConstraints(min_rating=7.0, max_runtime=120),
            experience_type="screening",
        )

        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00", "shared_max_runtime": 120},
            auto_approve=True,
        )
        ProposalService.record_decision(
            session=self.session,
            user=self.guest,
            proposal_id=proposal.id,
            decision="approve",
        )
        outbox_msg = ProposalOutboxMessage.objects.get(proposal=proposal)

        worker = ProposalExecutionWorker()
        claimed = worker.claim_next_message()

        # Simulate exception during manifest save inside atomic transaction
        with patch.object(CollaborativeAgreement, "save", side_effect=RuntimeError("Simulated DB Disk Full")):
            with self.assertRaises(RuntimeError):
                worker.execute_message(claimed)

        # Database state verification: EVERYTHING must be rolled back!
        self.agreement.refresh_from_db()
        proposal.refresh_from_db()
        claimed.refresh_from_db()

        # Constraints remain original
        self.assertEqual(self.agreement.shared_min_rating, Decimal("8.00"))
        self.assertEqual(self.agreement.shared_max_runtime, 100)
        # Manifest not appended
        self.assertEqual(len(self.agreement.deck_manifest), 1)
        # Proposal not marked completed
        self.assertNotEqual(proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED)

    def test_declined_proposal_cannot_be_dispatched(self):
        """Declined proposals cannot be dispatched by worker."""
        proposal = ProposalService.create_proposal(
            session=self.session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.00"},
            auto_approve=True,
        )
        proposal, _ = ProposalService.record_decision(
            session=self.session,
            user=self.guest,
            proposal_id=proposal.id,
            decision="decline",
        )
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_DECLINED)

        # Manually create outbox message pointing to declined proposal
        outbox_msg = ProposalOutboxMessage.objects.create(
            proposal=proposal,
            session=self.session,
            status=ProposalOutboxMessage.STATUS_PENDING,
            scheduled_at=timezone.now(),
        )

        worker = ProposalExecutionWorker()
        claimed = worker.claim_next_message()
        self.assertEqual(claimed.id, outbox_msg.id)

        success = worker.execute_message(claimed)
        self.assertFalse(success)

        claimed.refresh_from_db()
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_FAILED)
        self.assertIn("terminal state", claimed.error_message)

    def test_model_status_choices_include_insufficient_and_failed(self):
        """Verify model status choices include replenishment_insufficient and replenishment_failed."""
        choices_dict = dict(ConstraintExpansionProposal.STATUS_CHOICES)
        self.assertIn(ConstraintExpansionProposal.STATUS_REPLENISHMENT_INSUFFICIENT, choices_dict)
        self.assertIn(ConstraintExpansionProposal.STATUS_REPLENISHMENT_FAILED, choices_dict)
        self.assertIn(ConstraintExpansionProposal.STATUS_SUPERSEDED, choices_dict)
        self.assertIn(ConstraintExpansionProposal.STATUS_EXPIRED, choices_dict)

