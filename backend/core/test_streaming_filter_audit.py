import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.models import (
    Movie,
    Genre,
    Session,
    StreamingProvider,
    MovieStreamingAvailability,
)
from core.services.retrieval import (
    HardConstraints,
    HardConstraintFilter,
    CandidateRetrievalService,
    resolve_streaming_provider_ids,
)

User = get_user_model()


@override_settings(DEBUG=True)
class StreamingFilterAuditTests(TestCase):
    """
    Exhaustive regression test suite ensuring:
    1. Synthetic test fixtures ('SciFi Test', 'Deck Movie', etc.) never surface in discovery.
    2. Streaming platform filters ('Stream on:') filter discovery correctly.
    3. 'Streaming Services (Optional)' in session creation preserves provider IDs through questionnaire.
    4. Screening deck candidate retrieval strictly respects selected streaming providers.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="stream_tester",
            email="tester@stream.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

        self.genre_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.genre_scifi = Genre.objects.create(name="Sci-Fi", tmdb_id=878)

        # Provider 8: Netflix
        self.provider_netflix = StreamingProvider.objects.create(
            id=8,
            name="Netflix",
            country_code="IN",
            is_active=True,
        )
        # Provider 4: Amazon Prime Video (TMDB ID 119)
        self.provider_prime = StreamingProvider.objects.create(
            id=4,
            name="Amazon Prime Video",
            country_code="IN",
            is_active=True,
        )
        # Provider 1: JioHotstar (TMDB IDs 122 and 2336)
        self.provider_hotstar = StreamingProvider.objects.create(
            id=1,
            name="JioHotstar",
            country_code="IN",
            is_active=True,
        )

        # Real movie available on Netflix
        self.movie_netflix = Movie.objects.create(
            tmdb_id=5001,
            title="Extraction (Netflix)",
            overview="An authentic action movie.",
            poster_path="/extraction.jpg",
            rating=7.5,
            vote_count=1000,
            original_language="en",
            release_date=datetime.date(2020, 4, 24),
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_netflix.genres.add(self.genre_action)
        MovieStreamingAvailability.objects.create(
            movie=self.movie_netflix,
            provider=self.provider_netflix,
            monetization_type="flatrate",
        )

        # Real movie available on Prime Video
        self.movie_prime = Movie.objects.create(
            tmdb_id=5002,
            title="The Rings of Power (Prime)",
            overview="An authentic fantasy series.",
            poster_path="/rings.jpg",
            rating=7.8,
            vote_count=1200,
            original_language="en",
            release_date=datetime.date(2022, 9, 1),
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_prime.genres.add(self.genre_action)
        MovieStreamingAvailability.objects.create(
            movie=self.movie_prime,
            provider=self.provider_prime,
            monetization_type="flatrate",
        )

        # Real movie available on Hotstar
        self.movie_hotstar = Movie.objects.create(
            tmdb_id=5003,
            title="Avengers: Endgame (Hotstar)",
            overview="An authentic superhero movie.",
            poster_path="/endgame.jpg",
            rating=8.4,
            vote_count=2000,
            original_language="en",
            release_date=datetime.date(2019, 4, 26),
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )
        self.movie_hotstar.genres.add(self.genre_action)
        MovieStreamingAvailability.objects.create(
            movie=self.movie_hotstar,
            provider=self.provider_hotstar,
            monetization_type="flatrate",
        )

        # Synthetic fixture (must NEVER surface)
        self.movie_synthetic = Movie.objects.create(
            tmdb_id=99991,
            title="SciFi Test",
            overview="A synthetic test movie.",
            poster_path=None,
            rating=9.9,
            vote_count=9999,
            original_language="en",
            provenance="synthetic_fixture",
            display_ready=False,
            recommendable=False,
        )
        self.movie_synthetic.genres.add(self.genre_scifi)

        # Deck Movie dummy (must NEVER surface)
        self.movie_deck_dummy = Movie.objects.create(
            tmdb_id=99992,
            title="Deck Movie 2",
            overview="Deck test dummy.",
            poster_path=None,
            rating=9.8,
            vote_count=500,
            original_language="en",
            provenance="needs_review",
            display_ready=False,
            recommendable=False,
        )
        self.movie_deck_dummy.genres.add(self.genre_action)

    def test_provider_resolver_maps_tmdb_ids_to_local_providers(self):
        """TMDB provider IDs (8, 119) resolve to local StreamingProvider IDs (8, 4)."""
        pks_netflix = resolve_streaming_provider_ids([8])
        self.assertIn(self.provider_netflix.id, pks_netflix)

        pks_prime = resolve_streaming_provider_ids([119])
        self.assertIn(self.provider_prime.id, pks_prime)

    def test_discover_local_fallback_filters_by_watch_provider(self):
        """When TMDB fails/falls back, /api/discover/?watch_provider_id=8 filters to Netflix movies only."""
        with patch("core.services.tmdb.discover_movies", side_effect=Exception("TMDB offline")):
            res = self.client.get("/api/discover/?watch_provider_id=8")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            titles = [m["title"] for m in data.get("movies", [])]

            self.assertIn("Extraction (Netflix)", titles)
            self.assertNotIn("The Rings of Power (Prime)", titles)
            self.assertNotIn("SciFi Test", titles)
            self.assertNotIn("Deck Movie 2", titles)

    def test_complete_catalogue_filters_by_watch_provider(self):
        """/api/catalogue/?watch_provider_id=119 filters to Prime Video movies only."""
        res = self.client.get("/api/catalogue/?watch_provider_id=119")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        titles = [m["title"] for m in data.get("movies", [])]

        self.assertIn("The Rings of Power (Prime)", titles)
        self.assertNotIn("Extraction (Netflix)", titles)
        self.assertNotIn("SciFi Test", titles)
        self.assertNotIn("Deck Movie 2", titles)

    def test_session_creation_preserves_streaming_provider_ids_through_questionnaire(self):
        """Host setting streaming_provider_ids retains them after questionnaire submission."""
        # 1. Create session
        r1 = self.client.post("/api/sessions/create/", {}, format="json")
        self.assertEqual(r1.status_code, 201)
        session_id = r1.json()["id"]

        # 2. Set genre with streaming_provider_ids = [8]
        r2 = self.client.post(
            "/api/sessions/genre/",
            {
                "session_id": session_id,
                "genre_id": self.genre_action.id,
                "industry": "mixed",
                "languages": ["en"],
                "streaming_provider_ids": [8],
            },
            format="json",
        )
        self.assertEqual(r2.status_code, 200)

        # 3. Submit questionnaire preferences (mood/pace)
        r3 = self.client.post(
            "/api/sessions/preferences/",
            {
                "session_id": session_id,
                "preferences": {"mood": ["exciting"], "pace": ["fast"]},
            },
            format="json",
        )
        self.assertEqual(r3.status_code, 200)

        sess = Session.objects.get(id=session_id)
        # Verify streaming_provider_ids was NOT wiped by preferences submission
        self.assertEqual(sess.host_preferences.get("streaming_provider_ids"), [8])
        self.assertEqual(sess.host_preferences.get("mood"), ["exciting"])

    def test_retrieval_service_filters_deck_by_streaming_providers(self):
        """CandidateRetrievalService limits screening candidates to movies on the selected platform."""
        sess = Session.objects.create(
            host=self.user,
            genre=self.genre_action,
            industry="mixed",
            selected_languages=["en"],
            host_preferences={"streaming_provider_ids": [8]},
        )
        hc = HardConstraints(
            languages=["en"],
            required_genre_ids=[self.genre_action.tmdb_id],
            streaming_provider_ids=[8],
        )

        pool = CandidateRetrievalService.retrieve_candidates(
            session=sess,
            constraints=hc,
            auto_replenish=False,
        )

        candidate_titles = [c.title for c in pool.candidates]
        self.assertIn("Extraction (Netflix)", candidate_titles)
        self.assertNotIn("The Rings of Power (Prime)", candidate_titles)
        self.assertNotIn("SciFi Test", candidate_titles)
        self.assertNotIn("Deck Movie 2", candidate_titles)

    def test_hard_constraint_filter_evaluates_streaming_providers(self):
        """HardConstraintFilter.matches_all rejects movies not streaming on the required platform."""
        hc_netflix = HardConstraints(streaming_provider_ids=[8])
        hc_prime = HardConstraints(streaming_provider_ids=[119])

        self.assertTrue(HardConstraintFilter.matches_all(self.movie_netflix, hc_netflix))
        self.assertFalse(HardConstraintFilter.matches_all(self.movie_netflix, hc_prime))

        self.assertTrue(HardConstraintFilter.matches_all(self.movie_prime, hc_prime))
        self.assertFalse(HardConstraintFilter.matches_all(self.movie_prime, hc_netflix))

    def test_provider_resolver_maps_both_122_and_2336_to_hotstar(self):
        """Both TMDB provider IDs (122 and 2336) resolve to local JioHotstar ID (1)."""
        pks_122 = resolve_streaming_provider_ids([122])
        self.assertIn(self.provider_hotstar.id, pks_122)

        pks_2336 = resolve_streaming_provider_ids([2336])
        self.assertIn(self.provider_hotstar.id, pks_2336)

    def test_discover_local_fallback_filters_by_hotstar_ids(self):
        """When TMDB falls back, watch_provider_id=122 and 2336 both return Hotstar movie."""
        with patch("core.services.tmdb.discover_movies", side_effect=Exception("TMDB offline")):
            for pid in ["122", "2336", "122|2336"]:
                res = self.client.get(f"/api/discover/?watch_provider_id={pid}")
                self.assertEqual(res.status_code, 200)
                data = res.json()
                titles = [m["title"] for m in data.get("movies", [])]
                self.assertIn("Avengers: Endgame (Hotstar)", titles)
                self.assertNotIn("Extraction (Netflix)", titles)
                self.assertNotIn("The Rings of Power (Prime)", titles)

    @patch("core.services.tmdb._get_session")
    def test_discover_movies_expands_hotstar_id_for_in_region(self, mock_get_session):
        """discover_movies expands watch_provider_id='122' to '122|2336' when watch_region is IN."""
        from core.services.tmdb import discover_movies

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [], "total_pages": 1, "total_results": 0}
        mock_session_instance = MagicMock()
        mock_session_instance.get.return_value = mock_resp
        mock_get_session.return_value = mock_session_instance

        # Call with watch_provider_id="122" and region="IN"
        discover_movies(page=1, watch_provider_id="122", watch_region="IN")

        # Verify query params passed to TMDB
        self.assertTrue(mock_session_instance.get.called)
        call_params = mock_session_instance.get.call_args[1].get("params", {})
        self.assertEqual(call_params.get("with_watch_providers"), "122|2336")
        self.assertEqual(call_params.get("watch_region"), "IN")
