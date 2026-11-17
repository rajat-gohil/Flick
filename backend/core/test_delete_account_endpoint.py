"""
Tests for DeleteAccountView (/api/users/delete-account/).
Verifies:
1. Authenticated deletion with correct password succeeds (HTTP 200).
2. Unauthenticated deletion is rejected (HTTP 401).
3. Missing or incorrect password is rejected (HTTP 400).
4. System tombstone actor deletion is blocked (HTTP 403).
5. User's InteractionLog records are reassigned to system_deleted_actor with anonymized metadata.
6. UserIdentityLink, UserTasteProfile, and UserProfile records are purged.
7. Subsequent requests with deleted user token are rejected (HTTP 401).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from core.models import (
    GuestProfile,
    InteractionLog,
    Movie,
    UserIdentityLink,
    UserProfile,
    UserTasteProfile,
)
from core.services.tombstone import TombstoneService

User = get_user_model()


class DeleteAccountEndpointTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.raw_password = "SecurePassword123!"
        self.user = User.objects.create_user(
            username="delete_me_user",
            password=self.raw_password,
            email="delete_me@example.com",
        )
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.movie = Movie.objects.create(
            title="Memento",
            tmdb_id=77,
            rating=8.4,
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )

        # Create user profile, taste profile, and interaction logs
        UserProfile.objects.create(user=self.user, display_name="Test Dossier")
        UserTasteProfile.objects.create(user=self.user, learned_weights={"genres": {"Mystery": 2.0}})
        self.log1 = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="like",
            weight=1.0,
            metadata={"ip": "192.168.1.1", "device": "iPhone 15"},
        )

        # Create a linked guest actor
        self.guest = User.objects.create_user(username="guest_actor_99")
        UserIdentityLink.objects.create(
            canonical_user=self.user,
            linked_actor_id=self.guest.id,
            link_type="guest_conversion",
        )

    def test_unauthenticated_deletion_rejected(self):
        self.client.credentials()  # Clear credentials
        response = self.client.delete("/api/users/delete-account/", {"password": self.raw_password}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_missing_password_rejected(self):
        response = self.client.delete("/api/users/delete-account/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data.get("error", "").lower())

    def test_invalid_password_rejected(self):
        response = self.client.delete("/api/users/delete-account/", {"password": "WrongPassword999"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get("error"), "Invalid password.")

    def test_system_tombstone_actor_deletion_blocked(self):
        tombstone_actor = TombstoneService.get_or_create_tombstone_actor()
        t_token = Token.objects.create(user=tombstone_actor)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {t_token.key}")

        # The tombstone actor is inactive (is_active=False), so authentication is immediately rejected (401)
        response = self.client.delete("/api/users/delete-account/", {"password": "any"}, format="json")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # If somehow authenticated, view-level check explicitly blocks deletion with 403
        tombstone_actor.is_active = True
        tombstone_actor.save(update_fields=["is_active"])
        response2 = self.client.delete("/api/users/delete-account/", {"password": "any"}, format="json")
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("system tombstone actor", response2.data.get("error", "").lower())

    def test_successful_authenticated_deletion_and_tombstoning(self):
        user_id = self.user.id
        response = self.client.delete(
            "/api/users/delete-account/",
            {"password": self.raw_password},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["metrics"]["logs_reassigned"], 1)
        self.assertEqual(response.data["metrics"]["links_purged"], 1)

        # 1. User row deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())

        # 2. Token deleted
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

        # 3. UserProfile and UserTasteProfile deleted
        self.assertFalse(UserProfile.objects.filter(user_id=user_id).exists())
        self.assertFalse(UserTasteProfile.objects.filter(user_id=user_id).exists())

        # 4. UserIdentityLink purged
        self.assertFalse(UserIdentityLink.objects.filter(canonical_user_id=user_id).exists())

        # 5. InteractionLog preserved and reassigned to system_deleted_actor with anonymized metadata
        self.log1.refresh_from_db()
        tombstone_actor = TombstoneService.get_or_create_tombstone_actor()
        self.assertEqual(self.log1.user_id, tombstone_actor.id)
        self.assertEqual(self.log1.weight, 1.0)
        self.assertEqual(self.log1.event_type, "like")
        self.assertEqual(self.log1.metadata.get("anonymized"), True)
        self.assertNotIn("ip", self.log1.metadata)
        self.assertNotIn("device", self.log1.metadata)

        # 6. Subsequent requests with original token are rejected
        subsequent = self.client.delete(
            "/api/users/delete-account/",
            {"password": self.raw_password},
            format="json",
        )
        self.assertEqual(subsequent.status_code, status.HTTP_401_UNAUTHORIZED)
