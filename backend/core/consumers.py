import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from core.models import Session

logger = logging.getLogger(__name__)


class MatchConsumer(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_session(self, session_id):
        try:
            return Session.objects.select_related("host", "guest").get(id=session_id)
        except (Session.DoesNotExist, ValueError, TypeError):
            return None

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"
        self.user = self.scope.get("user")
        self._in_group = False
        self._in_user_group = False
        self._revoked = False

        # 1. Authentication check
        if not self.user or isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            logger.warning("WebSocket rejected: unauthenticated connection attempt for session=%s", self.session_id)
            await self.close(code=4001)
            return

        # 2. Session existence check
        session = await self.get_session(self.session_id)
        if not session:
            logger.warning("WebSocket rejected: session=%s not found for user_id=%s", self.session_id, self.user.id)
            await self.close(code=4004)
            return

        # 3. Authorization check: authenticated user must be session host or guest
        is_host = session.host_id == self.user.id
        is_guest = session.guest_id == self.user.id
        if not (is_host or is_guest):
            logger.warning("WebSocket rejected: user_id=%s unauthorized for session=%s", self.user.id, self.session_id)
            await self.close(code=4003)
            return

        # 4. Negotiate subprotocol if requested by client (e.g. 'token')
        subprotocols = self.scope.get("subprotocols", [])
        chosen_subprotocol = None
        if any(s.lower() == "token" for s in subprotocols):
            chosen_subprotocol = "token"
        elif any(s.lower() == "bearer" for s in subprotocols):
            chosen_subprotocol = "bearer"

        # 5. Join user credentials channel group for revocation broadcasts
        self.user_group_name = f"user_credentials_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        self._in_user_group = True

        # 6. Join session channel group ONLY after authentication and authorization pass
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        if chosen_subprotocol:
            await self.accept(subprotocol=chosen_subprotocol)
        else:
            await self.accept()

        self._in_group = True

        # Broadcast online presence
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "presence_event",
                "user_id": self.user.id,
                "status": "online",
            }
        )

    async def disconnect(self, close_code):
        if getattr(self, "_in_user_group", False):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
            self._in_user_group = False

        if getattr(self, "_in_group", False):
            if self.user and self.user.is_authenticated:
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "presence_event",
                        "user_id": self.user.id,
                        "status": "offline",
                    }
                )

            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            self._in_group = False

    async def match_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "match_event",
            "session_id": event["session_id"],
            "movie_id": event["movie_id"],
            "movie_title": event["movie_title"],
            "poster_url": event.get("poster_url") or "",
            "release_year": event.get("release_year"),
            "rating": event.get("rating"),
            "superlike_attribution": event.get("superlike_attribution") or "none",
            "match_type": event.get("match_type") or "ordinary",
        }))

    async def session_ended_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "session_ended",
            "session_id": event["session_id"],
            "ended_by": event.get("ended_by", "participant"),
        }))

    async def partner_left_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "partner_left",
            "session_id": event["session_id"],
            "user_id": event.get("user_id"),
            "role": event.get("role"),
        }))

    async def swipe_event(self, event):
        # Do not echo back swiping notification to oneself
        if event.get("user_id") == self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "partner_swiping",
            "user_id": event["user_id"],
        }))

    async def partner_disconnected(self, event):
        # Do not notify the user who disconnected
        if self.channel_name == event.get("channel"):
            return
        await self.send(text_data=json.dumps({
            "type": "partner_disconnected",
        }))

    async def presence_event(self, event):
        # Do not notify user of their own presence
        if event.get("user_id") == self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "presence",
            "user_id": event["user_id"],
            "status": event["status"],
        }))

    async def partner_joined_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "partner_joined",
            "session_id": event["session_id"],
            "username": event.get("username", ""),
            "display_name": event.get("display_name", event.get("username", "")),
        }))

    async def preferences_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "preferences_updated",
            "session_id": event["session_id"],
            "user_id": event.get("user_id"),
            "role": event.get("role"),
            "host_preferences_set": event.get("host_preferences_set", False),
            "guest_preferences_set": event.get("guest_preferences_set", False),
            "preferences_set": event.get("preferences_set", False),
            "both_ready": event.get("both_ready", False),
            "overlap_score": event.get("overlap_score", 0),
        }))

    async def proposal_event(self, event):
        # Prevent cross-session data leakage
        if str(event.get("session_id")) != str(self.session_id):
            return
        await self.send(text_data=json.dumps(event))

    async def session_state_event(self, event):
        # Prevent cross-session data leakage
        current_session_id = getattr(self, "session_id", None)
        if current_session_id is not None and event.get("session_id") and str(event.get("session_id")) != str(current_session_id):
            return
        await self.send(text_data=json.dumps({
            "type": "session_state_changed",
            "session_id": event.get("session_id", current_session_id),
            "status": event.get("status"),
            "ended": event.get("ended", False),
            "preferences_set": event.get("preferences_set", False),
            "session": event.get("session"),
        }))

    async def user_credentials_revoked(self, event):
        """
        Handler for user_credentials_revoked Channels broadcast event.
        Dispatched when user authentication credentials are rotated or revoked.
        Notifies client and disconnects WebSocket with close code 4001.
        """
        if getattr(self, "_revoked", False):
            return
        self._revoked = True

        try:
            await self.send(text_data=json.dumps({
                "type": "credentials_revoked",
                "reason": event.get("reason", "token_rotated"),
            }))
        except Exception as e:
            logger.debug("Failed sending credentials_revoked payload before closing socket: %s", e)

        try:
            await self.close(code=4001)
        except Exception as e:
            logger.debug("Error closing WebSocket during credential revocation: %s", e)


def broadcast_credential_revocation(user_id: int, reason: str = "token_rotated") -> bool:
    """
    Broadcasts a user_credentials_revoked event across the channel layer
    to terminate any active WebSockets authenticated with revoked credentials.

    Returns True if successfully dispatched, False otherwise.
    Safe against channel layer failure; logs errors and never raises.
    Supports both synchronous thread contexts (via async_to_sync) and
    active asyncio event loop contexts (via asyncio.ensure_future).
    """
    try:
        import asyncio
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.warning("No channel layer configured; WebSocket revocation event not dispatched for user_id=%s", user_id)
            return False

        group_name = f"user_credentials_{user_id}"
        message = {
            "type": "user_credentials_revoked",
            "reason": reason,
            "user_id": user_id,
        }

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            asyncio.ensure_future(channel_layer.group_send(group_name, message), loop=loop)
        else:
            from asgiref.sync import async_to_sync
            async_to_sync(channel_layer.group_send)(group_name, message)

        return True
    except Exception as e:
        logger.error("Failed to broadcast WebSocket credential revocation for user_id=%s: %s", user_id, e)
        return False

