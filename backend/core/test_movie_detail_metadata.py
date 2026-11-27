from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Genre, Match, Movie, Session
from core.serializers import MovieSerializer
from core.services.deck_state import DeckAdvancementService
from core.services.enrichment_handlers import handle_catalogue_enrichment

User = get_user_model()


class MovieDetailMetadataTests(TestCase):
    def setUp(self):
        self.drama = Genre.objects.create(tmdb_id=18, name="Drama")
        self.thriller = Genre.objects.create(tmdb_id=53, name="Thriller")

    def test_serializer_returns_genre_names_and_tmdb_fallback_and_runtime(self):
        movie_m2m = Movie.objects.create(
            tmdb_id=90001,
            title="With M2M Genres",
            overview="Overview",
            release_date=date(2020, 5, 1),
            credits_summary={"runtime": 134, "directors": [{"name": "Director"}]},
        )
        movie_m2m.genres.add(self.drama, self.thriller)

        data = MovieSerializer(movie_m2m).data
        self.assertEqual(set(data["genres"]), {"Drama", "Thriller"})
        self.assertEqual(data["runtime"], 134)

        movie_fallback = Movie.objects.create(
            tmdb_id=90002,
            title="TMDB Fallback",
            overview="Overview",
            tmdb_genre_ids=[18, 878],
            credits_summary={"runtime": 0},
        )
        fallback_data = MovieSerializer(movie_fallback).data
        self.assertEqual(fallback_data["genres"], ["Drama", "Science Fiction"])
        self.assertIsNone(fallback_data["runtime"])

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    @patch("core.services.enrichment_handlers.acquire_tmdb_token", return_value=True)
    @patch("core.services.enrichment_handlers.recalculate_movie_eligibility")
    def test_enrichment_persists_runtime_and_preserves_existing_credits_summary(
        self, _mock_elig, _mock_token, mock_tmdb_get
    ):
        movie = Movie.objects.create(
            tmdb_id=90003,
            title="Old Title",
            credits_summary={"custom_note": "keep-me", "runtime": 115},
        )

        # 1. Valid runtime updates and preserves custom_note
        resp_valid = MagicMock(status_code=200)
        resp_valid.json.return_value = {
            "title": "Enriched Title",
            "overview": "Updated overview",
            "runtime": 142,
            "genres": [{"id": 18, "name": "Drama"}],
            "keywords": {"keywords": []},
            "credits": {"cast": [], "crew": []},
        }
        mock_tmdb_get.return_value = resp_valid
        job = SimpleNamespace(entity_id=movie.id)
        handle_catalogue_enrichment(job, "w1", "lease-1", 1)

        movie.refresh_from_db()
        self.assertEqual(movie.credits_summary.get("runtime"), 142)
        self.assertEqual(movie.credits_summary.get("custom_note"), "keep-me")

        # 2. Malformed / null runtime does NOT overwrite valid existing runtime
        resp_invalid = MagicMock(status_code=200)
        resp_invalid.json.return_value = {
            "title": "Enriched Title",
            "runtime": None,
            "genres": [],
            "keywords": {"keywords": []},
            "credits": {"cast": [], "crew": []},
        }
        mock_tmdb_get.return_value = resp_invalid
        handle_catalogue_enrichment(job, "w1", "lease-2", 2)

        movie.refresh_from_db()
        self.assertEqual(movie.credits_summary.get("runtime"), 142)
        self.assertEqual(movie.credits_summary.get("custom_note"), "keep-me")

    def test_deck_card_payload_and_session_match_payloads_include_genres_and_runtime(self):
        host = User.objects.create_user(username="host_meta", password="pw")
        guest = User.objects.create_user(username="guest_meta", password="pw")
        session = Session.objects.create(
            code="META01",
            host=host,
            guest=guest,
            preferences_set=True,
        )

        movie = Movie.objects.create(
            tmdb_id=90004,
            title="Deck & Match Film",
            overview="Full metadata",
            release_date=date(2022, 1, 15),
            credits_summary={"runtime": 128},
        )
        movie.genres.add(self.drama)

        manifest = [{"movie_id": movie.id, "slot_type": "core", "turn": 1, "scores": {}}]

        card = DeckAdvancementService._build_card_payload(manifest, 0)
        self.assertIsNotNone(card)
        self.assertEqual(card["genres"], ["Drama"])
        self.assertEqual(card["runtime"], 128)

        Match.objects.create(session=session, movie=movie)
        client = APIClient()
        client.force_authenticate(user=host)

        res_session_matches = client.get(f"/api/matches/?session_id={session.id}")
        self.assertEqual(res_session_matches.status_code, 200)
        self.assertEqual(res_session_matches.data["matches"][0]["genres"], ["Drama"])
        self.assertEqual(res_session_matches.data["matches"][0]["runtime"], 128)

        res_history = client.get("/api/matches/")
        self.assertEqual(res_history.status_code, 200)
        self.assertEqual(res_history.data["matches"][0]["genres"], ["Drama"])
        self.assertEqual(res_history.data["matches"][0]["runtime"], 128)
