"""
Tests for Flick Persistent Guest Account Phase 1:
- Cryptographic utilities (Crockford Base32, entropy, canonicalization)
- Dual-token recovery digests (HMAC-SHA256, slow PBKDF2 hash)
- Constant-time dummy verification
- HMAC key configuration & versioning
- GuestProfile model constraints, indexes, and relationships
"""

import uuid
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone
from core.models import GuestProfile
from core.guest_security import (
    CROCKFORD_BASE32_ALPHABET,
    calculate_entropy_bits,
    generate_recovery_code,
    canonicalize_recovery_code,
    compute_recovery_lookup_digest,
    hash_recovery_code,
    verify_recovery_code,
    dummy_verify_recovery_code,
    get_recovery_hmac_key,
)


class GuestSecurityCryptoTests(TestCase):
    """Test suite for recovery code cryptography and canonicalization."""

    def test_crockford_alphabet_length_and_composition(self):
        """Verify Crockford Base32 alphabet is exactly 32 chars and excludes I, L, O, U."""
        self.assertEqual(len(CROCKFORD_BASE32_ALPHABET), 32)
        for excluded in ("I", "L", "O", "U"):
            self.assertNotIn(excluded, CROCKFORD_BASE32_ALPHABET)

    def test_entropy_calculation(self):
        """Verify 16 Crockford Base32 chars mathematically provide exactly 80 bits of entropy."""
        entropy = calculate_entropy_bits(16, 32)
        self.assertEqual(entropy, 80.0)

    def test_generate_recovery_code_format(self):
        """Verify generated recovery code matches FLICK-XXXX-XXXX-XXXX-XXXX."""
        code = generate_recovery_code()
        self.assertTrue(code.startswith("FLICK-"))
        parts = code.split("-")
        self.assertEqual(len(parts), 5)  # FLICK, 4 chars, 4 chars, 4 chars, 4 chars
        self.assertEqual(parts[0], "FLICK")
        for chunk in parts[1:]:
            self.assertEqual(len(chunk), 4)
            for char in chunk:
                self.assertIn(char, CROCKFORD_BASE32_ALPHABET)

    def test_generate_recovery_code_uniqueness(self):
        """Verify random generation does not produce duplicate codes."""
        codes = {generate_recovery_code() for _ in range(50)}
        self.assertEqual(len(codes), 50)

    def test_canonicalize_recovery_code_clean(self):
        """Standard valid code canonicalizes to identical standard format."""
        code = "FLICK-0123-4567-89AB-CDEF"
        self.assertEqual(canonicalize_recovery_code(code), code)

    def test_canonicalize_case_and_separators(self):
        """Canonicalization normalizes lowercase, spaces, underscores, and missing prefix."""
        raw_variants = [
            "flick-0123-4567-89ab-cdef",
            "FLICK 0123 4567 89AB CDEF",
            "0123-4567-89ab-cdef",
            "0123_4567_89AB_cdef",
            "0123456789abcdef",
            "  FLICK-0123-4567-89AB-CDEF  ",
        ]
        expected = "FLICK-0123-4567-89AB-CDEF"
        for variant in raw_variants:
            self.assertEqual(canonicalize_recovery_code(variant), expected)

    def test_canonicalize_confusable_characters(self):
        """Verify Crockford confusable substitutions: O->0, I->1, L->1."""
        raw_code = "FLICK-O123-4567-89AB-CILF"
        # O -> 0, I -> 1, L -> 1
        expected = "FLICK-0123-4567-89AB-C11F"
        self.assertEqual(canonicalize_recovery_code(raw_code), expected)

    def test_canonicalize_invalid_characters_rejected(self):
        """Characters outside Crockford set (e.g. U, special symbols) raise ValueError."""
        with self.assertRaises(ValueError):
            canonicalize_recovery_code("FLICK-0123-4567-89AB-CDEU")  # U is excluded

        with self.assertRaises(ValueError):
            canonicalize_recovery_code("FLICK-0123-4567-89AB-CDE!")

    def test_canonicalize_invalid_length_rejected(self):
        """Short or long codes raise ValueError."""
        with self.assertRaises(ValueError):
            canonicalize_recovery_code("FLICK-0123-4567-89AB-CD")  # only 14 chars
        with self.assertRaises(ValueError):
            canonicalize_recovery_code("FLICK-0123-4567-89AB-CDEF00")  # 18 chars
        with self.assertRaises(ValueError):
            canonicalize_recovery_code("")

    def test_canonicalize_non_string_rejected(self):
        """Non-string inputs raise TypeError."""
        with self.assertRaises(TypeError):
            canonicalize_recovery_code(1234567890123456)  # type: ignore


class GuestSecurityHMACAndVerificationTests(TestCase):
    """Test suite for HMAC lookup digest and slow verification hashing."""

    @override_settings(
        GUEST_RECOVERY_HMAC_KEYS={1: "test-secret-key-version-1", 2: "test-secret-key-version-2"}
    )
    def test_deterministic_hmac_lookup_digest(self):
        """Lookup digest is strictly deterministic for identical recovery codes across formatting."""
        code1 = "FLICK-7K2M-9P4W-X8B3-0123"
        code2 = "7k2m 9p4w x8b3 o123"  # Contains lowercase, spaces, and O->0

        digest1 = compute_recovery_lookup_digest(code1, key_version=1)
        digest2 = compute_recovery_lookup_digest(code2, key_version=1)

        self.assertEqual(digest1, digest2)
        self.assertEqual(len(digest1), 64)  # SHA-256 hex digest length
        self.assertTrue(all(c in "0123456789abcdef" for c in digest1))

    @override_settings(
        GUEST_RECOVERY_HMAC_KEYS={1: "test-secret-key-version-1", 2: "test-secret-key-version-2"}
    )
    def test_key_versioning_produces_distinct_digests(self):
        """Different key versions produce completely different digests for the same code."""
        code = "FLICK-7K2M-9P4W-X8B3-0123"
        digest_v1 = compute_recovery_lookup_digest(code, key_version=1)
        digest_v2 = compute_recovery_lookup_digest(code, key_version=2)
        self.assertNotEqual(digest_v1, digest_v2)

    @override_settings(GUEST_RECOVERY_HMAC_KEYS={1: "test-secret-key-version-1"})
    def test_unconfigured_key_version_raises(self):
        """Requesting unconfigured key version raises ValueError."""
        with self.assertRaises(ValueError):
            get_recovery_hmac_key(version=99)

    def test_salted_hash_and_verification(self):
        """Hash creation and verification passes for matching code, fails for non-matching."""
        code = "FLICK-7K2M-9P4W-X8B3-0123"
        v_hash = hash_recovery_code(code)

        self.assertTrue(v_hash.startswith("pbkdf2_sha256$"))
        # Verifies with identical code
        self.assertTrue(verify_recovery_code(code, v_hash))
        # Verifies with unformatted equivalent code (lowercase, no dashes, confusable char O)
        self.assertTrue(verify_recovery_code("7k2m9p4wx8b3o123", v_hash))
        # Fails for different code
        self.assertFalse(verify_recovery_code("FLICK-7K2M-9P4W-X8B3-0000", v_hash))
        # Fails safely for invalid / empty string
        self.assertFalse(verify_recovery_code("invalid", v_hash))
        self.assertFalse(verify_recovery_code(code, ""))

    def test_dummy_verification_returns_false(self):
        """Dummy verification always returns False."""
        self.assertFalse(dummy_verify_recovery_code())


class GuestSecurityDeploymentSettingsTests(TestCase):
    """Test suite for deployment HMAC key configuration safety."""

    @override_settings(
        GUEST_RECOVERY_HMAC_KEYS={},
        GUEST_RECOVERY_HMAC_KEY=None,
        DEBUG=False,
        IS_TESTING=False
    )
    def test_missing_hmac_key_raises_in_production(self):
        """When DEBUG=False and IS_TESTING=False, missing HMAC key raises ValueError."""
        with self.assertRaises(ValueError):
            get_recovery_hmac_key(version=1)

    @override_settings(
        GUEST_RECOVERY_HMAC_KEYS={},
        GUEST_RECOVERY_HMAC_KEY=None,
        DEBUG=True,
        IS_TESTING=False,
        SECRET_KEY="dev-secret-key"
    )
    def test_fallback_to_secret_key_in_debug_mode(self):
        """When DEBUG=True, version 1 safely falls back to SECRET_KEY."""
        key = get_recovery_hmac_key(version=1)
        self.assertEqual(key, "dev-secret-key")



class GuestProfileModelTests(TestCase):
    """Test suite for GuestProfile model creation, constraints, and relationships."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="guest_testuser_01",
            password=None
        )

    def test_guest_profile_creation_and_defaults(self):
        """Verify GuestProfile can be created with dual-token attributes."""
        code = generate_recovery_code()
        digest = compute_recovery_lookup_digest(code)
        v_hash = hash_recovery_code(code)

        profile = GuestProfile.objects.create(
            user=self.user,
            recovery_lookup_digest=digest,
            recovery_verification_hash=v_hash,
            recovery_key_version=1,
        )

        self.assertIsInstance(profile.id, uuid.UUID)
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.guest_uuid, profile.id)
        self.assertFalse(profile.is_claimed)
        self.assertFalse(profile.is_converted)
        self.assertIsNone(profile.claimed_at)
        self.assertIsNone(profile.converted_at)
        self.assertIn("Guest", str(profile))

    def test_guest_profile_property_setters(self):
        """Verify is_converted and converted_at setter aliases update is_claimed and claimed_at."""
        profile = GuestProfile.objects.create(user=self.user)
        now = timezone.now()

        profile.is_converted = True
        profile.converted_at = now
        profile.save()

        refreshed = GuestProfile.objects.get(pk=profile.pk)
        self.assertTrue(refreshed.is_claimed)
        self.assertTrue(refreshed.is_converted)
        self.assertEqual(refreshed.claimed_at, now)
        self.assertEqual(refreshed.converted_at, now)
        self.assertIn("Permanent", str(refreshed))

    def test_guest_profile_one_to_one_constraint(self):
        """A user cannot have multiple GuestProfiles."""
        GuestProfile.objects.create(user=self.user)
        with self.assertRaises(IntegrityError):
            GuestProfile.objects.create(user=self.user)

    def test_guest_profile_cascade_deletion(self):
        """Deleting the user cascades to delete GuestProfile."""
        profile = GuestProfile.objects.create(user=self.user)
        profile_id = profile.id

        self.user.delete()
        self.assertFalse(GuestProfile.objects.filter(id=profile_id).exists())

    def test_lookup_by_digest_query(self):
        """Verifies O(1) B-tree lookup on recovery_lookup_digest works properly."""
        code = generate_recovery_code()
        digest = compute_recovery_lookup_digest(code)
        v_hash = hash_recovery_code(code)

        GuestProfile.objects.create(
            user=self.user,
            recovery_lookup_digest=digest,
            recovery_verification_hash=v_hash,
        )

        retrieved = GuestProfile.objects.filter(
            recovery_lookup_digest=digest,
            is_claimed=False
        ).select_related("user").first()

        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.user.username, "guest_testuser_01")
        self.assertTrue(verify_recovery_code(code, retrieved.recovery_verification_hash))
