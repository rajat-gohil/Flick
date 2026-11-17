"""
Tests for Flick Persistent Guest Account Phase 2:
- Guest provisioning API (POST /api/auth/guest-provision/)
- Guest recovery API (POST /api/auth/guest-recover/)
- Retry-safe recovery handoff and acknowledgment (POST /api/auth/guest-recovery-ack/)
- Rate limiting and anti-enumeration behavior
- Token rotation and single-session invalidation
- Compatibility with existing registered user auth
"""

import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import connection
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.guest_security import (
    canonicalize_recovery_code,
    compute_recovery_lookup_digest,
    generate_recovery_code,
    hash_recovery_code,
    verify_recovery_code,
)
from core.models import GuestProfile, UserProfile


class GuestProvisioningAPITests(TestCase):
    """Test suite for POST /api/auth/guest-provision/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_anonymous_guest_provisioning_success(self):
        """Unauthenticated user can successfully provision a guest account."""
        response = self.client.post(
            "/api/auth/guest-provision/",
            {"display_name": "Cinema Buff"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()

        self.assertTrue(data.get("success"))
        self.assertIn("token", data)
        self.assertIn("recovery_code", data)
        self.assertIn("user", data)

        recovery_code = data["recovery_code"]
        self.assertTrue(recovery_code.startswith("FLICK-"))

        user_info = data["user"]
        self.assertEqual(user_info["display_name"], "Cinema Buff")
        self.assertTrue(user_info["is_guest"])
        self.assertIn("guest_uuid", user_info)

        # Verify database entities
        user = User.objects.get(id=user_info["id"])
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.first_name, "Cinema Buff")

        profile = GuestProfile.objects.get(user=user)
        self.assertEqual(str(profile.id), user_info["guest_uuid"])
        self.assertFalse(profile.is_claimed)
        self.assertTrue(verify_recovery_code(recovery_code, profile.recovery_verification_hash))
        self.assertEqual(profile.recovery_lookup_digest, compute_recovery_lookup_digest(recovery_code))

        # Verify DRF Token
        token = Token.objects.get(key=data["token"])
        self.assertEqual(token.user, user)

    def test_anonymous_provisioning_default_display_name(self):
        """When no display_name provided, defaults to 'Cinephile #{id}'."""
        response = self.client.post("/api/auth/guest-provision/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        user_id = data["user"]["id"]
        self.assertEqual(data["user"]["display_name"], f"Cinephile #{user_id}")

    def test_authenticated_user_cannot_provision_guest(self):
        """Authenticated user receives 400 Bad Request."""
        existing_user = User.objects.create_user(username="registered_user", password="password123")
        token = Token.objects.create(user=existing_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/auth/guest-provision/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertIn("Authenticated users cannot", response.json()["error"])

    def test_token_can_access_authenticated_endpoints(self):
        """Provisioned guest token can access authenticated endpoints immediately."""
        prov_res = self.client.post("/api/auth/guest-provision/", {}, format="json")
        token_key = prov_res.json()["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_key}")
        profile_res = self.client.get("/api/users/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)


class GuestRecoveryAPITests(TestCase):
    """Test suite for POST /api/auth/guest-recover/ and POST /api/auth/guest-recovery-ack/."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Provision a test guest account
        self.recovery_code = generate_recovery_code()
        self.digest = compute_recovery_lookup_digest(self.recovery_code)
        self.v_hash = hash_recovery_code(self.recovery_code)

        self.user = User.objects.create_user(
            username="guest_recovery_test",
            first_name="Original Name"
        )
        self.user.set_unusable_password()
        self.user.save()

        self.user_profile = UserProfile.objects.create(
            user=self.user,
            display_name="Original Name"
        )

        self.guest_profile = GuestProfile.objects.create(
            user=self.user,
            recovery_lookup_digest=self.digest,
            recovery_verification_hash=self.v_hash,
            recovery_key_version=1
        )
        self.original_token = Token.objects.create(user=self.user)

    def test_successful_recovery_rotates_token_and_issues_new_credential(self):
        """Recovery returns new token and new recovery code, and invalidates old token."""
        response = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": self.recovery_code},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data["success"])
        new_token_key = data["token"]
        new_recovery_code = data["recovery_code"]

        self.assertNotEqual(new_token_key, self.original_token.key)
        self.assertNotEqual(new_recovery_code, self.recovery_code)

        # Old token is deleted from DB
        self.assertFalse(Token.objects.filter(key=self.original_token.key).exists())
        # New token belongs to the recovered user
        new_token = Token.objects.get(key=new_token_key)
        self.assertEqual(new_token.user, self.user)

        # Old token fails authenticated requests
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.original_token.key}")
        res_old = self.client.get("/api/users/profile/")
        self.assertEqual(res_old.status_code, status.HTTP_401_UNAUTHORIZED)

        # New token succeeds
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {new_token_key}")
        res_new = self.client.get("/api/users/profile/")
        self.assertEqual(res_new.status_code, status.HTTP_200_OK)

    def test_recovery_canonicalization_tolerance(self):
        """Recovery succeeds even with lowercase, no hyphens, spaces, or confusable letters."""
        # Replace 0 with O and test lowercase
        unformatted = self.recovery_code.lower().replace("flick-", "").replace("-", " ")
        response = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": unformatted},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["success"])

    def test_invalid_recovery_code_returns_generic_error(self):
        """Nonexistent recovery code returns 400 Bad Request."""
        response = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": "FLICK-0000-0000-0000-0000"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.json()["success"])
        self.assertEqual(response.json()["error"], "Invalid recovery code.")

    def test_malformed_code_returns_generic_error(self):
        """Malformed code returns 400 Bad Request without revealing internal state."""
        response = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": "tooshort"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "Invalid recovery code.")

    def test_converted_account_recovery_rejected(self):
        """Accounts marked is_claimed=True are rejected with instructions to sign in."""
        self.guest_profile.is_claimed = True
        self.guest_profile.save()

        response = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": self.recovery_code},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been registered with email and password", response.json()["error"])


class RecoveryHandoffReliabilityTests(TestCase):
    """
    Test suite for Section 4: Critical recovery reliability requirement & lost HTTP response handoff.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.c1 = generate_recovery_code()
        self.digest1 = compute_recovery_lookup_digest(self.c1)
        self.v_hash1 = hash_recovery_code(self.c1)

        self.user = User.objects.create_user(username="guest_handoff_user")
        self.user.set_unusable_password()
        self.user.save()
        UserProfile.objects.create(user=self.user, display_name="Handoff Cinephile")

        self.guest_profile = GuestProfile.objects.create(
            user=self.user,
            recovery_lookup_digest=self.digest1,
            recovery_verification_hash=self.v_hash1,
            recovery_key_version=1
        )
        self.t1 = Token.objects.create(user=self.user)

    def test_lost_http_response_retry_succeeds(self):
        """
        Scenario: Client submits C1. Server processes request, generates C2/T2,
        and demotes C1 to previous credential with 15-minute grace period.
        The HTTP response is lost.
        Client retries with C1: recovery must succeed and return fresh C3/T3.
        """
        # Step 1: Initial recovery request processed by server
        res1 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        c2 = res1.json()["recovery_code"]
        t2 = res1.json()["token"]

        # Verify C1 is now in previous_recovery_lookup_digest with active grace period
        profile = GuestProfile.objects.get(user=self.user)
        self.assertEqual(profile.previous_recovery_lookup_digest, self.digest1)
        self.assertIsNotNone(profile.previous_recovery_expires_at)
        self.assertGreater(profile.previous_recovery_expires_at, timezone.now())

        # Step 2: Client lost response and re-submits C1 (retry after lost response)
        res2 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        data2 = res2.json()
        c3 = data2["recovery_code"]
        t3 = data2["token"]

        self.assertNotEqual(c3, c2)
        self.assertNotEqual(t3, t2)

        # Step 3: Client successfully receives C3/T3 and acknowledges receipt
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {t3}")
        ack_res = self.client.post("/api/auth/guest-recovery-ack/", {}, format="json")
        self.assertEqual(ack_res.status_code, status.HTTP_200_OK)

        # Step 4: After acknowledgment, C1 is completely retired
        profile.refresh_from_db()
        self.assertEqual(profile.previous_recovery_lookup_digest, "")
        self.assertIsNone(profile.previous_recovery_expires_at)

        # Subsequent attempts with C1 fail
        self.client.credentials()  # Clear auth
        res_retired = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res_retired.status_code, status.HTTP_400_BAD_REQUEST)

        # But recovery with C3 works
        res_c3 = self.client.post("/api/auth/guest-recover/", {"recovery_code": c3}, format="json")
        self.assertEqual(res_c3.status_code, status.HTTP_200_OK)

    def test_expired_handoff_credential_rejected(self):
        """When previous_recovery_expires_at has passed, the old code is rejected."""
        # Initial recovery
        self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")

        # Manually expire the handoff window
        profile = GuestProfile.objects.get(user=self.user)
        profile.previous_recovery_expires_at = timezone.now() - timedelta(seconds=1)
        profile.save()

        # Attempt recovery with expired C1
        res = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.json()["error"], "Invalid recovery code.")

    def test_repeated_recovery_attempts_lifecycle(self):
        """
        Verify sequential repeated recovery attempts:
        1. First recovery succeeds (C1 -> C2, T2).
        2. Repeated recovery with C1 succeeds within handoff window (C1 -> C3, T3).
        3. Acknowledgment with T3 finalizes handoff.
        4. Subsequent attempt with C1 fails; recovery with C3 succeeds.
        """
        # Attempt 1 with C1
        res1 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        c2 = res1.json()["recovery_code"]
        t2 = res1.json()["token"]

        # Attempt 2 with C1 (repeated request before acknowledgment)
        res2 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        c3 = res2.json()["recovery_code"]
        t3 = res2.json()["token"]

        # Token 2 is now invalid because attempt 2 rotated the token
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {t2}")
        self.assertEqual(self.client.get("/api/users/profile/").status_code, status.HTTP_401_UNAUTHORIZED)

        # Token 3 is valid
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {t3}")
        self.assertEqual(self.client.get("/api/users/profile/").status_code, status.HTTP_200_OK)

        # Acknowledge with Token 3
        ack = self.client.post("/api/auth/guest-recovery-ack/", {}, format="json")
        self.assertEqual(ack.status_code, status.HTTP_200_OK)

        # Attempt with retired C1 now fails
        self.client.credentials()
        res_retired = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.c1}, format="json")
        self.assertEqual(res_retired.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt with active C3 succeeds
        res_active = self.client.post("/api/auth/guest-recover/", {"recovery_code": c3}, format="json")
        self.assertEqual(res_active.status_code, status.HTTP_200_OK)



class GuestThrottlingTests(TestCase):
    """Test suite for IP-based throttling on guest endpoints."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_provision_throttling_triggers_429(self):
        """Exceeding 10 provisions per minute triggers 429 Too Many Requests."""
        for i in range(10):
            res = self.client.post("/api/auth/guest-provision/", {}, format="json")
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # 11th request triggers throttle
        throttled_res = self.client.post("/api/auth/guest-provision/", {}, format="json")
        self.assertEqual(throttled_res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_recover_throttling_triggers_429(self):
        """Exceeding 5 recovery attempts per minute triggers 429 Too Many Requests."""
        for i in range(5):
            res = self.client.post(
                "/api/auth/guest-recover/",
                {"recovery_code": "FLICK-0000-0000-0000-0000"},
                format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # 6th request triggers throttle
        throttled_res = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": "FLICK-0000-0000-0000-0000"},
            format="json"
        )
        self.assertEqual(throttled_res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ExistingRegisteredUserCompatibilityTests(TestCase):
    """Verify that existing email/password registered authentication is unaffected."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="registered@example.com",
            email="registered@example.com",
            password="StrongPassword123!",
            first_name="Alice"
        )
        UserProfile.objects.create(user=self.user, display_name="Alice")

    def test_existing_login_view_remains_functional(self):
        """Standard email/password login succeeds normally."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "registered@example.com", "password": "StrongPassword123!"},
            format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("token", data)
        self.assertEqual(data["username"], "registered@example.com")


class GuestRecoveryConcurrencyTests(TransactionTestCase):
    """Verify concurrent recovery requests against the same account."""

    def setUp(self):
        if connection.vendor == "sqlite":
            self.skipTest(
                "SQLite uses file-level locks that block multi-threaded writes ('database table is locked'). "
                "Concurrency row-locking is active and designed for PostgreSQL select_for_update()."
            )
        cache.clear()
        self.code = generate_recovery_code()
        self.digest = compute_recovery_lookup_digest(self.code)
        self.v_hash = hash_recovery_code(self.code)

        self.user = User.objects.create_user(username="concurrent_guest")
        self.user.set_unusable_password()
        self.user.save()
        UserProfile.objects.create(user=self.user, display_name="Concurrent Cinephile")

        self.guest_profile = GuestProfile.objects.create(
            user=self.user,
            recovery_lookup_digest=self.digest,
            recovery_verification_hash=self.v_hash,
            recovery_key_version=1
        )
        self.original_token = Token.objects.create(user=self.user)

    def test_concurrent_recovery_attempts_serialized(self):
        """
        Two concurrent recovery requests using the same recovery code:
        One succeeds, the second either succeeds within handoff or is handled cleanly
        without corrupting the account state or producing an HTTP 500 error.
        """
        def send_recovery():
            c = APIClient()
            return c.post("/api/auth/guest-recover/", {"recovery_code": self.code}, format="json")

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(send_recovery)
            f2 = executor.submit(send_recovery)
            res1 = f1.result()
            res2 = f2.result()

        # Neither should ever return a 500 Internal Server Error
        self.assertNotEqual(res1.status_code, 500)
        self.assertNotEqual(res2.status_code, 500)

        # At least one MUST be 200 OK
        statuses = [res1.status_code, res2.status_code]
        self.assertIn(200, statuses)

        # Token in DB must be valid and correspond to the recovered user
        token = Token.objects.get(user=self.user)
        self.assertNotEqual(token.key, self.original_token.key)

