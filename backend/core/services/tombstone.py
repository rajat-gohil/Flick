"""
Tombstone Service for Flick User Privacy & Account Deletion.

Enforces GDPR/CCPA compliant privacy tombstoning:
1. Reassigns raw InteractionLog records to a system tombstone actor ('system_deleted_actor').
2. Anonymizes log metadata (purging IPs, sessions, user-agents, device fingerprints)
   while preserving event_type and historical signal weights for learning loops.
3. Purges guest identity links (UserIdentityLink).
4. Deletes personal taste profiles (UserTasteProfile), user profiles (UserProfile),
   and guest profiles (GuestProfile).
5. Safely deletes the auth_user row within an atomic transaction.
"""

import logging
from typing import Any, Dict

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models, transaction

from core.models import (
    GuestProfile,
    InteractionLog,
    MovieExposure,
    UserProfile,
    UserTasteProfile,
)

logger = logging.getLogger(__name__)


class TombstoneService:
    """
    Handles privacy-compliant user deletion and interaction log tombstoning.
    """

    TOMBSTONE_USERNAME = "system_deleted_actor"

    @classmethod
    def get_or_create_tombstone_actor(cls):
        """
        Retrieves or creates the system tombstone actor.
        The actor is disabled (is_active=False) so it cannot authenticate.
        """
        User = get_user_model()
        actor, _ = User.objects.get_or_create(
            username=cls.TOMBSTONE_USERNAME,
            defaults={"is_active": False},
        )
        return actor

    @classmethod
    def anonymize_and_delete_user(cls, user) -> Dict[str, Any]:
        """
        Atomically anonymizes interaction logs, purges linked identities, deletes
        taste and profile records, and removes the User account.

        Returns:
            Dict[str, Any] with metrics:
            {
                'logs_reassigned': int,
                'links_purged': int,
                'taste_deleted': int,
            }
        """
        User = get_user_model()
        if not isinstance(user, User):
            raise ValueError(f"Expected User model instance, got {type(user)}")

        tombstone_actor = cls.get_or_create_tombstone_actor()

        if user.id == tombstone_actor.id:
            raise ValueError("Cannot anonymize or delete the system tombstone actor.")

        with transaction.atomic():
            # 1. Reassign InteractionLog records and overwrite metadata per event_type
            distinct_event_types = list(
                InteractionLog.objects.filter(user=user)
                .values_list("event_type", flat=True)
                .distinct()
            )
            logs_reassigned = 0
            for et in distinct_event_types:
                count = InteractionLog.objects.filter(user=user, event_type=et).update(
                    user=tombstone_actor,
                    metadata={"anonymized": True, "event_type": et},
                )
                logs_reassigned += count

            # In case there are interaction logs with empty or untracked event types
            remaining_logs = InteractionLog.objects.filter(user=user).update(
                user=tombstone_actor,
                metadata={"anonymized": True},
            )
            logs_reassigned += remaining_logs

            # 2. Purge UserIdentityLink records
            links_purged = 0
            try:
                UserIdentityLink = apps.get_model("core", "UserIdentityLink")
            except (LookupError, ValueError):
                UserIdentityLink = None

            if UserIdentityLink is not None:
                del_count, _ = UserIdentityLink.objects.filter(
                    models.Q(canonical_user=user) | models.Q(linked_actor_id=user.id)
                ).delete()
                links_purged = del_count

            # 3. Delete UserTasteProfile
            taste_deleted_tuple = UserTasteProfile.objects.filter(user=user).delete()
            taste_deleted = taste_deleted_tuple[0]

            # 4. Delete MovieExposure if user field exists
            if any(f.name == "user" for f in MovieExposure._meta.get_fields()):
                MovieExposure.objects.filter(user=user).delete()

            # 5. Delete UserProfile and GuestProfile
            UserProfile.objects.filter(user=user).delete()
            GuestProfile.objects.filter(user=user).delete()

            # 6. Safely delete the user row
            user_id = user.id
            user.delete()

            logger.info(
                "Tombstoned and deleted user_id=%s. Reassigned %d logs, purged %d links, deleted %d taste records.",
                user_id,
                logs_reassigned,
                links_purged,
                taste_deleted,
            )

            return {
                "logs_reassigned": logs_reassigned,
                "links_purged": links_purged,
                "taste_deleted": taste_deleted,
            }
