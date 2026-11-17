import contextvars
import logging
import re
from typing import Any, Optional
from django.conf import settings

correlation_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    """Return the active correlation ID or '-' if unset."""
    return correlation_id_ctx.get()


def set_correlation_id(correlation_id: str):
    """Set the active correlation ID in the contextvar. Returns a token for resetting."""
    return correlation_id_ctx.set(correlation_id)


def reset_correlation_id(token) -> None:
    """Reset the correlation ID to its previous contextvar state."""
    if token is not None:
        correlation_id_ctx.reset(token)


class SecretRedactionFilter(logging.Filter):
    """
    Logging filter that scrubs sensitive credentials (such as TMDB API keys,
    Bearer tokens, or Django secret keys) from log messages, format arguments,
    and exception payloads across all handlers.
    """

    KEY_PATTERNS = [
        re.compile(r'([?&]api_key=)[^&\s"\']+', re.IGNORECASE),
        re.compile(r'(Bearer\s+)[a-zA-Z0-9_\-\.]+', re.IGNORECASE),
        re.compile(r'([?&]password=)[^&\s"\']+', re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            self._redact_record(record)
        except Exception:
            pass
        return True

    @classmethod
    def redact_text(cls, text: Any) -> str:
        if text is None:
            return ""
        s = str(text)
        for pattern in cls.KEY_PATTERNS:
            s = pattern.sub(r'\1[REDACTED]', s)

        # Redact active TMDB API key if configured
        api_key = getattr(settings, "TMDB_API_KEY", None)
        if api_key and len(str(api_key)) > 5 and str(api_key) in s:
            s = s.replace(str(api_key), "[REDACTED]")

        # Redact Django SECRET_KEY if configured
        secret_key = getattr(settings, "SECRET_KEY", None)
        if secret_key and len(str(secret_key)) > 5 and str(secret_key) in s:
            s = s.replace(str(secret_key), "[REDACTED]")

        return s

    def _redact_record(self, record: logging.LogRecord) -> None:
        if record.args:
            try:
                record.msg = str(record.msg) % record.args
                record.args = None
            except Exception:
                if isinstance(record.args, tuple):
                    record.args = tuple(
                        self.redact_text(arg) if (isinstance(arg, (str, Exception)) or hasattr(arg, "__str__")) else arg
                        for arg in record.args
                    )
                elif isinstance(record.args, dict):
                    record.args = {
                        k: (self.redact_text(v) if (isinstance(v, (str, Exception)) or hasattr(v, "__str__")) else v)
                        for k, v in record.args.items()
                    }

        if record.msg is not None:
            record.msg = self.redact_text(str(record.msg))

        if record.exc_text:
            record.exc_text = self.redact_text(record.exc_text)


class CorrelationIdFilter(logging.Filter):
    """
    Logging filter that injects the active correlation ID into log records,
    ensuring all formatted log records have a record.correlation_id attribute.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class SecretRedactionFormatter(logging.Formatter):
    """
    Logging formatter that renders the standard log record and applies
    a secondary post-format redaction pass to scrub any secrets that might
    have emerged from exception tracebacks or third-party formatting.
    """

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "server_time"):
            record.server_time = "-"
        formatted = super().format(record)
        return SecretRedactionFilter.redact_text(formatted)
