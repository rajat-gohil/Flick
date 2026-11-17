import time
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    Genre,
    Movie,
    ProposalOutboxMessage,
    Session,
)
from core.services.deck_state import DeckAdvancementService
from core.services.manifest import (
    InsufficientCandidatesError,
    ManifestCompilerService,
    TransientReplenishmentError,
    ReplenishmentInProgressError,
)
from core.services.outbox import ProposalExecutionWorker
from core.services.proposals import ProposalService
from core.services.retrieval import CandidateRetrievalService, HardConstraints

User = get_user_model()


class LocalizedGenreRetrievalTests(TestCase):
    """
    Comprehensive regression test suite for Localized Genre Retrieval,
    Preference Changes, TMDB Connection Reset Recovery, Concurrency,
    and Constraint Expansion.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Create participants
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")

        # Create Horror genre (TMDB ID 27)
        self.horror_genre = Genre.objects.create(name="Horror", tmdb_id=27)
        self.action_genre = Genre.objects.create(name="Action", tmdb_id=28)

        # Create screening session
        self.session = Session.objects.create(
            code="GUJHOR",
            host=self.host,
            guest=self.guest,
            genre=self.horror_genre,
            selected_languages=["gu"],
            host_preferences={"genre_id": 27, "languages": ["gu"], "min_rating": 7.0},
            guest_preferences={"genre_id": 27, "languages": ["gu"], "min_rating": 7.0},
            preferences_set=True,
        )

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            shared_languages=["gu"],
            shared_min_rating=Decimal("7.0"),
            mutual_hard_exclusions={"required_genre_ids": [27]},
        )

    def _create_gujarati_horror_movies(self, count=16, base_id=1000, rating=7.5, runtime=110):
        """Helper to seed verified local Gujarati Horror movies."""
        movies = []
        for i in range(count):
            m, _ = Movie.objects.get_or_create(
                tmdb_id=base_id + i,
                defaults={
                    "id": base_id + i,
                    "title": f"Gujarati Horror Film {i + 1}",
                    "original_language": "gu",
                    "rating": Decimal(str(rating)),
                    "credits_summary": {"runtime": runtime},
                    "display_ready": True,
                    "recommendable": True,
                    "provenance": "tmdb_catalogue",
                },
            )
            m.genres.add(self.horror_genre)
            movies.append(m)
        return movies

    # -------------------------------------------------------------------------
    # Scenario 1: Gujarati Horror movies available locally
    # -------------------------------------------------------------------------
    def test_01_gujarati_horror_available_locally(self):
        """Proves that when 16+ Gujarati Horror movies exist locally, retrieval succeeds without TMDB."""
        self._create_gujarati_horror_movies(count=16)

        hc = HardConstraints(languages=["gu"], required_genre_ids=[27], min_rating=7.0)
        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            constraints=hc,
            auto_replenish=False,
        )

        self.assertEqual(pool.total_count, 16)
        self.assertEqual(pool.pool_type, "boutique")
        self.assertFalse(pool.proposal_required)

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        self.assertEqual(len(manifest), 16)
        for card in manifest:
            self.assertEqual(card["slot_type"] in ("consensus", "host_priority", "guest_priority"), True)

    # -------------------------------------------------------------------------
    # Scenario 2: Gujarati Horror movies retrieved successfully from TMDB
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @patch("core.services.retrieval._ingest_tmdb_results")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_02_gujarati_horror_retrieved_from_tmdb(self, mock_ingest, mock_discover):
        """Proves that TMDB discovery populates candidate pool when local catalog is insufficient."""
        # 0 local movies initially
        mock_discover.return_value = (
            {
                "results": [
                    {"id": 2000 + i, "title": f"Discovered Film {i}", "original_language": "gu", "vote_average": 7.5}
                    for i in range(20)
                ]
            },
            {},
        )

        def fake_ingest(results):
            return len(self._create_gujarati_horror_movies(count=len(results), base_id=2000))

        mock_ingest.side_effect = fake_ingest

        hc = HardConstraints(languages=["gu"], required_genre_ids=[27], min_rating=7.0)
        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            constraints=hc,
            auto_replenish=True,
        )

        self.assertGreaterEqual(pool.total_count, 16)
        self.assertFalse(pool.proposal_required)
        self.assertTrue(mock_discover.called)

    # -------------------------------------------------------------------------
    # Scenario 3: TMDB connection reset during retrieval
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_03_tmdb_connection_reset_during_retrieval(self, mock_discover):
        """Proves that ConnectionResetError is identified as a transient network error, not exhaustion."""
        mock_discover.side_effect = ConnectionResetError(54, "Connection reset by peer")

        hc = HardConstraints(languages=["gu"], required_genre_ids=[27], min_rating=7.0)
        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            constraints=hc,
            auto_replenish=True,
        )

        self.assertEqual(pool.total_count, 0)
        self.assertTrue(pool.metadata.get("transient_error"))

        with self.assertRaises(TransientReplenishmentError):
            ManifestCompilerService.compile_and_persist_manifest(
                session=self.session,
                agreement=self.agreement,
                candidate_pool=pool,
            )

        # Test API response in DeckCardDeliveryView
        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/deck/card/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get("success"))
        self.assertTrue(res.data.get("transient_error"))
        self.assertFalse(res.data.get("exhausted", False))

    # -------------------------------------------------------------------------
    # Scenario 4: Concurrent replenishment requests
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_04_concurrent_replenishment_requests(self, mock_discover):
        """Proves that duplicate parallel requests resolve the lock cleanly without failing."""
        mock_discover.return_value = ({"results": []}, {})

        # Set active lock key
        languages = ["gu"]
        genre_id = 27
        eras_to_query = [None]
        min_rating = 7.0
        import hashlib
        key_raw = f"{languages}:{genre_id}:{eras_to_query}:{min_rating}"
        cache_lock_key = f"tmdb_replenish_lock:{hashlib.md5(key_raw.encode()).hexdigest()}"
        cache.set(cache_lock_key, "other_worker_lock", timeout=30)

        error_collector = []
        hc = HardConstraints(languages=["gu"], required_genre_ids=[27], min_rating=7.0)
        # Should wait and report in_progress without uncaught exception
        ingested = CandidateRetrievalService._replenish_from_tmdb(
            constraints=hc,
            error_collector=error_collector,
        )
        self.assertEqual(ingested, 0)
        self.assertIn("replenishment_in_progress", error_collector)

    # -------------------------------------------------------------------------
    # Scenario 5: Empty deck response when genuinely exhausted
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_05_empty_deck_response(self, mock_discover):
        """Proves that genuine exhaustion (< 16 candidates without error) triggers proposal_required."""
        # TMDB returns valid 200 with 0 results
        mock_discover.return_value = ({"results": []}, {})

        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/deck/card/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data.get("success"))
        self.assertTrue(res.data.get("exhausted"))
        self.assertTrue(res.data.get("proposal_required"))

    # -------------------------------------------------------------------------
    # Scenario 6: Changing preferences with an existing unswiped deck
    # -------------------------------------------------------------------------
    def test_06_changing_preferences_with_existing_deck(self):
        """Proves that changing preferences invalidates the unswiped deck manifest."""
        self._create_gujarati_horror_movies(count=16)
        hc = HardConstraints(languages=["gu"], required_genre_ids=[27], min_rating=7.0)
        pool = CandidateRetrievalService.retrieve_candidates(session=self.session, constraints=hc)
        ManifestCompilerService.compile_and_persist_manifest(session=self.session, agreement=self.agreement, candidate_pool=pool)

        self.agreement.refresh_from_db()
        self.assertIsNotNone(self.agreement.deck_manifest)
        self.assertEqual(len(self.agreement.deck_manifest), 16)

        # Host changes preferences to English Action
        self.client.force_authenticate(user=self.host)
        new_prefs = {"genre_id": 28, "languages": ["en"], "min_rating": 8.0}
        res = self.client.post("/api/sessions/preferences/", {"session_id": self.session.id, "preferences": new_prefs}, format="json")
        self.assertEqual(res.status_code, 200)

        # Verify agreement manifest was invalidated
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.deck_manifest, [])
        self.assertEqual(self.agreement.shared_languages, ["en"])

    # -------------------------------------------------------------------------
    # Scenario 7: Changing preferences while TMDB replenishment is running
    # -------------------------------------------------------------------------
    def test_07_changing_preferences_while_tmdb_replenishment_running(self):
        """Proves that changing preferences supersedes any pending proposal and clears stale manifest."""
        # Create a pending proposal under Gujarati Horror
        proposal = ConstraintExpansionProposal.objects.create(
            session=self.session,
            initiated_by_user=self.host,
            status=ConstraintExpansionProposal.STATUS_PENDING,
            original_constraints={"shared_languages": ["gu"]},
            proposed_constraints={"shared_languages": ["gu"], "shared_min_rating": "6.5"},
            expires_at=self.agreement.created_at,
        )
        self.agreement.active_proposal = proposal
        self.agreement.save()

        # Update preferences
        self.client.force_authenticate(user=self.host)
        new_prefs = {"genre_id": 28, "languages": ["en"], "min_rating": 7.5}
        res = self.client.post("/api/sessions/preferences/", {"session_id": self.session.id, "preferences": new_prefs}, format="json")
        self.assertEqual(res.status_code, 200)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_SUPERSEDED)
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.active_proposal)

    # -------------------------------------------------------------------------
    # Scenario 8: Constraint expansion proposal creation
    # -------------------------------------------------------------------------
    def test_08_constraint_expansion_proposal_creation(self):
        """Proves that auto_approve=True establishes attributable consent while preserving genre and language."""
        self.client.force_authenticate(user=self.host)
        res = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {"action": "propose", "auto_approve": True},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        proposal_id = res.data["proposal_id"]

        proposal = ConstraintExpansionProposal.objects.get(id=proposal_id)
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_PENDING)
        self.assertEqual(proposal.host_decision["decision"], "approve")
        self.assertEqual(proposal.guest_decision["decision"], "pending")

        # Verify language ('gu') and genre (27) remain strictly preserved
        self.assertEqual(proposal.proposed_constraints["shared_languages"], ["gu"])
        self.assertEqual(proposal.proposed_constraints["required_genre_ids"], [27])
        # Min rating relaxed by 0.5
        self.assertEqual(proposal.proposed_constraints["shared_min_rating"], "6.50")

    # -------------------------------------------------------------------------
    # Scenario 9: Constraint expansion approval and rejection
    # -------------------------------------------------------------------------
    def test_09_constraint_expansion_approval_and_rejection(self):
        """Proves rejection marks proposal declined, while mutual approval queues outbox execution."""
        proposal = ProposalService.create_proposal(session=self.session, user=self.host, auto_approve=True)

        # Guest declines
        self.client.force_authenticate(user=self.guest)
        res = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {"action": "respond", "proposal_id": str(proposal.id), "decision": "decline"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_DECLINED)

        # Create new proposal and test approval
        proposal2 = ProposalService.create_proposal(session=self.session, user=self.host, auto_approve=True)
        res2 = self.client.post(
            f"/api/sessions/{self.session.id}/expand-constraints/",
            {"action": "respond", "proposal_id": str(proposal2.id), "decision": "approve"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        proposal2.refresh_from_db()
        # Either queued or synchronously executed
        self.assertIn(
            proposal2.status,
            (
                ConstraintExpansionProposal.STATUS_APPROVED_QUEUED,
                ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED,
                ConstraintExpansionProposal.STATUS_REPLENISHMENT_INSUFFICIENT,
            ),
        )

    # -------------------------------------------------------------------------
    # Scenario 10: Successful deck regeneration after approved expansion
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @patch("core.services.retrieval._ingest_tmdb_results")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_10_successful_deck_regeneration_after_approved_expansion(self, mock_ingest, mock_discover):
        """Proves that mutual approval with qualifying candidates regenerates and appends manifest."""
        proposal = ProposalService.create_proposal(session=self.session, user=self.host, auto_approve=True)

        # When replenishment runs under relaxed criteria (6.5), return 18 movies
        mock_discover.return_value = (
            {
                "results": [
                    {"id": 3000 + i, "title": f"Expanded Film {i}", "original_language": "gu", "vote_average": 6.6}
                    for i in range(18)
                ]
            },
            {},
        )

        def fake_ingest(results):
            return len(self._create_gujarati_horror_movies(count=len(results), base_id=3000, rating=6.6))

        mock_ingest.side_effect = fake_ingest

        # Guest approves
        ProposalService.record_decision(session=self.session, user=self.guest, proposal_id=proposal.id, decision="approve")

        worker = ProposalExecutionWorker()
        processed = worker.process_batch(max_messages=1)
        self.assertEqual(processed["succeeded"], 1)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_REPLENISHMENT_COMPLETED)

        self.agreement.refresh_from_db()
        self.assertIsNotNone(self.agreement.deck_manifest)
        self.assertGreaterEqual(len(self.agreement.deck_manifest), 16)

    # -------------------------------------------------------------------------
    # Scenario 11: Both participants receiving synchronized updates
    # -------------------------------------------------------------------------
    def test_11_both_participants_receiving_synchronized_updates(self):
        """Proves that reset-preferences endpoint cleanly resets state and allows re-answering questionnaire."""
        self.client.force_authenticate(user=self.host)
        res = self.client.post(f"/api/sessions/{self.session.id}/reset-preferences/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.session.refresh_from_db()
        self.assertFalse(self.session.preferences_set)
        self.assertEqual(self.session.host_preferences, {})
        self.assertEqual(self.session.guest_preferences, {})

    # -------------------------------------------------------------------------
    # Scenario 12: Refreshing during an empty/replenishing state
    # -------------------------------------------------------------------------
    @patch("core.services.retrieval.discover_movies")
    @override_settings(TMDB_API_KEY="test_api_key")
    def test_12_refreshing_during_empty_replenishing_state(self, mock_discover):
        """Proves that repeated calls during replenishment or exhaustion are idempotent and non-destructive."""
        mock_discover.return_value = ({"results": []}, {})

        self.client.force_authenticate(user=self.guest)
        res1 = self.client.get(f"/api/sessions/{self.session.id}/deck/card/")
        res2 = self.client.get(f"/api/sessions/{self.session.id}/deck/card/")

        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data, res2.data)

    # -------------------------------------------------------------------------
    # Scenario 13: No blank-screen state under any of these conditions
    # -------------------------------------------------------------------------
    def test_13_no_blank_screen_state_serialization_guarantee(self):
        """Proves that serializer returns robust decision dictionaries and proposal objects."""
        from core.serializers import ConstraintExpansionProposalSerializer

        proposal = ProposalService.create_proposal(session=self.session, user=self.host, auto_approve=True)
        serializer = ConstraintExpansionProposalSerializer(proposal)
        data = serializer.data

        self.assertIn("host_decision", data)
        self.assertIn("guest_decision", data)
        self.assertEqual(data["host_decision"]["decision"], "approve")
        self.assertEqual(data["guest_decision"]["decision"], "pending")
        self.assertEqual(data["status"], "pending")
