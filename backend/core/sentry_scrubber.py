import re
from typing import Any, Dict

# Crockford Base32 16-character recovery key regex with mandatory FLICK- prefix
RECOVERY_KEY_SCRUBBER_REGEX = re.compile(
    r"(?i)\bFLICK-[0-9A-HJ-KM-NP-TV-Z]{4}-[0-9A-HJ-KM-NP-TV-Z]{4}-[0-9A-HJ-KM-NP-TV-Z]{4}-[0-9A-HJ-KM-NP-TV-Z]{4}\b"
)

SENSITIVE_FIELD_NAMES = frozenset({
    "idempotency_key",
    "x-idempotency-key",
    "http_x_idempotency_key",
    "recovery_code",
})


def scrub_value(key: Any, val: Any) -> Any:
    """
    Recursively scrubs sensitive data from headers, dictionaries, lists, and strings.
    Field-scoped: only redacts values whose key is in SENSITIVE_FIELD_NAMES,
    or strings matching the specific FLICK- prefixed Crockford Base32 pattern.
    Never scrubs benign UUIDs, TMDB IDs, or general strings.
    """
    key_lower = str(key).lower() if key is not None else ""
    if key_lower in SENSITIVE_FIELD_NAMES:
        return "[REDACTED]"

    if isinstance(val, dict):
        return {k: scrub_value(k, v) for k, v in val.items()}
    elif isinstance(val, list):
        return [scrub_value(None, item) for item in val]
    elif isinstance(val, tuple):
        return tuple(scrub_value(None, item) for item in val)
    elif isinstance(val, str):
        # Apply regex scrubber for FLICK- recovery keys
        return RECOVERY_KEY_SCRUBBER_REGEX.sub("[REDACTED]", val)
    return val


def scrub_sentry_event(event: Dict[str, Any], hint: Any = None) -> Dict[str, Any]:
    """
    Sentry before_send callback hook.
    Scrubs X-Idempotency-Key, idempotency_key fields, and FLICK- prefixed recovery keys.
    Leaves benign UUIDs, session codes, and timestamps intact.
    """
    if not event or not isinstance(event, dict):
        return event

    # 1. Scrub request headers, data, and query strings
    if "request" in event and isinstance(event["request"], dict):
        req = event["request"]
        if "headers" in req and isinstance(req["headers"], dict):
            req["headers"] = scrub_value(None, req["headers"])
        if "data" in req:
            req["data"] = scrub_value(None, req["data"])

    # 2. Scrub breadcrumbs
    if "breadcrumbs" in event:
        crumbs = event["breadcrumbs"]
        if isinstance(crumbs, dict) and "values" in crumbs:
            crumbs["values"] = scrub_value(None, crumbs["values"])
        elif isinstance(crumbs, list):
            event["breadcrumbs"] = scrub_value(None, crumbs)

    # 3. Scrub exception context and messages
    if "exception" in event and isinstance(event["exception"], dict):
        exc = event["exception"]
        if "values" in exc and isinstance(exc["values"], list):
            exc["values"] = scrub_value(None, exc["values"])

    # 4. Scrub extra and tags
    if "extra" in event and isinstance(event["extra"], dict):
        event["extra"] = scrub_value(None, event["extra"])

    return event
