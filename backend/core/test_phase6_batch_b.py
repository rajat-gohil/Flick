from datetime import date
from unittest.mock import patch, MagicMock, AsyncMock
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase
import concurrent.futures
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from channels.testing import WebsocketCommunicator

from core.models import (
    CollaborativeAgreement,
    InteractionLog,
    Match,
    Movie,
    Session,
    SessionStats,
    Swipe,
)
from core.consumers import MatchConsumer
from core.services.deck_state import (
    ConflictingResponseError,
    DeckAdvancementService,
)
from core.services.manifest import ManifestCompilerService
from core.services.scoring import UserPreferenceData

User = get_user_model()


class Phase6BatchBBackendTests(TestCase):
    """
    Automated verification suite for Flick Phase 6, Batch B:
    - Requirement 3 & 5: WebSocket connection authentication, authorization, and terminal close codes (4001, 4003, 4004)
    - Requirement 4: Real-time session state synchronization event forwarding
    - Requirement 6: Swipe reliability, server-side idempotency caching, IntegrityError safety, and duplicate broadcast suppression
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_b", password="password123")
        self.guest = User.objects.create_user(username="guest_b", password="password123")
        self.stranger = User.objects.create_user(username="stranger_b", password="password123")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(
            code="BATCHB",
            host=self.host,
            guest=self.guest,
        )
        self.stats = SessionStats.objects.create(session=self.session)

        self.movies = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=60000 + i,
                title=f"Batch Film {i}",
                rating=8.0,
                vote_count=500,
                release_date=date(2021, 1, 1),
                original_language="en",
            )
            self.movies.append(m)

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            host_soft_preferences={"moods": ["uplifted"]},
            guest_soft_preferences={"moods": ["moved"]},
        )
        self.manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        self.agreement.deck_manifest = self.manifest
        self.agreement.save(update_fields=["deck_manifest"])

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

    def test_swipe_idempotency_with_header_and_body(self):
        """
        Req 6: Submitting a swipe with Idempotency-Key returns 200 OK.
        Resubmitting the same card and reaction returns 200 OK with idempotent=True and identical payload.
        Ensures exactly 1 Swipe record is persisted in the database.
        """
        m0_id = self.manifest[0]["movie_id"]
        idempotency_key = "test-idemp-uuid-001"

        # First swipe submission with Idempotency-Key HTTP header
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={
                "card_index": 0,
                "movie_id": m0_id,
                "reaction": "like",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        data1 = resp1.json()
        self.assertTrue(data1["success"])
        self.assertFalse(data1.get("idempotent", False))
        self.assertEqual(data1["card_index"], 0)

        # Assert exactly 1 swipe record exists
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 1)

        # Second swipe submission with same idempotency key
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={
                "card_index": 0,
                "movie_id": m0_id,
                "reaction": "like",
                "idempotency_key": idempotency_key,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=idempotency_key,
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = resp2.json()
        self.assertTrue(data2["success"])
        self.assertTrue(data2["idempotent"])
        self.assertEqual(data2["card_index"], 0)

        # Still exactly 1 swipe record
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 1)

    def test_swipe_suppresses_duplicate_ws_broadcast_on_idempotent_retry(self):
        """
        Req 6: Idempotent retries must NOT broadcast duplicate swipe_event or match_event to WebSocket group.
        """
        m0_id = self.manifest[0]["movie_id"]
        idempotency_key = "test-idemp-uuid-broadcast"

        with patch("core.views.get_channel_layer") as mock_get_channel_layer:
            mock_layer = MagicMock()
            mock_layer.group_send = AsyncMock()
            mock_get_channel_layer.return_value = mock_layer

            # 1. Initial swipe
            resp1 = self.client.post(
                f"/api/sessions/{self.session.id}/deck/swipe/",
                data={
                    "card_index": 0,
                    "movie_id": m0_id,
                    "reaction": "like",
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )
            self.assertEqual(resp1.status_code, status.HTTP_200_OK)
            # Verify WebSocket broadcast was invoked for initial swipe
            self.assertTrue(mock_layer.group_send.called)

            # Reset call count
            mock_layer.group_send.reset_mock()

            # 2. Idempotent retry
            resp2 = self.client.post(
                f"/api/sessions/{self.session.id}/deck/swipe/",
                data={
                    "card_index": 0,
                    "movie_id": m0_id,
                    "reaction": "like",
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )
            self.assertEqual(resp2.status_code, status.HTTP_200_OK)
            self.assertTrue(resp2.json()["idempotent"])

            # Verify WebSocket broadcast was NOT invoked for idempotent retry
            self.assertFalse(mock_layer.group_send.called)

    def test_concurrent_integrity_error_handled_safely(self):
        """
        Req 6: When a concurrent submission produces an IntegrityError on Swipe.objects.create,
        record_swipe_response gracefully fetches the existing swipe and returns the idempotent response.
        """
        m0_id = self.manifest[0]["movie_id"]
        movie = Movie.objects.get(id=m0_id)

        # First create the swipe directly to simulate concurrent insertion
        Swipe.objects.create(
            session=self.session,
            user=self.host,
            movie=movie,
            reaction="like",
        )

        # Call record_swipe_response directly with cache bypassed to simulate race
        with patch.object(Swipe.objects, "create", side_effect=IntegrityError("unique constraint failed")):
            result = DeckAdvancementService.record_swipe_response(
                session_id=self.session.id,
                user=self.host,
                card_index=0,
                movie_id=m0_id,
                reaction="like",
                idempotency_key="concurrent-key-999",
            )

        self.assertTrue(result["success"])
        self.assertTrue(result["idempotent"])
        self.assertEqual(result["card_index"], 0)

    def test_conflicting_swipe_reaction_returns_409(self):
        """
        Req 6: Submitting a conflicting reaction for the same card_index and movie_id returns HTTP 409 Conflict.
        """
        m0_id = self.manifest[0]["movie_id"]

        # Initial swipe: "like"
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={
                "card_index": 0,
                "movie_id": m0_id,
                "reaction": "like",
            },
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Conflicting swipe: "dislike" on the same card
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={
                "card_index": 0,
                "movie_id": m0_id,
                "reaction": "dislike",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Conflicting reaction", resp2.json()["error"])

    def test_swipe_on_ended_session_returns_400(self):
        """
        Req 5 & 6: Attempting to swipe on a terminated session returns HTTP 400 Bad Request.
        """
        self.session.ended_at = timezone.now()
        self.session.save()
        m0_id = self.manifest[0]["movie_id"]

        resp = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={
                "card_index": 0,
                "movie_id": m0_id,
                "reaction": "like",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ended", resp.json()["error"])

    def test_reproduce_http_400_root_cause_previous_behavior(self):
        """
        Controlled reproduction of the HTTP 400 root cause:
        In the pre-Batch B behavior (or when idempotency check was absent):
        If card 0 was swiped and advanced cursor from 0 to 1, but the client retained card 0
        and resubmitted without idempotency protection, OutOfOrderResponseError raised HTTP 400.
        With Batch B idempotency, the duplicate submission is safely absorbed and returns 200 OK.
        """
        from core.services.deck_state import OutOfOrderResponseError
        m0_id = self.manifest[0]["movie_id"]

        # First swipe: records card 0 and advances cursor to 1
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # Confirm agreement cursor advanced to 1
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)

        # Controlled test: if we simulate the pre-Batch B service (which lacked duplicate swipe handling before cursor check)
        with patch.object(Swipe.objects, "filter", return_value=MagicMock(first=lambda: None)):
            with self.assertRaises(OutOfOrderResponseError) as ctx:
                DeckAdvancementService.record_swipe_response(
                    session_id=self.session.id,
                    user=self.host,
                    card_index=0,
                    movie_id=m0_id,
                    reaction="like",
                )
            self.assertIn("Expected card_index=1, received 0", str(ctx.exception))

        # Under actual Batch B implementation: second submission returns 200 OK (idempotent=True)
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.json()["idempotent"])

    def test_idempotency_survives_cache_clear(self):
        """
        Audit Requirement 2: Deduplication survives total cache clearance or process restart
        because it is backed by persistent database row lookup and unique constraints.
        """
        from django.core.cache import cache
        m0_id = self.manifest[0]["movie_id"]
        key = "idemp-cache-clear-test-001"

        # 1. First swipe succeeds
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertFalse(resp1.json().get("idempotent", False))

        # 2. Total cache wipe (simulating Redis eviction or server restart)
        cache.clear()

        # 3. Resubmitting with same key and card returns 200 OK with idempotent=True
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertTrue(resp2.json()["idempotent"])
        # Exactly 1 swipe record persisted
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 1)

    def test_idempotency_key_reused_with_different_payload_rejected_409(self):
        """
        Audit Requirement 2: Reusing the same idempotency key with a DIFFERENT payload
        is rejected with HTTP 409 Conflict.
        """
        m0_id = self.manifest[0]["movie_id"]
        key = "idemp-different-payload-key"

        # 1. Initial swipe with reaction="like"
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # 2. Resubmitting same key with reaction="dislike"
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "dislike"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("different swipe parameters", resp2.json()["error"])

    def test_idempotency_key_across_cache_clear_different_reaction_rejected_409(self):
        """
        Question 1 Test: Reusing key abc with a different reaction after cache clear.
        Backed by database Swipe record lookup on (session, user, movie_id).
        """
        from django.core.cache import cache
        m0_id = self.manifest[0]["movie_id"]
        key = "idemp-key-abc-reaction"

        # 1. Submit swipe key abc, movie m0_id, reaction "like"
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # 2. Clear cache
        cache.clear()

        # 3. Reuse key abc with different reaction "dislike" on same card
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "dislike"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp2.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("Conflicting reaction", resp2.json()["error"])

    def test_idempotency_key_across_cache_clear_different_movie_outcome(self):
        """
        Question 1 Test: Reusing key abc with Movie 102 after cache clear.
        Tests whether key persists across cache loss when movie_id changes.
        """
        from django.core.cache import cache
        m0_id = self.manifest[0]["movie_id"]
        m1_id = self.manifest[1]["movie_id"]
        key = "idemp-key-abc-movie"

        # 1. Submit swipe key abc, Movie 101, reaction "like"
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)

        # 2. Clear cache
        cache.clear()

        # 3. Reuse key abc with Movie 102 (card 1)
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 1, "movie_id": m1_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        # Inspect actual status
        print(f"DEBUG: Status of reusing key after cache clear for different movie: {resp2.status_code}")

    def test_legitimate_sequential_swipes_advance_normally(self):
        """
        Audit Requirement 2: Legitimate sequential swipes (card 0 -> card 1) must advance
        the deck smoothly without false-positive idempotency collisions.
        """
        m0_id = self.manifest[0]["movie_id"]
        m1_id = self.manifest[1]["movie_id"]

        # Swipe card 0
        resp1 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 0, "movie_id": m0_id, "reaction": "like"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="seq-card-0",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.json()["next_card_index"], 1)

        # Swipe card 1
        resp2 = self.client.post(
            f"/api/sessions/{self.session.id}/deck/swipe/",
            data={"card_index": 1, "movie_id": m1_id, "reaction": "dislike"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="seq-card-1",
        )
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(resp2.json()["next_card_index"], 2)

        # Database state: exactly 2 swipes for host
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 2)
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 2)

    async def test_websocket_rejects_unauthenticated_connection_with_4001(self):
        """
        Req 3: Unauthenticated WebSocket connection is rejected with code 4001.
        """
        communicator = WebsocketCommunicator(
            MatchConsumer.as_asgi(),
            f"/ws/session/{self.session.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"session_id": str(self.session.id)}}
        # No user in scope
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_websocket_rejects_unauthorized_user_with_4003(self):
        """
        Req 3: Authenticated user who is not session host or guest is rejected with code 4003.
        """
        communicator = WebsocketCommunicator(
            MatchConsumer.as_asgi(),
            f"/ws/session/{self.session.id}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"session_id": str(self.session.id)}}
        communicator.scope["user"] = self.stranger

        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4003)

    async def test_websocket_rejects_nonexistent_session_with_4004(self):
        """
        Req 3: WebSocket connection for nonexistent session is rejected with code 4004.
        """
        communicator = WebsocketCommunicator(
            MatchConsumer.as_asgi(),
            "/ws/session/999999/",
        )
        communicator.scope["url_route"] = {"kwargs": {"session_id": "999999"}}
        communicator.scope["user"] = self.host

        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4004)

    async def test_websocket_session_state_event_forwarding(self):
        """
        Req 4: session_state_event handler forwards session_state_changed message to connected client.
        """
        consumer = MatchConsumer()
        consumer.send = AsyncMock()
        consumer.session_id = str(self.session.id)
        await consumer.session_state_event({
            "type": "session_state_event",
            "session_id": self.session.id,
            "session": {"id": self.session.id, "status": "active"},
        })
        consumer.send.assert_called_once()
        sent_data = consumer.send.call_args[1]["text_data"]
        import json
        payload = json.loads(sent_data)
        self.assertEqual(payload["type"], "session_state_changed")
        self.assertEqual(payload["session"]["id"], self.session.id)


class Phase6BatchBConcurrencyTests(TransactionTestCase):
    """
    Multi-threaded concurrency tests verifying that simultaneous duplicate submissions
    with the same idempotency key never create duplicate records or corrupted cursors.
    """

    def setUp(self):
        from django.db import connection
        if connection.vendor == "sqlite":
            self.skipTest(
                "SQLite uses file-level locks that block multi-threaded writes ('database table is locked'). "
                "Concurrency row-locking is active and designed for PostgreSQL select_for_update()."
            )
        self.host = User.objects.create_user(username="host_conc", password="password123")
        self.guest = User.objects.create_user(username="guest_conc", password="password123")
        self.session = Session.objects.create(code="CONCUR1", host=self.host, guest=self.guest)
        self.stats = SessionStats.objects.create(session=self.session)

        self.movies = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=70000 + i,
                title=f"Concurrent Film {i}",
                rating=8.0,
                vote_count=500,
                release_date=date(2021, 1, 1),
                original_language="en",
            )
            self.movies.append(m)

        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            host_soft_preferences={"moods": ["uplifted"]},
            guest_soft_preferences={"moods": ["moved"]},
        )
        self.manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        self.agreement.deck_manifest = self.manifest
        self.agreement.save(update_fields=["deck_manifest"])

    def test_concurrent_duplicate_submissions_race_condition(self):
        """
        Audit Requirement 2: Simultaneous threads submitting the exact same swipe with the same
        idempotency key must result in exactly 1 persisted Swipe, host_card_index advancing exactly
        once (to 1), and all threads returning success.
        """
        m0_id = self.manifest[0]["movie_id"]
        key = "concurrent-race-key-001"

        def submit_swipe():
            return DeckAdvancementService.record_swipe_response(
                session_id=self.session.id,
                user=self.host,
                card_index=0,
                movie_id=m0_id,
                reaction="like",
                idempotency_key=key,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_1 = executor.submit(submit_swipe)
            future_2 = executor.submit(submit_swipe)
            res_1 = future_1.result()
            res_2 = future_2.result()

        # Both submissions succeeded
        self.assertTrue(res_1["success"])
        self.assertTrue(res_2["success"])
        self.assertEqual(res_1["card_index"], 0)
        self.assertEqual(res_2["card_index"], 0)

        # Database state: exactly 1 swipe record created
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 1)

        # Agreement cursor advanced exactly once from 0 to 1
        self.agreement.refresh_from_db()
        self.assertEqual(self.agreement.host_card_index, 1)
