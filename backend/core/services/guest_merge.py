import logging
from typing import Any, Dict

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core.models import (
    ConstraintExpansionProposal,
    GuestProfile,
    InteractionLog,
    Match,
    Session,
    SessionChemistry,
    Swipe,
    UserIdentityLink,
    UserProfile,
    UserTasteProfile,
    UserTasteSignal,
    WatchlistItem,
)
from core.services.catalogue_queue import CatalogueQueueService
from core.services.identity_linking import IdentityLinkingService

logger = logging.getLogger(__name__)


class MergeConflictError(Exception):
    """
    Raised when guest claim state or identity link is in an inconsistent
    or conflicting state (HTTP 409).
    """
    pass


class MergeInputError(ValueError):
    """
    Raised when input guards fail: self-merge, unclaimed target, inactive target (HTTP 400).
    """
    pass


def normalize_pair(user1: Any, user2: Any) -> tuple:
    """
    Ensures user pair ordering is consistent: user with lower id is first.
    """
    return (user1, user2) if user1.id < user2.id else (user2, user1)


def verify_zero_orphans(guest_user: Any, permanent_user: Any) -> None:
    """
    Service-level assertion function.
    Verifies that all operational data has been re-parented or cleanly deduplicated.
    All checks use fresh database state and explicit exceptions (never bare assertions).
    """
    # 1. Re-read fresh state from database to avoid stale in-memory attributes
    guest_user.refresh_from_db()

    # 2. Query orphan counts fresh from database
    orphans = {
        "swipes": Swipe.objects.filter(user=guest_user).count(),
        "watchlist": WatchlistItem.objects.filter(user=guest_user).count(),
        "hosted_sessions": Session.objects.filter(host=guest_user).count(),
        "joined_sessions": Session.objects.filter(guest=guest_user).count(),
        "interaction_logs": InteractionLog.objects.filter(user=guest_user).count(),
        "taste_signals": UserTasteSignal.objects.filter(user=guest_user).count(),
        "chemistry_a": SessionChemistry.objects.filter(user_a=guest_user).count(),
        "chemistry_b": SessionChemistry.objects.filter(user_b=guest_user).count(),
        "proposals": ConstraintExpansionProposal.objects.filter(initiated_by_user=guest_user).count(),
        "taste_profile": UserTasteProfile.objects.filter(user=guest_user).count(),
        "active_tokens": Token.objects.filter(user=guest_user).count(),
    }

    violations = {k: v for k, v in orphans.items() if v > 0}
    if violations:
        raise ValidationError(f"Migration postcondition failed: orphaned records remain: {violations}")

    # 3. Standardized UserIdentityLink verification fresh from DB
    links = UserIdentityLink.objects.filter(linked_actor_id=guest_user.id)
    if links.count() != 1:
        raise ValidationError(
            f"Expected exactly 1 UserIdentityLink for guest {guest_user.id}, found {links.count()}"
        )
    link = links.first()
    if link.canonical_user_id != permanent_user.id:
        raise ValidationError(
            f"Link canonical_user {link.canonical_user_id} != expected {permanent_user.id}"
        )
    if link.link_type != UserIdentityLink.LinkType.GUEST_CONVERSION:
        raise ValidationError(
            f"Link type {link.link_type} != {UserIdentityLink.LinkType.GUEST_CONVERSION}"
        )

    # 4. Explicit verification of intentional retention of audit records
    guest_profile = GuestProfile.objects.filter(user=guest_user).first()
    if not guest_profile or not guest_profile.is_claimed or guest_profile.recovery_code != "":
        raise ValidationError(
            f"GuestProfile for user {guest_user.id} not properly soft-retired or recovery_code not wiped."
        )
    if not UserProfile.objects.filter(user=guest_user).exists():
        raise ValidationError(f"UserProfile audit record for guest {guest_user.id} missing.")
    if guest_user.is_active:
        raise ValidationError(
            f"Guest user {guest_user.id} remains active in database after retirement."
        )


def merge_guest_activity(guest_user: Any, permanent_user: Any) -> Dict[str, Any]:
    """
    Atomically reconciles and migrates all guest activity and relationships
    into a canonical permanent user account.

    Evaluates 3 input guards, 6-way claim matrix, locks GuestProfile followed by
    PK-ordered User rows, reconciles 14 relationship rules, soft-retires the guest,
    and validates zero-orphans postcondition.
    """
    # -------------------------------------------------------------
    # Step 1: Input Guards Validation (Evaluated before transaction)
    # -------------------------------------------------------------
    if guest_user.id == permanent_user.id:
        raise MergeInputError("Self-merge is not allowed.")

    if GuestProfile.objects.filter(user=permanent_user, is_claimed=False).exists() and permanent_user.is_active:
        raise MergeInputError("Cannot merge into an unclaimed guest account.")

    if not permanent_user.is_active:
        raise MergeInputError("Cannot merge into an inactive account.")

    if not GuestProfile.objects.filter(user_id=guest_user.id).exists():
        raise MergeInputError(f"User {guest_user.id} is not a guest account.")

    User = get_user_model()

    # -------------------------------------------------------------
    # Step 2: Begin Atomic Transaction
    # -------------------------------------------------------------
    with transaction.atomic():
        # Step 3: Exclusively lock GuestProfile without joined User row
        # Note: Do NOT filter by user__is_active=True so retired guests can be inspected
        guest_profile = GuestProfile.objects.select_for_update(of=("self",)).get(user_id=guest_user.id)

        # Step 4: Evaluate 6-Way Claim-State Matrix
        link = UserIdentityLink.objects.select_for_update().filter(linked_actor_id=guest_user.id).first()

        if not guest_profile.is_claimed:
            if link is not None:
                # Row 2: Inconsistent state (unclaimed but link exists)
                raise MergeConflictError(
                    f"Inconsistent state: Guest {guest_user.id} is unclaimed but linked to user {link.canonical_user_id}."
                )
            # Row 1: Normal merge, proceed to Step 5
        else:
            # guest_profile.is_claimed is True
            if link is None:
                # Row 6: Inconsistent state (claimed but no link exists)
                raise MergeConflictError(
                    f"Inconsistent state: Guest {guest_user.id} is claimed but has no UserIdentityLink."
                )
            if link.canonical_user_id == permanent_user.id:
                # Row 3: Idempotent retry by the same permanent user
                logger.info(
                    "Guest %s already merged into permanent user %s. Returning idempotent success.",
                    guest_user.id,
                    permanent_user.id,
                )
                return {
                    "status": "previously_merged",
                    "already_merged": True,
                    "canonical_user_id": permanent_user.id,
                    "guest_user_id": guest_user.id,
                }
            else:
                # Link points to a different canonical user
                canonical = link.canonical_user
                if canonical.is_active:
                    # Row 4: Claimed by a different active user
                    raise MergeConflictError(
                        f"Guest account {guest_user.id} has already been claimed by another user."
                    )
                else:
                    # Row 5: Link points to a deactivated/merged user
                    raise MergeConflictError(
                        f"Guest account {guest_user.id} was previously claimed by deactivated user {canonical.id}."
                    )

        # Step 5: Lock User rows in deterministic primary-key order
        pks = sorted([guest_user.id, permanent_user.id])
        locked_users = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=pks)}
        guest_user = locked_users[guest_user.id]
        permanent_user = locked_users[permanent_user.id]

        # Post-lock re-checks (Guards 2 and 3 only)
        # Re-check Guard 3: Target is active
        if not permanent_user.is_active:
            raise MergeInputError("Cannot merge into an inactive account.")

        # Re-check Guard 2: Target is not an active, unclaimed guest
        # Reading target's GuestProfile must NOT take a lock out of hierarchy order (no select_for_update)
        if GuestProfile.objects.filter(user_id=permanent_user.id, is_claimed=False).exists() and permanent_user.is_active:
            raise MergeInputError("Cannot merge into an unclaimed guest account.")

        # -------------------------------------------------------------
        # Step 6: Reconcile 14 Relationship Rules
        # -------------------------------------------------------------

        # Rule 1: core.Swipe.user
        for guest_swipe in Swipe.objects.select_for_update().filter(user=guest_user):
            perm_swipe = Swipe.objects.filter(
                user=permanent_user,
                session_id=guest_swipe.session_id,
                movie_id=guest_swipe.movie_id,
            ).first()
            if perm_swipe:
                # Before deleting guest_swipe, ensure Match attribution is permanently captured
                match = Match.objects.select_for_update().filter(
                    session_id=guest_swipe.session_id,
                    movie_id=guest_swipe.movie_id,
                ).first()
                if match and match.attribution is None:
                    session = match.session
                    host_id = session.host_id
                    guest_id = session.guest_id
                    swipes = [guest_swipe, perm_swipe]
                    host_rx = next((s.reaction for s in swipes if s.user_id == host_id), None)
                    guest_rx = next((s.reaction for s in swipes if s.user_id == guest_id), None)
                    if host_rx and guest_rx:
                        if host_rx == Swipe.SUPERLIKE and guest_rx == Swipe.SUPERLIKE:
                            match.attribution = "mutual"
                        elif host_rx == Swipe.SUPERLIKE:
                            match.attribution = "host"
                        elif guest_rx == Swipe.SUPERLIKE:
                            match.attribution = "guest"
                        else:
                            match.attribution = "none"
                    else:
                        match.attribution = "unknown"
                    match.save(update_fields=["attribution"])
                guest_swipe.delete()
            else:
                guest_swipe.user = permanent_user
                guest_swipe.save(update_fields=["user"])

        # Rule 2: core.WatchlistItem.user
        for guest_item in WatchlistItem.objects.select_for_update().filter(user=guest_user):
            perm_item = WatchlistItem.objects.select_for_update().filter(
                user=permanent_user,
                movie_id=guest_item.movie_id,
            ).first()
            if perm_item:
                if guest_item.watched and not perm_item.watched:
                    perm_item.watched = True
                    perm_item.watched_at = timezone.now()
                    perm_item.save(update_fields=["watched", "watched_at"])
                guest_item.delete()
            else:
                guest_item.user = permanent_user
                guest_item.save(update_fields=["user"])

        # Rule 3: core.Session.host
        for session in Session.objects.select_for_update().filter(host=guest_user):
            if session.guest_id == permanent_user.id:
                # Re-parent host to permanent, close session per spec
                session.host = permanent_user
                session.ended_at = timezone.now()
                session.save(update_fields=["host", "ended_at"])
            else:
                session.host = permanent_user
                session.save(update_fields=["host"])

        # Rule 4: core.Session.guest
        for session in Session.objects.select_for_update().filter(guest=guest_user):
            if session.host_id == permanent_user.id:
                # Re-parent guest to permanent, close session per spec
                session.guest = permanent_user
                session.ended_at = timezone.now()
                session.save(update_fields=["guest", "ended_at"])
            else:
                session.guest = permanent_user
                session.save(update_fields=["guest"])

        # Rule 5: core.InteractionLog.user (append-only ledger)
        InteractionLog.objects.filter(user=guest_user).update(user=permanent_user)

        # Rule 6: core.UserTasteSignal.user
        for guest_signal in UserTasteSignal.objects.select_for_update().filter(user=guest_user):
            perm_signal = UserTasteSignal.objects.select_for_update().filter(
                user=permanent_user,
                tag_id=guest_signal.tag_id,
            ).first()
            if perm_signal:
                perm_signal.like_count += guest_signal.like_count
                perm_signal.dislike_count += guest_signal.dislike_count
                if guest_signal.last_interacted_at:
                    if (
                        not perm_signal.last_interacted_at
                        or guest_signal.last_interacted_at > perm_signal.last_interacted_at
                    ):
                        perm_signal.last_interacted_at = guest_signal.last_interacted_at
                perm_signal.save()
                guest_signal.delete()
            else:
                guest_signal.user = permanent_user
                guest_signal.save(update_fields=["user"])

        # Rule 7: core.SessionChemistry
        chemistry_rows = SessionChemistry.objects.select_for_update().filter(
            Q(user_a=guest_user) | Q(user_b=guest_user)
        )
        for row in chemistry_rows:
            partner = row.user_b if row.user_a_id == guest_user.id else row.user_a
            if partner.id == permanent_user.id:
                # Self-chemistry elimination
                row.delete()
                continue

            new_a, new_b = normalize_pair(permanent_user, partner)
            existing = SessionChemistry.objects.select_for_update().filter(
                user_a=new_a,
                user_b=new_b,
                tag=row.tag,
            ).first()

            if existing:
                latest_timestamp = existing.last_matched_at
                if row.last_matched_at:
                    if not latest_timestamp or row.last_matched_at > latest_timestamp:
                        latest_timestamp = row.last_matched_at
                SessionChemistry.objects.filter(id=existing.id).update(
                    match_count=F("match_count") + row.match_count,
                    swipe_count=F("swipe_count") + row.swipe_count,
                    last_matched_at=latest_timestamp,
                )
                row.delete()
            else:
                try:
                    with transaction.atomic():
                        row.user_a = new_a
                        row.user_b = new_b
                        row.save()
                except IntegrityError:
                    # Concurrent task inserted target chemistry row during merge
                    existing = SessionChemistry.objects.select_for_update().get(
                        user_a=new_a,
                        user_b=new_b,
                        tag=row.tag,
                    )
                    latest_timestamp = existing.last_matched_at
                    if row.last_matched_at:
                        if not latest_timestamp or row.last_matched_at > latest_timestamp:
                            latest_timestamp = row.last_matched_at
                    SessionChemistry.objects.filter(id=existing.id).update(
                        match_count=F("match_count") + row.match_count,
                        swipe_count=F("swipe_count") + row.swipe_count,
                        last_matched_at=latest_timestamp,
                    )
                    row.delete()

        # Rule 8: core.ConstraintExpansionProposal
        ConstraintExpansionProposal.objects.filter(initiated_by_user=guest_user).update(
            initiated_by_user=permanent_user
        )

        # Rule 9: core.ProposalOutboxMessage
        # Preserved in place because proposals are re-parented rather than deleted.

        # Rule 10: core.UserTasteProfile
        IdentityLinkingService.reconcile_guest_taste_profile_into_canonical(
            permanent_user, guest_user
        )
        UserTasteProfile.objects.filter(user=guest_user).delete()

        # Rule 11: core.UserProfile
        UserProfile.objects.get_or_create(user=guest_user)

        # -------------------------------------------------------------
        # Step 7: Complete Guest Soft-Retirement & Credential Invalidation
        # -------------------------------------------------------------
        # Rule 12: core.GuestProfile
        guest_profile.is_claimed = True
        guest_profile.claimed_at = timezone.now()
        guest_profile.recovery_code = ""
        guest_profile.recovery_lookup_digest = ""
        guest_profile.recovery_verification_hash = ""
        guest_profile.previous_recovery_lookup_digest = ""
        guest_profile.previous_recovery_verification_hash = ""
        guest_profile.previous_recovery_expires_at = None
        guest_profile.save()

        # Rule 13: core.UserIdentityLink
        existing_link = (
            UserIdentityLink.objects.select_for_update()
            .filter(linked_actor_id=guest_user.id)
            .first()
        )
        if existing_link:
            if (
                existing_link.canonical_user_id != permanent_user.id
                or existing_link.link_type != UserIdentityLink.LinkType.GUEST_CONVERSION
            ):
                raise MergeConflictError(
                    f"Conflicting link exists for guest {guest_user.id}: bound to {existing_link.canonical_user_id}"
                )
        else:
            UserIdentityLink.objects.create(
                canonical_user=permanent_user,
                linked_actor_id=guest_user.id,
                link_type=UserIdentityLink.LinkType.GUEST_CONVERSION,
            )

        # Rule 14: authtoken.Token & User deactivation
        Token.objects.filter(user=guest_user).delete()
        guest_user.is_active = False
        guest_user.save(update_fields=["is_active"])

        # Purge idempotency record if present
        try:
            from core.models import GuestProvisioningIdempotency
            GuestProvisioningIdempotency.objects.filter(user=guest_user).delete()
        except Exception:
            pass

        # -------------------------------------------------------------
        # Step 8: Execute Postcondition Validation (Reads Fresh DB State)
        # -------------------------------------------------------------
        verify_zero_orphans(guest_user, permanent_user)

        # -------------------------------------------------------------
        # Step 9: Register Post-Commit External Queue Jobs
        # -------------------------------------------------------------
        transaction.on_commit(
            lambda: CatalogueQueueService.enqueue(
                job_type="recompute_taste_profile",
                entity_type="user",
                entity_id=str(permanent_user.id),
                priority=100,
            )
        )

        # -------------------------------------------------------------
        # Step 10: Return summary dictionary (Transaction Commits)
        # -------------------------------------------------------------
        return {
            "status": "merged",
            "already_merged": False,
            "canonical_user_id": permanent_user.id,
            "guest_user_id": guest_user.id,
        }
