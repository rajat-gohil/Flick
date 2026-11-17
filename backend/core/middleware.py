import logging
import re
import uuid
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone
from rest_framework.authtoken.models import Token
from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from core.models import GuestProfile
from core.logging import set_correlation_id, reset_correlation_id

logger = logging.getLogger(__name__)

CORRELATION_ID_REGEX = re.compile(r'^[a-zA-Z0-9_\-\.]{8,64}$')


class CorrelationIdMiddleware:
    """
    HTTP middleware that extracts or generates a unique request correlation ID.
    Supports both synchronous WSGI and asynchronous ASGI/Daphne execution flows.
    Stores the ID in a Python contextvar (for async-safe propagation under ASGI/Daphne)
    and echoes it back in the X-Request-ID and X-Correlation-ID response headers.
    """
    sync_capable = True
    async_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        if iscoroutinefunction(self.get_response):
            markcoroutinefunction(self)

    def _resolve_request_id(self, request) -> str:
        incoming_id = request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
        if incoming_id and CORRELATION_ID_REGEX.match(incoming_id.strip()):
            return incoming_id.strip()
        return str(uuid.uuid4())

    def __call__(self, request):
        if iscoroutinefunction(self.get_response):
            return self.__acall__(request)

        req_id = self._resolve_request_id(request)
        token = set_correlation_id(req_id)
        request.correlation_id = req_id

        try:
            response = self.get_response(request)
            response["X-Request-ID"] = req_id
            response["X-Correlation-ID"] = req_id
            return response
        finally:
            reset_correlation_id(token)

    async def __acall__(self, request):
        req_id = self._resolve_request_id(request)
        token = set_correlation_id(req_id)
        request.correlation_id = req_id

        try:
            response = await self.get_response(request)
            response["X-Request-ID"] = req_id
            response["X-Correlation-ID"] = req_id
            return response
        finally:
            reset_correlation_id(token)


@database_sync_to_async
def get_user_from_token_key(token_key):
    try:
        token = Token.objects.select_related("user").get(key=token_key)
        return token.user
    except (Token.DoesNotExist, TypeError, ValueError):
        return AnonymousUser()


class TokenAuthMiddleware:
    """
    Channels ASGI middleware for DRF Token Authentication.
    Extracts token from:
    1. WebSocket subprotocols: 'Sec-WebSocket-Protocol: token, <token_key>'
       (Supported by modern browsers; keeps credentials out of URLs and access logs).
    2. HTTP headers: 'Authorization: Token <key>' or 'Authorization: Bearer <key>'
       (Supported by native mobile and test clients).
    Query-string credentials are intentionally not accepted to prevent token leakage in access logs.
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "websocket":
            user = scope.get("user")
            if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
                token_key = None

                # 1. Check WebSocket subprotocols (preferred for browsers to avoid URL logging)
                subprotocols = scope.get("subprotocols", [])
                if len(subprotocols) >= 2 and subprotocols[0].lower() in ("token", "bearer"):
                    token_key = subprotocols[1]
                elif len(subprotocols) == 1 and subprotocols[0].startswith("token."):
                    token_key = subprotocols[0].split(".", 1)[1]

                # 2. Check HTTP headers (for programmatic clients/tests)
                if not token_key:
                    headers = dict(scope.get("headers", []))
                    auth_header = headers.get(b"authorization", b"").decode("utf-8")
                    if auth_header:
                        parts = auth_header.split()
                        if len(parts) == 2 and parts[0].lower() in ("token", "bearer"):
                            token_key = parts[1]

                if token_key:
                    scope["user"] = await get_user_from_token_key(token_key)
                    scope["auth_token"] = token_key
                else:
                    scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)


def TokenAuthMiddlewareStack(inner):
    from channels.auth import AuthMiddlewareStack
    return AuthMiddlewareStack(TokenAuthMiddleware(inner))


class GuestActivityMiddleware:
    """
    HTTP middleware that records last_active_at for active persistent guest accounts.
    Executes after view dispatch to ensure DRF TokenAuthentication has populated request.user.
    Throttles database updates using atomic cache.add('guest_act_lock:{user_id}', 1, timeout=900)
    to enforce at most one DB update per 15 minutes per guest under normal operation.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._track_guest_activity(request)
        except Exception as e:
            logger.warning("Error in GuestActivityMiddleware: %s", e)
        return response

    def _track_guest_activity(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        # Ordinary registered users and converted accounts have a usable password.
        # Persistent guest accounts have an unusable password.
        # Bypassing usable passwords avoids unnecessary database queries for registered users.
        if user.has_usable_password():
            return

        # Check if user has an unclaimed guest profile
        guest_profile = getattr(user, "guest_profile", None)
        if not guest_profile or guest_profile.is_claimed:
            return

        # Attempt atomic cache lock (15 minutes = 900 seconds)
        lock_key = f"guest_act_lock:{user.id}"
        try:
            acquired = cache.add(lock_key, 1, timeout=900)
        except Exception as e:
            logger.warning("Cache lock acquisition failed for user_id=%s: %s", user.id, e)
            return

        if acquired:
            now = timezone.now()
            GuestProfile.objects.filter(
                user_id=user.id,
                is_claimed=False
            ).update(last_active_at=now)
            guest_profile.last_active_at = now

