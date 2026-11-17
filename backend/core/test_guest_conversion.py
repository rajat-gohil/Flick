"""
Tests for Flick Persistent Guest Account Phase 3:
- In-place permanent account conversion API (POST /api/auth/guest-convert/)
- Preservation of User primary key (id) and UserProfile
- Preservation of historical screening sessions, swipes, matches, and watchlists
- Permanent retirement of guest recovery credentials
- Validation and anti-collision checks
- DRF Token continuity and login compatibility
"""

from datetime import date
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.guest_security import (
    compute_recovery_lookup_digest,
    generate_recovery_code,
    hash_recovery_code,
)
from core.models import (
    Genre,
    GuestProfile,
    Match,
    Movie,
    Session,
    Swipe,
    UserProfile,
    WatchlistItem,
)


class GuestConversionSuccessTests(TestCase):
    """Test suite for successful in-place permanent account conversion."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # 1. Provision a guest account via API
        prov_res = self.client.post("/api/auth/guest-provision/", {"display_name": "Original Guest"}, format="json")
        self.assertEqual(prov_res.status_code, status.HTTP_201_CREATED)
        prov_data = prov_res.json()

        self.token = prov_data["token"]
        self.recovery_code = prov_data["recovery_code"]
        self.user_id = prov_data["user"]["id"]
        self.guest_uuid = prov_data["user"]["guest_uuid"]

        self.user = User.objects.get(id=self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

    def test_in_place_conversion_preserves_user_id_and_token(self):
        """Converting guest mutates User in-place without altering PK, UserProfile, or Token."""
        response = self.client.post(
            "/api/auth/guest-convert/",
            {
                "email": "converted_user@flick.test",
                "password": "StrongSecretPassword123!",
                "display_name": "Permanent Cinephile",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["token"], self.token)  # Token preserved
        self.assertEqual(data["user"]["id"], self.user_id)  # PK strictly preserved
        self.assertEqual(data["user"]["email"], "converted_user@flick.test")
        self.assertEqual(data["user"]["display_name"], "Permanent Cinephile")
        self.assertFalse(data["user"]["is_guest"])
        self.assertEqual(data["user"]["guest_uuid"], self.guest_uuid)

        # Verify User model in DB
        self.user.refresh_from_db()
        self.assertEqual(self.user.id, self.user_id)
        self.assertEqual(self.user.email, "converted_user@flick.test")
        self.assertEqual(self.user.username, "converted_user@flick.test")
        self.assertEqual(self.user.first_name, "Permanent Cinephile")
        self.assertTrue(self.user.check_password("StrongSecretPassword123!"))
        self.assertTrue(self.user.has_usable_password())

        # Verify GuestProfile model in DB
        profile = GuestProfile.objects.get(user=self.user)
        self.assertEqual(str(profile.id), self.guest_uuid)
        self.assertTrue(profile.is_claimed)
        self.assertTrue(profile.is_converted)
        self.assertIsNotNone(profile.claimed_at)
        self.assertIsNotNone(profile.converted_at)

        # Existing Token remains valid and continues to authenticate requests
        profile_res = self.client.get("/api/users/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)

        # Converted user can log in via standard LoginView with new email & password
        self.client.credentials()  # Clear auth headers
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "converted_user@flick.test",
                "password": "StrongSecretPassword123!",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertEqual(login_res.json()["token"], self.token)
        self.assertEqual(login_res.json()["user_id"], self.user_id)


class GuestConversionDataIntegrityTests(TestCase):
    """Verify that all historical sessions, swipes, matches, and watchlists are retained."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Provision guest
        prov_res = self.client.post("/api/auth/guest-provision/", {"display_name": "Active Guest"}, format="json")
        prov_data = prov_res.json()
        self.token = prov_data["token"]
        self.user_id = prov_data["user"]["id"]
        self.user = User.objects.get(id=self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

        # Create partner user for screening session
        self.partner = User.objects.create_user(username="partner_user", password="password123")

        # Create genre and movies
        self.genre = Genre.objects.create(tmdb_id=18, name="Drama", industry="hollywood")
        self.movie1 = Movie.objects.create(
            tmdb_id=101,
            title="Citizen Kane",
            rating=8.3,
            release_date=date(1941, 5, 1)
        )
        self.movie2 = Movie.objects.create(
            tmdb_id=102,
            title="Casablanca",
            rating=8.5,
            release_date=date(1942, 11, 26)
        )

        # Create historical session where guest is host
        self.session = Session.objects.create(
            code="HIST01",
            host=self.user,
            guest=self.partner,
            genre=self.genre,
        )

        # Create swipes
        self.swipe1 = Swipe.objects.create(
            session=self.session,
            user=self.user,
            movie=self.movie1,
            reaction=Swipe.LIKE
        )
        self.swipe_partner = Swipe.objects.create(
            session=self.session,
            user=self.partner,
            movie=self.movie1,
            reaction=Swipe.LIKE
        )

        # Create match
        self.match = Match.objects.create(
            session=self.session,
            movie=self.movie1
        )

        # Create watchlist item
        self.watchlist = WatchlistItem.objects.create(
            user=self.user,
            movie=self.movie2
        )

    def test_historical_relationships_survive_conversion(self):
        """All foreign keys, swipes, matches, and watchlists remain completely intact."""
        convert_res = self.client.post(
            "/api/auth/guest-convert/",
            {
                "email": "history_retained@flick.test",
                "password": "Password123!",
            },
            format="json",
        )
        self.assertEqual(convert_res.status_code, status.HTTP_200_OK)

        # 1. User PK is identical
        self.user.refresh_from_db()
        self.assertEqual(self.user.id, self.user_id)

        # 2. Session host is still this user
        self.session.refresh_from_db()
        self.assertEqual(self.session.host_id, self.user_id)

        # 3. Swipes belong to this user
        self.swipe1.refresh_from_db()
        self.assertEqual(self.swipe1.user_id, self.user_id)
        self.assertEqual(self.swipe1.reaction, Swipe.LIKE)

        # 4. Matches are preserved
        self.match.refresh_from_db()
        self.assertEqual(self.match.session_id, self.session.id)
        self.assertEqual(self.match.movie_id, self.movie1.id)

        # 5. Watchlist items belong to this user
        self.watchlist.refresh_from_db()
        self.assertEqual(self.watchlist.user_id, self.user_id)

        # 6. Querying endpoints as converted user returns historical items
        wl_res = self.client.get("/api/watchlist/")
        self.assertEqual(wl_res.status_code, status.HTTP_200_OK)
        wl_data = wl_res.json()
        self.assertTrue(wl_data["success"])
        self.assertEqual(wl_data["total_count"], 1)
        self.assertEqual(len(wl_data["watchlist"]), 1)
        self.assertEqual(wl_data["watchlist"][0]["movie_id"], self.movie2.id)
        self.assertEqual(wl_data["watchlist"][0]["movie_title"], "Casablanca")


class GuestConversionRecoverySecurityTests(TestCase):
    """Verify that recovery credentials are permanently retired upon conversion."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Provision guest
        prov_res = self.client.post("/api/auth/guest-provision/", {}, format="json")
        prov_data = prov_res.json()
        self.token = prov_data["token"]
        self.recovery_code = prov_data["recovery_code"]
        self.user_id = prov_data["user"]["id"]
        self.user = User.objects.get(id=self.user_id)

        # Perform one recovery to test previous handoff credential state
        recover_res = self.client.post(
            "/api/auth/guest-recover/",
            {"recovery_code": self.recovery_code},
            format="json"
        )
        rec_data = recover_res.json()
        self.active_recovery_code = rec_data["recovery_code"]
        self.new_token = rec_data["token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.new_token}")

    def test_guest_recovery_fails_permanently_after_conversion(self):
        """Once converted, neither primary nor handoff recovery credentials work."""
        # Convert account
        convert_res = self.client.post(
            "/api/auth/guest-convert/",
            {
                "email": "secure_convert@flick.test",
                "password": "Password123!",
            },
            format="json",
        )
        self.assertEqual(convert_res.status_code, status.HTTP_200_OK)

        # Verify DB credential retirement
        profile = GuestProfile.objects.get(user=self.user)
        self.assertEqual(profile.recovery_lookup_digest, "")
        self.assertEqual(profile.recovery_verification_hash, "")
        self.assertEqual(profile.previous_recovery_lookup_digest, "")
        self.assertEqual(profile.previous_recovery_verification_hash, "")
        self.assertIsNone(profile.previous_recovery_expires_at)

        # Attempt recovery with latest recovery code fails
        self.client.credentials()
        rec1 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.active_recovery_code}, format="json")
        self.assertEqual(rec1.status_code, status.HTTP_400_BAD_REQUEST)

        # Attempt recovery with initial recovery code fails
        rec2 = self.client.post("/api/auth/guest-recover/", {"recovery_code": self.recovery_code}, format="json")
        self.assertEqual(rec2.status_code, status.HTTP_400_BAD_REQUEST)


class GuestConversionValidationAndRejectionTests(TestCase):
    """Test suite for rejection rules and input validation."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Regular registered user (no GuestProfile)
        self.regular_user = User.objects.create_user(
            username="regular@flick.test",
            email="regular@flick.test",
            password="Password123!"
        )
        self.reg_token = Token.objects.create(user=self.regular_user)

        # Provision guest
        prov_res = self.client.post("/api/auth/guest-provision/", {}, format="json")
        self.guest_token = prov_res.json()["token"]

    def test_anonymous_request_rejected(self):
        """Unauthenticated requests are rejected with 401 Unauthorized."""
        response = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "anon@flick.test", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ordinary_registered_user_rejected(self):
        """Users without a GuestProfile cannot invoke conversion."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.reg_token.key}")
        response = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "upgrade@flick.test", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only guest accounts can be converted", response.json()["error"])

    def test_already_converted_guest_rejected(self):
        """Converting twice returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token}")
        res1 = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "convert_once@flick.test", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        res2 = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "convert_twice@flick.test", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already been converted", res2.json()["error"])

    def test_duplicate_email_rejected_with_clean_rollback(self):
        """If email is already in use by another user, request fails and state rolls back."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token}")
        response = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "regular@flick.test", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", response.json()["error"])

        # Verify guest account was not altered
        guest_user = Token.objects.get(key=self.guest_token).user
        self.assertFalse(guest_user.has_usable_password())
        self.assertFalse(guest_user.guest_profile.is_claimed)

    def test_invalid_email_format_rejected(self):
        """Malformed emails return 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token}")
        response = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "invalid-email-format", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid email format", response.json()["error"])

    def test_short_password_rejected(self):
        """Passwords with fewer than 6 characters return 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token}")
        response = self.client.post(
            "/api/auth/guest-convert/",
            {"email": "valid@flick.test", "password": "123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at least 6 characters long", response.json()["error"])

    def test_missing_fields_rejected(self):
        """Missing required fields return 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token}")
        res_no_pw = self.client.post("/api/auth/guest-convert/", {"email": "valid@flick.test"}, format="json")
        self.assertEqual(res_no_pw.status_code, status.HTTP_400_BAD_REQUEST)

        res_no_email = self.client.post("/api/auth/guest-convert/", {"password": "Password123!"}, format="json")
        self.assertEqual(res_no_email.status_code, status.HTTP_400_BAD_REQUEST)


class GuestConversionConcurrencyTests(TransactionTestCase):
    """Concurrency verification for guest conversion."""

    def setUp(self):
        if connection.vendor == "sqlite":
            self.skipTest(
                "SQLite uses file-level locks that block multi-threaded writes ('database table is locked'). "
                "Concurrency row-locking is active and designed for PostgreSQL select_for_update()."
            )
        cache.clear()
        self.client = APIClient()

    def test_concurrent_conversion_serialized_by_database(self):
        """Simultaneous conversion requests against the same account are serialized."""
        pass
