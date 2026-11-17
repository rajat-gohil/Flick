"""
Flick Cinema Journal - Persistent Guest Account Cryptographic Utilities.

Provides Crockford Base32 recovery code generation, canonicalization,
O(1) dual-token HMAC-SHA256 lookup digests, and slow PBKDF2 verification hashes.
"""

import hashlib
import hmac
import math
import re
import secrets
from typing import Optional
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

# Crockford's Base32 alphabet: 32 characters, exactly 5 bits of entropy per character.
# Excludes I, L, O, and U to avoid visual ambiguity and accidental offensive words.
CROCKFORD_BASE32_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CROCKFORD_SET = frozenset(CROCKFORD_BASE32_ALPHABET)

# Confusable character substitutions per Crockford Base32 standard
CONFUSABLE_MAP = {
    "O": "0",
    "I": "1",
    "L": "1",
}

# Pre-computed dummy hash using standard PBKDF2 format to prevent timing side-channels
# when a recovery lookup digest does not match any database record.
# Evaluates PBKDF2 with 1,000,000 iterations identical to real password verification.
DUMMY_PBKDF2_HASH = (
    "pbkdf2_sha256$1000000$dummy000000000000000000$"
    "0000000000000000000000000000000000000000000="
)


def calculate_entropy_bits(num_chars: int = 16, alphabet_size: int = 32) -> float:
    """Calculate theoretical information entropy in bits for an alphabet."""
    return num_chars * math.log2(alphabet_size)


def generate_recovery_code() -> str:
    """
    Generate a cryptographically secure 16-character Crockford Base32 recovery code.
    Entropy: 16 characters * 5 bits = 80 bits of entropy (~1.2 x 10^24 states).
    Formatted with hyphens: FLICK-XXXX-XXXX-XXXX-XXXX.
    """
    chars = [secrets.choice(CROCKFORD_BASE32_ALPHABET) for _ in range(16)]
    return f"FLICK-{chars[0]}{chars[1]}{chars[2]}{chars[3]}-" \
           f"{chars[4]}{chars[5]}{chars[6]}{chars[7]}-" \
           f"{chars[8]}{chars[9]}{chars[10]}{chars[11]}-" \
           f"{chars[12]}{chars[13]}{chars[14]}{chars[15]}"


def canonicalize_recovery_code(code: str) -> str:
    """
    Canonicalize a recovery code string.

    Normalization steps:
    1. Strip leading and trailing whitespace.
    2. Convert to uppercase.
    3. Remove optional 'FLICK:' or 'FLICK-' or 'FLICK ' prefix.
    4. Remove all hyphens, spaces, and underscores.
    5. Map confusable characters (O->0, I->1, L->1).
    6. Validate length is exactly 16 characters.
    7. Validate all characters are in Crockford's Base32 set.
    8. Return canonical formatted string: FLICK-XXXX-XXXX-XXXX-XXXX.

    Raises:
        TypeError: If code is not a string.
        ValueError: If code length is incorrect or contains invalid characters.
    """
    if not isinstance(code, str):
        raise TypeError("Recovery code must be a string")

    cleaned = code.strip().upper()
    if not cleaned:
        raise ValueError("Recovery code cannot be empty")

    # Strip prefix if present
    if cleaned.startswith("FLICK-"):
        cleaned = cleaned[6:]
    elif cleaned.startswith("FLICK:"):
        cleaned = cleaned[6:]
    elif cleaned.startswith("FLICK "):
        cleaned = cleaned[6:]

    # Remove formatting separators
    cleaned = re.sub(r"[\s\-_]+", "", cleaned)

    # Normalize confusable characters
    trans_table = str.maketrans(CONFUSABLE_MAP)
    normalized = cleaned.translate(trans_table)

    if len(normalized) != 16:
        raise ValueError(
            f"Invalid recovery code length: expected 16 characters, got {len(normalized)}"
        )

    invalid_chars = set(normalized) - CROCKFORD_SET
    if invalid_chars:
        sorted_invalid = sorted(list(invalid_chars))
        raise ValueError(f"Invalid character(s) in recovery code: {', '.join(sorted_invalid)}")

    return (
        f"FLICK-{normalized[0:4]}-{normalized[4:8]}-"
        f"{normalized[8:12]}-{normalized[12:16]}"
    )


def get_recovery_hmac_key(version: int = 1) -> str:
    """
    Retrieve HMAC key for the specified version from Django settings.
    Raises ValueError if version is unconfigured or key is missing.
    """
    keys = getattr(settings, "GUEST_RECOVERY_HMAC_KEYS", None)
    if not keys:
        single_key = getattr(settings, "GUEST_RECOVERY_HMAC_KEY", None)
        if single_key:
            keys = {1: single_key}
        else:
            keys = {}

    key = keys.get(version)
    if not key:
        is_dev = getattr(settings, "DEBUG", False) or getattr(settings, "IS_TESTING", False)
        if is_dev and version == 1:
            key = getattr(settings, "SECRET_KEY", "flick-dev-recovery-hmac-key-default")
        else:
            raise ValueError(
                f"Guest recovery HMAC key for version {version} is not configured"
            )
    return str(key)


def compute_recovery_lookup_digest(code: str, key_version: int = 1) -> str:
    """
    Compute deterministic HMAC-SHA256 lookup digest for O(1) database queries.
    Uses canonicalized recovery code and domain-separated message string.
    Returns 64-character lowercase hexadecimal digest.
    """
    canonical_code = canonicalize_recovery_code(code)
    key = get_recovery_hmac_key(key_version)
    msg = f"flick_guest_rec_v{key_version}:{canonical_code}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def hash_recovery_code(code: str) -> str:
    """
    Generate salted verification hash using Django's standard password hasher (PBKDF2/Argon2).
    """
    canonical_code = canonicalize_recovery_code(code)
    return make_password(canonical_code)


def verify_recovery_code(code: str, hashed_code: str) -> bool:
    """
    Verify user-provided recovery code against stored salted verification hash.
    Safely canonicalizes code before verification; returns False on invalid formats.
    """
    if not hashed_code or not isinstance(hashed_code, str):
        return False
    try:
        canonical_code = canonicalize_recovery_code(code)
    except (ValueError, TypeError):
        return False
    return check_password(canonical_code, hashed_code)


def dummy_verify_recovery_code() -> bool:
    """
    Execute constant-time dummy verification calculation.
    Used when a lookup digest is not found in the database to prevent timing enumeration attacks.
    Always returns False.
    """
    return check_password("FLICK-0000-0000-0000-0000", DUMMY_PBKDF2_HASH)
