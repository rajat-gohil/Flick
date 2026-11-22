import logging
from datetime import timedelta
from typing import Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import (
    ConstraintExpansionProposal,
    GuestProfile,
    InteractionLog,
    Session,
    SessionChemistry,
    Swipe,
    UserTasteProfile,
    UserTasteSignal,
    WatchlistItem,
)

logger = logging.getLogger(__name__)


def is_taste_profile_customized(taste_profile: Optional[UserTasteProfile]) -> bool:
    """
    Returns True if the taste profile has any customized explicit preferences
    or learned weights differing from system baseline defaults.
    """
    if not taste_profile:
        return False

    # 1. Explicit Preferences Safeguards (baseline: all empty/defaults)
    if taste_profile.emotional_tonality:
        return True
    if taste_profile.narrative_structures:
        return True
    if taste_profile.thematic_interests:
        return True
    if taste_profile.viewing_rhythm and taste_profile.viewing_rhythm != "balanced":
        return True
    if taste_profile.preferred_languages:
        return True
    if taste_profile.default_min_rating is not None:
        return True
    if taste_profile.default_max_runtime is not None:
        return True
    if taste_profile.default_eras:
        return True
    if taste_profile.hard_exclusions not in ({}, None, ""):
        return True

    # 2. Learned Weights Safeguard
    if taste_profile.learned_weights not in ({}, None, ""):
        return True

    return False


def reap_abandoned_guests(
    days_inactive: int = 30,
    batch_size: int = 100,
) -> int:
    """
    Safely reaps abandoned, uncustomized guest accounts that have had zero activity
    for `days_inactive` (default 30 days).

    Safeguards:
    - Never deletes claimed or merged accounts (is_claimed=True).
    - NOTE ON RECOVERY KEY REVEAL EXEMPTION:
      A guest revealing their recovery key cannot be queried without a persisted
      `recovery_key_revealed_at` timestamp on GuestProfile. Adding this field requires
      a schema migration marked NEEDS MY APPROVAL. Until approved, the exemption is
      not yet enforceable. The reaper remains disabled and unscheduled.
    - Never deletes accounts with any swipes, watchlist items, session participation,
      interaction logs, taste signals, session chemistry, or expansion proposals.
    - Never deletes accounts with customized explicit preferences or learned weights.
    - Concurrency & Lock Hierarchy:
      Acquires `GuestProfile` via `select_for_update(of=('self',), skip_locked=True)`,
      followed by `User` via `select_for_update()`.
      PostgreSQL Lock Interaction: A child-row insert (e.g. `Swipe.objects.create`)
      acquires a `FOR KEY SHARE` lock on the parent `auth_user` row as part of foreign key
      validation. `FOR KEY SHARE` conflicts with the reaper's `FOR UPDATE` lock on `auth_user`,
      causing the child insert to block until the reaper transaction commits or rolls back.
      If the child insert committed immediately before lock acquisition, the in-transaction
      safeguard re-checks observe the new activity and abort deletion.
    """
    now = timezone.now()
    cutoff = now - timedelta(days=days_inactive)
    User = get_user_model()

    # Initial query for candidate guest profiles past inactivity cutoff
    candidate_ids = list(
        GuestProfile.objects.filter(
            is_claimed=False,
            last_active_at__lt=cutoff,
        ).values_list("id", flat=True)[:batch_size]
    )

    reaped_count = 0

    for profile_id in candidate_ids:
        try:
            with transaction.atomic():
                # 1. Lock GuestProfile using of=("self",) and skip_locked=True so active users are never blocked
                profile = (
                    GuestProfile.objects.select_for_update(of=("self",), skip_locked=True)
                    .filter(id=profile_id)
                    .first()
                )
                if not profile:
                    # Row locked by another concurrent transaction or deleted
                    continue

                # 2. Lock parent User row in compatible lock hierarchy (GuestProfile then User)
                try:
                    user = User.objects.select_for_update().get(id=profile.user_id)
                except User.DoesNotExist:
                    continue

                # 3. Re-verify every eligibility condition inside the transaction holding both locks:
                if profile.is_claimed:
                    continue
                if profile.last_active_at >= cutoff:
                    continue

                # Safeguard 1: Swipes
                if Swipe.objects.filter(user=user).exists():
                    continue

                # Safeguard 2: Watchlist
                if WatchlistItem.objects.filter(user=user).exists():
                    continue

                # Safeguard 3: Sessions (host or guest)
                if Session.objects.filter(Q(host=user) | Q(guest=user)).exists():
                    continue

                # Safeguard 4: Interaction Logs
                if InteractionLog.objects.filter(user=user).exists():
                    continue

                # Safeguard 5: UserTasteSignal
                if UserTasteSignal.objects.filter(user=user).exists():
                    continue

                # Safeguard 6: SessionChemistry
                if SessionChemistry.objects.filter(Q(user_a=user) | Q(user_b=user)).exists():
                    continue

                # Safeguard 7: ConstraintExpansionProposal
                if ConstraintExpansionProposal.objects.filter(initiated_by_user=user).exists():
                    continue

                # Safeguard 8: Taste Profile Customization Protection
                taste_profile = UserTasteProfile.objects.filter(user=user).first()
                if is_taste_profile_customized(taste_profile):
                    continue

                # All safeguards verified under lock: safe to delete user (cascades to profile, tokens, etc.)
                logger.info("Reaping abandoned guest user %s (profile %s)", user.id, profile.id)
                user.delete()
                reaped_count += 1

        except Exception as exc:
            logger.warning("Error evaluating candidate guest %s for reaping: %s", profile_id, exc)
            continue

    return reaped_count
