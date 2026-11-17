"""
Unit and Integration Tests for TasteEngineService and run_intelligence_worker integration.

Tests verify:
1. Early return on no pending events without DB mutations.
2. Aggregation of interaction signals (likes, dislikes, superlikes, matches) into learned_weights.
3. Deterministic undo event handling with inverse signal cancellation.
4. Linked guest actor interactions combined into canonical taste profile.
5. Idempotency and determinism of the complete event ledger.
6. Integration worker handler registration and job execution.
"""

from typing import Any, Dict
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    CatalogueJob,
    Genre,
    InteractionLog,
    LinkType,
    Movie,
    MovieKeyword,
    MovieTag,
    Session,
    Swipe,
    UserIdentityLink,
    UserTasteProfile,
)
from core.management.commands.run_intelligence_worker import (
    DEFAULT_JOB_HANDLERS,
    JOB_HANDLERS,
    IntelligenceWorkerProcess,
    reset_handlers,
)
from core.services.catalogue_queue import CatalogueQueueService
from core.services.taste_engine import (
    TasteEngineService,
    handle_recompute_taste_profile,
    recompute_user_taste_profile,
)

User = get_user_model()


class TasteEngineServiceTests(TestCase):
    """Unit tests for TasteEngineService."""

    def setUp(self):
        reset_handlers()
        self.user = User.objects.create_user(username="taste_user_1", password="pw")
        self.guest = User.objects.create_user(username="taste_guest_1", password="pw")

        # Genres
        self.genre_action = Genre.objects.get_or_create(tmdb_id=28, defaults={"name": "Action"})[0]
        self.genre_scifi = Genre.objects.get_or_create(tmdb_id=878, defaults={"name": "Science Fiction"})[0]

        # Tags
        self.tag_cyberpunk = MovieTag.objects.create(name="cyberpunk")
        self.tag_noir = MovieTag.objects.create(name="noir")
        self.tag_slow = MovieTag.objects.create(name="slow-burn")

        # Keywords
        self.kw_ai = MovieKeyword.objects.create(name="artificial intelligence", tmdb_id=101)
        self.kw_dystopia = MovieKeyword.objects.create(name="dystopia", tmdb_id=102)

        # Movies
        self.movie_blade = Movie.objects.create(
            tmdb_id=1001,
            title="Blade Runner 2049",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[878],
        )
        self.movie_blade.genres.add(self.genre_scifi)
        self.movie_blade.tags.add(self.tag_cyberpunk, self.tag_noir)
        self.movie_blade.keywords.add(self.kw_ai, self.kw_dystopia)

        self.movie_matrix = Movie.objects.create(
            tmdb_id=1002,
            title="The Matrix",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[28, 878],
        )
        self.movie_matrix.genres.add(self.genre_action, self.genre_scifi)
        self.movie_matrix.tags.add(self.tag_cyberpunk)
        self.movie_matrix.keywords.add(self.kw_ai)

        self.movie_art = Movie.objects.create(
            tmdb_id=1003,
            title="Stalker",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[878],
        )
        self.movie_art.genres.add(self.genre_scifi)
        self.movie_art.tags.add(self.tag_slow)

    def test_recompute_early_return_when_no_pending_events(self):
        """When there are no pending interaction logs, return early with status 'noop'."""
        result = TasteEngineService.recompute_user_taste_profile(self.user)
        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["events_processed"], 0)
        self.assertEqual(result["user_id"], self.user.id)

        # Profile is created with empty learned_weights
        profile = UserTasteProfile.objects.get(user=self.user)
        self.assertEqual(profile.learned_weights, {})

    def test_recompute_aggregates_likes_and_dislikes(self):
        """Pending swipe_like and swipe_dislike events update learned_weights."""
        # Like Blade Runner (+1.0)
        log1 = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_blade,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        # Dislike Stalker (-1.2)
        log2 = InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_art,
            event_type="swipe_dislike",
            weight=-1.2,
            processing_status="pending",
        )

        result = TasteEngineService.recompute_user_taste_profile(self.user)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["events_processed"], 2)

        # Logs marked as processed
        log1.refresh_from_db()
        log2.refresh_from_db()
        self.assertEqual(log1.processing_status, "processed")
        self.assertIsNotNone(log1.processed_at)
        self.assertEqual(log2.processing_status, "processed")
        self.assertIsNotNone(log2.processed_at)

        profile = UserTasteProfile.objects.get(user=self.user)
        weights = profile.learned_weights

        # Science Fiction appeared in both (+1.0 and -1.2) -> -0.2
        self.assertAlmostEqual(weights["genres"]["Science Fiction"], -0.2, places=3)
        self.assertAlmostEqual(weights["Science Fiction"], -0.2, places=3)

        # Cyberpunk appeared in Blade Runner (+1.0)
        self.assertAlmostEqual(weights["tags"]["cyberpunk"], 1.0, places=3)
        self.assertAlmostEqual(weights["cyberpunk"], 1.0, places=3)

        # Slow-burn appeared in Stalker (-1.2)
        self.assertAlmostEqual(weights["tags"]["slow-burn"], -1.2, places=3)
        self.assertAlmostEqual(weights["slow-burn"], -1.2, places=3)

        # Keywords in Blade Runner (+1.0)
        self.assertAlmostEqual(weights["keywords"]["artificial intelligence"], 1.0, places=3)
        self.assertAlmostEqual(weights["keywords"]["dystopia"], 1.0, places=3)

    def test_undo_inverse_event_cancellation(self):
        """Undo events properly invert signal weights and restore baseline."""
        # 1. User superlikes The Matrix (+3.0)
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_matrix,
            event_type="superlike",
            weight=3.0,
            processing_status="pending",
        )
        TasteEngineService.recompute_user_taste_profile(self.user)
        profile = UserTasteProfile.objects.get(user=self.user)
        self.assertAlmostEqual(profile.learned_weights["Action"], 3.0, places=3)

        # 2. User undos the superlike (-3.0)
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_matrix,
            event_type="undo",
            weight=-3.0,
            processing_status="pending",
            metadata={"undone_reaction": "superlike"},
        )
        TasteEngineService.recompute_user_taste_profile(self.user)
        profile.refresh_from_db()

        # Action and Cyberpunk should now be 0.0
        self.assertAlmostEqual(profile.learned_weights["Action"], 0.0, places=3)
        self.assertAlmostEqual(profile.learned_weights["tags"]["cyberpunk"], 0.0, places=3)

    def test_linked_guest_identity_aggregation(self):
        """Interactions logged by a linked guest actor are incorporated into canonical user profile."""
        # Link guest to canonical user
        UserIdentityLink.objects.create(
            canonical_user=self.user,
            linked_actor_id=self.guest.id,
            link_type=LinkType.GUEST_CONVERSION,
        )

        # Guest interacted with Blade Runner (+1.0)
        InteractionLog.objects.create(
            user=self.guest,
            movie=self.movie_blade,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        # Canonical user interacted with The Matrix (+3.0)
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_matrix,
            event_type="superlike",
            weight=3.0,
            processing_status="pending",
        )

        # Recompute canonical profile
        result = TasteEngineService.recompute_user_taste_profile(self.user)
        self.assertEqual(result["events_processed"], 2)

        profile = UserTasteProfile.objects.get(user=self.user)
        # Science Fiction was in Blade Runner (+1.0) and Matrix (+3.0) -> +4.0
        self.assertAlmostEqual(profile.learned_weights["Science Fiction"], 4.0, places=3)
        # Cyberpunk was in both (+1.0 + 3.0) -> +4.0
        self.assertAlmostEqual(profile.learned_weights["tags"]["cyberpunk"], 4.0, places=3)
        # Action was only in Matrix (+3.0)
        self.assertAlmostEqual(profile.learned_weights["Action"], 3.0, places=3)

    def test_idempotency_and_determinism(self):
        """Recomputing with force=True produces identical learned_weights."""
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_blade,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_matrix,
            event_type="superlike",
            weight=3.0,
            processing_status="pending",
        )

        res1 = TasteEngineService.recompute_user_taste_profile(self.user)
        weights1 = res1["learned_weights"]

        # Recompute with force=True (all events are now 'processed')
        res2 = TasteEngineService.recompute_user_taste_profile(self.user, force=True)
        weights2 = res2["learned_weights"]

        self.assertEqual(weights1, weights2)


class IntelligenceWorkerTasteHandlerTests(TestCase):
    """Tests worker handler registration and job execution."""

    def setUp(self):
        reset_handlers()
        self.user = User.objects.create_user(username="worker_user_1", password="pw")
        self.movie = Movie.objects.create(
            tmdb_id=2001,
            title="Worker Movie",
            provenance="tmdb_catalogue",
            tmdb_genre_ids=[28],
        )
        genre_action = Genre.objects.get_or_create(tmdb_id=28, defaults={"name": "Action"})[0]
        self.movie.genres.add(genre_action)

    def test_handler_registered_in_default_and_active_handlers(self):
        """recompute_taste_profile is registered in DEFAULT_JOB_HANDLERS and JOB_HANDLERS."""
        self.assertIn("recompute_taste_profile", DEFAULT_JOB_HANDLERS)
        self.assertIn("recompute_taste_profile", JOB_HANDLERS)
        self.assertEqual(DEFAULT_JOB_HANDLERS["recompute_taste_profile"], handle_recompute_taste_profile)

    def test_worker_processes_recompute_taste_profile_job(self):
        """IntelligenceWorkerProcess successfully executes recompute_taste_profile job."""
        # Create pending interaction log
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie,
            event_type="swipe_like",
            weight=1.0,
            processing_status="pending",
        )

        # Enqueue job
        enqueue_res = CatalogueQueueService.enqueue(
            job_type="recompute_taste_profile",
            entity_type="user",
            entity_id=str(self.user.id),
            priority=100,
        )
        job = enqueue_res[0] if isinstance(enqueue_res, tuple) else enqueue_res

        worker = IntelligenceWorkerProcess(worker_id="test-taste-worker")
        metrics = worker.run_loop(once=True, max_batches=1)

        self.assertEqual(metrics["completed"], 1)
        self.assertEqual(metrics["failed"], 0)

        # Job is marked succeeded
        job.refresh_from_db()
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(job.payload["events_processed"], 1)

        # Taste profile is updated
        profile = UserTasteProfile.objects.get(user=self.user)
        self.assertAlmostEqual(profile.learned_weights["Action"], 1.0, places=3)
