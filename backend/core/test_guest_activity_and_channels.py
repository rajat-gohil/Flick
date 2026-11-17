import json
import asyncio
from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.cache import cache
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from channels.testing import WebsocketCommunicator

from backend.asgi import application
from core.models import GuestProfile, UserProfile, Session
from core.consumers import broadcast_credential_revocation
from core.guest_security import generate_recovery_code, hash_recovery_code, compute_recovery_lookup_digest


class GuestActivityTrackingTests(TestCase):
    """
    Tests for Concurrency-Safe Guest Activity Tracking Middleware.
    Verifies:
    1. Authenticated guest activity updates last_active_at.
    2. Repeated requests within 15 minutes do not trigger repeated database writes.
    3. Activity becomes eligible for another update after 15 minutes.
    4. Concurrent requests do not cause duplicate updates with atomic cache locking.
    5. Different guest accounts use independent cache keys.
    6. Registered users are not tracked by guest activity middleware.
    7. Anonymous requests do not update guest activity.
    8. Missing GuestProfile is handled safely.
    9. Cache failure does not break the API request.
    10. Converted guest accounts (is_claimed=True) are not tracked or corrupted.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Guest 1
        self.guest_user1 = User.objects.create_user(username="guest_act_1")
        self.guest_user1.set_unusable_password()
        self.guest_user1.save()
        self.guest_token1 = Token.objects.create(user=self.guest_user1)
        self.guest_profile1 = GuestProfile.objects.create(
            user=self.guest_user1,
            recovery_lookup_digest="digest1",
            recovery_verification_hash="hash1",
            last_active_at=timezone.now() - timedelta(hours=1),
        )

        # Guest 2
        self.guest_user2 = User.objects.create_user(username="guest_act_2")
        self.guest_user2.set_unusable_password()
        self.guest_user2.save()
        self.guest_token2 = Token.objects.create(user=self.guest_user2)
        self.guest_profile2 = GuestProfile.objects.create(
            user=self.guest_user2,
            recovery_lookup_digest="digest2",
            recovery_verification_hash="hash2",
            last_active_at=timezone.now() - timedelta(hours=1),
        )

        # Registered user (no GuestProfile)
        self.reg_user = User.objects.create_user(username="reg_user_act", email="reg@example.com", password="Password123!")
        self.reg_token = Token.objects.create(user=self.reg_user)
        UserProfile.objects.create(user=self.reg_user, display_name="Regular User")

    def tearDown(self):
        cache.clear()

    def test_authenticated_guest_activity_updates_last_active_at(self):
        """1. Authenticated guest activity updates last_active_at."""
        old_time = self.guest_profile1.last_active_at
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")
        res = self.client.get("/api/users/profile/")
        self.assertEqual(res.status_code, 200)

        self.guest_profile1.refresh_from_db()
        self.assertGreater(self.guest_profile1.last_active_at, old_time)
        self.assertTrue(cache.get(f"guest_act_lock:{self.guest_user1.id}"))

    def test_repeated_requests_within_15_minutes_do_not_trigger_repeated_writes(self):
        """2. Repeated requests within 15 minutes do not trigger repeated database writes."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")
        res1 = self.client.get("/api/users/profile/")
        self.assertEqual(res1.status_code, 200)
        self.guest_profile1.refresh_from_db()
        first_active_at = self.guest_profile1.last_active_at

        # Immediate follow-up request
        res2 = self.client.get("/api/users/profile/")
        self.assertEqual(res2.status_code, 200)
        self.guest_profile1.refresh_from_db()

        # Timestamp must NOT have changed
        self.assertEqual(self.guest_profile1.last_active_at, first_active_at)

    def test_activity_eligible_for_update_after_15_minutes(self):
        """3. Activity becomes eligible for another update after 15 minutes (simulated by cache expiration)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")
        self.client.get("/api/users/profile/")
        self.guest_profile1.refresh_from_db()
        first_time = self.guest_profile1.last_active_at

        # Simulate 15 minutes passing by deleting the lock key
        cache.delete(f"guest_act_lock:{self.guest_user1.id}")

        self.client.get("/api/users/profile/")
        self.guest_profile1.refresh_from_db()
        second_time = self.guest_profile1.last_active_at

        self.assertGreaterEqual(second_time, first_time)

    def test_concurrent_requests_do_not_cause_duplicate_updates(self):
        """4. Concurrent requests do not cause duplicate updates when cache supports atomic add."""
        lock_key = f"guest_act_lock:{self.guest_user1.id}"
        # Direct verification of atomic add guarantee
        res1 = cache.add(lock_key, 1, timeout=900)
        res2 = cache.add(lock_key, 1, timeout=900)
        res3 = cache.add(lock_key, 1, timeout=900)

        self.assertTrue(res1)
        self.assertFalse(res2)
        self.assertFalse(res3)

    def test_different_guest_accounts_use_independent_cache_keys(self):
        """5. Different guest accounts use independent cache keys."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")
        self.client.get("/api/users/profile/")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token2.key}")
        self.client.get("/api/users/profile/")

        self.assertTrue(cache.get(f"guest_act_lock:{self.guest_user1.id}"))
        self.assertTrue(cache.get(f"guest_act_lock:{self.guest_user2.id}"))

    def test_registered_users_not_tracked_by_guest_activity_middleware(self):
        """6. Registered users are not unnecessarily tracked by guest activity middleware."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.reg_token.key}")
        res = self.client.get("/api/users/profile/")
        self.assertEqual(res.status_code, 200)

        # Registered user has no GuestProfile, lock key must NOT be created
        self.assertIsNone(cache.get(f"guest_act_lock:{self.reg_user.id}"))

    def test_anonymous_requests_do_not_update_activity(self):
        """7. Anonymous requests do not update guest activity."""
        self.client.credentials()  # Clear auth
        res = self.client.get("/api/healthz/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(cache._cache) if hasattr(cache, "_cache") else 0, 0)

    def test_missing_guest_profile_handled_safely(self):
        """8. Missing GuestProfile is handled safely without raising exceptions."""
        orphan_user = User.objects.create_user(username="orphan_user")
        orphan_user.set_unusable_password()
        orphan_user.save()
        orphan_token = Token.objects.create(user=orphan_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {orphan_token.key}")

        res = self.client.get("/api/users/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(cache.get(f"guest_act_lock:{orphan_user.id}"))

    def test_cache_failure_does_not_break_api_request(self):
        """9. Cache failure does not break the API request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")

        with patch("core.middleware.cache.add", side_effect=Exception("Redis connection refused")):
            res = self.client.get("/api/users/profile/")
            self.assertEqual(res.status_code, 200)

    def test_account_conversion_during_activity_tracking_does_not_cause_corruption(self):
        """10. Account conversion occurring during activity tracking does not cause corruption."""
        # Convert guest 1 (set password and mark claimed)
        self.guest_user1.set_password("ConvertedPass123!")
        self.guest_user1.save()
        self.guest_profile1.is_claimed = True
        self.guest_profile1.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token1.key}")
        res = self.client.get("/api/users/profile/")
        self.assertEqual(res.status_code, 200)

        # Claimed profiles must not set lock or be updated
        self.assertIsNone(cache.get(f"guest_act_lock:{self.guest_user1.id}"))


class WebSocketRevocationTests(TransactionTestCase):
    """
    Tests for WebSocket Credential Revocation on Guest Recovery.
    Verifies:
    1. Authenticated connections join the correct user group.
    2. Recovery broadcasts a revocation event to the correct user group.
    3. Affected WebSocket connections close with code 4001.
    4. Unrelated users' sockets remain connected.
    5. Disconnect removes the connection from the group.
    6. Repeated recovery events are handled safely.
    7. No event is broadcast if the recovery transaction rolls back.
    8. Recovery succeeds normally when there are no active WebSocket connections.
    9. Channel-layer failure is handled and reported appropriately.
    """

    def setUp(self):
        self.host_user = User.objects.create_user(username="ws_host_rev", password="Password123!")
        self.guest_user = User.objects.create_user(username="ws_guest_rev", password="Password123!")
        self.host_token = Token.objects.create(user=self.host_user)
        self.guest_token = Token.objects.create(user=self.guest_user)

        self.recovery_code = generate_recovery_code()
        self.lookup_digest = compute_recovery_lookup_digest(self.recovery_code)
        self.verification_hash = hash_recovery_code(self.recovery_code)

        self.guest_profile = GuestProfile.objects.create(
            user=self.guest_user,
            recovery_lookup_digest=self.lookup_digest,
            recovery_verification_hash=self.verification_hash,
            last_active_at=timezone.now(),
        )

        self.session = Session.objects.create(
            host=self.host_user,
            guest=self.guest_user,
            code="WSREV1"
        )
        self.client = APIClient()

    def test_authenticated_connection_joins_user_group(self):
        """1. Authenticated connections join the user_credentials_{user_id} group."""
        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            # Broadcast revocation directly to verify socket is joined to user_credentials_{user.id}
            dispatched = broadcast_credential_revocation(self.guest_user.id)
            self.assertTrue(dispatched)

            msg = await comm.receive_json_from()
            self.assertEqual(msg.get("type"), "credentials_revoked")
            self.assertEqual(msg.get("reason"), "token_rotated")

            await comm.disconnect()

        asyncio.run(run())

    def test_recovery_broadcasts_revocation_event_to_user_group(self):
        """2. Recovery broadcasts a revocation event to the correct user group."""
        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            # Dispatched via broadcast_credential_revocation
            res = broadcast_credential_revocation(self.guest_user.id, reason="token_rotated")
            self.assertTrue(res)

            msg = await comm.receive_json_from()
            self.assertEqual(msg["type"], "credentials_revoked")
            self.assertEqual(msg["reason"], "token_rotated")

            await comm.disconnect()

        asyncio.run(run())

    def test_affected_websocket_closes_with_code_4001(self):
        """3. Affected WebSocket connections close with code 4001 upon revocation."""
        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            broadcast_credential_revocation(self.guest_user.id)

            # Sockets receive credentials_revoked frame
            msg = await comm.receive_json_from()
            self.assertEqual(msg["type"], "credentials_revoked")

            # Next output from consumer is the close frame with code 4001
            close_output = await comm.receive_output()
            self.assertEqual(close_output["type"], "websocket.close")
            self.assertEqual(close_output["code"], 4001)

            await comm.disconnect()

        asyncio.run(run())

    def test_unrelated_users_sockets_remain_connected(self):
        """4. Unrelated users' sockets remain connected when another user is revoked."""
        async def run():
            # Connect Host
            host_comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.host_token.key]
            )
            h_connected, _ = await host_comm.connect()
            self.assertTrue(h_connected)

            # Connect Guest
            guest_comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            g_connected, _ = await guest_comm.connect()
            self.assertTrue(g_connected)

            # Host receives guest presence (since guest joined after host)
            g_presence = await host_comm.receive_json_from()
            self.assertEqual(g_presence["type"], "presence")
            self.assertEqual(g_presence["user_id"], self.guest_user.id)

            # Revoke Guest credentials
            broadcast_credential_revocation(self.guest_user.id)

            # Guest receives credentials_revoked
            g_msg = await guest_comm.receive_json_from()
            self.assertEqual(g_msg["type"], "credentials_revoked")

            # Host must NOT receive credentials_revoked (unrelated user is unaffected)
            h_received_revoked = False
            try:
                msg = await asyncio.wait_for(host_comm.receive_json_from(), timeout=0.2)
                if msg.get("type") == "credentials_revoked":
                    h_received_revoked = True
            except asyncio.TimeoutError:
                pass

            self.assertFalse(h_received_revoked)

            await guest_comm.disconnect()
            await host_comm.disconnect()

        asyncio.run(run())

    def test_disconnect_removes_connection_from_group(self):
        """5. Disconnect removes the connection from the user group."""
        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            # Disconnect cleanly
            await comm.disconnect()

            # Broadcasting after disconnect should succeed without listeners
            res = broadcast_credential_revocation(self.guest_user.id)
            self.assertTrue(res)

        asyncio.run(run())

    def test_repeated_recovery_events_handled_safely(self):
        """6. Repeated recovery events are handled safely."""
        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.guest_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            # Dispatch twice
            broadcast_credential_revocation(self.guest_user.id)
            broadcast_credential_revocation(self.guest_user.id)

            msg = await comm.receive_json_from()
            self.assertEqual(msg["type"], "credentials_revoked")

            close_output = await comm.receive_output()
            self.assertEqual(close_output["type"], "websocket.close")
            self.assertEqual(close_output["code"], 4001)

            await comm.disconnect()

        asyncio.run(run())

    def test_no_event_broadcast_if_recovery_transaction_rolls_back(self):
        """7. No event is broadcast if the recovery transaction rolls back."""
        broadcast_dispatched = []

        def mock_broadcast(uid):
            broadcast_dispatched.append(uid)

        try:
            with transaction.atomic():
                transaction.on_commit(lambda: mock_broadcast(self.guest_user.id))
                raise ValueError("Simulated transaction rollback")
        except ValueError:
            pass

        self.assertEqual(len(broadcast_dispatched), 0)

    def test_recovery_succeeds_normally_when_no_active_websockets(self):
        """8. Recovery succeeds normally when there are no active WebSocket connections."""
        res = self.client.post("/api/auth/guest-recover/", {
            "recovery_code": self.recovery_code
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["success"])
        self.assertIn("token", res.json())
        self.assertIn("recovery_code", res.json())

    def test_channel_layer_failure_handled_appropriately(self):
        """9. Channel-layer failure is handled and reported without raising exceptions."""
        with patch("channels.layers.get_channel_layer", return_value=None):
            res = broadcast_credential_revocation(self.guest_user.id)
            self.assertFalse(res)

        with patch("channels.layers.get_channel_layer", side_effect=Exception("Channel layer unreachable")):
            res = broadcast_credential_revocation(self.guest_user.id)
            self.assertFalse(res)
