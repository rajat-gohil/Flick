"""
Batch 4: Reconciliation, Identity Linking, Taste Engine, and Tombstoning Test Suite.

Comprehensive tests covering:
1. UserIdentityLink uniqueness, cardinality, and constraints.
2. InteractionLog processing_status state machine, indices, and source_swipe_id uniqueness.
3. SwipeUndoView inverse weight parity (-1.0 for like, +1.2 for dislike, -3.0 for superlike).
4. HistoricalReconciliationService idempotency, batching, and metrics.
5. IdentityLinkingService guest-to-canonical linking, query aggregation, and taste profile merging.
6. TasteEngineService pending event processing, learned weights aggregation, and deterministic recomputation.
7. TombstoneService privacy anonymization, metadata sanitization, and account deletion.
"""

from datetime import timedelta
from typing import Any, Dict
import unittest

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    Genre,
    GuestProfile,
    InteractionLog,
    LinkType,
    Match,
    Movie,
    MovieExposure,
    MovieKeyword,
    MovieTag,
    Session,
    Swipe,
    UserIdentityLink,
    UserProfile,
    UserTasteProfile,
)
from core.services.historical_reconciliation import HistoricalReconciliationService
from core.services.identity_linking import (
    DuplicateIdentityLinkError,
    IdentityLinkingService,
)
from core.services.taste_engine import TasteEngineService
from core.services.tombstone import TombstoneService

User = get_user_model()


class UserIdentityLinkModelTests(TestCase):
    """
    Verifies UserIdentityLink uniqueness constraints, cardinality, and relationships.
    """

    def setUp(self):
        self.canonical_user = User.objects.create_user(username="canonical_1", password="pw")
        self.guest_user_1 = User.objects.create_user(username="guest_1", password="pw")
        self.guest_user_2 = User.objects.create_user(username="guest_2", password="pw")

    def test_link_creation_and_attributes(self):
        link = UserIdentityLink.objects.create(
            canonical_user=self.canonical_user,
            linked_actor_id=self.guest_user_1.id,
            link_type=LinkType.GUEST_CONVERSION,
        )
        self.assertEqual(link.canonical_user, self.canonical_user)
        self.assertEqual(link.linked_actor_id, self.guest_user_1.id)
        self.assertEqual(link.link_type, "guest_conversion")
        self.assertIsNotNone(link.linked_at)

    def test_linked_actor_id_uniqueness(self):
        """
        A guest actor can only be linked to AT MOST one canonical user.
        Attempting to link the same linked_actor_id again must raise IntegrityError.
        """
        UserIdentityLink.objects.create(
            canonical_user=self.canonical_user,
            linked_actor_id=self.guest_user_1.id,
            link_type=LinkType.GUEST_CONVERSION,
        )

        canonical_user_2 = User.objects.create_user(username="canonical_2", password="pw")
        with self.assertRaises(IntegrityError):
            UserIdentityLink.objects.create(
                canonical_user=canonical_user_2,
                linked_actor_id=self.guest_user_1.id,
                link_type=LinkType.SESSION_CLAIM,
            )

    def test_canonical_user_cardinality_one_to_many(self):
        """
        A canonical user can claim multiple distinct guest identities (1:N).
        """
        link1 = UserIdentityLink.objects.create(
            canonical_user=self.canonical_user,
            linked_actor_id=self.guest_user_1.id,
            link_type=LinkType.GUEST_CONVERSION,
        )
        link2 = UserIdentityLink.objects.create(
            canonical_user=self.canonical_user,
            linked_actor_id=self.guest_user_2.id,
            link_type=LinkType.SESSION_CLAIM,
        )

        linked_guest_identities = self.canonical_user.linked_guest_identities.all()
        self.assertEqual(linked_guest_identities.count(), 2)
        linked_actor_ids = set(linked_guest_identities.values_list("linked_actor_id", flat=True))
        self.assertEqual(linked_actor_ids, {self.guest_user_1.id, self.guest_user_2.id})

    def test_cascade_delete_on_canonical_user(self):
        """
        Deleting canonical_user cascades and removes the identity links.
        """
        UserIdentityLink.objects.create(
            canonical_user=self.canonical_user,
            linked_actor_id=self.guest_user_1.id,
            link_type=LinkType.GUEST_CONVERSION,
        )
        self.assertEqual(UserIdentityLink.objects.count(), 1)
        self.canonical_user.delete()
        self.assertEqual(UserIdentityLink.objects.count(), 0)


class InteractionLogProcessingStatusTests(TestCase):
    """
    Verifies InteractionLog processing_status state machine and constraints.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="interaction_user", password="pw")
        self.movie = Movie.objects.create(tmdb_id=201, title="Interaction Movie", provenance="tmdb_catalogue")

    def test_default_processing_status_is_pending(self):
        log = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
        )
        self.assertEqual(log.processing_status, "pending")
        self.assertIsNone(log.processed_at)

    def test_transition_to_processed(self):
        log = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
        )
        now = timezone.now()
        log.processing_status = "processed"
        log.processed_at = now
        log.save()

        refreshed = InteractionLog.objects.get(id=log.id)
        self.assertEqual(refreshed.processing_status, "processed")
        self.assertIsNotNone(refreshed.processed_at)

    def test_source_swipe_id_uniqueness(self):
        """
        source_swipe_id must enforce unique constraint when non-null.
        """
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
            source_swipe_id=777,
        )
        with self.assertRaises(IntegrityError):
            InteractionLog.objects.create(
                user=self.user,
                movie=self.movie,
                event_type="swipe_like",
                weight=1.0,
                source_swipe_id=777,
            )

    def test_composite_index_lookup(self):
        """
        Queries filtering on user and processing_status execute cleanly.
        """
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        pending_logs = InteractionLog.objects.filter(user=self.user, processing_status="pending")
        self.assertEqual(pending_logs.count(), 1)


class SwipeUndoViewInverseParityTests(TestCase):
    """
    Verifies SwipeUndoView inverse weight calculation parity:
    - LIKE (+1.0) -> undo weight = -1.0
    - DISLIKE (-1.2) -> undo weight = +1.2
    - SUPERLIKE (+3.0) -> undo weight = -3.0
    """

    def setUp(self):
        self.client = APIClient()
        self.host_user = User.objects.create_user(username="host_user", password="pw")
        self.guest_user = User.objects.create_user(username="guest_user_session", password="pw")
        self.session = Session.objects.create(
            host=self.host_user,
            guest=self.guest_user,
            code="UNDO01",
        )
        self.movie_like = Movie.objects.create(tmdb_id=301, title="Like Movie", provenance="tmdb_catalogue")
        self.movie_dislike = Movie.objects.create(tmdb_id=302, title="Dislike Movie", provenance="tmdb_catalogue")
        self.movie_superlike = Movie.objects.create(tmdb_id=303, title="Superlike Movie", provenance="tmdb_catalogue")

    def test_undo_like_inverse_weight_parity(self):
        self.client.force_authenticate(user=self.host_user)
        swipe = Swipe.objects.create(
            user=self.host_user,
            session=self.session,
            movie=self.movie_like,
            reaction=Swipe.LIKE,
        )

        response = self.client.delete(
            "/api/swipes/undo/",
            data={"session_id": self.session.id, "movie_id": self.movie_like.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Swipe.objects.filter(id=swipe.id).exists())

        undo_log = InteractionLog.objects.filter(
            user=self.host_user,
            session=self.session,
            movie=self.movie_like,
            event_type="undo",
        ).first()
        self.assertIsNotNone(undo_log)
        self.assertEqual(undo_log.weight, -1.0)
        self.assertEqual(undo_log.processing_status, "pending")
        self.assertEqual(undo_log.metadata.get("undone_swipe_id"), swipe.id)
        self.assertEqual(undo_log.metadata.get("undone_reaction"), Swipe.LIKE)

    def test_undo_dislike_inverse_weight_parity(self):
        self.client.force_authenticate(user=self.host_user)
        swipe = Swipe.objects.create(
            user=self.host_user,
            session=self.session,
            movie=self.movie_dislike,
            reaction=Swipe.DISLIKE,
        )

        response = self.client.delete(
            "/api/swipes/undo/",
            data={"session_id": self.session.id, "movie_id": self.movie_dislike.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Swipe.objects.filter(id=swipe.id).exists())

        undo_log = InteractionLog.objects.filter(
            user=self.host_user,
            session=self.session,
            movie=self.movie_dislike,
            event_type="undo",
        ).first()
        self.assertIsNotNone(undo_log)
        self.assertEqual(undo_log.weight, 1.2)
        self.assertEqual(undo_log.processing_status, "pending")
        self.assertEqual(undo_log.metadata.get("undone_swipe_id"), swipe.id)
        self.assertEqual(undo_log.metadata.get("undone_reaction"), Swipe.DISLIKE)

    def test_undo_superlike_inverse_weight_parity(self):
        self.client.force_authenticate(user=self.host_user)
        swipe = Swipe.objects.create(
            user=self.host_user,
            session=self.session,
            movie=self.movie_superlike,
            reaction=Swipe.SUPERLIKE,
        )

        response = self.client.delete(
            "/api/swipes/undo/",
            data={"session_id": self.session.id, "movie_id": self.movie_superlike.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Swipe.objects.filter(id=swipe.id).exists())

        undo_log = InteractionLog.objects.filter(
            user=self.host_user,
            session=self.session,
            movie=self.movie_superlike,
            event_type="undo",
        ).first()
        self.assertIsNotNone(undo_log)
        self.assertEqual(undo_log.weight, -3.0)
        self.assertEqual(undo_log.processing_status, "pending")
        self.assertEqual(undo_log.metadata.get("undone_swipe_id"), swipe.id)
        self.assertEqual(undo_log.metadata.get("undone_reaction"), Swipe.SUPERLIKE)


class TombstoneServiceTests(TestCase):
    """
    Verifies TombstoneService anonymization and account deletion preserving analytical logs.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tombstone_target", password="pw")
        self.movie_1 = Movie.objects.create(tmdb_id=401, title="Tombstone Movie 1", provenance="tmdb_catalogue")
        self.movie_2 = Movie.objects.create(tmdb_id=402, title="Tombstone Movie 2", provenance="tmdb_catalogue")

        self.user_profile = UserProfile.objects.create(user=self.user, display_name="Target")
        self.taste_profile = UserTasteProfile.objects.create(
            user=self.user,
            learned_weights={"dark": 1.5, "noir": 0.8},
        )

        self.guest_user = User.objects.create_user(username="linked_guest", password="pw")
        self.identity_link = UserIdentityLink.objects.create(
            canonical_user=self.user,
            linked_actor_id=self.guest_user.id,
            link_type=LinkType.GUEST_CONVERSION,
        )

        self.log_like = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_1,
            event_type="swipe_like",
            weight=1.0,
            metadata={"ip": "192.168.1.100", "user_agent": "Mozilla/5.0", "session": "s1"},
        )
        self.log_dislike = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_2,
            event_type="swipe_dislike",
            weight=-1.2,
            metadata={"ip": "192.168.1.100", "user_agent": "Mozilla/5.0", "geo": "US"},
        )

    def test_anonymize_and_delete_user_metrics_and_side_effects(self):
        user_id = self.user.id
        metrics = TombstoneService.anonymize_and_delete_user(self.user)

        self.assertEqual(metrics["logs_reassigned"], 2)
        self.assertEqual(metrics["links_purged"], 1)
        self.assertEqual(metrics["taste_deleted"], 1)

        # 1. User record is deleted
        self.assertFalse(User.objects.filter(id=user_id).exists())

        # 2. Associated profiles and links are deleted
        self.assertFalse(UserProfile.objects.filter(id=self.user_profile.id).exists())
        self.assertFalse(UserTasteProfile.objects.filter(id=self.taste_profile.id).exists())
        self.assertFalse(UserIdentityLink.objects.filter(id=self.identity_link.id).exists())

        # 3. System tombstone actor exists and is disabled
        tombstone_actor = TombstoneService.get_or_create_tombstone_actor()
        self.assertEqual(tombstone_actor.username, TombstoneService.TOMBSTONE_USERNAME)
        self.assertFalse(tombstone_actor.is_active)

        # 4. Analytical interaction logs are preserved under tombstone actor
        self.log_like.refresh_from_db()
        self.log_dislike.refresh_from_db()
        self.assertEqual(self.log_like.user, tombstone_actor)
        self.assertEqual(self.log_dislike.user, tombstone_actor)

        # 5. Metadata is scrubbed, preserving only anonymized=True and event_type
        self.assertEqual(self.log_like.metadata, {"anonymized": True, "event_type": "swipe_like"})
        self.assertEqual(self.log_dislike.metadata, {"anonymized": True, "event_type": "swipe_dislike"})
        self.assertNotIn("ip", self.log_like.metadata)
        self.assertNotIn("user_agent", self.log_like.metadata)

    def test_tombstone_actor_cannot_be_deleted(self):
        tombstone_actor = TombstoneService.get_or_create_tombstone_actor()
        with self.assertRaises(ValueError):
            TombstoneService.anonymize_and_delete_user(tombstone_actor)


class HistoricalReconciliationServiceTests(TestCase):
    """
    Verifies HistoricalReconciliationService idempotency and backdating guarantees.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="recon_user", password="pw")
        self.other_user = User.objects.create_user(username="recon_partner", password="pw")
        self.session = Session.objects.create(host=self.user, guest=self.other_user, code="RECON1")
        self.movie_like = Movie.objects.create(tmdb_id=501, title="Recon Like", provenance="tmdb_catalogue")
        self.movie_dislike = Movie.objects.create(tmdb_id=502, title="Recon Dislike", provenance="tmdb_catalogue")
        self.movie_superlike = Movie.objects.create(tmdb_id=503, title="Recon Superlike", provenance="tmdb_catalogue")

    def test_reconciliation_run1_ingests_run2_idempotently_skips(self):
        """
        Run 1 ingests 3 missing historical swipes into InteractionLogs.
        Run 2 detects existing source_swipe_ids and ingests 0 (100% idempotent).
        """
        past_time = timezone.now() - timedelta(days=5)
        swipe1 = Swipe.objects.create(
            user=self.user,
            session=self.session,
            movie=self.movie_like,
            reaction=Swipe.LIKE,
            created_at=past_time,
        )
        swipe2 = Swipe.objects.create(
            user=self.user,
            session=self.session,
            movie=self.movie_dislike,
            reaction=Swipe.DISLIKE,
            created_at=past_time,
        )
        swipe3 = Swipe.objects.create(
            user=self.user,
            session=self.session,
            movie=self.movie_superlike,
            reaction=Swipe.SUPERLIKE,
            created_at=past_time,
        )

        # Initial state: 0 interaction logs
        self.assertEqual(InteractionLog.objects.count(), 0)

        # Run 1: Must reconcile 3 swipes
        summary1 = HistoricalReconciliationService.reconcile(dry_run=False, batch_size=10)
        self.assertEqual(summary1["reconciled_count"], 3)
        self.assertEqual(summary1["skipped_count"], 0)
        self.assertEqual(InteractionLog.objects.count(), 3)

        # Verify weights and event types
        log1 = InteractionLog.objects.get(source_swipe_id=swipe1.id)
        self.assertEqual(log1.event_type, "swipe_like")
        self.assertEqual(log1.weight, 1.0)
        self.assertEqual(log1.processing_status, "pending")
        self.assertTrue(log1.metadata.get("reconciled"))

        log2 = InteractionLog.objects.get(source_swipe_id=swipe2.id)
        self.assertEqual(log2.event_type, "swipe_dislike")
        self.assertEqual(log2.weight, -1.2)

        log3 = InteractionLog.objects.get(source_swipe_id=swipe3.id)
        self.assertEqual(log3.event_type, "superlike")
        self.assertEqual(log3.weight, 3.0)

        # Run 2: Immediate retry must ingest 0 and skip 3
        summary2 = HistoricalReconciliationService.reconcile(dry_run=False, batch_size=10)
        self.assertEqual(summary2["reconciled_count"], 0)
        self.assertEqual(summary2["skipped_count"], 3)
        self.assertEqual(InteractionLog.objects.count(), 3)

    def test_reconciliation_dry_run_no_database_mutations(self):
        """
        dry_run=True inspects and reports pending swipes without creating any records.
        """
        Swipe.objects.create(
            user=self.user,
            session=self.session,
            movie=self.movie_like,
            reaction=Swipe.LIKE,
        )
        Swipe.objects.create(
            user=self.user,
            session=self.session,
            movie=self.movie_dislike,
            reaction=Swipe.DISLIKE,
        )

        summary = HistoricalReconciliationService.reconcile(dry_run=True, batch_size=10)
        self.assertEqual(summary["reconciled_count"], 2)
        self.assertTrue(summary["dry_run"])
        self.assertEqual(InteractionLog.objects.count(), 0)


class IdentityLinkingServiceTests(TestCase):
    """
    Verifies IdentityLinkingService linking guest to canonical user, query aggregation,
    and taste preference reconciliation.
    """

    def setUp(self):
        self.canonical_user = User.objects.create_user(username="canonical_primary", password="pw")
        self.guest_user_1 = User.objects.create_user(username="guest_actor_alpha", password="pw")
        self.guest_user_2 = User.objects.create_user(username="guest_actor_beta", password="pw")

    def test_link_guest_to_user_success_and_query_aggregation(self):
        link = IdentityLinkingService.link_guest_to_user(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user_1,
            link_type="guest_conversion",
        )
        self.assertEqual(link.canonical_user, self.canonical_user)
        self.assertEqual(link.linked_actor_id, self.guest_user_1.id)

        # Verify get_all_actor_ids_for_user returns canonical and guest id
        actor_ids = IdentityLinkingService.get_all_actor_ids_for_user(self.canonical_user)
        self.assertEqual(set(actor_ids), {self.canonical_user.id, self.guest_user_1.id})

    def test_link_guest_duplicate_different_canonical_rejected(self):
        IdentityLinkingService.link_guest_to_user(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user_1,
            link_type="guest_conversion",
        )

        other_canonical = User.objects.create_user(username="canonical_secondary", password="pw")
        with self.assertRaises(DuplicateIdentityLinkError):
            IdentityLinkingService.link_guest_to_user(
                canonical_user=other_canonical,
                guest_user=self.guest_user_1,
                link_type="session_claim",
            )

    def test_link_guest_to_same_canonical_is_idempotent(self):
        link1 = IdentityLinkingService.link_guest_to_user(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user_1,
            link_type="guest_conversion",
        )
        link2 = IdentityLinkingService.link_guest_to_user(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user_1,
            link_type="guest_conversion",
        )
        self.assertEqual(link1.id, link2.id)

    def test_link_self_rejected(self):
        with self.assertRaises(ValueError):
            IdentityLinkingService.link_guest_to_user(
                canonical_user=self.canonical_user,
                guest_user=self.canonical_user,
            )

    def test_reconcile_guest_taste_profile_into_canonical(self):
        UserTasteProfile.objects.create(
            user=self.canonical_user,
            default_eras=["80s", "90s"],
            preferred_languages=["en", "es"],
            default_max_runtime=120,
            hard_exclusions={"genres": ["horror"]},
        )
        UserTasteProfile.objects.create(
            user=self.guest_user_1,
            default_eras=["90s", "2000s"],
            preferred_languages=["en", "fr"],
            default_max_runtime=150,
            hard_exclusions={"genres": ["documentary"]},
        )

        IdentityLinkingService.reconcile_guest_taste_profile_into_canonical(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user_1,
        )

        canonical_profile = UserTasteProfile.objects.get(user=self.canonical_user)
        self.assertEqual(canonical_profile.default_eras, ["80s", "90s", "2000s"])
        self.assertEqual(canonical_profile.preferred_languages, ["en", "es", "fr"])
        self.assertEqual(canonical_profile.default_max_runtime, 150)
        self.assertIn("horror", canonical_profile.hard_exclusions["genres"])
        self.assertIn("documentary", canonical_profile.hard_exclusions["genres"])


class TasteEngineServiceTests(TestCase):
    """
    Verifies TasteEngineService pending event processing, learned weights aggregation,
    undo inverse signal handling, and cross-identity profile recomputation.
    """

    def setUp(self):
        self.canonical_user = User.objects.create_user(username="taste_canonical", password="pw")
        self.guest_user = User.objects.create_user(username="taste_guest", password="pw")

        # Create Genre, MovieTag, and MovieKeyword
        self.genre_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.genre_sci_fi = Genre.objects.create(name="Science Fiction", tmdb_id=878)
        self.tag_cyberpunk = MovieTag.objects.create(name="cyberpunk")
        self.kw_ai = MovieKeyword.objects.create(name="artificial-intelligence", tmdb_id=9901)

        # Create movies
        self.movie_matrix = Movie.objects.create(
            tmdb_id=601,
            title="The Matrix",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[28, 878],
        )
        self.movie_matrix.genres.add(self.genre_action, self.genre_sci_fi)
        self.movie_matrix.tags.add(self.tag_cyberpunk)
        self.movie_matrix.keywords.add(self.kw_ai)

        self.movie_dune = Movie.objects.create(
            tmdb_id=602,
            title="Dune",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[878],
        )
        self.movie_dune.genres.add(self.genre_sci_fi)
        self.movie_dune.tags.add(self.tag_cyberpunk)

    def test_recompute_pending_events_accumulates_weights_and_marks_processed(self):
        """
        Creates pending InteractionLogs for canonical user, triggers recompute,
        and verifies learned_weights contain expected genre, tag, and keyword values.
        """
        log1 = InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_matrix,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        log2 = InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_dune,
            event_type="superlike",
            weight=3.0,
            processing_status="pending",
        )

        res = TasteEngineService.recompute_user_taste_profile(self.canonical_user)
        self.assertEqual(res["events_claimed"], 2)
        self.assertEqual(res["remaining_pending"], 0)

        # Logs must be updated to processed
        log1.refresh_from_db()
        log2.refresh_from_db()
        self.assertEqual(log1.processing_status, "processed")
        self.assertIsNotNone(log1.processed_at)
        self.assertEqual(log2.processing_status, "processed")
        self.assertIsNotNone(log2.processed_at)

        # Verify UserTasteProfile learned_weights
        profile = UserTasteProfile.objects.get(user=self.canonical_user)
        weights = profile.learned_weights

        # Action: in movie_matrix (+1.0)
        self.assertAlmostEqual(weights["genres"]["Action"], 1.0, places=3)
        # Science Fiction: in matrix (+1.0) and dune (+3.0) -> +4.0
        self.assertAlmostEqual(weights["genres"]["Science Fiction"], 4.0, places=3)
        # Cyberpunk tag: in matrix (+1.0) and dune (+3.0) -> +4.0
        self.assertAlmostEqual(weights["tags"]["cyberpunk"], 4.0, places=3)
        # artificial-intelligence keyword: in matrix (+1.0)
        self.assertAlmostEqual(weights["keywords"]["artificial-intelligence"], 1.0, places=3)

    def test_recompute_early_return_when_no_pending_events(self):
        """
        When there are no pending interaction logs, recompute exits early without updating version.
        """
        profile = UserTasteProfile.objects.create(user=self.canonical_user, version=1)
        res = TasteEngineService.recompute_user_taste_profile(self.canonical_user)

        self.assertEqual(res["events_claimed"], 0)
        profile.refresh_from_db()
        self.assertEqual(profile.version, 1)

    def test_undo_inverse_signal_cancels_previous_swipe(self):
        """
        A like (+1.0) followed by an undo (-1.0) on the same movie deterministically
        yields net 0.0 learned weights for that movie's traits.
        """
        InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_matrix,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_matrix,
            event_type="undo",
            weight=-1.0,
            processing_status="pending",
            metadata={"undone_reaction": "like"},
        )

        TasteEngineService.recompute_user_taste_profile(self.canonical_user)
        profile = UserTasteProfile.objects.get(user=self.canonical_user)
        weights = profile.learned_weights

        # Net weights should be 0.0
        self.assertAlmostEqual(weights["genres"]["Action"], 0.0, places=3)
        self.assertAlmostEqual(weights["genres"]["Science Fiction"], 0.0, places=3)
        self.assertAlmostEqual(weights["tags"]["cyberpunk"], 0.0, places=3)

    def test_cross_identity_linking_aggregates_guest_events_into_canonical_profile(self):
        """
        Verifies that when a guest user is linked to a canonical user,
        TasteEngineService recomputes canonical profile combining events from BOTH users.
        """
        # Link guest to canonical
        IdentityLinkingService.link_guest_to_user(
            canonical_user=self.canonical_user,
            guest_user=self.guest_user,
            link_type="guest_conversion",
        )

        # InteractionLog under canonical user
        InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_matrix,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )

        # InteractionLog under guest user
        InteractionLog.objects.create(
            user=self.guest_user,
            movie=self.movie_dune,
            event_type="superlike",
            weight=3.0,
            processing_status="pending",
        )

        res = TasteEngineService.recompute_user_taste_profile(self.canonical_user)
        self.assertEqual(res["events_claimed"], 2)

        profile = UserTasteProfile.objects.get(user=self.canonical_user)
        # Science Fiction should combine canonical's matrix (+1.0) and guest's dune (+3.0) -> 4.0
        self.assertAlmostEqual(profile.learned_weights["genres"]["Science Fiction"], 4.0, places=3)

    def test_idempotent_recomputation_from_complete_event_ledger(self):
        """
        The event ledger is the single source of truth. Recomputing with force=True
        over all historical events yields the exact same deterministic weights.
        """
        InteractionLog.objects.create(
            user=self.canonical_user,
            movie=self.movie_matrix,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )

        # First run processes pending
        res1 = TasteEngineService.recompute_user_taste_profile(self.canonical_user)
        self.assertEqual(res1["events_claimed"], 1)
        profile1 = UserTasteProfile.objects.get(user=self.canonical_user)
        weights1 = dict(profile1.learned_weights)

        # Forced run recalculates from entire ledger
        res2 = TasteEngineService.recompute_user_taste_profile(self.canonical_user, force=True)
        profile2 = UserTasteProfile.objects.get(user=self.canonical_user)
        weights2 = dict(profile2.learned_weights)

        self.assertEqual(weights1["genres"], weights2["genres"])
        self.assertEqual(weights1["tags"], weights2["tags"])
        self.assertEqual(weights1["keywords"], weights2["keywords"])
