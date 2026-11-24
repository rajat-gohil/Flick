"""
production_settings.py — drop into backend/ and load via:
  DJANGO_SETTINGS_MODULE=backend.production_settings

All secrets MUST come from environment variables — never hardcode them.

Quick setup:
  1. Copy this file to backend/production_settings.py
  2. Set env vars (see each setting below for the var name)
  3. Run: python manage.py check --deploy
"""

from .settings import *  # noqa: F401,F403 — inherit all dev settings, override below
import os

# ─────────────────────────────────────────────────────────────
# SECURITY — CRITICAL: these 3 must be set before any traffic
# ─────────────────────────────────────────────────────────────

# Never commit the real secret key. Generate one with:
#   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]  # will raise KeyError if not set — intentional

DEBUG = False  # MUST be False in production

# Set to your actual domain(s). E.g. ["flickapp.in", "www.flickapp.in", "api.flickapp.in"]
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
# If using PostgreSQL (recommended), set DATABASE_URL:
#   DATABASE_URL=postgres://user:pass@host:5432/dbname
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    import dj_database_url
    DATABASES = {"default": dj_database_url.config(default=_db_url, conn_max_age=600)}

# ─────────────────────────────────────────────────────────────
# HTTPS / SECURITY HEADERS
# ─────────────────────────────────────────────────────────────
SECURE_SSL_REDIRECT          = True
SECURE_HSTS_SECONDS          = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD          = True
SECURE_PROXY_SSL_HEADER      = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE        = True
CSRF_COOKIE_SECURE           = True
X_FRAME_OPTIONS              = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF  = True

# ─────────────────────────────────────────────────────────────
# EMAIL — choose ONE provider
# ─────────────────────────────────────────────────────────────
#
# OPTION A: Resend (recommended — free 3k emails/month)
#   pip install django-anymail[resend]
#   Env vars: RESEND_API_KEY=re_...
#
# OPTION B: SendGrid
#   pip install django-anymail[sendgrid]
#   Env vars: SENDGRID_API_KEY=SG...
#
# OPTION C: Gmail SMTP (dev/small scale only)
#   Env vars: EMAIL_HOST_USER=you@gmail.com, EMAIL_HOST_PASSWORD=app-password
#
# OPTION D: AWS SES
#   pip install django-anymail[amazon_ses]

_email_provider = os.environ.get("EMAIL_PROVIDER", "smtp").lower()

if _email_provider == "resend":
    INSTALLED_APPS += ["anymail"]  # type: ignore[name-defined]
    ANYMAIL = {"RESEND_API_KEY": os.environ["RESEND_API_KEY"]}
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"

elif _email_provider == "sendgrid":
    INSTALLED_APPS += ["anymail"]  # type: ignore[name-defined]
    ANYMAIL = {"SENDGRID_API_KEY": os.environ["SENDGRID_API_KEY"]}
    EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"

else:
    # Default: SMTP (Gmail / any SMTP relay)
    EMAIL_BACKEND     = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST        = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT        = int(os.environ.get("EMAIL_PORT", 587))
    EMAIL_USE_TLS     = os.environ.get("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER   = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Flick <discoverflick@gmail.com>")

# ─────────────────────────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────────────────────────
# Used to build absolute links in emails (password reset, verification)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://flick-kappa.vercel.app")

# ─────────────────────────────────────────────────────────────
# CORS — restrict to your domain in production
# ─────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = os.environ.get(
    "CORS_ALLOWED_ORIGINS",
    "https://flick-kappa.vercel.app"
).split(",")
CORS_ALLOW_ALL_ORIGINS = False  # override dev setting if any

# ─────────────────────────────────────────────────────────────
# RATE LIMITING — Django REST Framework throttling
# ─────────────────────────────────────────────────────────────
_throttle_rates = REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})  # type: ignore[name-defined]
_throttle_rates.update({
    "anon_auth":   "10/minute",   # login + register
    "anon_reset":  "5/hour",      # password reset
    "anon_social": "20/minute",   # social login
})
REST_FRAMEWORK.update({  # type: ignore[name-defined]
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": _throttle_rates,
})

# ─────────────────────────────────────────────────────────────
# PUSH NOTIFICATIONS (Firebase)
# ─────────────────────────────────────────────────────────────
# Get from: Firebase Console → Project Settings → Cloud Messaging → Server key
FIREBASE_SERVER_KEY = os.environ.get("FIREBASE_SERVER_KEY", "")

# ─────────────────────────────────────────────────────────────
# SOCIAL AUTH
# ─────────────────────────────────────────────────────────────
# Get from: Google Cloud Console → APIs & Services → Credentials
GOOGLE_CLIENT_IDS = os.environ.get("GOOGLE_CLIENT_IDS", "").split(",")
# Get from: Apple Developer → Certificates, Identifiers & Profiles → Services IDs
APPLE_CLIENT_ID = os.environ.get("APPLE_CLIENT_ID", "")

# ─────────────────────────────────────────────────────────────
# STATIC & MEDIA FILES
# ─────────────────────────────────────────────────────────────
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # type: ignore[name-defined]
MEDIA_ROOT  = os.environ.get("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))  # type: ignore[name-defined]
MEDIA_URL   = "/media/"

# ─────────────────────────────────────────────────────────────
# LOGGING — production-grade
# ─────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}

# ─────────────────────────────────────────────────────────────
# SENTRY — error monitoring (Item 15)
# ─────────────────────────────────────────────────────────────
# pip install sentry-sdk
# Set SENTRY_DSN env var from https://sentry.io → Project → Settings → SDK Setup
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from core.sentry_scrubber import scrub_sentry_event

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration(), RedisIntegration()],
        before_send=scrub_sentry_event,
        traces_sample_rate=0.1,   # capture 10% of transactions for performance
        send_default_pii=False,   # don't send user IPs / emails to Sentry
        environment="production",
    )

# ─────────────────────────────────────────────────────────────
# RUN THIS AFTER SETTING UP:
#   python manage.py check --deploy
#   python manage.py collectstatic --no-input
#   python manage.py migrate
# ─────────────────────────────────────────────────────────────
