import concurrent.futures
from datetime import date, datetime
from unittest.mock import patch, MagicMock, AsyncMock

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    CollaborativeAgreement,
    InteractionLog,
    Match,
    Movie,
    Session,
    SessionStats,
    Swipe,
)
from core.services.deck_state import (
    ConflictingResponseError,
    DeckAdvancementService,
    InvalidCardIndexError,
    OutOfOrderResponseError,
    StaleManifestError,
    UndoNotPermittedError,
)
from core.services.manifest import ManifestCompilerService
from core.services.scoring import UserPreferenceData

User = get_user_model()


class DeckStateFunctionalTests(TestCase):
    """
    Workstream 5 Test Suite: Card Delivery, Response Persistence, and Joint Resolution State Machine.
    Covers decoupled delivery cursors, idempotency, sequential ordering, joint resolution,
    partner lag buffer, undo mechanics, and session completion.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_ds", password="password123")
        self.guest = User.objects.create_user(username="guest_ds", password="password123")
        self.session = Session.objects.create(
            code="DECK01",
            host=self.host,
            guest=self.guest,
        )
        self.stats = SessionStats.objects.create(session=self.session)

        # Create 16 movies for a clean 16-card boutique manifest
        self.movies = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=50000 + i,
                title=f"Deck Film {i}",
                rating=7.5 + (i % 5) * 0.2,
                vote_count=250 + i * 10,
                release_date=date(2020, 1, 1),
                original_language="en",
            )
            self.movies.append(m)

        # Compile and persist initial manifest
        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            host_soft_preferences={"moods": ["uplifted"]},
            guest_soft_preferences={"moods": ["moved"]},
        )
        self.manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=None,  # will score from candidates
        )
        # For test predictability, set candidates directly in manifest
        self.manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        self.agreement.deck_manifest = self.manifest
        self.agreement.save(update_fields=["deck_manifest"])

    # -----------------------------------------------------------------
    # 1. Decoupled Delivery Tests
    # -----------------------------------------------------------------

    def test_host_delivery_independent_of_guest_delivery(self):
        """Host advancing does NOT advance, alter, or invalidate Guest's delivery cursor."""
        # Initial delivery for both: card 0
        h_card = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        g_card = DeckAdvancementService.get_current_delivery_card(self.session, self.guest)

        self.assertEqual(h_card["card_index"], 0)
        self.assertEqual(g_card["card_index"], 0)
        self.assertEqual(h_card["card"]["movie_id"], self.manifest[0]["movie_id"])
        self.assertEqual(g_card["card"]["movie_id"], self.manifest[0]["movie_id"])

        # Host swipes card 0 and card 1
        m0_id = self.manifest[0]["movie_id"]
        m1_id = self.manifest[1]["movie_id"]

        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 1, m1_id, "dislike")

        # Refresh state
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 2)
        self.assertEqual(self.agreement.guest_card_index, 0, "Guest cursor must remain unchanged at 0")

        # Next card for Host is card 2; next card for Guest is still card 0
        h_next = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        g_still = DeckAdvancementService.get_current_delivery_card(self.session, self.guest)

        self.assertEqual(h_next["card_index"], 2)
        self.assertEqual(g_still["card_index"], 0)
        self.assertEqual(g_still["card"]["movie_id"], m0_id, "Guest must still be served card 0")

    def test_guest_delivery_independent_of_host_delivery(self):
        """Guest advancing does NOT advance or invalidate Host's delivery cursor."""
        m0_id = self.manifest[0]["movie_id"]
        DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "like")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.guest_card_index, 1)
        self.assertEqual(self.agreement.host_card_index, 0)

        h_card = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        self.assertEqual(h_card["card_index"], 0)

    # -----------------------------------------------------------------
    # 2. Joint Resolution & Match Logic
    # -----------------------------------------------------------------

    def test_one_response_does_not_advance_joint_resolution(self):
        """A single participant's swipe leaves card PENDING_PARTNER; resolved_card_index remains 0."""
        m0_id = self.manifest[0]["movie_id"]

        result = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")

        self.assertFalse(result["jointly_resolved"])
        self.assertFalse(result["match_formed"])
        self.assertEqual(result["resolved_card_index"], 0)

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.resolved_card_index, 0, "Resolution cursor must not advance on single response")
        self.assertFalse(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

    def test_resolution_after_second_response_mutual_like(self):
        """When both participants like card 0, it transitions to JOINTLY_RESOLVED and creates Match."""
        m0_id = self.manifest[0]["movie_id"]

        # Host likes card 0
        r1 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        self.assertFalse(r1["jointly_resolved"])

        # Guest likes card 0
        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "like")
        self.assertTrue(r2["jointly_resolved"])
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["resolved_card_index"], 1)

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.resolved_card_index, 1)
        self.assertTrue(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

    def test_resolution_after_second_response_no_match(self):
        """When one participant dislikes card 0, it is JOINTLY_RESOLVED without creating a Match."""
        m0_id = self.manifest[0]["movie_id"]

        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "dislike")

        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"])
        self.assertEqual(r2["resolved_card_index"], 1)

        self.assertFalse(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

    def test_superlike_with_dislike_forms_no_match_upon_joint_resolution(self):
        """Superlike with partner dislike does NOT create a match; both must be positive."""
        m0_id = self.manifest[0]["movie_id"]

        r1 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "superlike")
        self.assertFalse(r1["jointly_resolved"])
        self.assertFalse(r1["match_formed"])

        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "dislike")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"], "Superlike with partner dislike must NOT form a match")
        self.assertFalse(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

    def test_superlike_with_like_forms_match_with_attribution(self):
        """Superlike with partner like forms a match with correct Super-Like attribution."""
        m0_id = self.manifest[0]["movie_id"]

        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "superlike")
        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "like")

        self.assertTrue(r2["jointly_resolved"])
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["superlike_attribution"], "host")
        self.assertTrue(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

    # -----------------------------------------------------------------
    # 3. Response Validation & Idempotency
    # -----------------------------------------------------------------

    def test_duplicate_response_submissions_handled_idempotently(self):
        """Resubmitting the same card response returns success without duplicating Swipes."""
        m0_id = self.manifest[0]["movie_id"]

        r1 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        self.assertFalse(r1["idempotent"])
        self.assertEqual(r1["next_card_index"], 1)

        # Duplicate submission for card 0
        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        self.assertTrue(r2["idempotent"])
        self.assertTrue(r2["success"])
        self.assertEqual(r2["current_card_index"], 1)

        # Total swipes for host on movie 0 must be exactly 1
        swipe_count = Swipe.objects.filter(session=self.session, user=self.host, movie_id=m0_id).count()
        self.assertEqual(swipe_count, 1)

    def test_conflicting_response_retry_rejected(self):
        """
        Retrying an already processed card with a conflicting reaction is strictly rejected:
        - Like followed by Like: idempotent.
        - Like followed by Dislike: raises ConflictingResponseError.
        - Super-Like followed by Like: raises ConflictingResponseError.
        - Dislike followed by Super-Like: raises ConflictingResponseError.
        - Original reaction and cursor remain unchanged.
        """
        m0_id = self.manifest[0]["movie_id"]
        m1_id = self.manifest[1]["movie_id"]
        m2_id = self.manifest[2]["movie_id"]

        # Case 1: Initial 'like' on card 0
        r1 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        self.assertFalse(r1["idempotent"])
        self.assertEqual(r1["next_card_index"], 1)

        # 1a. Retry with same reaction 'like' -> Idempotent
        r_retry_same = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        self.assertTrue(r_retry_same["idempotent"])

        # 1b. Retry with conflicting reaction 'dislike' -> Rejected with ConflictingResponseError
        with self.assertRaises(ConflictingResponseError) as ctx:
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "dislike")
        self.assertIn("Conflicting reaction 'dislike'", str(ctx.exception))

        # Verify card 0 reaction in database is still 'like'
        s0 = Swipe.objects.get(session=self.session, user=self.host, movie_id=m0_id)
        self.assertEqual(s0.reaction, "like")

        # Verify cursor remains at 1
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)

        # Case 2: Super-Like on card 1 followed by conflicting Like
        r2 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 1, m1_id, "superlike")
        self.assertEqual(r2["next_card_index"], 2)

        with self.assertRaises(ConflictingResponseError):
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, 1, m1_id, "like")

        s1 = Swipe.objects.get(session=self.session, user=self.host, movie_id=m1_id)
        self.assertEqual(s1.reaction, "superlike")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 2)

        # Case 3: Dislike on card 2 followed by conflicting Super-Like
        r3 = DeckAdvancementService.record_swipe_response(self.session.id, self.host, 2, m2_id, "dislike")
        self.assertEqual(r3["next_card_index"], 3)

        with self.assertRaises(ConflictingResponseError):
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, 2, m2_id, "superlike")

        s2 = Swipe.objects.get(session=self.session, user=self.host, movie_id=m2_id)
        self.assertEqual(s2.reaction, "dislike")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 3)
        self.assertEqual(self.agreement.resolved_card_index, 0)

    def test_out_of_order_responses_rejected(self):
        """Attempting to submit card 2 when cursor is at 0 raises OutOfOrderResponseError."""
        m2_id = self.manifest[2]["movie_id"]

        with self.assertRaises(OutOfOrderResponseError):
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, 2, m2_id, "like")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 0, "Cursor must not change on rejected request")

    def test_stale_manifest_movie_id_mismatch_rejected(self):
        """Submitting an invalid movie_id for card_index 0 raises StaleManifestError."""
        with self.assertRaises(StaleManifestError):
            DeckAdvancementService.record_swipe_response(
                self.session.id,
                self.host,
                0,
                999999,  # Wrong movie_id
                "like",
            )

    def test_out_of_bounds_card_index_rejected(self):
        """Card index < 0 or >= total_cards raises InvalidCardIndexError."""
        m0_id = self.manifest[0]["movie_id"]
        with self.assertRaises(InvalidCardIndexError):
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, -1, m0_id, "like")
        with self.assertRaises(InvalidCardIndexError):
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, 100, m0_id, "like")

    # -----------------------------------------------------------------
    # 4. Partner Lag Buffer & Session Completion
    # -----------------------------------------------------------------

    def test_partner_lag_buffer_limit(self):
        """When host gets 5 cards ahead of guest, waiting_for_partner flags True."""
        for k in range(5):
            m_id = self.manifest[k]["movie_id"]
            res = DeckAdvancementService.record_swipe_response(self.session.id, self.host, k, m_id, "like")

        self.assertEqual(res["partner_lag"], 5)
        self.assertTrue(res["waiting_for_partner"], "Partner lag >= 5 must trigger waiting_for_partner")

        # Delivery check for host
        h_card = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        self.assertTrue(h_card["waiting_for_partner"])

        # Guest catches up 1 card -> lag is now 4 (< 5) -> waiting_for_partner is False
        m0_id = self.manifest[0]["movie_id"]
        DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "like")

        h_card_after = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        self.assertFalse(h_card_after["waiting_for_partner"])
        self.assertEqual(h_card_after["partner_lag"], 4)

    def test_session_completion_on_final_card(self):
        """When both participants complete all cards, is_completed becomes True."""
        total = len(self.manifest)
        for k in range(total):
            m_id = self.manifest[k]["movie_id"]
            DeckAdvancementService.record_swipe_response(self.session.id, self.host, k, m_id, "like")
            res_g = DeckAdvancementService.record_swipe_response(self.session.id, self.guest, k, m_id, "like")

        self.assertTrue(res_g["is_completed"])
        self.assertEqual(res_g["resolved_card_index"], total)

        h_done = DeckAdvancementService.get_current_delivery_card(self.session, self.host)
        self.assertTrue(h_done["is_completed"])
        self.assertFalse(h_done["has_more"])
        self.assertIsNone(h_done["card"])

    # -----------------------------------------------------------------
    # 5. Undo Semantics
    # -----------------------------------------------------------------

    def test_undo_most_recent_swipe_succeeds(self):
        """Participant can undo their most recent swipe, regressing cursor."""
        m0_id = self.manifest[0]["movie_id"]
        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "dislike")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)

        # Undo card 0
        undo_res = DeckAdvancementService.undo_card_response(self.session.id, self.host, 0, m0_id)
        self.assertTrue(undo_res["success"])
        self.assertEqual(undo_res["host_card_index"], 0)

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 0)
        self.assertFalse(Swipe.objects.filter(session=self.session, user=self.host, movie_id=m0_id).exists())

    def test_undo_blocked_if_match_formed(self):
        """Cannot undo a swipe once a mutual match has been formed."""
        m0_id = self.manifest[0]["movie_id"]
        DeckAdvancementService.record_swipe_response(self.session.id, self.host, 0, m0_id, "like")
        DeckAdvancementService.record_swipe_response(self.session.id, self.guest, 0, m0_id, "like")

        # Mutual match exists now
        self.assertTrue(Match.objects.filter(session=self.session, movie_id=m0_id).exists())

        # Guest attempts to undo card 0 -> blocked!
        with self.assertRaises(UndoNotPermittedError):
            DeckAdvancementService.undo_card_response(self.session.id, self.guest, 0, m0_id)


class DeckStateAPITests(TestCase):
    """
    API Integration Tests for Deck Delivery, Swipe Response, and Undo Endpoints.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="api_host", password="password123")
        self.guest = User.objects.create_user(username="api_guest", password="password123")
        self.session = Session.objects.create(
            code="APIDEK",
            host=self.host,
            guest=self.guest,
        )
        self.client_host = APIClient()
        self.client_host.force_authenticate(user=self.host)
        self.client_guest = APIClient()
        self.client_guest.force_authenticate(user=self.guest)

        # Create movies
        self.movies = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=60000 + i,
                title=f"API Movie {i}",
                rating=7.5,
                release_date=date(2021, 1, 1),
            )
            self.movies.append(m)

        self.agreement = CollaborativeAgreement.objects.create(session=self.session)
        self.manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        self.agreement.deck_manifest = self.manifest
        self.agreement.save(update_fields=["deck_manifest"])

    def test_get_card_delivery_api(self):
        """GET /api/sessions/<id>/deck/card/ delivers active card."""
        url = f"/api/sessions/{self.session.id}/deck/card/"
        res = self.client_host.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["card_index"], 0)
        self.assertEqual(res.data["card"]["movie_id"], self.manifest[0]["movie_id"])

    def test_candidate_exhaustion_returns_structured_response_without_500(self):
        """GET /api/sessions/<id>/deck/card/ returns structured exhausted payload on InsufficientCandidatesError."""
        from unittest.mock import patch
        from core.services.manifest import InsufficientCandidatesError

        url = f"/api/sessions/{self.session.id}/deck/card/"
        with patch("core.services.deck_state.DeckAdvancementService.get_current_delivery_card", side_effect=InsufficientCandidatesError("Pool < 16")):
            res = self.client_host.get(url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["success"])
        self.assertTrue(res.data["exhausted"])
        self.assertTrue(res.data["proposal_required"])
        self.assertIn("Eligible candidate pool exhausted", res.data["error"])

    def test_legacy_session_returns_legacy_indicator(self):
        """GET /api/sessions/<id>/deck/card/ returns legacy indicator when session is legacy."""
        from unittest.mock import patch

        url = f"/api/sessions/{self.session.id}/deck/card/"
        with patch.object(Session.objects, "get", return_value=self.session):
            self.session.is_legacy = True
            try:
                res = self.client_host.get(url)
                self.assertEqual(res.status_code, status.HTTP_200_OK)
                self.assertFalse(res.data["success"])
                self.assertTrue(res.data["is_legacy"])
            finally:
                delattr(self.session, "is_legacy")

    def test_post_swipe_response_api(self):
        """POST /api/sessions/<id>/deck/swipe/ records response and advances cursor."""
        url = f"/api/sessions/{self.session.id}/deck/swipe/"
        m0_id = self.manifest[0]["movie_id"]

        payload = {
            "card_index": 0,
            "movie_id": m0_id,
            "reaction": "like",
        }
        res = self.client_host.post(url, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["next_card_index"], 1)
        self.assertFalse(res.data["jointly_resolved"])

    @patch("core.views.get_channel_layer")
    def test_post_swipe_broadcasts_websocket_events(self, mock_get_channel_layer):
        """POST /api/sessions/<id>/deck/swipe/ broadcasts swipe_event and match_event."""
        mock_layer = MagicMock()
        mock_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_layer
        url = f"/api/sessions/{self.session.id}/deck/swipe/"
        m0_id = self.manifest[0]["movie_id"]

        # 1. Host swipes like -> broadcasts swipe_event
        res_host = self.client_host.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
        )
        self.assertEqual(res_host.status_code, status.HTTP_200_OK)
        mock_layer.group_send.assert_any_call(
            f"session_{self.session.id}",
            {"type": "swipe_event", "user_id": self.host.id},
        )

        # 2. Guest swipes superlike on same card -> mutual match formed -> broadcasts match_event
        mock_layer.group_send.reset_mock()
        res_guest = self.client_guest.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "superlike"},
            format="json",
        )
        self.assertEqual(res_guest.status_code, status.HTTP_200_OK)
        self.assertTrue(res_guest.data["match_formed"])
        self.assertEqual(res_guest.data["superlike_attribution"], "guest")

        mock_layer.group_send.assert_any_call(
            f"session_{self.session.id}",
            {"type": "swipe_event", "user_id": self.guest.id},
        )
        # Check match_event was sent
        match_calls = [
            c for c in mock_layer.group_send.call_args_list
            if c[0][1].get("type") == "match_event"
        ]
        self.assertTrue(len(match_calls) >= 1)
        self.assertEqual(match_calls[0][0][1]["movie_id"], m0_id)
        self.assertEqual(match_calls[0][0][1]["superlike_attribution"], "guest")
        self.assertEqual(match_calls[0][0][1]["match_type"], "superlike")

    def test_post_swipe_conflict_returns_409_api(self):
        """POST /api/sessions/<id>/deck/swipe/ returns HTTP 409 on conflicting reaction retry."""
        url = f"/api/sessions/{self.session.id}/deck/swipe/"
        m0_id = self.manifest[0]["movie_id"]

        # 1. Initial swipe: 'like'
        res1 = self.client_host.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertFalse(res1.data["idempotent"])

        # 2. Duplicate retry with same reaction: 200 OK idempotent
        res2 = self.client_host.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["idempotent"])

        # 3. Conflicting retry with 'dislike': 409 CONFLICT
        res_conflict = self.client_host.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "dislike"},
            format="json",
        )
        self.assertEqual(res_conflict.status_code, status.HTTP_409_CONFLICT)
        self.assertFalse(res_conflict.data["success"])
        self.assertIn("Conflicting reaction", res_conflict.data["error"])

        # 4. Conflicting retry with 'superlike': 409 CONFLICT
        res_conflict2 = self.client_host.post(
            url,
            {"card_index": 0, "movie_id": m0_id, "reaction": "superlike"},
            format="json",
        )
        self.assertEqual(res_conflict2.status_code, status.HTTP_409_CONFLICT)

        # 5. Verify database integrity
        s0 = Swipe.objects.get(session=self.session, user=self.host, movie_id=m0_id)
        self.assertEqual(s0.reaction, "like")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)

    def test_post_swipe_undo_api(self):
        """POST /api/sessions/<id>/deck/undo/ reverses most recent swipe."""
        m0_id = self.manifest[0]["movie_id"]
        # First swipe
        self.client_host.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            {"card_index": 0, "movie_id": m0_id, "reaction": "dislike"},
            format="json",
        )

        # Undo
        res = self.client_host.post(
            f"/api/sessions/{self.session.id}/deck/undo/",
            {"card_index": 0, "movie_id": m0_id},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["host_card_index"], 0)


class DeckStateConcurrencyTests(TransactionTestCase):
    """
    Concurrency and Race-Condition Tests for DeckAdvancementService.
    Uses TransactionTestCase so transactions commit and rollback across threads.
    Tests concurrent submissions by host & guest, and concurrent duplicates by one user.
    Note: SQLite uses file-level locking and locks the entire database table across threads;
    PostgreSQL uses fine-grained row-level locks (select_for_update).
    """

    def setUp(self):
        if connection.vendor == "sqlite":
            self.skipTest(
                "SQLite uses file-level locks that block multi-threaded writes ('database table is locked'). "
                "Concurrency row-locking is active and designed for PostgreSQL select_for_update()."
            )
        self.host = User.objects.create_user(username="concur_host", password="password123")
        self.guest = User.objects.create_user(username="concur_guest", password="password123")
        self.session = Session.objects.create(
            code="CONCUR",
            host=self.host,
            guest=self.guest,
        )
        self.movies = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=70000 + i,
                title=f"Concur Film {i}",
                rating=8.0,
                release_date=date(2022, 1, 1),
            )
            self.movies.append(m)

        self.agreement = CollaborativeAgreement.objects.create(session=self.session)
        self.manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        self.agreement.deck_manifest = self.manifest
        self.agreement.save(update_fields=["deck_manifest"])

    def test_concurrent_host_and_guest_submissions_resolve_atomically(self):
        """
        When Host and Guest submit swipes for card 0 in parallel threads:
        Both swipes must succeed, exactly 1 match formed, and card jointly resolved.
        """
        m0_id = self.manifest[0]["movie_id"]

        def submit_host():
            return DeckAdvancementService.record_swipe_response(
                session_id=self.session.id,
                user=self.host,
                card_index=0,
                movie_id=m0_id,
                reaction="like",
            )

        def submit_guest():
            return DeckAdvancementService.record_swipe_response(
                session_id=self.session.id,
                user=self.guest,
                card_index=0,
                movie_id=m0_id,
                reaction="like",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_h = executor.submit(submit_host)
            future_g = executor.submit(submit_guest)
            res_h = future_h.result()
            res_g = future_g.result()

        self.assertTrue(res_h["success"])
        self.assertTrue(res_g["success"])

        # Check resolution state
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)
        self.assertEqual(self.agreement.guest_card_index, 1)
        self.assertEqual(self.agreement.resolved_card_index, 1)

        # Exactly 1 match record
        matches = Match.objects.filter(session=self.session, movie_id=m0_id)
        self.assertEqual(matches.count(), 1)

    def test_concurrent_duplicate_submissions_by_single_user(self):
        """
        When a user fires duplicate requests for card 0 concurrently (e.g. rapid double-tap):
        Only 1 swipe is recorded and both return without error (idempotent).
        """
        m0_id = self.manifest[0]["movie_id"]

        def submit_duplicate():
            return DeckAdvancementService.record_swipe_response(
                session_id=self.session.id,
                user=self.host,
                card_index=0,
                movie_id=m0_id,
                reaction="like",
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_1 = executor.submit(submit_duplicate)
            future_2 = executor.submit(submit_duplicate)
            res_1 = future_1.result()
            res_2 = future_2.result()

        self.assertTrue(res_1["success"])
        self.assertTrue(res_2["success"])

        # At least one must be identified as idempotent or both succeeded cleanly
        swipes = Swipe.objects.filter(session=self.session, user=self.host, movie_id=m0_id)
        self.assertEqual(swipes.count(), 1, "Exactly one Swipe record must exist despite concurrent double-tap")

        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)
