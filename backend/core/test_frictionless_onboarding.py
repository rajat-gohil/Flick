import threading
import time
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.guest_security import (
    compute_recovery_lookup_digest,
    generate_recovery_code,
    hash_recovery_code,
)
from core.models import (
    ConstraintExpansionProposal,
    Genre,
    GuestProfile,
    GuestProvisioningIdempotency,
    InteractionLog,
    Match,
    Movie,
    MovieTag,
    ProposalOutboxMessage,
    Session,
    SessionChemistry,
    Swipe,
    UserIdentityLink,
    UserProfile,
    UserTasteProfile,
    UserTasteSignal,
    WatchlistItem,
)
from core.sentry_scrubber import scrub_sentry_event
from core.services.guest_cleanup import is_taste_profile_customized, reap_abandoned_guests
from core.services.guest_merge import (
    MergeConflictError,
    MergeInputError,
    merge_guest_activity,
    normalize_pair,
    verify_zero_orphans,
)

User = get_user_model()


class FrictionlessOnboardingBaseTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient()

        # Create permanent user
        self.perm_user = User.objects.create_user(
            username="permanent_cinephile",
            email="cinephile@example.com",
            password="securepassword123",
            first_name="Permanent Cinephile",
        )
        self.perm_profile = UserProfile.objects.create(
            user=self.perm_user,
            display_name="Permanent Cinephile",
            email_verified=True,
        )
        self.perm_token = Token.objects.create(user=self.perm_user)

        self.genre = Genre.objects.create(tmdb_id=18, name="Drama")
        self.movie1 = Movie.objects.create(
            tmdb_id=101,
            title="Pulp Fiction",
            overview="Crime classic",
        )
        self.movie2 = Movie.objects.create(
            tmdb_id=102,
            title="Inception",
            overview="Dream heist",
        )
        self.tag1 = MovieTag.objects.create(name="neo-noir")
        self.tag2 = MovieTag.objects.create(name="mind-bending")

    def create_guest(self, username_suffix="1", with_recovery_code=True):
        username = f"guest_test_{username_suffix}_{uuid.uuid4().hex[:6]}"
        user = User.objects.create_user(username=username)
        user.set_unusable_password()
        user.save()

        UserProfile.objects.create(user=user, display_name=f"Guest {username_suffix}")
        token = Token.objects.create(user=user)

        recovery_code = generate_recovery_code() if with_recovery_code else ""
        digest = compute_recovery_lookup_digest(recovery_code) if recovery_code else ""
        v_hash = hash_recovery_code(recovery_code) if recovery_code else ""

        guest_profile = GuestProfile.objects.create(
            user=user,
            recovery_code=recovery_code,
            recovery_lookup_digest=digest,
            recovery_verification_hash=v_hash,
            last_active_at=timezone.now(),
            is_claimed=False,
        )
        return user, guest_profile, token, recovery_code


class GuestMergeServiceTests(FrictionlessOnboardingBaseTestCase):
    # D.6a: Three separate fast-fail input guards
    def test_d6a_fast_fail_guard_1_self_merge(self):
        with self.assertRaises(MergeInputError) as ctx:
            merge_guest_activity(self.perm_user, self.perm_user)
        self.assertIn("Self-merge is not allowed", str(ctx.exception))

    def test_d6a_fast_fail_guard_2_target_active_unclaimed_guest(self):
        guest_user, _, _, _ = self.create_guest("d6a_source")
        unclaimed_target, _, _, _ = self.create_guest("d6a_unclaimed_target")
        with self.assertRaises(MergeInputError) as ctx:
            merge_guest_activity(guest_user, unclaimed_target)
        self.assertIn("Cannot merge into an unclaimed guest account", str(ctx.exception))

    def test_d6a_fast_fail_guard_3_target_inactive(self):
        guest_user, _, _, _ = self.create_guest("d6a_inactive")
        self.perm_user.is_active = False
        self.perm_user.save()
        with self.assertRaises(MergeInputError) as ctx:
            merge_guest_activity(guest_user, self.perm_user)
        self.assertIn("Cannot merge into an inactive account", str(ctx.exception))

    def test_d6a_fast_fail_source_not_a_guest(self):
        regular_user = User.objects.create_user(username="regular_non_guest")
        with self.assertRaises(MergeInputError) as ctx:
            merge_guest_activity(regular_user, self.perm_user)
        self.assertIn("is not a guest account", str(ctx.exception))

    # D.6b: Post-lock re-checks for guards 2 and 3 only
    def test_d6b_post_lock_recheck_guard_2_target_becomes_unclaimed_guest(self):
        guest_user, _, _, _ = self.create_guest("d6b_g2_guest")
        original_select = User.objects.select_for_update

        # Simulate target becoming an unclaimed guest after fast-fail pre-check
        def patched_select_for_update(*args, **kwargs):
            GuestProfile.objects.get_or_create(
                user=self.perm_user,
                defaults={"is_claimed": False, "recovery_code": "FLICK-TEST-1234-5678"},
            )
            return original_select(*args, **kwargs)

        with patch.object(User.objects, "select_for_update", side_effect=patched_select_for_update):
            with self.assertRaises(MergeInputError) as ctx:
                merge_guest_activity(guest_user, self.perm_user)
            self.assertIn("Cannot merge into an unclaimed guest account", str(ctx.exception))

        # Assert transaction rolled back
        guest_user.refresh_from_db()
        self.assertTrue(guest_user.is_active)
        self.assertFalse(UserIdentityLink.objects.filter(linked_actor_id=guest_user.id).exists())

    def test_d6b_post_lock_recheck_guard_3_target_becomes_inactive(self):
        guest_user, _, _, _ = self.create_guest("d6b_g3_guest")
        original_select = User.objects.select_for_update

        # Simulate target becoming inactive after fast-fail pre-check
        def patched_select_for_update(*args, **kwargs):
            User.objects.filter(id=self.perm_user.id).update(is_active=False)
            return original_select(*args, **kwargs)

        with patch.object(User.objects, "select_for_update", side_effect=patched_select_for_update):
            with self.assertRaises(MergeInputError) as ctx:
                merge_guest_activity(guest_user, self.perm_user)
            self.assertIn("Cannot merge into an inactive account", str(ctx.exception))

        # Assert transaction rolled back
        guest_user.refresh_from_db()
        self.assertTrue(guest_user.is_active)
        self.assertFalse(UserIdentityLink.objects.filter(linked_actor_id=guest_user.id).exists())

    # D.5: Idempotent retry after merge with deactivated guest
    def test_d5_idempotent_retry_after_merge_with_deactivated_guest(self):
        guest_user, guest_profile, _, _ = self.create_guest("d5_retry")
        res1 = merge_guest_activity(guest_user, self.perm_user)
        self.assertEqual(res1["status"], "merged")

        # Confirm guest is soft-retired (is_active=False, is_claimed=True)
        guest_user.refresh_from_db()
        guest_profile.refresh_from_db()
        self.assertFalse(guest_user.is_active)
        self.assertTrue(guest_profile.is_claimed)

        # Calling merge again with the deactivated guest must return Row 3 idempotent success
        res2 = merge_guest_activity(guest_user, self.perm_user)
        self.assertEqual(res2["status"], "previously_merged")
        self.assertTrue(res2["already_merged"])
        self.assertEqual(res2["canonical_user_id"], self.perm_user.id)
        self.assertEqual(res2["guest_user_id"], guest_user.id)

    def test_claim_matrix_rows(self):
        # Row 2: is_claimed=False but link exists -> 409 Conflict
        guest_user, guest_profile, _, _ = self.create_guest("row2")
        UserIdentityLink.objects.create(
            canonical_user=self.perm_user,
            linked_actor_id=guest_user.id,
            link_type=UserIdentityLink.LinkType.GUEST_CONVERSION,
        )
        with self.assertRaises(MergeConflictError) as ctx:
            merge_guest_activity(guest_user, self.perm_user)
        self.assertIn("Inconsistent state: Guest", str(ctx.exception))

        # Row 6: is_claimed=True but link does NOT exist -> 409 Conflict
        guest_user6, guest_profile6, _, _ = self.create_guest("row6")
        guest_profile6.is_claimed = True
        guest_profile6.save()
        with self.assertRaises(MergeConflictError) as ctx:
            merge_guest_activity(guest_user6, self.perm_user)
        self.assertIn("has no UserIdentityLink", str(ctx.exception))

        # Row 4: Claimed by a different active user -> 409 Conflict
        guest_user4, guest_profile4, _, _ = self.create_guest("row4")
        other_user = User.objects.create_user(username="other_active_user")
        guest_profile4.is_claimed = True
        guest_profile4.save()
        UserIdentityLink.objects.create(
            canonical_user=other_user,
            linked_actor_id=guest_user4.id,
            link_type=UserIdentityLink.LinkType.GUEST_CONVERSION,
        )
        with self.assertRaises(MergeConflictError) as ctx:
            merge_guest_activity(guest_user4, self.perm_user)
        self.assertIn("already been claimed by another user", str(ctx.exception))

        # Row 5: Claimed by a deactivated user -> 409 Conflict
        guest_user5, guest_profile5, _, _ = self.create_guest("row5")
        deactivated_user = User.objects.create_user(username="deact_user", is_active=False)
        guest_profile5.is_claimed = True
        guest_profile5.save()
        UserIdentityLink.objects.create(
            canonical_user=deactivated_user,
            linked_actor_id=guest_user5.id,
            link_type=UserIdentityLink.LinkType.GUEST_CONVERSION,
        )
        with self.assertRaises(MergeConflictError) as ctx:
            merge_guest_activity(guest_user5, self.perm_user)
        self.assertIn("previously claimed by deactivated user", str(ctx.exception))

    def test_reconciliation_all_14_rules(self):
        guest_user, guest_profile, guest_token, recovery_code = self.create_guest("reconcile_all")

        session1 = Session.objects.create(host=guest_user, code="GUEST1")
        session2 = Session.objects.create(host=self.perm_user, guest=guest_user, code="PAIR01")

        # 1. Swipes
        Swipe.objects.create(user=guest_user, session=session1, movie=self.movie1, reaction="like")
        Swipe.objects.create(user=guest_user, session=session2, movie=self.movie2, reaction="dislike")
        Swipe.objects.create(user=self.perm_user, session=session2, movie=self.movie2, reaction="like")

        # 2. Watchlist
        WatchlistItem.objects.create(user=guest_user, movie=self.movie1, watched=True)
        WatchlistItem.objects.create(user=guest_user, movie=self.movie2, watched=True)
        WatchlistItem.objects.create(user=self.perm_user, movie=self.movie2, watched=False)

        # 5. InteractionLog
        InteractionLog.objects.create(user=guest_user, movie=self.movie1, event_type="app_opened")

        # 6. UserTasteSignal
        UserTasteSignal.objects.create(user=guest_user, tag=self.tag1, like_count=2, dislike_count=1)
        UserTasteSignal.objects.create(user=self.perm_user, tag=self.tag1, like_count=5, dislike_count=0)
        UserTasteSignal.objects.create(user=guest_user, tag=self.tag2, like_count=1, dislike_count=0)

        # 7. SessionChemistry
        partner = User.objects.create_user(username="chemistry_partner")
        SessionChemistry.objects.create(
            user_a=guest_user,
            user_b=partner,
            tag=self.tag1.name,
            match_count=3,
            swipe_count=5,
            last_matched_at=timezone.now() - timedelta(hours=2),
        )
        u1, u2 = normalize_pair(guest_user, self.perm_user)
        SessionChemistry.objects.create(
            user_a=u1,
            user_b=u2,
            tag=self.tag2.name,
            match_count=1,
            swipe_count=2,
            last_matched_at=timezone.now() - timedelta(hours=1),
        )

        # 8 & 9. ConstraintExpansionProposal & Outbox
        proposal = ConstraintExpansionProposal.objects.create(
            initiated_by_user=guest_user,
            session=session1,
            original_constraints={"genre": "drama"},
            proposed_constraints={"genre": "all"},
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        outbox = ProposalOutboxMessage.objects.create(
            proposal=proposal,
            session=session1,
            topic="proposal_created",
            payload={"status": "pending"},
        )

        # 10. UserTasteProfile
        UserTasteProfile.objects.create(
            user=guest_user,
            emotional_tonality=["quirky"],
            learned_weights={"director:lynch": 2.0},
        )
        UserTasteProfile.objects.create(
            user=self.perm_user,
            emotional_tonality=["moody"],
            learned_weights={"director:nolan": 1.5},
        )

        # Execute Merge
        res = merge_guest_activity(guest_user, self.perm_user)
        self.assertEqual(res["status"], "merged")

        # Verify zero orphans
        verify_zero_orphans(guest_user, self.perm_user)

        # Rule 1: Swipes
        self.assertEqual(Swipe.objects.filter(user=guest_user).count(), 0)
        self.assertEqual(Swipe.objects.filter(user=self.perm_user, movie=self.movie1).count(), 1)
        self.assertEqual(
            Swipe.objects.get(user=self.perm_user, session=session2, movie=self.movie2).reaction,
            "like",
        )

        # Rule 2: Watchlist
        self.assertEqual(WatchlistItem.objects.filter(user=guest_user).count(), 0)
        w2 = WatchlistItem.objects.get(user=self.perm_user, movie=self.movie2)
        self.assertTrue(w2.watched)

        # Rule 3 & 4: Sessions
        session1.refresh_from_db()
        self.assertEqual(session1.host_id, self.perm_user.id)
        session2.refresh_from_db()
        self.assertIsNotNone(session2.ended_at)

        # Rule 5: InteractionLog
        self.assertEqual(InteractionLog.objects.filter(user=guest_user).count(), 0)
        self.assertEqual(InteractionLog.objects.filter(user=self.perm_user, event_type="app_opened").count(), 1)

        # Rule 6: UserTasteSignal
        self.assertEqual(UserTasteSignal.objects.filter(user=guest_user).count(), 0)
        signal1 = UserTasteSignal.objects.get(user=self.perm_user, tag=self.tag1)
        self.assertEqual(signal1.like_count, 7)
        self.assertEqual(signal1.dislike_count, 1)

        # Rule 7: SessionChemistry
        self.assertEqual(SessionChemistry.objects.filter(user_a=guest_user).count(), 0)
        self.assertEqual(SessionChemistry.objects.filter(user_b=guest_user).count(), 0)
        self.assertFalse(SessionChemistry.objects.filter(tag=self.tag2.name).exists())
        ca, cb = normalize_pair(self.perm_user, partner)
        self.assertTrue(SessionChemistry.objects.filter(user_a=ca, user_b=cb, tag=self.tag1.name).exists())

        # Rule 8 & 9: Proposal & Outbox
        proposal.refresh_from_db()
        self.assertEqual(proposal.initiated_by_user_id, self.perm_user.id)
        outbox.refresh_from_db()
        self.assertEqual(outbox.proposal.initiated_by_user_id, self.perm_user.id)

        # Rule 10: UserTasteProfile
        self.assertEqual(UserTasteProfile.objects.filter(user=guest_user).count(), 0)
        perm_tp = UserTasteProfile.objects.get(user=self.perm_user)
        self.assertIn("quirky", perm_tp.emotional_tonality)
        self.assertIn("moody", perm_tp.emotional_tonality)
        self.assertEqual(perm_tp.learned_weights.get("director:nolan"), 1.5)

        # Rule 11 & 12 & 13 & 14: Soft retirement
        guest_profile.refresh_from_db()
        self.assertTrue(guest_profile.is_claimed)
        self.assertEqual(guest_profile.recovery_code, "")
        self.assertEqual(guest_profile.recovery_lookup_digest, "")
        self.assertEqual(guest_profile.recovery_verification_hash, "")
        self.assertEqual(Token.objects.filter(user=guest_user).count(), 0)
        guest_user.refresh_from_db()
        self.assertFalse(guest_user.is_active)

    # I.2: SessionChemistry IntegrityError fallback with timestamps & null handling
    def test_i2_session_chemistry_integrity_error_fallback(self):
        guest_user, _, _, _ = self.create_guest("i2_guest")
        partner = User.objects.create_user(username="i2_partner")

        t_guest = timezone.now() - timedelta(minutes=5)
        t_existing = timezone.now() - timedelta(hours=1)

        # Guest row
        SessionChemistry.objects.create(
            user_a=guest_user,
            user_b=partner,
            tag="noir",
            match_count=2,
            swipe_count=4,
            last_matched_at=t_guest,
        )

        new_a, new_b = normalize_pair(self.perm_user, partner)

        # Pre-create conflicting row that will trigger IntegrityError on save
        conflicting_row = SessionChemistry.objects.create(
            user_a=new_a,
            user_b=new_b,
            tag="noir",
            match_count=5,
            swipe_count=10,
            last_matched_at=t_existing,
        )

        # Merge should hit IntegrityError and fallback to update existing row
        merge_guest_activity(guest_user, self.perm_user)

        conflicting_row.refresh_from_db()
        self.assertEqual(conflicting_row.match_count, 7)  # 5 + 2
        self.assertEqual(conflicting_row.swipe_count, 14)  # 10 + 4
        self.assertEqual(conflicting_row.last_matched_at, t_guest)  # max(t_guest, t_existing)

    def test_i2_session_chemistry_integrity_error_fallback_with_null_timestamp(self):
        guest_user, _, _, _ = self.create_guest("i2_null_guest")
        partner = User.objects.create_user(username="i2_null_partner")

        t_guest = timezone.now()

        SessionChemistry.objects.create(
            user_a=guest_user,
            user_b=partner,
            tag="indie",
            match_count=1,
            swipe_count=2,
            last_matched_at=t_guest,
        )

        new_a, new_b = normalize_pair(self.perm_user, partner)

        conflicting_row = SessionChemistry.objects.create(
            user_a=new_a,
            user_b=new_b,
            tag="indie",
            match_count=3,
            swipe_count=5,
            last_matched_at=None,
        )

        merge_guest_activity(guest_user, self.perm_user)

        conflicting_row.refresh_from_db()
        self.assertEqual(conflicting_row.match_count, 4)  # 3 + 1
        self.assertEqual(conflicting_row.swipe_count, 7)  # 5 + 2
        self.assertEqual(conflicting_row.last_matched_at, t_guest)  # preserves non-null timestamp

    def test_verify_zero_orphans_triggers_rollback(self):
        guest_user, _, _, _ = self.create_guest("rollback_test")

        with patch("core.services.guest_merge.verify_zero_orphans", side_effect=ValidationError("Orphans detected")):
            with self.assertRaises(ValidationError):
                merge_guest_activity(guest_user, self.perm_user)

        # Database transaction rolled back!
        guest_user.refresh_from_db()
        self.assertTrue(guest_user.is_active)
        self.assertEqual(Token.objects.filter(user=guest_user).count(), 1)
        self.assertFalse(UserIdentityLink.objects.filter(linked_actor_id=guest_user.id).exists())

    def test_guest_merge_swipe_collision_and_match_attribution_regression(self):
        """
        Part B Regression Test:
        Establish real database behavior when guest and permanent account swipe the same movie
        in the same session and an associated Match exists.
        """
        guest_user, _, _, _ = self.create_guest("collision_guest")
        session = Session.objects.create(host=self.perm_user, guest=guest_user, code="COL101")

        movie_ord = Movie.objects.create(title="Ordinary Match Movie", tmdb_id=101001)
        movie_guest_sup = Movie.objects.create(title="Guest Superlike Movie", tmdb_id=101002)
        movie_mutual_sup = Movie.objects.create(title="Mutual Superlike Movie", tmdb_id=101003)

        # 1. Ordinary Match: perm LIKE, guest LIKE
        Swipe.objects.create(user=self.perm_user, session=session, movie=movie_ord, reaction=Swipe.LIKE)
        Swipe.objects.create(user=guest_user, session=session, movie=movie_ord, reaction=Swipe.LIKE)
        match_ord = Match.objects.create(session=session, movie=movie_ord)
        self.assertEqual(match_ord.superlike_attribution, "none")

        # 2. Guest Superlike: perm LIKE, guest SUPERLIKE
        Swipe.objects.create(user=self.perm_user, session=session, movie=movie_guest_sup, reaction=Swipe.LIKE)
        Swipe.objects.create(user=guest_user, session=session, movie=movie_guest_sup, reaction=Swipe.SUPERLIKE)
        match_guest_sup = Match.objects.create(session=session, movie=movie_guest_sup)
        self.assertEqual(match_guest_sup.superlike_attribution, "guest")

        # 3. Mutual Superlike: perm SUPERLIKE, guest SUPERLIKE
        Swipe.objects.create(user=self.perm_user, session=session, movie=movie_mutual_sup, reaction=Swipe.SUPERLIKE)
        Swipe.objects.create(user=guest_user, session=session, movie=movie_mutual_sup, reaction=Swipe.SUPERLIKE)
        match_mutual_sup = Match.objects.create(session=session, movie=movie_mutual_sup)
        self.assertEqual(match_mutual_sup.superlike_attribution, "mutual")

        # Confirm 2 swipe rows per movie prior to merge
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_ord).count(), 2)
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_guest_sup).count(), 2)
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_mutual_sup).count(), 2)

        # Execute Merge
        res = merge_guest_activity(guest_user, self.perm_user)
        self.assertEqual(res["status"], "merged")

        # Database state after merge:
        # A. All 3 matches survived
        self.assertTrue(Match.objects.filter(session=session, movie=movie_ord).exists())
        self.assertTrue(Match.objects.filter(session=session, movie=movie_guest_sup).exists())
        self.assertTrue(Match.objects.filter(session=session, movie=movie_mutual_sup).exists())

        # B. Exactly 1 swipe row survived per movie (guest swipe deleted by Rule 1 collision reconciliation)
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_ord).count(), 1)
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_guest_sup).count(), 1)
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie_mutual_sup).count(), 1)

        # C. Surviving swipe is permanent user swipe
        surviving_ord = Swipe.objects.get(session=session, movie=movie_ord)
        self.assertEqual(surviving_ord.user_id, self.perm_user.id)
        self.assertEqual(surviving_ord.reaction, Swipe.LIKE)

        surviving_guest_sup = Swipe.objects.get(session=session, movie=movie_guest_sup)
        self.assertEqual(surviving_guest_sup.user_id, self.perm_user.id)
        self.assertEqual(surviving_guest_sup.reaction, Swipe.LIKE)  # Perm user's LIKE survived; Guest's SUPERLIKE was deleted

        surviving_mutual_sup = Swipe.objects.get(session=session, movie=movie_mutual_sup)
        self.assertEqual(surviving_mutual_sup.user_id, self.perm_user.id)
        self.assertEqual(surviving_mutual_sup.reaction, Swipe.SUPERLIKE)

        # D. Attribution consequences:
        match_ord.refresh_from_db()
        self.assertEqual(match_ord.attribution, "none")
        self.assertEqual(match_ord.superlike_attribution, "none")

        match_guest_sup.refresh_from_db()
        # Fixed: Attribution preserved as 'guest' even though guest swipe was deleted
        self.assertEqual(match_guest_sup.attribution, "guest")
        self.assertEqual(match_guest_sup.superlike_attribution, "guest")

        match_mutual_sup.refresh_from_db()
        # Fixed: Attribution preserved as 'mutual' even though guest swipe was deleted and session self-paired
        self.assertEqual(match_mutual_sup.attribution, "mutual")
        self.assertEqual(match_mutual_sup.superlike_attribution, "mutual")

    def test_legacy_match_without_swipes_returns_unknown(self):
        """
        Legacy Match without persisted attribution and missing swipe data
        must explicitly evaluate to 'unknown' rather than falsely defaulting to 'none'.
        """
        user1 = self.perm_user
        user2, _, _, _ = self.create_guest("legacy_guest")
        session = Session.objects.create(host=user1, guest=user2, code="LEG001")
        movie = Movie.objects.create(title="Legacy Movie", tmdb_id=202001)

        # Create match directly with attribution=None (representing pre-migration legacy match)
        match = Match.objects.create(session=session, movie=movie, attribution=None)
        # Update via queryset to bypass save() auto-population
        Match.objects.filter(id=match.id).update(attribution=None)
        match.refresh_from_db()
        self.assertIsNone(match.attribution)

        # Case 1: No swipes exist for this match
        self.assertEqual(match.superlike_attribution, "unknown")
        self.assertEqual(match.match_type, "unknown")

        # Case 2: Only 1 swipe exists for this match
        Swipe.objects.create(user=user1, session=session, movie=movie, reaction=Swipe.LIKE)
        match = Match.objects.get(id=match.id)
        self.assertEqual(match.superlike_attribution, "unknown")
        self.assertEqual(match.match_type, "unknown")

    def test_guest_merge_reconciliation_failure_atomicity_rollback(self):
        """
        Part B Regression Test:
        Verifies that any unexpected reconciliation failure rolls back all merge operations,
        leaving guest swipes, matches, and guest account fully intact.
        """
        guest_user, _, _, _ = self.create_guest("rollback_atomicity_guest")
        session = Session.objects.create(host=self.perm_user, guest=guest_user, code="COL102")
        movie = Movie.objects.create(title="Atomicity Movie", tmdb_id=101004)

        Swipe.objects.create(user=self.perm_user, session=session, movie=movie, reaction=Swipe.LIKE)
        Swipe.objects.create(user=guest_user, session=session, movie=movie, reaction=Swipe.SUPERLIKE)
        match = Match.objects.create(session=session, movie=movie)

        # Force a failure during Rule 5 (InteractionLog)
        with patch.object(InteractionLog.objects, "filter", side_effect=RuntimeError("Simulated ledger failure")):
            with self.assertRaises(RuntimeError):
                merge_guest_activity(guest_user, self.perm_user)

        # Verify atomic rollback:
        # 1. Guest user still active
        guest_user.refresh_from_db()
        self.assertTrue(guest_user.is_active)
        # 2. Both swipe rows still intact
        self.assertEqual(Swipe.objects.filter(session=session, movie=movie).count(), 2)
        guest_swipe = Swipe.objects.get(user=guest_user, session=session, movie=movie)
        self.assertEqual(guest_swipe.reaction, Swipe.SUPERLIKE)
        # 3. Match attribution preserved
        match.refresh_from_db()
        self.assertEqual(match.superlike_attribution, "guest")
        # 4. Session participants preserved
        session.refresh_from_db()
        self.assertEqual(session.host_id, self.perm_user.id)
        self.assertEqual(session.guest_id, guest_user.id)
        self.assertIsNone(session.ended_at)


class GuestViewsTests(FrictionlessOnboardingBaseTestCase):
    def test_recovery_key_retrieval_endpoint_security(self):
        guest_user, guest_profile, guest_token, recovery_code = self.create_guest("sec_test")

        # G.1: Unauthenticated request -> 401
        res = self.client.get("/api/auth/guest-recovery-key/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # G.2: Permanent user request -> 403
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.perm_token.key}")
        res = self.client.get("/api/auth/guest-recovery-key/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Valid Guest request -> 200 with no-store headers
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {guest_token.key}")
        res = self.client.get("/api/auth/guest-recovery-key/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["recovery_code"], recovery_code)
        # G.5: Cache-Control: no-store
        self.assertIn("no-store", res.headers.get("Cache-Control", ""))

        # G.3: Claimed/converted guest -> 403
        guest_profile.is_claimed = True
        guest_profile.save()
        res = self.client.get("/api/auth/guest-recovery-key/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_recovery_flow_endpoint(self):
        guest_user, guest_profile, old_token, recovery_code = self.create_guest("recover_flow")

        res = self.client.post("/api/auth/guest-recover/", {"recovery_code": recovery_code}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        new_token_key = res.data["token"]
        self.assertNotEqual(new_token_key, old_token.key)
        self.assertEqual(res.data["user"]["id"], guest_user.id)

        # Re-post with original code within handoff window returns HTTP 200
        res_retry = self.client.post("/api/auth/guest-recover/", {"recovery_code": recovery_code}, format="json")
        self.assertEqual(res_retry.status_code, status.HTTP_200_OK)
        self.assertTrue(res_retry.data["success"])
        self.assertEqual(res_retry.data["user"]["id"], guest_user.id)


class GuestProvisioningIdempotencyTests(FrictionlessOnboardingBaseTestCase):
    def test_provisioning_idempotency_replay(self):
        key = str(uuid.uuid4())

        res1 = self.client.post(
            "/api/auth/guest-provision/",
            {"display_name": "Idempotent Explorer"},
            HTTP_X_IDEMPOTENCY_KEY=key,
            format="json",
        )
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        token1 = res1.data["token"]
        user_id = res1.data["user"]["id"]

        res2 = self.client.post(
            "/api/auth/guest-provision/",
            HTTP_X_IDEMPOTENCY_KEY=key,
            format="json",
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["token"], token1)
        self.assertEqual(res2.data["user"]["id"], user_id)

    # C.6: Uniform 410 for missing, purged, expired, claimed, and deactivated user replays
    def test_c6_uniform_410_responses(self):
        expected_body = {
            "success": False,
            "error": "Provisioning replay capability is expired or no longer available.",
        }

        # 1. Expired record
        key_exp = str(uuid.uuid4())
        u_exp, _, _, _ = self.create_guest("c6_exp")
        GuestProvisioningIdempotency.objects.create(
            idempotency_key=key_exp,
            user=u_exp,
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        res_exp = self.client.post("/api/auth/guest-provision/", HTTP_X_IDEMPOTENCY_KEY=key_exp, format="json")
        self.assertEqual(res_exp.status_code, status.HTTP_410_GONE)
        self.assertEqual(res_exp.data, expected_body)

        # 2. Claimed guest
        key_claimed = str(uuid.uuid4())
        u_claimed, p_claimed, _, _ = self.create_guest("c6_claimed")
        p_claimed.is_claimed = True
        p_claimed.save()
        GuestProvisioningIdempotency.objects.create(
            idempotency_key=key_claimed,
            user=u_claimed,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        res_claimed = self.client.post("/api/auth/guest-provision/", HTTP_X_IDEMPOTENCY_KEY=key_claimed, format="json")
        self.assertEqual(res_claimed.status_code, status.HTTP_410_GONE)
        self.assertEqual(res_claimed.data, expected_body)

        # 3. Deactivated user
        key_deact = str(uuid.uuid4())
        u_deact, _, _, _ = self.create_guest("c6_deact")
        u_deact.is_active = False
        u_deact.save()
        GuestProvisioningIdempotency.objects.create(
            idempotency_key=key_deact,
            user=u_deact,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        res_deact = self.client.post("/api/auth/guest-provision/", HTTP_X_IDEMPOTENCY_KEY=key_deact, format="json")
        self.assertEqual(res_deact.status_code, status.HTTP_410_GONE)
        self.assertEqual(res_deact.data, expected_body)


class AbandonedGuestReaperTests(FrictionlessOnboardingBaseTestCase):
    # H.6: Reaper eligibility baseline cases
    def test_h6_reaper_untouched_provisioned_profile_reaped(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_untouched", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=31)
        guest_profile.save()

        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 1)
        self.assertFalse(User.objects.filter(id=guest_user.id).exists())

    def test_h6_reaper_customized_explicit_preference_with_empty_learned_weights_protected(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_custom_explicit", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=35)
        guest_profile.save()

        UserTasteProfile.objects.create(
            user=guest_user,
            emotional_tonality=["moody"],
            learned_weights={},
        )
        self.assertTrue(is_taste_profile_customized(UserTasteProfile.objects.get(user=guest_user)))

        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 0)
        self.assertTrue(User.objects.filter(id=guest_user.id).exists())

    def test_h6_reaper_null_learned_weights_reaped_if_untouched(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_null_weights", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=35)
        guest_profile.save()

        # In-memory check for null learned_weights
        dummy_profile = UserTasteProfile(user=guest_user, emotional_tonality=[], learned_weights=None)
        self.assertFalse(is_taste_profile_customized(dummy_profile))

        # DB untouched profile is reaped
        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 1)
        self.assertFalse(User.objects.filter(id=guest_user.id).exists())

    def test_h6_reaper_empty_learned_weights_reaped_if_untouched(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_empty_weights", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=35)
        guest_profile.save()

        UserTasteProfile.objects.create(
            user=guest_user,
            emotional_tonality=[],
            learned_weights={},
        )
        self.assertFalse(is_taste_profile_customized(UserTasteProfile.objects.get(user=guest_user)))

        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 1)
        self.assertFalse(User.objects.filter(id=guest_user.id).exists())

    def test_h6_reaper_non_empty_learned_weights_protected(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_non_empty_weights", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=35)
        guest_profile.save()

        UserTasteProfile.objects.create(
            user=guest_user,
            emotional_tonality=[],
            learned_weights={"director:nolan": 1.5},
        )
        self.assertTrue(is_taste_profile_customized(UserTasteProfile.objects.get(user=guest_user)))

        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 0)
        self.assertTrue(User.objects.filter(id=guest_user.id).exists())

    def test_reaper_protects_active_guest(self):
        guest_user, guest_profile, _, _ = self.create_guest("h6_active_recent", with_recovery_code=True)
        guest_profile.last_active_at = timezone.now() - timedelta(days=10)
        guest_profile.save()

        count = reap_abandoned_guests(days_inactive=30)
        self.assertEqual(count, 0)
        self.assertTrue(User.objects.filter(id=guest_user.id).exists())


class SentryScrubberTests(TestCase):
    # G.7: Sentry payload scrubber assertion
    def test_g7_sentry_payload_scrubbing_and_negative_assertion(self):
        benign_uuid = "e7230834-789e-486c-913c-8b6998e3ce3d"
        movie_tmdb_id = 157336

        event = {
            "request": {
                "headers": {
                    "X-Idempotency-Key": "4a71b123-4567-489a-bcde-f0123456789a",
                    "User-Agent": "FlickApp/1.0",
                },
                "data": {
                    "idempotency_key": "4a71b123-4567-489a-bcde-f0123456789a",
                    "recovery_code": "FLICK-ABCD-EFGH-JKMN-PQRT",
                    "movie_id": movie_tmdb_id,
                    "request_uuid": benign_uuid,
                },
            },
            "breadcrumbs": [
                {
                    "message": "User entered FLICK-WXYZ-2345-6789-ABCD to recover",
                    "category": "auth",
                }
            ],
            "exception": {
                "values": [
                    {"value": "Failed verifying FLICK-9999-8888-7777-6666 for session"}
                ]
            },
        }

        scrubbed = scrub_sentry_event(event)

        # 1. Assert header redacted
        self.assertEqual(scrubbed["request"]["headers"]["X-Idempotency-Key"], "[REDACTED]")
        # 2. Assert payload fields redacted
        self.assertEqual(scrubbed["request"]["data"]["idempotency_key"], "[REDACTED]")
        self.assertEqual(scrubbed["request"]["data"]["recovery_code"], "[REDACTED]")
        # 3. Assert regex replacement in breadcrumbs and exceptions
        self.assertIn("[REDACTED]", scrubbed["breadcrumbs"][0]["message"])
        self.assertNotIn("FLICK-WXYZ-2345-6789-ABCD", scrubbed["breadcrumbs"][0]["message"])
        self.assertIn("[REDACTED]", scrubbed["exception"]["values"][0]["value"])
        self.assertNotIn("FLICK-9999-8888-7777-6666", scrubbed["exception"]["values"][0]["value"])

        # 4. NEGATIVE ASSERTIONS: Benign values are NOT redacted
        self.assertEqual(scrubbed["request"]["data"]["request_uuid"], benign_uuid)
        self.assertEqual(scrubbed["request"]["data"]["movie_id"], movie_tmdb_id)
        self.assertEqual(scrubbed["request"]["headers"]["User-Agent"], "FlickApp/1.0")


class FrictionlessOnboardingConcurrencyTests(TransactionTestCase):
    """
    Real multi-connection PostgreSQL concurrency test suite.
    Tests lock acquisition, serialization, race recovery, and deadlock freedom.
    """

    def setUp(self):
        super().setUp()
        self.genre = Genre.objects.create(tmdb_id=18, name="Drama")
        self.movie = Movie.objects.create(tmdb_id=201, title="Concurrency Movie")

    def create_guest(self, username_suffix="conc"):
        username = f"guest_c_{username_suffix}_{uuid.uuid4().hex[:6]}"
        user = User.objects.create_user(username=username)
        user.set_unusable_password()
        user.save()
        UserProfile.objects.create(user=user, display_name=f"Guest {username_suffix}")
        token = Token.objects.create(user=user)
        recovery_code = generate_recovery_code()
        digest = compute_recovery_lookup_digest(recovery_code)
        v_hash = hash_recovery_code(recovery_code)
        guest_profile = GuestProfile.objects.create(
            user=user,
            recovery_code=recovery_code,
            recovery_lookup_digest=digest,
            recovery_verification_hash=v_hash,
            last_active_at=timezone.now(),
            is_claimed=False,
        )
        return user, guest_profile, token, recovery_code

    # C.7: Same-key provisioning race
    def test_c7_same_key_provisioning_race(self):
        key = str(uuid.uuid4())
        results = []
        barrier = threading.Barrier(2)

        def worker():
            close_old_connections()
            client = APIClient()
            try:
                barrier.wait(timeout=5)
                res = client.post(
                    "/api/auth/guest-provision/",
                    {"display_name": "Racer"},
                    HTTP_X_IDEMPOTENCY_KEY=key,
                    format="json",
                )
                results.append(res)
            finally:
                close_old_connections()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(results), 2)
        status_codes = sorted([r.status_code for r in results])
        self.assertEqual(status_codes, [status.HTTP_200_OK, status.HTTP_201_CREATED])

        # Both must receive the exact same auth token and user ID
        token1 = results[0].data["token"]
        token2 = results[1].data["token"]
        self.assertEqual(token1, token2)

        uid1 = results[0].data["user"]["id"]
        uid2 = results[1].data["user"]["id"]
        self.assertEqual(uid1, uid2)

        # Assert exactly one user was created in DB for this key
        count = GuestProvisioningIdempotency.objects.filter(idempotency_key=key).count()
        self.assertEqual(count, 1)

    # D.1: Concurrent same-user merge
    def test_d1_concurrent_same_user_merge(self):
        guest_user, _, _, _ = self.create_guest("d1")
        perm_user = User.objects.create_user(username=f"perm_d1_{uuid.uuid4().hex[:6]}")
        UserProfile.objects.create(user=perm_user, display_name="Perm D1")
        Token.objects.create(user=perm_user)

        results = []
        barrier = threading.Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                res = merge_guest_activity(guest_user, perm_user)
                results.append({"status": "ok", "data": res})
            except Exception as e:
                results.append({"status": "error", "error": e})
            finally:
                close_old_connections()

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(results), 2)
        statuses = sorted([r["data"]["status"] for r in results if r["status"] == "ok"])
        self.assertEqual(statuses, ["merged", "previously_merged"])
        verify_zero_orphans(guest_user, perm_user)

    # D.2: Concurrent different-user merge
    def test_d2_concurrent_different_user_merge(self):
        guest_user, _, _, _ = self.create_guest("d2")
        perm_user1 = User.objects.create_user(username=f"perm_d2_1_{uuid.uuid4().hex[:6]}")
        UserProfile.objects.create(user=perm_user1, display_name="Perm D2 1")
        Token.objects.create(user=perm_user1)

        perm_user2 = User.objects.create_user(username=f"perm_d2_2_{uuid.uuid4().hex[:6]}")
        UserProfile.objects.create(user=perm_user2, display_name="Perm D2 2")
        Token.objects.create(user=perm_user2)

        results = []
        barrier = threading.Barrier(2)

        def worker(target_user):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                res = merge_guest_activity(guest_user, target_user)
                results.append({"target": target_user.id, "result": res})
            except Exception as e:
                results.append({"target": target_user.id, "error": e})
            finally:
                close_old_connections()

        t1 = threading.Thread(target=worker, args=(perm_user1,))
        t2 = threading.Thread(target=worker, args=(perm_user2,))
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(results), 2)
        successes = [r for r in results if "result" in r]
        conflicts = [r for r in results if "error" in r and isinstance(r["error"], MergeConflictError)]
        self.assertEqual(len(successes), 1)
        self.assertEqual(len(conflicts), 1)

    # D.7: Concurrent merge vs GuestConvertView (asserting no deadlock)
    def test_d7_concurrent_merge_vs_guest_convert_deadlock_free(self):
        guest_user, guest_profile, guest_token, recovery_code = self.create_guest("d7")
        perm_user = User.objects.create_user(username=f"perm_d7_{uuid.uuid4().hex[:6]}")
        UserProfile.objects.create(user=perm_user, display_name="Perm D7")
        Token.objects.create(user=perm_user)

        results = []
        barrier = threading.Barrier(2)

        def merge_worker():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                res = merge_guest_activity(guest_user, perm_user)
                results.append({"op": "merge", "res": res})
            except Exception as e:
                results.append({"op": "merge", "error": repr(e)})
            finally:
                close_old_connections()

        def convert_worker():
            close_old_connections()
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Token {guest_token.key}")
            try:
                barrier.wait(timeout=5)
                res = client.post(
                    "/api/auth/guest-convert/",
                    {
                        "username": f"conv_{uuid.uuid4().hex[:8]}",
                        "email": f"conv_{uuid.uuid4().hex[:6]}@example.com",
                        "password": "Password123!",
                    },
                    format="json",
                )
                results.append({"op": "convert", "res": res.status_code})
            except Exception as e:
                results.append({"op": "convert", "error": repr(e)})
            finally:
                close_old_connections()

        t1 = threading.Thread(target=merge_worker)
        t2 = threading.Thread(target=convert_worker)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        self.assertEqual(len(results), 2)
        for r in results:
            err = r.get("error", "")
            self.assertNotIn("deadlock detected", err.lower())

    # H.7: Real two-connection blocking test - Outcome 1: Reaper deletes guest; blocked Swipe insert fails
    def test_h7_reaper_blocking_outcome_1_reaper_deletes_guest_swipe_fails(self):
        guest_user, guest_profile, _, _ = self.create_guest("h7_block_del")
        session = Session.objects.create(code="H7DEL", host=guest_user)

        b_started = threading.Event()
        b_done = threading.Event()
        b_result = {}

        def thread_b():
            close_old_connections()
            b_started.set()
            try:
                t0 = time.time()
                # Swipe insert takes foreign key check on auth_user (FOR KEY SHARE)
                s = Swipe.objects.create(
                    user=guest_user,
                    movie=self.movie,
                    session=session,
                    reaction="like",
                )
                b_result["duration"] = time.time() - t0
                b_result["status"] = "success"
                b_result["swipe_id"] = s.id
            except Exception as e:
                b_result["status"] = "error"
                b_result["error"] = repr(e)
            finally:
                b_done.set()
                close_old_connections()

        # Transaction A (Reaper deletes guest)
        with transaction.atomic():
            GuestProfile.objects.select_for_update(of=("self",)).get(id=guest_profile.id)
            User.objects.select_for_update().get(id=guest_user.id)

            t_b = threading.Thread(target=thread_b)
            t_b.start()
            b_started.wait(timeout=5)

            # Give thread B time to attempt insert and block
            time.sleep(0.4)
            # PROVE BLOCKING: Thread B is NOT done while A holds lock
            self.assertFalse(b_done.is_set(), "Thread B must be blocked waiting on auth_user FOR UPDATE lock")

            # Reaper deletes the guest account
            guest_profile.delete()
            session.delete()
            guest_user.delete()

        # After Transaction A commits delete, Thread B fails because parent row is gone
        t_b.join(timeout=5)
        self.assertTrue(b_done.is_set(), "Thread B should complete after A releases lock")
        self.assertEqual(b_result.get("status"), "error")
        # Assert failure: Swipe was NOT created
        self.assertFalse(Swipe.objects.filter(user_id=guest_user.id).exists())

    # H.7: Real two-connection blocking test - Outcome 2: Reaper aborts delete; blocked Swipe insert proceeds
    def test_h7_reaper_blocking_outcome_2_reaper_aborts_delete_swipe_succeeds(self):
        guest_user, guest_profile, _, _ = self.create_guest("h7_block_abort")
        session = Session.objects.create(code="H7ABT", host=guest_user)

        b_started = threading.Event()
        b_done = threading.Event()
        b_result = {}

        def thread_b():
            close_old_connections()
            b_started.set()
            try:
                t0 = time.time()
                # Swipe insert takes foreign key check on auth_user (FOR KEY SHARE)
                s = Swipe.objects.create(
                    user=guest_user,
                    movie=self.movie,
                    session=session,
                    reaction="like",
                )
                b_result["duration"] = time.time() - t0
                b_result["status"] = "success"
                b_result["swipe_id"] = s.id
            except Exception as e:
                b_result["status"] = "error"
                b_result["error"] = repr(e)
            finally:
                b_done.set()
                close_old_connections()

        # Transaction A (Reaper lock hierarchy, rechecks activity, aborts delete)
        with transaction.atomic():
            GuestProfile.objects.select_for_update(of=("self",)).get(id=guest_profile.id)
            User.objects.select_for_update().get(id=guest_user.id)

            t_b = threading.Thread(target=thread_b)
            t_b.start()
            b_started.wait(timeout=5)

            # Give thread B time to attempt insert and block
            time.sleep(0.4)
            # PROVE BLOCKING: Thread B is NOT done while A holds lock
            self.assertFalse(b_done.is_set(), "Thread B must be blocked waiting on auth_user FOR UPDATE lock")

            # Reaper does NOT delete because activity was signaled/detected; transaction commits/exits

        # Exiting transaction A releases lock -> Thread B unblocks and succeeds
        t_b.join(timeout=5)
        self.assertTrue(b_done.is_set(), "Thread B should complete after A releases lock")
        self.assertEqual(b_result.get("status"), "success")
        self.assertGreaterEqual(b_result.get("duration", 0), 0.35)
        self.assertTrue(Swipe.objects.filter(id=b_result["swipe_id"]).exists())

    # Reaper skip_locked test
    def test_h7_reaper_skip_locked_skips_locked_profile(self):
        guest_user, guest_profile, _, _ = self.create_guest("h7_skip")
        guest_profile.last_active_at = timezone.now() - timedelta(days=35)
        guest_profile.save()

        a_locked = threading.Event()
        reaper_done = threading.Event()
        reaper_count = []

        def locker_thread():
            close_old_connections()
            with transaction.atomic():
                GuestProfile.objects.select_for_update(of=("self",)).get(id=guest_profile.id)
                a_locked.set()
                reaper_done.wait(timeout=5)
            close_old_connections()

        t_lock = threading.Thread(target=locker_thread)
        t_lock.start()
        a_locked.wait(timeout=5)

        try:
            # Reaper runs while guest_profile is locked; skip_locked=True must skip it immediately
            count = reap_abandoned_guests(days_inactive=30)
            reaper_count.append(count)
        finally:
            reaper_done.set()
            t_lock.join(timeout=5)

        self.assertEqual(reaper_count, [0])
        self.assertTrue(User.objects.filter(id=guest_user.id).exists())
