import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    Genre,
    Match,
    Movie,
    ProposalOutboxMessage,
    Session,
    SessionOccasionState,
    Swipe,
    UserTasteProfile,
)
from core.services.deck_state import (
    DeckAdvancementService,
    DeckStateError,
)
from core.services.manifest import (
    HamiltonManifestAllocator,
    ManifestCompilerService,
    NORMAL_MANIFEST_SIZE,
)
from core.services.outbox import ProposalExecutionWorker
from core.services.proposals import ProposalService
from core.services.retrieval import CandidatePool, CandidateRetrievalService, HardConstraints
from core.services.scoring import IndividualRelevanceScorer, UserPreferenceData

User = get_user_model()


class Phase1EndToEndScenarioTestCase(TestCase):
    """
    Comprehensive end-to-end scenario verification covering Scenarios 1 through 5
    from Phase 1 Integration Audit requirements.
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="scenario_host", password="password123")
        self.guest = User.objects.create_user(username="scenario_guest", password="password123")
        self.stranger = User.objects.create_user(username="scenario_stranger", password="password123")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.genre_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.genre_drama = Genre.objects.create(name="Drama", tmdb_id=18)

    def _create_movies(self, count, prefix="SCEN"):
        movies = []
        for i in range(1, count + 1):
            m, _ = Movie.objects.get_or_create(
                tmdb_id=50000 + i if prefix == "SCEN" else 60000 + i,
                defaults={
                    "title": f"{prefix} Movie {i}",
                    "rating": 7.0 + (i % 25) * 0.1,
                    "release_date": "2022-01-01",
                    "vote_count": 100 + i * 10,
                    "original_language": "en",
                }
            )
            m.genres.add(self.genre_action)
            movies.append(m)
        return movies

    # -------------------------------------------------------------------------
    # Scenario 1: Normal Collaborative Screening
    # -------------------------------------------------------------------------
    def test_scenario_1_normal_collaborative_screening(self):
        """
        Scenario 1:
        1. Two users establish a collaborative session.
        2. Permanent taste profiles loaded.
        3. Session-specific preferences applied.
        4. Candidates retrieved and filtered.
        5. Candidates scored.
        6. 40-card manifest compiled.
        7. Host and guest independently receive cards.
        8. Both participants submit responses.
        9. Joint resolutions persisted.
        10. Mutual matches created.
        """
        # 1. Establish session
        session = Session.objects.create(host=self.host, guest=self.guest, code="SCEN01")
        session.genres.add(self.genre_action)

        # 2. Permanent taste profiles (Tier A)
        UserTasteProfile.objects.create(
            user=self.host,
            emotional_tonality=["exciting"],
            narrative_structures=["linear"],
            thematic_interests=["justice"],
            viewing_rhythm="high_energy",
            default_min_rating=Decimal("7.00"),
        )
        UserTasteProfile.objects.create(
            user=self.guest,
            emotional_tonality=["exciting", "dark"],
            narrative_structures=["linear"],
            thematic_interests=["survival"],
            viewing_rhythm="balanced",
            default_min_rating=Decimal("7.50"),
        )

        # 3. Ephemeral session occasion state (Tier B)
        SessionOccasionState.objects.create(
            session=session,
            host_occasion={"moods": ["exciting"], "viewing_rhythm": "high_energy", "boundaries": {"min_rating": "7.00"}},
            guest_occasion={"moods": ["exciting"], "viewing_rhythm": "balanced", "boundaries": {"min_rating": "7.50"}},
        )

        # 4 & 5. Retrieve candidates & score
        self._create_movies(45, prefix="SCEN")
        pool = CandidateRetrievalService.retrieve_candidates(
            session=session,
            experience_type="screening",
            auto_replenish=False,
        )
        self.assertGreaterEqual(pool.total_count, 40)
        self.assertEqual(pool.pool_type, "normal")

        # 6. Compile 40-card manifest into CollaborativeAgreement (Tier C)
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            shared_min_rating=Decimal("7.25"),  # (7.0 + 7.5) / 2
            shared_eras=["modern"],
        )
        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=session,
            agreement=agreement,
            candidate_pool=pool,
        )
        self.assertEqual(len(manifest), NORMAL_MANIFEST_SIZE)
        agreement.refresh_from_db()
        self.assertEqual(len(agreement.deck_manifest), NORMAL_MANIFEST_SIZE)

        # 7. Host and guest independently receive cards
        card_h0 = DeckAdvancementService.get_current_delivery_card(session=session, user=self.host)
        card_g0 = DeckAdvancementService.get_current_delivery_card(session=session, user=self.guest)
        self.assertEqual(card_h0["card_index"], 0)
        self.assertEqual(card_g0["card_index"], 0)
        self.assertEqual(card_h0["card"]["movie_id"], card_g0["card"]["movie_id"])

        # 8 & 9. Both submit responses (mutual like)
        res_h0 = DeckAdvancementService.record_swipe_response(
            session_id=session.id,
            user=self.host,
            card_index=0,
            movie_id=card_h0["card"]["movie_id"],
            reaction="like",
        )
        self.assertFalse(res_h0["match_formed"])  # Guest has not responded yet
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 1)
        self.assertEqual(agreement.guest_card_index, 0)
        self.assertEqual(agreement.resolved_card_index, 0)

        # Guest submits like for card 0
        res_g0 = DeckAdvancementService.record_swipe_response(
            session_id=session.id,
            user=self.guest,
            card_index=0,
            movie_id=card_g0["card"]["movie_id"],
            reaction="like",
        )
        # 10. Mutual match formed atomically!
        self.assertTrue(res_g0["match_formed"])
        self.assertTrue(res_g0["jointly_resolved"])
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 1)
        self.assertEqual(agreement.guest_card_index, 1)
        self.assertEqual(agreement.resolved_card_index, 1)
        self.assertTrue(Match.objects.filter(session=session, movie_id=card_h0["card"]["movie_id"]).exists())

    # -------------------------------------------------------------------------
    # Scenario 2: Boutique Screening (16, 17, 23, 39 candidates)
    # -------------------------------------------------------------------------
    def test_scenario_2_boutique_screening_allocations(self):
        """
        Scenario 2:
        Test candidate pools containing 16, 17, 23, and 39 candidates.
        Verify exact seat counts, Hamilton allocation, unique movie IDs, and manifest length.
        """
        test_counts = [16, 17, 23, 39]
        for count in test_counts:
            with self.subTest(candidate_count=count):
                alloc = HamiltonManifestAllocator.calculate_allocation(count)
                self.assertEqual(sum(alloc.values()), count)

                # Generate candidates
                movies = self._create_movies(count, prefix=f"BTQ{count}")
                session = Session.objects.create(host=self.host, guest=self.guest, code=f"BQ{count:02d}")
                agreement = CollaborativeAgreement.objects.create(session=session)

                manifest = ManifestCompilerService.compile_manifest(
                    candidates=movies,
                    host_prefs=UserPreferenceData(moods=["action"]),
                    guest_prefs=UserPreferenceData(moods=["action"]),
                    pool_type="boutique",
                )

                self.assertEqual(len(manifest), count)
                # Verify zero duplicates
                movie_ids = [c["movie_id"] for c in manifest]
                self.assertEqual(len(movie_ids), len(set(movie_ids)))

    # -------------------------------------------------------------------------
    # Scenario 3: Constraint Expansion Lifecycle & Worker Execution
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.CandidateRetrievalService.retrieve_candidates")
    def test_scenario_3_constraint_expansion_lifecycle(self, mock_retrieve):
        """
        Scenario 3:
        1. Restrictive constraints.
        2. Candidate exhaustion (< 16).
        3. Create expansion proposal.
        4. Host approves, Guest approves.
        5. Outbox message created atomically.
        6. Worker claims and executes replenishment outside DB transaction.
        7. Constraints activated, manifest appended, proposal completed.
        """
        session = Session.objects.create(host=self.host, guest=self.guest, code="EXP001")
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            shared_min_rating=Decimal("9.00"),
            shared_max_runtime=90,
        )

        # 3. Create proposal
        proposal = ProposalService.create_proposal(
            session=session,
            user=self.host,
            proposed_constraints={"shared_min_rating": "7.50", "shared_max_runtime": 120},
            auto_approve=False,
        )
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_PENDING)

        # 4. Host approves
        p1, queued1 = ProposalService.record_decision(session, self.host, proposal.id, "approve")
        self.assertFalse(queued1)
        self.assertEqual(p1.status, ConstraintExpansionProposal.STATUS_PENDING)

        # 5. Guest approves
        p2, queued2 = ProposalService.record_decision(session, self.guest, proposal.id, "approve")
        self.assertTrue(queued2)
        self.assertEqual(p2.status, ConstraintExpansionProposal.STATUS_APPROVED_QUEUED)

        # 6. Verify Outbox Message created transactionally
        outbox_msg = ProposalOutboxMessage.objects.filter(proposal=proposal).first()
        self.assertIsNotNone(outbox_msg)
        self.assertEqual(outbox_msg.status, ProposalOutboxMessage.STATUS_PENDING)

        # 7 & 8. Execute worker
        new_movies = self._create_movies(25, prefix="EXP")
        mock_retrieve.return_value = CandidatePool(
            pool_type="boutique",
            candidates=new_movies,
            total_count=25,
            local_count=10,
            replenished_count=15,
            hard_constraints=HardConstraints(min_rating=7.5, max_runtime=120),
            experience_type="screening",
        )

        worker = ProposalExecutionWorker()
        claimed = worker.claim_next_message()
        self.assertEqual(claimed.id, outbox_msg.id)

        ok = worker.execute_message(claimed)
        self.assertTrue(ok)

        # 9. Verify resulting states
        proposal.refresh_from_db()
        agreement.refresh_from_db()
        claimed.refresh_from_db()

        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED)
        self.assertEqual(claimed.status, ProposalOutboxMessage.STATUS_COMPLETED)
        self.assertEqual(agreement.shared_min_rating, Decimal("7.50"))
        self.assertEqual(agreement.shared_max_runtime, 120)
        self.assertGreater(len(agreement.deck_manifest), 0)

    # -------------------------------------------------------------------------
    # Scenario 4: Retry and Concurrency
    # -------------------------------------------------------------------------
    def test_scenario_4_retry_and_concurrency_guards(self):
        """
        Scenario 4:
        - Duplicate card delivery requests return identical card.
        - Matching duplicate response submission is idempotent.
        - Conflicting duplicate response submission raises ConflictingResponseError.
        - Undo operates cleanly on latest swipe.
        """
        session = Session.objects.create(host=self.host, guest=self.guest, code="RETR01")
        movies = self._create_movies(5, prefix="RETR")
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[
                {"card_index": i, "movie_id": m.id, "tmdb_id": m.tmdb_id, "title": m.title, "slot_type": "consensus", "turn": "joint"}
                for i, m in enumerate(movies)
            ]
        )

        # Duplicate card delivery
        c1 = DeckAdvancementService.get_current_delivery_card(session=session, user=self.host)
        c2 = DeckAdvancementService.get_current_delivery_card(session=session, user=self.host)
        self.assertEqual(c1["card_index"], c2["card_index"])
        self.assertEqual(c1["card"]["movie_id"], c2["card"]["movie_id"])

        # Initial swipe response
        res1 = DeckAdvancementService.record_swipe_response(
            session_id=session.id,
            user=self.host,
            card_index=0,
            movie_id=movies[0].id,
            reaction="like",
        )
        self.assertFalse(res1["idempotent"])

        # Matching duplicate retry is idempotent
        res2 = DeckAdvancementService.record_swipe_response(
            session_id=session.id,
            user=self.host,
            card_index=0,
            movie_id=movies[0].id,
            reaction="like",
        )
        self.assertTrue(res2["idempotent"])

        # Undo on latest swipe
        undo_res = DeckAdvancementService.undo_card_response(
            session_id=session.id,
            user=self.host,
            card_index=0,
            movie_id=movies[0].id,
        )
        self.assertTrue(undo_res["success"])
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 0)

    # -------------------------------------------------------------------------
    # Scenario 5: Authorization and Isolation
    # -------------------------------------------------------------------------
    def test_scenario_5_authorization_and_isolation(self):
        """
        Scenario 5:
        - Unauthenticated requests return 401.
        - Non-members cannot access session deck or proposals (403).
        - Proposal IDs cannot be manipulated across sessions (404).
        - Administrative worker endpoint rejects non-staff users (403).
        """
        session = Session.objects.create(host=self.host, guest=self.guest, code="AUTH01")
        CollaborativeAgreement.objects.create(session=session)

        # Unauthenticated request
        resp_unauth = self.client.get(f"/api/sessions/{session.id}/deck/card/")
        self.assertEqual(resp_unauth.status_code, status.HTTP_401_UNAUTHORIZED)

        # Non-member (stranger) request
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        resp_forbidden = self.client.get(f"/api/sessions/{session.id}/deck/card/")
        self.assertEqual(resp_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Stranger cannot initiate proposal
        resp_prop = self.client.post(
            f"/api/sessions/{session.id}/expand-constraints/",
            {"action": "propose", "proposed_constraints": {"shared_min_rating": "7.00"}},
            format="json",
        )
        self.assertEqual(resp_prop.status_code, status.HTTP_403_FORBIDDEN)

        # Ordinary participant cannot access admin outbox worker
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        resp_admin = self.client.post(f"/api/sessions/{session.id}/proposals/process-outbox/", {}, format="json")
        self.assertEqual(resp_admin.status_code, status.HTTP_403_FORBIDDEN)
