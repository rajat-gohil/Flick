import logging
from typing import Any, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from core.models import UserIdentityLink, UserTasteProfile
from core.services.catalogue_queue import CatalogueQueueService

logger = logging.getLogger(__name__)


class DuplicateIdentityLinkError(ValueError):
    """
    Raised when attempting to link a guest identity that is already
    bound to a different canonical user.
    """
    pass


class IdentityLinkingService:
    """
    Service responsible for linking guest actor identities to canonical users,
    querying linked actor sets, and reconciling guest taste profile preferences
    into the canonical user's taste profile.
    """

    @classmethod
    def _resolve_user(cls, user_or_id: Any) -> Any:
        """
        Resolves a User instance from either a User instance or user ID.
        """
        if isinstance(user_or_id, (int, str)):
            User = get_user_model()
            return User.objects.get(id=int(user_or_id))
        return user_or_id

    @classmethod
    def link_guest_to_user(
        cls,
        canonical_user: Any,
        guest_user: Any,
        link_type: str = "guest_conversion",
    ) -> UserIdentityLink:
        """
        Links a guest actor identity to a canonical user account.

        - Validates that guest_user is not already linked to another canonical user
          (strict 1:1 guest ownership).
        - If already linked to the same canonical user, returns the existing link idempotently.
        - If linked to another, raises DuplicateIdentityLinkError (subclass of ValueError).
        - Validates that canonical_user != guest_user.
        - Atomically creates UserIdentityLink(canonical_user=canonical_user, linked_actor_id=guest_user.id, link_type=link_type).
        - Merges guest taste profile preferences into the canonical profile.
        - Enqueues recompute_taste_profile job for canonical_user via CatalogueQueueService.enqueue.
        """
        canonical = cls._resolve_user(canonical_user)
        guest = cls._resolve_user(guest_user)

        if canonical.id == guest.id:
            raise ValueError(
                f"Cannot link user to itself: canonical_user and guest_user have identical ID ({canonical.id})."
            )

        if hasattr(link_type, "value"):
            link_type_str = link_type.value
        else:
            link_type_str = str(link_type)

        with transaction.atomic():
            # Check existing links with row lock to prevent concurrent double-binding
            existing_link = (
                UserIdentityLink.objects.select_for_update()
                .filter(linked_actor_id=guest.id)
                .first()
            )

            if existing_link:
                if existing_link.canonical_user_id == canonical.id:
                    # Idempotent return if already bound to the same canonical user
                    logger.info(
                        "Identity link already exists between canonical user %s and guest actor %s",
                        canonical.id,
                        guest.id,
                    )
                    return existing_link
                else:
                    raise DuplicateIdentityLinkError(
                        f"Guest actor {guest.id} is already linked to another canonical user ({existing_link.canonical_user_id})."
                    )

            # Reconcile taste preferences safely
            cls.reconcile_guest_taste_profile_into_canonical(canonical, guest)

            try:
                link = UserIdentityLink.objects.create(
                    canonical_user=canonical,
                    linked_actor_id=guest.id,
                    link_type=link_type_str,
                )
            except IntegrityError as exc:
                # Handle concurrent insertion race condition
                existing = UserIdentityLink.objects.filter(linked_actor_id=guest.id).first()
                if existing and existing.canonical_user_id == canonical.id:
                    return existing
                raise DuplicateIdentityLinkError(
                    f"Guest actor {guest.id} is already linked to another canonical user."
                ) from exc

            # Enqueue asynchronous taste profile recomputation job for the canonical user
            CatalogueQueueService.enqueue(
                job_type="recompute_taste_profile",
                entity_type="user",
                entity_id=str(canonical.id),
                priority=100,
            )

            logger.info(
                "Successfully linked guest actor %s to canonical user %s (link_type=%s)",
                guest.id,
                canonical.id,
                link_type_str,
            )
            return link

    @classmethod
    def get_all_actor_ids_for_user(cls, user: Any) -> List[int]:
        """
        Returns canonical user id plus all linked guest actor IDs for this user.
        Signature:
            get_all_actor_ids_for_user(user: User) -> List[int]
        """
        user_id = user.id if hasattr(user, "id") else int(user)
        linked_ids = list(
            UserIdentityLink.objects.filter(canonical_user_id=user_id).values_list(
                "linked_actor_id", flat=True
            )
        )
        return [user_id] + linked_ids

    @classmethod
    def reconcile_guest_taste_profile_into_canonical(
        cls,
        canonical_user: Any,
        guest_user: Any,
    ) -> Optional[UserTasteProfile]:
        """
        Merges preferences (eras, runtime, languages, exclusions) safely without double counting.
        Leaves interaction history intact under original user_id = guest_user.id so
        TasteEngineService can recompute canonical profile from combined event ledger.
        """
        canonical = cls._resolve_user(canonical_user)
        guest = cls._resolve_user(guest_user)

        guest_profile = UserTasteProfile.objects.filter(user=guest).first()
        if not guest_profile:
            # Nothing to reconcile from guest taste profile; ensure canonical profile exists
            canonical_profile, _ = UserTasteProfile.objects.get_or_create(user=canonical)
            return canonical_profile

        with transaction.atomic():
            canonical_profile, _ = UserTasteProfile.objects.select_for_update().get_or_create(
                user=canonical,
                defaults={
                    "emotional_tonality": [],
                    "narrative_structures": [],
                    "thematic_interests": [],
                    "preferred_languages": [],
                    "default_eras": [],
                    "hard_exclusions": {},
                    "learned_weights": {},
                },
            )

            # 1. Eras: Union lists preserving order without duplicates
            canonical_eras = list(canonical_profile.default_eras or [])
            guest_eras = list(guest_profile.default_eras or [])
            canonical_profile.default_eras = list(dict.fromkeys(canonical_eras + guest_eras))

            # 2. Maximum Runtime: Preserve or take broader/max envelope
            if canonical_profile.default_max_runtime is None:
                canonical_profile.default_max_runtime = guest_profile.default_max_runtime
            elif guest_profile.default_max_runtime is not None:
                canonical_profile.default_max_runtime = max(
                    canonical_profile.default_max_runtime,
                    guest_profile.default_max_runtime,
                )

            # 3. Minimum Rating: Preserve or take lower threshold
            if canonical_profile.default_min_rating is None:
                canonical_profile.default_min_rating = guest_profile.default_min_rating
            elif guest_profile.default_min_rating is not None:
                canonical_profile.default_min_rating = min(
                    canonical_profile.default_min_rating,
                    guest_profile.default_min_rating,
                )

            # 4. Preferred Languages: Union lists preserving order without duplicates
            canonical_langs = list(canonical_profile.preferred_languages or [])
            guest_langs = list(guest_profile.preferred_languages or [])
            canonical_profile.preferred_languages = list(dict.fromkeys(canonical_langs + guest_langs))

            # 5. Exclusions: Union nested lists and keys without double counting
            canonical_exclusions = dict(canonical_profile.hard_exclusions or {})
            guest_exclusions = dict(guest_profile.hard_exclusions or {})
            merged_exclusions = dict(canonical_exclusions)

            for key, guest_val in guest_exclusions.items():
                if key in merged_exclusions:
                    can_val = merged_exclusions[key]
                    if isinstance(can_val, list) and isinstance(guest_val, list):
                        merged_exclusions[key] = list(dict.fromkeys(can_val + guest_val))
                    elif isinstance(can_val, dict) and isinstance(guest_val, dict):
                        sub = dict(can_val)
                        for sub_k, sub_v in guest_val.items():
                            if sub_k in sub and isinstance(sub[sub_k], list) and isinstance(sub_v, list):
                                sub[sub_k] = list(dict.fromkeys(sub[sub_k] + sub_v))
                            else:
                                sub[sub_k] = sub_v
                        merged_exclusions[key] = sub
                    else:
                        if can_val is None:
                            merged_exclusions[key] = guest_val
                else:
                    merged_exclusions[key] = guest_val

            canonical_profile.hard_exclusions = merged_exclusions

            # 6. Aesthetic dimensions (mood, narrative forms, thematic interests)
            canonical_tones = list(canonical_profile.emotional_tonality or [])
            guest_tones = list(guest_profile.emotional_tonality or [])
            if guest_tones:
                canonical_profile.emotional_tonality = list(
                    dict.fromkeys(canonical_tones + guest_tones)
                )[:3]

            canonical_narratives = list(canonical_profile.narrative_structures or [])
            guest_narratives = list(guest_profile.narrative_structures or [])
            if guest_narratives:
                canonical_profile.narrative_structures = list(
                    dict.fromkeys(canonical_narratives + guest_narratives)
                )[:2]

            canonical_themes = list(canonical_profile.thematic_interests or [])
            guest_themes = list(guest_profile.thematic_interests or [])
            if guest_themes:
                canonical_profile.thematic_interests = list(
                    dict.fromkeys(canonical_themes + guest_themes)
                )[:3]

            # 7. Increment version counter
            canonical_profile.version = (canonical_profile.version or 1) + 1
            canonical_profile.save()

            logger.info(
                "Reconciled guest %s taste profile into canonical user %s (version=%s)",
                guest.id,
                canonical.id,
                canonical_profile.version,
            )
            return canonical_profile
