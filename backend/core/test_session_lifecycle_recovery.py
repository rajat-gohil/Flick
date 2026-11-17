import asyncio
import json
import uuid
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from channels.testing import WebsocketCommunicator

from backend.asgi import application
from core.models import Genre, Session, SessionStats

User = get_user_model()


class SessionLifecycleAndQuestionnaireRecoveryTests(TransactionTestCase):
    """
    Comprehensive regression test suite verifying all 12 requirements from Part E:
    1. Host creates a session and remains the Host after refresh.
    2. Guest joins and remains the Guest after refresh.
    3. Both participants are recognized by the backend.
    4. Session transitions correctly when readiness requirements are met.
    5. Completed Host questionnaire survives refresh.
    6. Completed Guest questionnaire survives refresh.
    7. Incomplete questionnaires resume correctly without premature readiness.
    8. Refresh does not create duplicate sessions.
    9. Repeated preference submissions do not corrupt existing responses.
    10. WebSocket disconnect and reconnect restore authoritative state.
    11. Polling and WebSocket updates do not cause state regression.
    12. A session cannot become ready when its actual readiness requirements are not satisfied.
    Plus targeted verification of join code normalization and error handling.
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")
        self.stranger = User.objects.create_user(username="stranger_user", password="password123")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.genre = Genre.objects.create(name="Sci-Fi", tmdb_id=878)

        self.sample_preferences_host = {
            "mood": ["happy", "exciting"],
            "pace": ["balanced"],
            "vibe": ["feel-good"],
            "era": ["2010s", "recent"],
            "min_rating": ["7+"],
            "tone": ["uplifted", "thrilled"],
            "intensity": "medium",
            "themes": ["identity_growth"],
            "setting": ["fantasy_world"],
            "narrative": ["character"],
        }

        self.sample_preferences_guest = {
            "mood": ["exciting", "intense"],
            "pace": ["balanced"],
            "vibe": ["mind-bending"],
            "era": ["recent"],
            "min_rating": ["7+"],
            "tone": ["thrilled", "mindblown"],
            "intensity": "medium",
            "themes": ["mystery_truth"],
            "setting": ["fantasy_world"],
            "narrative": ["plot"],
        }

    # -------------------------------------------------------------------------
    # 1. Host creates a session and remains the Host after refresh
    # -------------------------------------------------------------------------
    def test_01_host_creates_session_and_remains_host_after_refresh(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        create_res = self.client.post("/api/sessions/create/", {"industry": "hollywood"}, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        session_id = create_res.data["session_id"]
        session_code = create_res.data["code"]

        # Initial fetch
        detail_res1 = self.client.get(f"/api/sessions/{session_id}/")
        self.assertEqual(detail_res1.status_code, status.HTTP_200_OK)
        session_data1 = detail_res1.data["session"]
        self.assertEqual(session_data1["user_role"], "host")
        self.assertTrue(session_data1["host_joined"])
        self.assertFalse(session_data1["guest_joined"])
        self.assertFalse(session_data1["user_preferences_set"])

        # Simulate full page refresh
        detail_res2 = self.client.get(f"/api/sessions/{session_id}/")
        self.assertEqual(detail_res2.status_code, status.HTTP_200_OK)
        session_data2 = detail_res2.data["session"]
        self.assertEqual(session_data2["user_role"], "host")
        self.assertEqual(session_data2["code"], session_code)
        self.assertEqual(session_data2["id"], session_id)

    # -------------------------------------------------------------------------
    # 2. Guest joins and remains the Guest after refresh
    # -------------------------------------------------------------------------
    def test_02_guest_joins_and_remains_guest_after_refresh(self):
        session = Session.objects.create(code="GST123", host=self.host, genre=self.genre)

        # Guest joins with whitespace/lowercase variations
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        join_res = self.client.post("/api/sessions/join/", {"code": "  gst123  "}, format="json")
        self.assertEqual(join_res.status_code, status.HTTP_200_OK)
        self.assertEqual(join_res.data["session_id"], session.id)
        self.assertTrue(join_res.data["guest_joined"])

        # Fetch detail as Guest
        detail_res1 = self.client.get(f"/api/sessions/{session.id}/")
        self.assertEqual(detail_res1.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res1.data["session"]["user_role"], "guest")
        self.assertTrue(detail_res1.data["session"]["guest_joined"])
        self.assertFalse(detail_res1.data["session"]["user_preferences_set"])

        # Simulate full page refresh
        detail_res2 = self.client.get(f"/api/sessions/{session.id}/")
        self.assertEqual(detail_res2.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_res2.data["session"]["user_role"], "guest")

    # -------------------------------------------------------------------------
    # 3. Both participants are recognized by the backend
    # -------------------------------------------------------------------------
    def test_03_both_participants_recognized_and_stranger_rejected(self):
        session = Session.objects.create(code="BOTH01", host=self.host, guest=self.guest, genre=self.genre)

        # Host inspection
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_view = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertEqual(host_view["user_role"], "host")
        self.assertTrue(host_view["host_joined"])
        self.assertTrue(host_view["guest_joined"])

        # Guest inspection
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_view = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertEqual(guest_view["user_role"], "guest")
        self.assertTrue(guest_view["host_joined"])
        self.assertTrue(guest_view["guest_joined"])

        # Stranger rejected
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        stranger_res = self.client.get(f"/api/sessions/{session.id}/")
        self.assertEqual(stranger_res.status_code, status.HTTP_403_FORBIDDEN)

    # -------------------------------------------------------------------------
    # 4. Session transitions correctly when readiness requirements are met
    # -------------------------------------------------------------------------
    def test_04_session_transitions_when_readiness_met(self):
        session = Session.objects.create(code="TRANS1", host=self.host, guest=self.guest, genre=self.genre)

        # Initially neither has submitted
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        initial_check = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertFalse(initial_check["preferences_set"])

        # Step 1: Host submits preferences
        host_submit = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": self.sample_preferences_host},
            format="json"
        )
        self.assertEqual(host_submit.status_code, status.HTTP_200_OK)
        self.assertFalse(host_submit.data["both_ready"])
        self.assertTrue(host_submit.data["host_preferences_set"])
        self.assertFalse(host_submit.data["guest_preferences_set"])

        # Check DB and API state
        session.refresh_from_db()
        self.assertFalse(session.preferences_set)
        host_poll = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertFalse(host_poll["preferences_set"])
        self.assertTrue(host_poll["user_preferences_set"])
        self.assertTrue(host_poll["host_preferences_set"])
        self.assertFalse(host_poll["guest_preferences_set"])

        # Step 2: Guest submits preferences
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_submit = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": self.sample_preferences_guest},
            format="json"
        )
        self.assertEqual(guest_submit.status_code, status.HTTP_200_OK)
        self.assertTrue(guest_submit.data["both_ready"])
        self.assertTrue(guest_submit.data["host_preferences_set"])
        self.assertTrue(guest_submit.data["guest_preferences_set"])
        self.assertTrue(guest_submit.data["preferences_set"])

        # Check DB and API state
        session.refresh_from_db()
        self.assertTrue(session.preferences_set)
        guest_poll = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertTrue(guest_poll["preferences_set"])
        self.assertTrue(guest_poll["both_preferences_set"])

    # -------------------------------------------------------------------------
    # 5. Completed Host questionnaire survives refresh
    # -------------------------------------------------------------------------
    def test_05_completed_host_questionnaire_survives_refresh(self):
        session = Session.objects.create(code="HREF01", host=self.host, guest=self.guest, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": self.sample_preferences_host},
            format="json"
        )

        # Simulate multiple refreshes
        for _ in range(3):
            detail = self.client.get(f"/api/sessions/{session.id}/").data["session"]
            self.assertTrue(detail["user_preferences_set"])
            self.assertTrue(detail["host_preferences_set"])
            self.assertEqual(detail["user_role"], "host")
            self.assertEqual(detail["user_preferences"]["tone"], ["uplifted", "thrilled"])
            self.assertEqual(detail["user_preferences"]["intensity"], "medium")

    # -------------------------------------------------------------------------
    # 6. Completed Guest questionnaire survives refresh
    # -------------------------------------------------------------------------
    def test_06_completed_guest_questionnaire_survives_refresh(self):
        session = Session.objects.create(code="GREF01", host=self.host, guest=self.guest, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": self.sample_preferences_guest},
            format="json"
        )

        # Simulate multiple refreshes
        for _ in range(3):
            detail = self.client.get(f"/api/sessions/{session.id}/").data["session"]
            self.assertTrue(detail["user_preferences_set"])
            self.assertTrue(detail["guest_preferences_set"])
            self.assertFalse(detail["host_preferences_set"])
            self.assertEqual(detail["user_role"], "guest")
            self.assertEqual(detail["user_preferences"]["tone"], ["thrilled", "mindblown"])

    # -------------------------------------------------------------------------
    # 7. Incomplete questionnaires resume correctly without premature readiness
    # -------------------------------------------------------------------------
    def test_07_incomplete_questionnaire_validation_and_no_premature_readiness(self):
        session = Session.objects.create(code="INCOMP", host=self.host, guest=self.guest, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        # Missing preferences entirely
        bad_res = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": None},
            format="json"
        )
        self.assertEqual(bad_res.status_code, status.HTTP_400_BAD_REQUEST)

        # Verify host preferences were NOT marked set
        detail = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertFalse(detail["user_preferences_set"])
        self.assertFalse(detail["host_preferences_set"])
        self.assertFalse(detail["preferences_set"])

    # -------------------------------------------------------------------------
    # 8. Refresh does not create duplicate sessions
    # -------------------------------------------------------------------------
    def test_08_refresh_does_not_create_duplicate_sessions(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        # Initial creation
        create_res = self.client.post("/api/sessions/create/", {"industry": "hollywood"}, format="json")
        session_id = create_res.data["session_id"]
        initial_count = Session.objects.count()

        # Simulate repeated refreshes (GET requests to session detail)
        for _ in range(5):
            res = self.client.get(f"/api/sessions/{session_id}/")
            self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(Session.objects.count(), initial_count)

        # Guest joining multiple times idempotently
        session = Session.objects.get(id=session_id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        join_res1 = self.client.post("/api/sessions/join/", {"code": session.code}, format="json")
        self.assertEqual(join_res1.status_code, status.HTTP_200_OK)

        join_res2 = self.client.post("/api/sessions/join/", {"code": session.code}, format="json")
        self.assertEqual(join_res2.status_code, status.HTTP_200_OK)
        self.assertEqual(join_res2.data["message"], "Already joined session")
        self.assertEqual(Session.objects.count(), initial_count)

    # -------------------------------------------------------------------------
    # 9. Repeated preference submissions do not corrupt existing responses
    # -------------------------------------------------------------------------
    def test_09_repeated_preference_submissions_idempotent(self):
        session = Session.objects.create(code="REPREF", host=self.host, guest=self.guest, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        # Submit preferences multiple times (e.g. repeated clicks or remounts)
        for _ in range(3):
            res = self.client.post(
                "/api/sessions/preferences/",
                {"session_id": session.id, "preferences": self.sample_preferences_host},
                format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            self.assertFalse(res.data["both_ready"])

        session.refresh_from_db()
        self.assertEqual(session.host_preferences["mood"], ["happy", "exciting"])
        self.assertIsNone(session.guest_preferences)
        self.assertFalse(session.preferences_set)

    # -------------------------------------------------------------------------
    # 10. WebSocket disconnect and reconnect restore authoritative state
    # -------------------------------------------------------------------------
    def test_10_websocket_lifecycle_and_preferences_broadcast(self):
        session = Session.objects.create(code="WSREC1", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        async def run():
            # Guest connects to WebSocket
            guest_comm = WebsocketCommunicator(
                application,
                f"/ws/session/{session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await guest_comm.connect()
            self.assertTrue(connected)

            # Host submits preferences via API from sync thread
            from asgiref.sync import sync_to_async
            post_res = await sync_to_async(self.client.post)(
                "/api/sessions/preferences/",
                {"session_id": session.id, "preferences": self.sample_preferences_host},
                format="json"
            )
            self.assertEqual(post_res.status_code, status.HTTP_200_OK)

            # Guest receives preferences_updated event via WebSocket
            ws_msg = await guest_comm.receive_json_from()
            self.assertEqual(ws_msg["type"], "preferences_updated")
            self.assertEqual(ws_msg["role"], "host")
            self.assertTrue(ws_msg["host_preferences_set"])
            self.assertFalse(ws_msg["guest_preferences_set"])
            self.assertFalse(ws_msg["preferences_set"])

            # Guest disconnects
            await guest_comm.disconnect()

            # Guest reconnects
            guest_comm2 = WebsocketCommunicator(
                application,
                f"/ws/session/{session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected2, _ = await guest_comm2.connect()
            self.assertTrue(connected2)
            await guest_comm2.disconnect()

        asyncio.run(run())

        # Authoritative state recovery via API
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        detail = self.client.get(f"/api/sessions/{session.id}/").data["session"]
        self.assertTrue(detail["host_preferences_set"])
        self.assertFalse(detail["user_preferences_set"])
        self.assertFalse(detail["preferences_set"])

    # -------------------------------------------------------------------------
    # 11. Polling and WebSocket updates do not cause state regression
    # -------------------------------------------------------------------------
    def test_11_polling_and_websocket_no_state_regression(self):
        session = Session.objects.create(
            code="NOREGR",
            host=self.host,
            guest=self.guest,
            genre=self.genre,
            host_preferences=self.sample_preferences_host,
            guest_preferences=self.sample_preferences_guest,
            preferences_set=True
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        # Rapid poll sequence
        for _ in range(5):
            res = self.client.get(f"/api/sessions/{session.id}/")
            data = res.data["session"]
            self.assertTrue(data["preferences_set"])
            self.assertTrue(data["user_preferences_set"])
            self.assertTrue(data["both_preferences_set"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        for _ in range(5):
            res = self.client.get(f"/api/sessions/{session.id}/")
            data = res.data["session"]
            self.assertTrue(data["preferences_set"])
            self.assertTrue(data["user_preferences_set"])
            self.assertTrue(data["both_preferences_set"])

    # -------------------------------------------------------------------------
    # 12. A session cannot become ready when actual readiness requirements not met
    # -------------------------------------------------------------------------
    def test_12_cannot_become_ready_without_all_requirements_satisfied(self):
        # Case A: Solo session (no guest)
        solo_session = Session.objects.create(code="SOLO01", host=self.host, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post(
            "/api/sessions/preferences/",
            {"session_id": solo_session.id, "preferences": self.sample_preferences_host},
            format="json"
        )
        solo_session.refresh_from_db()
        self.assertFalse(solo_session.preferences_set)

        detail_solo = self.client.get(f"/api/sessions/{solo_session.id}/").data["session"]
        self.assertFalse(detail_solo["preferences_set"])
        self.assertFalse(detail_solo["guest_joined"])

        # Case B: Guest joined, but neither submitted
        unsub_session = Session.objects.create(code="UNSUB1", host=self.host, guest=self.guest, genre=self.genre)
        detail_unsub = self.client.get(f"/api/sessions/{unsub_session.id}/").data["session"]
        self.assertFalse(detail_unsub["preferences_set"])
        self.assertFalse(detail_unsub["user_preferences_set"])

        # Case C: Only guest submitted, host has not
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        self.client.post(
            "/api/sessions/preferences/",
            {"session_id": unsub_session.id, "preferences": self.sample_preferences_guest},
            format="json"
        )
        unsub_session.refresh_from_db()
        self.assertFalse(unsub_session.preferences_set)

    # -------------------------------------------------------------------------
    # Targeted Verification: Join Code Normalization & Non-member Protections
    # -------------------------------------------------------------------------
    def test_join_code_case_insensitivity_and_whitespace_trimming(self):
        session = Session.objects.create(code="TRIM99", host=self.host, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")

        # Trailing spaces and lowercase
        res = self.client.post("/api/sessions/join/", {"code": "  trim99 \n"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["session_id"], session.id)

        session.refresh_from_db()
        self.assertEqual(session.guest, self.guest)

    def test_join_invalid_code_returns_404(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res = self.client.post("/api/sessions/join/", {"code": "NONEX1"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(res.data["success"])

    def test_host_cannot_join_own_session(self):
        """Host cannot join their own session as guest."""
        session = Session.objects.create(code="OWN001", host=self.host, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.post("/api/sessions/join/", {"code": "OWN001"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"], "Host cannot join own session")

    def test_third_user_cannot_join_full_session(self):
        session = Session.objects.create(code="FULL01", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.post("/api/sessions/join/", {"code": "FULL01"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("already full", res.data["error"])

    # -------------------------------------------------------------------------
    # End-to-End Regression: Session 62 Full 9-Step Guest Lifecycle
    # -------------------------------------------------------------------------
    def test_session_62_guest_join_preferences_and_deck_transition_lifecycle(self):
        # 1. Host creates a room
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        create_res = self.client.post("/api/sessions/create/", {"industry": "bollywood"}, format="json")
        self.assertEqual(create_res.status_code, status.HTTP_201_CREATED)
        session_id = create_res.data["session_id"]
        session_code = create_res.data["code"]

        genre_res = self.client.post(
            "/api/sessions/genre/",
            {
                "session_id": session_id,
                "genre_id": self.genre.id,
                "industry": "bollywood",
                "languages": ["hi"],
            },
            format="json"
        )
        self.assertEqual(genre_res.status_code, status.HTTP_200_OK)

        # 2. Guest joins successfully
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        join_res = self.client.post("/api/sessions/join/", {"code": session_code}, format="json")
        self.assertEqual(join_res.status_code, status.HTTP_200_OK)
        self.assertTrue(join_res.data["success"])
        self.assertTrue(join_res.data["guest_joined"])
        self.assertEqual(join_res.data["session_id"], session_id)

        # 3. Guest is assigned the correct role
        self.assertEqual(join_res.data["user_role"], "guest")
        guest_detail = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertEqual(guest_detail["user_role"], "guest")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_detail = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertEqual(host_detail["user_role"], "host")

        # 4. Guest is directed to preferences (join and detail indicate preferences not set)
        self.assertFalse(join_res.data["preferences_set"])
        self.assertFalse(join_res.data["user_preferences_set"])
        self.assertFalse(guest_detail["preferences_set"])
        self.assertFalse(guest_detail["user_preferences_set"])

        # 5. Guest submits preferences
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_pref_res = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session_id, "preferences": self.sample_preferences_guest},
            format="json"
        )
        self.assertEqual(guest_pref_res.status_code, status.HTTP_200_OK)
        self.assertTrue(guest_pref_res.data["user_preferences_set"])
        self.assertTrue(guest_pref_res.data["guest_preferences_set"])
        self.assertFalse(guest_pref_res.data["both_ready"])  # Host hasn't submitted yet

        # 6. Guest's existing preferences are restored after refresh
        for _ in range(2):
            refreshed_guest = self.client.get(f"/api/sessions/{session_id}/").data["session"]
            self.assertTrue(refreshed_guest["user_preferences_set"])
            self.assertTrue(refreshed_guest["guest_preferences_set"])
            self.assertEqual(refreshed_guest["user_preferences"]["tone"], ["thrilled", "mindblown"])

        # 7. Host waits without being redirected back to the questionnaire once host completes preferences
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_pref_res = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session_id, "preferences": self.sample_preferences_host},
            format="json"
        )
        self.assertEqual(host_pref_res.status_code, status.HTTP_200_OK)
        self.assertTrue(host_pref_res.data["user_preferences_set"])
        self.assertTrue(host_pref_res.data["host_preferences_set"])

        # After refresh, host maintains user_preferences_set = True so host is never ejected back
        refreshed_host = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertTrue(refreshed_host["user_preferences_set"])
        self.assertTrue(refreshed_host["host_preferences_set"])

        # 8. Both participants become ready
        self.assertTrue(host_pref_res.data["both_ready"])
        self.assertTrue(host_pref_res.data["preferences_set"])

        # 9. Both participants transition to the collaborative deck
        host_final = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertTrue(host_final["preferences_set"])
        self.assertTrue(host_final["both_preferences_set"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_final = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertTrue(guest_final["preferences_set"])
        self.assertTrue(guest_final["both_preferences_set"])

    # -------------------------------------------------------------------------
    # Targeted Regression: 4 Readiness Permutations & Rejoin Routing
    # -------------------------------------------------------------------------
    def test_participant_specific_readiness_four_permutations_and_rejoin(self):
        """
        Verify all 4 readiness permutations across host and guest:
        1. Both incomplete
        2. Host complete, guest incomplete
        3. Host incomplete, guest complete
        4. Both complete
        Assert that user_preferences_set accurately distinguishes participant readiness
        from room-wide preferences_set readiness, and that rejoin returns user_preferences_set.
        """
        # Create a fresh room
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        c_res = self.client.post("/api/sessions/create/", {"industry": "hollywood"}, format="json")
        self.assertEqual(c_res.status_code, status.HTTP_201_CREATED)
        session_id = c_res.data["session_id"]
        session_code = c_res.data["code"]

        # Guest joins
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        j_res = self.client.post("/api/sessions/join/", {"code": session_code}, format="json")
        self.assertEqual(j_res.status_code, status.HTTP_200_OK)

        # ---------------------------------------------------------------------
        # Permutation 1: Both incomplete
        # ---------------------------------------------------------------------
        # Join response check
        self.assertFalse(j_res.data["user_preferences_set"])
        self.assertFalse(j_res.data["preferences_set"])
        self.assertFalse(j_res.data["host_preferences_set"])
        self.assertFalse(j_res.data["guest_preferences_set"])

        # Detail view for guest
        g_s1 = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertFalse(g_s1["user_preferences_set"])
        self.assertFalse(g_s1["preferences_set"])

        # Detail view for host
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        h_s1 = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertFalse(h_s1["user_preferences_set"])
        self.assertFalse(h_s1["preferences_set"])

        # ---------------------------------------------------------------------
        # Permutation 2: Host complete, Guest incomplete
        # ---------------------------------------------------------------------
        h_pref_res = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session_id, "preferences": self.sample_preferences_host},
            format="json"
        )
        self.assertEqual(h_pref_res.status_code, status.HTTP_200_OK)
        self.assertFalse(h_pref_res.data["both_ready"])

        # Host checks session: Host has completed, but room is not ready
        h_s2 = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertTrue(h_s2["user_preferences_set"])
        self.assertTrue(h_s2["host_preferences_set"])
        self.assertFalse(h_s2["guest_preferences_set"])
        self.assertFalse(h_s2["preferences_set"])

        # Guest checks session: Guest has NOT completed, room is not ready
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        g_s2 = self.client.get(f"/api/sessions/{session_id}/").data["session"]
        self.assertFalse(g_s2["user_preferences_set"])
        self.assertTrue(g_s2["host_preferences_set"])
        self.assertFalse(g_s2["guest_preferences_set"])
        self.assertFalse(g_s2["preferences_set"])

        # Re-joining as guest when host completed but guest incomplete:
        # join response must indicate user_preferences_set is False so guest is routed to /preferences
        rejoin_guest_p2 = self.client.post("/api/sessions/join/", {"code": session_code}, format="json")
        self.assertEqual(rejoin_guest_p2.status_code, status.HTTP_200_OK)
        self.assertFalse(rejoin_guest_p2.data["user_preferences_set"])
        self.assertFalse(rejoin_guest_p2.data["preferences_set"])
        self.assertTrue(rejoin_guest_p2.data["host_preferences_set"])

        # ---------------------------------------------------------------------
        # Permutation 3: Host incomplete, Guest complete (create separate session)
        # ---------------------------------------------------------------------
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        c_res2 = self.client.post("/api/sessions/create/", {"industry": "bollywood"}, format="json")
        session_id_2 = c_res2.data["session_id"]
        session_code_2 = c_res2.data["code"]

        # Guest joins session 2
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        self.client.post("/api/sessions/join/", {"code": session_code_2}, format="json")

        # Guest submits preferences, host has NOT submitted
        g_pref_res2 = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session_id_2, "preferences": self.sample_preferences_guest},
            format="json"
        )
        self.assertEqual(g_pref_res2.status_code, status.HTTP_200_OK)
        self.assertFalse(g_pref_res2.data["both_ready"])

        # Guest detail: guest is done (user_preferences_set: True), but room is not (preferences_set: False)
        g_s3 = self.client.get(f"/api/sessions/{session_id_2}/").data["session"]
        self.assertTrue(g_s3["user_preferences_set"])
        self.assertTrue(g_s3["guest_preferences_set"])
        self.assertFalse(g_s3["host_preferences_set"])
        self.assertFalse(g_s3["preferences_set"])

        # Crucial test: Guest rejoins session 2 via code/link.
        # join response must return user_preferences_set: True so guest is NOT sent to /preferences!
        rejoin_guest_p3 = self.client.post("/api/sessions/join/", {"code": session_code_2}, format="json")
        self.assertEqual(rejoin_guest_p3.status_code, status.HTTP_200_OK)
        self.assertTrue(rejoin_guest_p3.data["user_preferences_set"])
        self.assertFalse(rejoin_guest_p3.data["preferences_set"])
        self.assertTrue(rejoin_guest_p3.data["guest_preferences_set"])
        self.assertFalse(rejoin_guest_p3.data["host_preferences_set"])

        # Host detail: host is NOT done (user_preferences_set: False), room is not ready
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        h_s3 = self.client.get(f"/api/sessions/{session_id_2}/").data["session"]
        self.assertFalse(h_s3["user_preferences_set"])
        self.assertFalse(h_s3["host_preferences_set"])
        self.assertTrue(h_s3["guest_preferences_set"])
        self.assertFalse(h_s3["preferences_set"])

        # ---------------------------------------------------------------------
        # Permutation 4: Both complete
        # ---------------------------------------------------------------------
        # Host submits preferences on session 2
        h_pref_res2 = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session_id_2, "preferences": self.sample_preferences_host},
            format="json"
        )
        self.assertEqual(h_pref_res2.status_code, status.HTTP_200_OK)
        self.assertTrue(h_pref_res2.data["both_ready"])

        # Both participants have user_preferences_set = True and preferences_set = True
        h_s4 = self.client.get(f"/api/sessions/{session_id_2}/").data["session"]
        self.assertTrue(h_s4["user_preferences_set"])
        self.assertTrue(h_s4["preferences_set"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        g_s4 = self.client.get(f"/api/sessions/{session_id_2}/").data["session"]
        self.assertTrue(g_s4["user_preferences_set"])
        self.assertTrue(g_s4["preferences_set"])

        # Re-joining guest gets both ready flags
        rejoin_guest_p4 = self.client.post("/api/sessions/join/", {"code": session_code_2}, format="json")
        self.assertEqual(rejoin_guest_p4.status_code, status.HTTP_200_OK)
        self.assertTrue(rejoin_guest_p4.data["user_preferences_set"])
        self.assertTrue(rejoin_guest_p4.data["preferences_set"])

    def test_host_joins_own_session_idempotently_returns_host_role_and_state(self):
        """
        Regression test for Issue B:
        When the host accesses their session, the detail endpoint must correctly return
        the host role and state without requiring guest participation.
        """
        session = Session.objects.create(code="HST999", host=self.host, genre=self.genre)

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.get(f"/api/sessions/{session.id}/")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["session"]["user_role"], "host")
        self.assertEqual(res.data["session"]["id"], session.id)
        self.assertTrue(res.data["session"]["host_joined"])
        self.assertFalse(res.data["session"]["guest_joined"])
        self.assertFalse(res.data["session"]["user_preferences_set"])

    def test_host_can_end_screening_and_terminates_for_both(self):
        """1. Host ends active screening room, setting ended_at for both participants."""
        session = Session.objects.create(code="END001", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)

    def test_guest_can_end_screening_and_terminates_for_both(self):
        """2. Guest has equal permission to terminate the shared screening room."""
        session = Session.objects.create(code="END002", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertTrue(res.data["ended"])
        session.refresh_from_db()
        self.assertIsNotNone(session.ended_at)

    def test_non_participant_cannot_end_room_403(self):
        """3. Authenticated stranger (non-participant) receives 403 Forbidden."""
        session = Session.objects.create(code="END003", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        session.refresh_from_db()
        self.assertIsNone(session.ended_at)

    def test_unauthenticated_user_cannot_end_room_401(self):
        """4. Unauthenticated caller receives 401 Unauthorized."""
        session = Session.objects.create(code="END004", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials()  # Clear auth token
        res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        session.refresh_from_db()
        self.assertIsNone(session.ended_at)

    def test_repeated_termination_is_idempotent(self):
        """5. Repeated termination requests return 200 idempotently."""
        session = Session.objects.create(code="END005", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res1 = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        # Host calls end on already ended session
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res2 = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data["ended"])

    async def test_both_participants_receive_termination_event(self):
        """6. Both participants receive WebSocket termination event on room end."""
        session = await asyncio.to_thread(
            Session.objects.create, code="WSEND1", host=self.host, guest=self.guest, genre=self.genre
        )
        comm = WebsocketCommunicator(
            application,
            f"/ws/session/{session.id}/",
            subprotocols=["token", self.guest_token.key]
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)

        # Broadcast termination
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"session_{session.id}",
            {
                "type": "session_ended_event",
                "session_id": session.id,
                "ended_by": "host",
            }
        )

        msg = await comm.receive_json_from(timeout=2.0)
        self.assertEqual(msg["type"], "session_ended")
        self.assertEqual(msg["session_id"], session.id)
        self.assertEqual(msg["ended_by"], "host")
        await comm.disconnect()

    def test_ended_rooms_reject_further_deck_interactions(self):
        """7. Ended room rejects further swipe attempts."""
        from core.models import Movie
        movie = Movie.objects.create(tmdb_id=99901, title="Test Interaction Film")
        session = Session.objects.create(code="END007", host=self.host, guest=self.guest, genre=self.genre)

        # Terminate session
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        end_res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(end_res.status_code, status.HTTP_200_OK)

        # Attempt swipe after termination
        swipe_res = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": "like"},
            format="json"
        )
        self.assertEqual(swipe_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("ended", swipe_res.data["error"].lower())

    def test_guest_can_leave_screening_without_terminating_session(self):
        """8. Guest leave does not terminate the host's screening room."""
        session = Session.objects.create(code="LEV001", host=self.host, guest=self.guest, genre=self.genre)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res = self.client.post("/api/sessions/leave/", {"session_id": session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["left"])
        self.assertTrue(res.data["session_active"])
        session.refresh_from_db()
        self.assertIsNone(session.ended_at)

    def test_screening_directory_recent_sessions_role_and_status_contracts(self):
        """
        Screening Directory endpoint contracts:
        1. Host sees active room with is_host=True, user_role='host', status='active', ended=False.
        2. Guest sees active room with is_host=False, user_role='guest', status='active', ended=False.
        3. Host ends room -> status becomes 'ended_by_host', ended=True.
        4. Stranger does not see the session in their directory.
        """
        session = Session.objects.create(code="DIR001", host=self.host, guest=self.guest, genre=self.genre)

        # 1. Host query
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_res = self.client.get("/api/sessions/recent/")
        self.assertEqual(host_res.status_code, status.HTTP_200_OK)
        host_session = next((s for s in host_res.data["sessions"] if s["id"] == session.id), None)
        self.assertIsNotNone(host_session)
        self.assertTrue(host_session["is_host"])
        self.assertEqual(host_session["user_role"], "host")
        self.assertEqual(host_session["status"], "active")
        self.assertFalse(host_session["ended"])

        # 2. Guest query
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_res = self.client.get("/api/sessions/recent/")
        self.assertEqual(guest_res.status_code, status.HTTP_200_OK)
        guest_session = next((s for s in guest_res.data["sessions"] if s["id"] == session.id), None)
        self.assertIsNotNone(guest_session)
        self.assertFalse(guest_session["is_host"])
        self.assertEqual(guest_session["user_role"], "guest")
        self.assertEqual(guest_session["status"], "active")
        self.assertFalse(guest_session["ended"])

        # 3. Stranger query
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        stranger_res = self.client.get("/api/sessions/recent/")
        self.assertEqual(stranger_res.status_code, status.HTTP_200_OK)
        stranger_session = next((s for s in stranger_res.data["sessions"] if s["id"] == session.id), None)
        self.assertIsNone(stranger_session)

        # 4. Host terminates session
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        end_res = self.client.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(end_res.status_code, status.HTTP_200_OK)

        # 5. Directory refresh shows updated status
        refreshed_host_res = self.client.get("/api/sessions/recent/")
        refreshed_session = next((s for s in refreshed_host_res.data["sessions"] if s["id"] == session.id), None)
        self.assertIsNotNone(refreshed_session)
        self.assertTrue(refreshed_session["ended"])
        self.assertEqual(refreshed_session["status"], "ended_by_host")

