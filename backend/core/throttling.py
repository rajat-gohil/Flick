from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """
    Rate throttle for unauthenticated authentication endpoints (login, register).
    Uses the 'anon_auth' rate limit in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
    """
    scope = "anon_auth"


class PasswordResetRateThrottle(AnonRateThrottle):
    """
    Rate throttle for sensitive email dispatch endpoints (password reset, email verification).
    Uses the 'anon_reset' rate limit in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
    """
    scope = "anon_reset"


class GuestProvisionThrottle(AnonRateThrottle):
    """
    Rate throttle for anonymous guest account initialization.
    Uses the 'guest_provision' rate limit in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
    """
    scope = "guest_provision"


class GuestRecoverThrottle(AnonRateThrottle):
    """
    Rate throttle for anonymous guest account recovery attempts.
    Uses the 'guest_recover' rate limit in settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'].
    """
    scope = "guest_recover"

