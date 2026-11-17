import uuid
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from core.models import (
    Session,
    Movie,
    Genre,
    UserTasteProfile,
    SessionOccasionState,
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    InteractionLog,
    ProposalOutboxMessage,
)


class IntelligenceModelsTestCase(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")
        self.genre = Genre.objects.create(tmdb_id=18, name="Drama")
        self.session = Session.objects.create(
            code="INTEL1",
            host=self.host,
            guest=self.guest,
            genre=self.genre,
        )
        self.movie = Movie.objects.create(
            tmdb_id=550,
            title="Fight Club",
            rating=8.4,
            vote_count=28000,
        )

    # -------------------------------------------------------------
    # 1. UserTasteProfile Tests
    # -------------------------------------------------------------
    def test_user_taste_profile_creation_and_defaults(self):
        profile = UserTasteProfile.objects.create(
            user=self.host,
            emotional_tonality=["uplifted", "mindblown"],
            narrative_structures=["character"],
            thematic_interests=["identity_growth"],
            default_min_rating=Decimal("7.50"),
            default_max_runtime=120,
            default_eras=["recent"],
            hard_exclusions={"excluded_genre_ids": [27]},
        )
        self.assertEqual(profile.user, self.host)
        self.assertEqual(profile.viewing_rhythm, "balanced")
        self.assertEqual(profile.version, 1)
        self.assertEqual(profile.default_min_rating, Decimal("7.50"))
        self.assertEqual(profile.hard_exclusions["excluded_genre_ids"], [27])
        self.assertIn("TasteProfile(host_user, v1)", str(profile))

    def test_user_taste_profile_one_to_one_constraint(self):
        UserTasteProfile.objects.create(user=self.host)
        with self.assertRaises(IntegrityError):
            UserTasteProfile.objects.create(user=self.host)

    # -------------------------------------------------------------
    # 2. SessionOccasionState Tests
    # -------------------------------------------------------------
    def test_session_occasion_state_creation_and_isolation(self):
        now = timezone.now()
        occasion = SessionOccasionState.objects.create(
            session=self.session,
            host_occasion={"moods": ["uplifted"], "experience": "balanced"},
            guest_occasion={"moods": ["thrilled"], "experience": "heavy"},
            host_submitted_at=now,
            guest_submitted_at=now,
        )
        self.assertEqual(occasion.session, self.session)
        self.assertEqual(occasion.host_occasion["moods"], ["uplifted"])
        self.assertEqual(occasion.guest_occasion["experience"], "heavy")
        self.assertIn(f"OccasionState(Session {self.session.code})", str(occasion))

    def test_session_occasion_state_one_to_one_constraint(self):
        SessionOccasionState.objects.create(session=self.session)
        with self.assertRaises(IntegrityError):
            SessionOccasionState.objects.create(session=self.session)

    # -------------------------------------------------------------
    # 3. ConstraintExpansionProposal Tests
    # -------------------------------------------------------------
    def test_constraint_expansion_proposal_lifecycle_and_properties(self):
        now = timezone.now()
        proposal = ConstraintExpansionProposal.objects.create(
            session=self.session,
            initiated_by_user=self.host,
            original_constraints={"shared_min_rating": "7.50", "shared_max_runtime": 105},
            proposed_constraints={"shared_min_rating": "7.00", "shared_max_runtime": 120},
            host_decision={"decision": "approve", "decided_at": now.isoformat()},
            guest_decision=None,
            expires_at=now + timedelta(minutes=10),
        )
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_PENDING)
        self.assertFalse(proposal.is_expired)
        self.assertFalse(proposal.is_mutually_approved)
        self.assertIn(f"Proposal {proposal.id}", str(proposal))

        # Record guest approval
        proposal.guest_decision = {"decision": "approve", "decided_at": now.isoformat()}
        proposal.status = ConstraintExpansionProposal.STATUS_APPROVED_QUEUED
        proposal.save()
        self.assertTrue(proposal.is_mutually_approved)

        # Expired proposal check
        past_proposal = ConstraintExpansionProposal.objects.create(
            session=self.session,
            initiated_by_user=self.guest,
            expires_at=now - timedelta(seconds=1),
        )
        self.assertTrue(past_proposal.is_expired)

    # -------------------------------------------------------------
    # 4. CollaborativeAgreement Tests
    # -------------------------------------------------------------
    def test_collaborative_agreement_fields_and_cursors(self):
        agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_min_rating=Decimal("7.75"),
            shared_max_runtime=110,
            shared_eras=["recent", "2010s"],
            shared_languages=["en", "fr"],
            mutual_hard_exclusions={"excluded_genre_ids": [27, 16]},
            deck_manifest=[
                {"movie_id": self.movie.id, "slot_type": "consensus", "turn": 1}
            ],
            host_card_index=0,
            guest_card_index=0,
            resolved_card_index=0,
        )
        self.assertEqual(agreement.shared_min_rating, Decimal("7.75"))
        self.assertEqual(agreement.shared_languages, ["en", "fr"])
        self.assertEqual(agreement.host_card_index, 0)
        self.assertEqual(agreement.guest_card_index, 0)
        self.assertEqual(agreement.resolved_card_index, 0)
        self.assertEqual(len(agreement.deck_manifest), 1)
        self.assertIn(f"CollaborativeAgreement(Session {self.session.code})", str(agreement))

    def test_collaborative_agreement_one_to_one_constraint(self):
        CollaborativeAgreement.objects.create(session=self.session)
        with self.assertRaises(IntegrityError):
            CollaborativeAgreement.objects.create(session=self.session)

    # -------------------------------------------------------------
    # 5. InteractionLog Tests
    # -------------------------------------------------------------
    def test_interaction_log_creation_and_ordering(self):
        log1 = InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
            metadata={"turn": 1, "slot_type": "consensus"},
        )
        log2 = InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.movie,
            event_type="superlike",
            weight=3.0,
            metadata={"turn": 2, "slot_type": "host"},
        )
        logs = list(InteractionLog.objects.filter(user=self.host))
        self.assertEqual(logs[0].id, log2.id)  # newest first
        self.assertEqual(logs[1].id, log1.id)
        self.assertIn("Interaction(host_user, superlike", str(log2))

    # -------------------------------------------------------------
    # 6. ProposalOutboxMessage Tests
    # -------------------------------------------------------------
    def test_proposal_outbox_message_creation_and_processing(self):
        now = timezone.now()
        proposal = ConstraintExpansionProposal.objects.create(
            session=self.session,
            initiated_by_user=self.host,
            expires_at=now + timedelta(minutes=10),
            status=ConstraintExpansionProposal.STATUS_APPROVED_QUEUED,
        )
        outbox_msg = ProposalOutboxMessage.objects.create(
            proposal=proposal,
            session=self.session,
            topic="proposal.replenishment",
            payload={"proposal_id": str(proposal.id), "session_id": self.session.id},
            status=ProposalOutboxMessage.STATUS_PENDING,
        )
        self.assertEqual(outbox_msg.status, "pending")
        self.assertEqual(outbox_msg.attempts, 0)
        self.assertEqual(outbox_msg.max_attempts, 3)
        self.assertIn(f"OutboxMessage({outbox_msg.id}", str(outbox_msg))

        # Advance status
        outbox_msg.status = ProposalOutboxMessage.STATUS_PROCESSING
        outbox_msg.attempts = 1
        outbox_msg.save()
        self.assertEqual(
            ProposalOutboxMessage.objects.filter(status=ProposalOutboxMessage.STATUS_PROCESSING).count(),
            1
        )
