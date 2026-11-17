"""
Unit tests for Recommendation Evaluation Service.

Verifies:
- compute_cohort_divergence (Jaccard similarity, empty sets, overlap)
- compute_preference_alignment (positive weights, fallback to logs, cold start)
- compute_negative_response_rate (penalized genres, hard exclusions, dislike logs)
- compute_unexposed_discovery_ratio (novelty, previous interactions, linked guest actor exposure)
- compute_shelf_diversity (disjoint, identical, partial overlap, edge cases)
- RecommendationEvaluationService aggregation methods
"""

from typing import Any, Dict, List
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
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
from core.services.recommendation_evaluation import (
    RecommendationEvaluationService,
    compute_cohort_divergence,
    compute_negative_response_rate,
    compute_preference_alignment,
    compute_shelf_diversity,
    compute_unexposed_discovery_ratio,
)

User = get_user_model()


class RecommendationEvaluationTests(TestCase):
    """Test suite for recommendation evaluation metrics."""

    def setUp(self):
        self.user = User.objects.create_user(username="eval_user_1", password="pw")
        self.guest = User.objects.create_user(username="eval_guest_1", password="pw")

        # Genres
        self.genre_scifi = Genre.objects.get_or_create(tmdb_id=878, defaults={"name": "Science Fiction"})[0]
        self.genre_horror = Genre.objects.get_or_create(tmdb_id=27, defaults={"name": "Horror"})[0]
        self.genre_romance = Genre.objects.get_or_create(tmdb_id=10749, defaults={"name": "Romance"})[0]
        self.genre_action = Genre.objects.get_or_create(tmdb_id=28, defaults={"name": "Action"})[0]

        # Tags & Keywords
        self.tag_cyberpunk = MovieTag.objects.create(name="cyberpunk")
        self.tag_jump_scare = MovieTag.objects.create(name="jump-scare")
        self.kw_ai = MovieKeyword.objects.create(name="artificial intelligence", tmdb_id=101)

        # Movies
        self.movie_blade = Movie.objects.create(
            tmdb_id=1001,
            title="Blade Runner 2049",
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_blade.genres.add(self.genre_scifi)
        self.movie_blade.tags.add(self.tag_cyberpunk)
        self.movie_blade.keywords.add(self.kw_ai)

        self.movie_conjuring = Movie.objects.create(
            tmdb_id=1002,
            title="The Conjuring",
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_conjuring.genres.add(self.genre_horror)
        self.movie_conjuring.tags.add(self.tag_jump_scare)

        self.movie_notebook = Movie.objects.create(
            tmdb_id=1003,
            title="The Notebook",
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_notebook.genres.add(self.genre_romance)

        self.movie_matrix = Movie.objects.create(
            tmdb_id=1004,
            title="The Matrix",
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_matrix.genres.add(self.genre_action, self.genre_scifi)
        self.movie_matrix.tags.add(self.tag_cyberpunk)

    def test_compute_cohort_divergence_metrics(self):
        """Test Jaccard similarity across identical, disjoint, and overlapping cohorts."""
        # 1. Identical cohorts
        self.assertEqual(compute_cohort_divergence([1, 2, 3], [1, 2, 3]), 1.0)

        # 2. Disjoint cohorts
        self.assertEqual(compute_cohort_divergence([1, 2, 3], [4, 5, 6]), 0.0)

        # 3. Partial overlap: intersection={2, 3} (2), union={1, 2, 3, 4} (4) -> 0.5
        self.assertEqual(compute_cohort_divergence([1, 2, 3], [2, 3, 4]), 0.5)

        # 4. Target verification: divergence under 0.30 for different taste cohorts
        # e.g., 1 shared out of 10 total -> 1 / 10 = 0.10 < 0.30
        cohort_a = [101, 102, 103, 104, 105]
        cohort_b = [105, 106, 107, 108, 109, 110]
        similarity = compute_cohort_divergence(cohort_a, cohort_b)
        # intersection: {105} (1), union: 10 items -> 1/10 = 0.1
        self.assertEqual(similarity, 0.1)
        self.assertLess(similarity, 0.30)

        # 5. Empty cohorts
        self.assertEqual(compute_cohort_divergence([], []), 0.0)
        self.assertEqual(compute_cohort_divergence([1, 2], []), 0.0)

    def test_compute_preference_alignment_with_learned_weights(self):
        """Test alignment ratio calculation based on user's learned weights."""
        UserTasteProfile.objects.create(
            user=self.user,
            learned_weights={
                "genres": {"Science Fiction": 2.5, "Action": 1.0},
                "tags": {"cyberpunk": 1.5},
                "keywords": {"artificial intelligence": 1.0},
            },
        )

        # List with 2 movies: Blade Runner (scifi, cyberpunk, ai) and The Matrix (action, scifi, cyberpunk)
        # Both align! Alignment should be 1.0
        aligned_ratio = compute_preference_alignment(self.user, [self.movie_blade, self.movie_matrix])
        self.assertEqual(aligned_ratio, 1.0)

        # Mixed list: Blade Runner (aligned) and The Notebook (romance, not aligned)
        mixed_ratio = compute_preference_alignment(self.user, [self.movie_blade, self.movie_notebook])
        self.assertEqual(mixed_ratio, 0.5)

        # Zero alignment list: The Notebook and The Conjuring
        zero_ratio = compute_preference_alignment(self.user, [self.movie_notebook, self.movie_conjuring])
        self.assertEqual(zero_ratio, 0.0)

    def test_compute_preference_alignment_cold_start(self):
        """Test cold start user with 0 interactions returns 0.0 alignment."""
        cold_user = User.objects.create_user(username="cold_user_1", password="pw")
        ratio = compute_preference_alignment(cold_user, [self.movie_blade, self.movie_notebook])
        self.assertEqual(ratio, 0.0)

    def test_compute_preference_alignment_fallback_to_interaction_logs(self):
        """Test alignment uses positive interaction logs when learned_weights are empty."""
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_blade,
            event_type="like",
            weight=1.0,
            processing_status="pending",
        )
        # Blade Runner has tag cyberpunk, genre Science Fiction
        # Matrix shares Science Fiction and cyberpunk!
        ratio = compute_preference_alignment(self.user, [self.movie_matrix])
        self.assertEqual(ratio, 1.0)

    def test_compute_negative_response_rate(self):
        """Test detection of disliked attributes, hard exclusions, and swiped dislikes."""
        UserTasteProfile.objects.create(
            user=self.user,
            hard_exclusions={"genres": ["Horror"]},
            learned_weights={
                "genres": {"Horror": -2.0},
                "tags": {"jump-scare": -1.5},
            },
        )

        # Clean list: Blade Runner and The Matrix -> rate should be 0.0
        clean_rate = compute_negative_response_rate(self.user, [self.movie_blade, self.movie_matrix])
        self.assertEqual(clean_rate, 0.0)

        # Contaminated list: The Conjuring (Horror, jump-scare) + Blade Runner
        # 1 out of 2 movies contains disliked attributes -> rate 0.5
        contaminated_rate = compute_negative_response_rate(
            self.user, [self.movie_blade, self.movie_conjuring]
        )
        self.assertEqual(contaminated_rate, 0.5)

    def test_compute_negative_response_rate_interaction_logs(self):
        """Test negative response rate detects explicit swipe dislikes in interaction log."""
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_notebook,
            event_type="dislike",
            weight=-1.2,
            processing_status="pending",
        )

        rate = compute_negative_response_rate(self.user, [self.movie_notebook, self.movie_blade])
        self.assertEqual(rate, 0.5)

    def test_compute_unexposed_discovery_ratio(self):
        """Test unexposed ratio computation and linked guest history propagation."""
        # Initially, all movies are unexposed
        ratio = compute_unexposed_discovery_ratio(
            self.user, [self.movie_blade, self.movie_matrix, self.movie_notebook]
        )
        self.assertEqual(ratio, 1.0)

        # User interacts with Blade Runner
        InteractionLog.objects.create(
            user=self.user,
            movie=self.movie_blade,
            event_type="like",
            weight=1.0,
        )

        # Now Blade Runner is exposed (1 out of 3 is exposed -> 2 unexposed -> ratio 2/3 = 0.6667)
        ratio_after_int = compute_unexposed_discovery_ratio(
            self.user, [self.movie_blade, self.movie_matrix, self.movie_notebook]
        )
        self.assertEqual(ratio_after_int, 0.6667)

        # Link guest user to canonical user
        UserIdentityLink.objects.create(
            canonical_user=self.user,
            linked_actor_id=self.guest.id,
            link_type=LinkType.GUEST_CONVERSION,
        )

        # Guest interacted with The Matrix
        session = Session.objects.create(code="EVAL01", host=self.guest)
        Swipe.objects.create(
            session=session,
            user=self.guest,
            movie=self.movie_matrix,
            reaction=Swipe.LIKE,
        )

        # Now both Blade Runner and The Matrix are exposed for canonical user!
        # Only The Notebook is unexposed -> ratio 1/3 = 0.3333
        ratio_after_guest = compute_unexposed_discovery_ratio(
            self.user, [self.movie_blade, self.movie_matrix, self.movie_notebook]
        )
        self.assertEqual(ratio_after_guest, 0.3333)

    def test_compute_shelf_diversity(self):
        """Test inter-shelf differentiation scoring."""
        # 1. Five completely disjoint shelves
        shelves_disjoint = {
            "shelf_1": [{"id": 1}, {"id": 2}],
            "shelf_2": [{"id": 3}, {"id": 4}],
            "shelf_3": [{"id": 5}, {"id": 6}],
            "shelf_4": [{"id": 7}, {"id": 8}],
            "shelf_5": [{"id": 9}, {"id": 10}],
        }
        score_disjoint = compute_shelf_diversity(shelves_disjoint)
        self.assertEqual(score_disjoint, 1.0)

        # 2. Five completely identical shelves
        shelves_identical = {
            "shelf_1": [{"id": 1}, {"id": 2}],
            "shelf_2": [{"id": 1}, {"id": 2}],
            "shelf_3": [{"id": 1}, {"id": 2}],
            "shelf_4": [{"id": 1}, {"id": 2}],
            "shelf_5": [{"id": 1}, {"id": 2}],
        }
        score_identical = compute_shelf_diversity(shelves_identical)
        self.assertEqual(score_identical, 0.0)

        # 3. Partially overlapping shelves
        shelves_partial = {
            "shelf_1": [{"id": 1}, {"id": 2}],
            "shelf_2": [{"id": 2}, {"id": 3}],
        }
        # sim = 1/3 = 0.3333 -> dist = 1 - 0.3333 = 0.6667
        score_partial = compute_shelf_diversity(shelves_partial)
        self.assertEqual(score_partial, 0.6667)

        # 4. Edge cases: single shelf and empty dict
        self.assertEqual(compute_shelf_diversity({"shelf_1": [{"id": 1}]}), 1.0)
        self.assertEqual(compute_shelf_diversity({}), 0.0)

    def test_recommendation_evaluation_service_facade(self):
        """Test RecommendationEvaluationService facade methods."""
        UserTasteProfile.objects.create(
            user=self.user,
            learned_weights={
                "genres": {"Science Fiction": 2.0},
            },
        )
        results = RecommendationEvaluationService.evaluate_user_recommendations(
            self.user, [self.movie_blade]
        )
        self.assertIn("preference_alignment", results)
        self.assertIn("negative_response_rate", results)
        self.assertIn("unexposed_discovery_ratio", results)
        self.assertEqual(results["preference_alignment"], 1.0)
        self.assertEqual(results["negative_response_rate"], 0.0)
        self.assertEqual(results["unexposed_discovery_ratio"], 1.0)
