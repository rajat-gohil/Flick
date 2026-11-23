"""
Unit and regression tests for Curator's Double Feature, Watchlist Batch,
and Screening Manifest Prioritization.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from core.models import (
    CollaborativeAgreement,
    Genre,
    GuestProfile,
    InteractionLog,
    Movie,
    MovieStreamingAvailability,
    Session,
    StreamingProvider,
    Swipe,
    UserTasteProfile,
    WatchlistItem,
)
from core.services.double_feature import DoubleFeatureService, EDITORIAL_CATALOGUE
from core.services.manifest import ManifestCompilerService
from core.services.retrieval import CandidatePool, HardConstraints


def create_test_movies():
    """Seeds the 14 verified movies for testing."""
    movies_data = [
        (799, 1949, "Zodiac", 2007, 7.5, ["Crime", "Mystery", "Thriller"]),
        (366, 807, "Se7en", 1995, 8.4, ["Crime", "Mystery", "Thriller"]),
        (42, 157336, "Interstellar", 2014, 8.5, ["Adventure", "Drama", "Science Fiction"]),
        (47, 693134, "Dune: Part Two", 2024, 8.1, ["Adventure", "Science Fiction"]),
        (156, 441717, "96", 2018, 7.7, ["Romance", "Drama"]),
        (66, 19404, "Dilwale Dulhania Le Jayenge", 1995, 8.5, ["Comedy", "Drama", "Romance"]),
        (270, 680, "Pulp Fiction", 1994, 8.5, ["Crime", "Comedy"]),
        (812, 185, "A Clockwork Orange", 1971, 8.2, ["Crime", "Science Fiction"]),
        (824, 37257, "Witness for the Prosecution", 1957, 8.2, ["Mystery", "Drama"]),
        (823, 829, "Chinatown", 1974, 7.9, ["Crime", "Mystery", "Thriller"]),
        (881, 27205, "Inception", 2010, 8.4, ["Action", "Science Fiction"]),
        (791, 1422, "The Departed", 2006, 8.2, ["Crime", "Thriller"]),
        (60, 278, "The Shawshank Redemption", 1994, 8.7, ["Drama", "Crime"]),
        (268, 13, "Forrest Gump", 1994, 8.5, ["Comedy", "Drama", "Romance"]),
    ]

    for mid, tmdb_id, title, year, rating, genre_names in movies_data:
        m, _ = Movie.objects.update_or_create(
            id=mid,
            defaults={
                "tmdb_id": tmdb_id,
                "title": title,
                "release_date": f"{year}-06-01",
                "rating": rating,
                "poster_path": f"/{mid}.jpg",
                "overview": f"Overview of {title}",
                "recommendable": True,
                "display_ready": True,
            }
        )
        for idx_g, gname in enumerate(genre_names):
            g, _ = Genre.objects.get_or_create(name=gname, defaults={"tmdb_id": 1000 + idx_g + mid})
            m.genres.add(g)


class DoubleFeatureServiceTests(TestCase):
    """Tests for DoubleFeatureService business logic and eligibility."""

    @classmethod
    def setUpTestData(cls):
        create_test_movies()

    def setUp(self):
        self.user = User.objects.create_user(username="cinephile_test", password="password123")
        self.guest_user = User.objects.create_user(username="guest_test", password="password123")
        GuestProfile.objects.create(user=self.guest_user, is_claimed=False)

    def test_unauthenticated_visitor_gets_daily_editorial(self):
        result = DoubleFeatureService.get_double_feature(user=None)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "daily_editorial")
        self.assertFalse(result["is_personalized"])
        self.assertIn("theme", result)
        self.assertIn("curator_note", result)
        self.assertNotEqual(result["film_1"]["id"], result["film_2"]["id"])
        self.assertIsNone(result["total_runtime_minutes"])

    def test_active_unclaimed_guest_gets_daily_editorial(self):
        result = DoubleFeatureService.get_double_feature(user=self.guest_user)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "daily_editorial")
        self.assertFalse(result["is_personalized"])

    def test_claimed_guest_without_signals_gets_daily_editorial(self):
        claimed_user = User.objects.create_user(username="claimed_test", password="password123")
        GuestProfile.objects.create(user=claimed_user, is_claimed=True)
        result = DoubleFeatureService.get_double_feature(user=claimed_user)
        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "daily_editorial")
        self.assertFalse(result["is_personalized"])

    def test_deterministic_rotation_same_day(self):
        dt1 = datetime(2026, 11, 23, 10, 0, 0, tzinfo=timezone.utc)
        dt2 = datetime(2026, 11, 23, 23, 59, 59, tzinfo=timezone.utc)
        idx1 = DoubleFeatureService.get_current_day_index(dt1)
        idx2 = DoubleFeatureService.get_current_day_index(dt2)
        self.assertEqual(idx1, idx2)

        res1 = DoubleFeatureService.get_double_feature(user=None, current_dt=dt1)
        res2 = DoubleFeatureService.get_double_feature(user=None, current_dt=dt2)
        self.assertEqual(res1["theme"], res2["theme"])
        self.assertEqual(res1["film_1"]["id"], res2["film_1"]["id"])
        self.assertEqual(res1["film_2"]["id"], res2["film_2"]["id"])

    def test_scheduled_day_progression(self):
        dt = datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        dt_next = dt + timedelta(days=1)
        idx_curr = DoubleFeatureService.get_current_day_index(dt)
        idx_next = DoubleFeatureService.get_current_day_index(dt_next)
        self.assertEqual((idx_curr + 1) % len(EDITORIAL_CATALOGUE), idx_next)

    def test_established_user_with_custom_profile_gets_personalized(self):
        UserTasteProfile.objects.create(
            user=self.user,
            emotional_tonality=["melancholic"],
            thematic_interests=["identity"],
        )
        is_est, reason = DoubleFeatureService.is_user_established(self.user)
        self.assertTrue(is_est)
        self.assertEqual(reason, "established")

    def test_established_user_with_distinct_interactions(self):
        m1 = Movie.objects.get(id=60)
        m2 = Movie.objects.get(id=268)
        m3 = Movie.objects.get(id=799)
        test_session = Session.objects.create(code="SWP01", host=self.user)
        Swipe.objects.create(session=test_session, user=self.user, movie=m1, reaction="like")
        InteractionLog.objects.create(user=self.user, movie=m2, event_type="detail_view")
        WatchlistItem.objects.create(user=self.user, movie=m3)

        is_est, reason = DoubleFeatureService.is_user_established(self.user)
        self.assertTrue(is_est)
        self.assertEqual(reason, "established")

    def test_candidate_shortage_falls_back_to_editorial(self):
        UserTasteProfile.objects.create(user=self.user, emotional_tonality=["melancholic"])
        # Mock recommendation engine returning empty candidate pool
        with patch("core.services.recommendation_engine.PersonalizedRecommendationEngine.get_recommendations", return_value={"movies": [], "confidence": "COLD_START"}):
            result = DoubleFeatureService.get_double_feature(user=self.user)
            self.assertTrue(result["success"])
            self.assertEqual(result["source"], "daily_editorial")
            self.assertFalse(result["is_personalized"])


class DoubleFeatureAPITests(TestCase):
    """Tests for GET /api/double-feature/ endpoint."""

    @classmethod
    def setUpTestData(cls):
        create_test_movies()

    def setUp(self):
        self.client = APIClient()

    def test_double_feature_endpoint_public_access(self):
        response = self.client.get("/api/double-feature/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertIn("theme", data)
        self.assertIn("curator_note", data)
        self.assertIn("film_1", data)
        self.assertIn("film_2", data)
        self.assertIn("genres", data["film_1"])
        self.assertIn("genres", data["film_2"])


class WatchlistBatchAPITests(TestCase):
    """Tests for WatchlistView single and batch atomic POST."""

    @classmethod
    def setUpTestData(cls):
        create_test_movies()

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="wl_user", password="password123")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_single_item_backward_compatibility(self):
        response = self.client.post("/api/watchlist/", {"movie_id": 60}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["created"])
        self.assertEqual(data["item"]["movie_id"], 60)

    def test_batch_atomic_addition_success(self):
        response = self.client.post("/api/watchlist/", {"movie_ids": [60, 268]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["batch"])
        self.assertEqual(data["total_processed"], 2)
        self.assertEqual(len(data["results"]), 2)
        self.assertTrue(WatchlistItem.objects.filter(user=self.user, movie_id=60).exists())
        self.assertTrue(WatchlistItem.objects.filter(user=self.user, movie_id=268).exists())

    def test_batch_idempotency_and_duplicates(self):
        WatchlistItem.objects.create(user=self.user, movie_id=60)
        response = self.client.post("/api/watchlist/", {"movie_ids": [60, 268, 60, 268]}, format="json")
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["total_processed"], 2)
        res_60 = next(r for r in data["results"] if r["movie_id"] == 60)
        self.assertFalse(res_60["created"])

    def test_batch_atomic_rollback_on_invalid_id(self):
        response = self.client.post("/api/watchlist/", {"movie_ids": [799, 999999999]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(WatchlistItem.objects.filter(user=self.user, movie_id=799).exists())


class ManifestPrioritizationTests(TestCase):
    """Tests for screening deck prioritization in ManifestCompilerService."""

    @classmethod
    def setUpTestData(cls):
        create_test_movies()

    def setUp(self):
        self.host = User.objects.create_user(username="host_prioritize", password="pw")
        self.session = Session.objects.create(
            code="PRIOR1",
            host=self.host,
            host_preferences={"prioritized_movie_ids": [799, 366]},  # Zodiac & Se7en
        )
        self.agreement = CollaborativeAgreement.objects.create(session=self.session)

    def test_prioritization_places_eligible_movies_in_opening_slots(self):
        m1 = Movie.objects.get(id=799)
        m2 = Movie.objects.get(id=366)
        other_candidates = []
        for i in range(45):
            m, _ = Movie.objects.get_or_create(
                id=2000 + i,
                defaults={
                    "tmdb_id": 30000 + i,
                    "title": f"Candidate {i}",
                    "release_date": "2010-01-01",
                    "rating": 7.0 + (i % 10) * 0.1,
                    "poster_path": f"/c_{i}.jpg",
                    "recommendable": True,
                    "display_ready": True,
                }
            )
            other_candidates.append(m)

        all_candidates = [m1, m2] + other_candidates
        candidate_pool = CandidatePool(
            pool_type="normal",
            candidates=all_candidates,
            total_count=len(all_candidates),
            local_count=len(all_candidates),
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=candidate_pool,
        )

        self.assertGreaterEqual(len(manifest), 40)
        opening_ids = {manifest[0]["movie_id"], manifest[1]["movie_id"]}
        self.assertIn(799, opening_ids)
        self.assertIn(366, opening_ids)

        self.assertEqual(manifest[0]["slot_type"], "consensus")
        self.assertEqual(manifest[1]["slot_type"], "host_priority")

    def test_prioritization_handles_ineligible_movie_gracefully(self):
        self.session.host_preferences = {"prioritized_movie_ids": [999999999, 60]}
        self.session.save()

        m_shawshank = Movie.objects.get(id=60)
        other_candidates = []
        for i in range(45):
            m, _ = Movie.objects.get_or_create(
                id=3000 + i,
                defaults={
                    "tmdb_id": 40000 + i,
                    "title": f"Candidate B {i}",
                    "release_date": "2010-01-01",
                    "rating": 7.0 + (i % 10) * 0.1,
                    "poster_path": f"/cb_{i}.jpg",
                    "recommendable": True,
                    "display_ready": True,
                }
            )
            other_candidates.append(m)

        candidate_pool = CandidatePool(
            pool_type="normal",
            candidates=[m_shawshank] + other_candidates,
            total_count=1 + len(other_candidates),
            local_count=1 + len(other_candidates),
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=candidate_pool,
            force_recompile=True,
        )

        self.assertGreaterEqual(len(manifest), 40)
        self.assertEqual(manifest[0]["movie_id"], 60)
