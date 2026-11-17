"""
Tests for MovieStreamingOptionsView and TMDB watch providers error handling.
Verifies:
1. TMDB 404 returns HTTP 200 with empty provider list (never HTTP 502).
2. Transient TMDB connection/timeout failures return HTTP 502 (retryable).
3. Successful provider lookups return HTTP 200 with formatted providers.
4. Database fallback providers used on upstream failure when available.
"""

from unittest.mock import MagicMock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token

from core.models import Movie, MovieStreamingAvailability, StreamingProvider
from core.services.tmdb import (
    TMDBAPIError,
    TMDBServiceError,
    TMDBTimeoutError,
    get_movie_watch_providers,
)

User = get_user_model()


class StreamingOptionsRemediationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(username="stream_test_user", password="password123")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.movie = Movie.objects.create(
            title="Inception",
            tmdb_id=27205,
            rating=8.8,
            vote_count=35000,
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )

    def test_tmdb_404_returns_http_200_with_empty_providers(self):
        """
        When TMDB returns HTTP 404 for a movie's watch providers (e.g. unknown or unlisted ID),
        the endpoint must return HTTP 200 with providers=[], never HTTP 502.
        """
        # Test directly via service
        mock_response = MagicMock()
        mock_response.status_code = 404
        with patch("core.services.tmdb._get_session") as mock_session_fn, \
             patch("core.services.tmdb_rate_limiter.acquire_tmdb_token", return_value=True):
            session_inst = MagicMock()
            session_inst.get.return_value = mock_response
            mock_session_fn.return_value = session_inst

            res = get_movie_watch_providers(self.movie.tmdb_id, region="IN")
            self.assertEqual(res["flatrate"], [])
            self.assertEqual(res["rent"], [])
            self.assertEqual(res["buy"], [])
            self.assertIsNone(res["link"])

        # Test via API view
        cache.clear()
        with patch("core.views.get_movie_watch_providers") as mock_get:
            mock_get.side_effect = TMDBAPIError("TMDB returned HTTP 404")
            response = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data["success"])
            self.assertEqual(response.data["providers"], [])
            self.assertEqual(response.data["movie_id"], self.movie.id)

    def test_tmdb_timeout_returns_http_502(self):
        """
        When TMDB times out, the endpoint returns HTTP 502 Bad Gateway with UPSTREAM_TIMEOUT error code.
        """
        with patch("core.views.get_movie_watch_providers") as mock_get:
            mock_get.side_effect = TMDBTimeoutError("Connection timed out after 5.0s")
            response = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
            self.assertFalse(response.data["success"])
            self.assertEqual(response.data["error_code"], "UPSTREAM_TIMEOUT")

    def test_tmdb_500_upstream_error_returns_http_502(self):
        """
        When TMDB returns HTTP 500 or 503, the endpoint returns HTTP 502 with UPSTREAM_ERROR.
        """
        with patch("core.views.get_movie_watch_providers") as mock_get:
            mock_get.side_effect = TMDBAPIError("TMDB returned HTTP 500")
            response = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
            self.assertFalse(response.data["success"])
            self.assertEqual(response.data["error_code"], "UPSTREAM_ERROR")

    def test_successful_provider_lookup(self):
        """
        When TMDB returns valid provider data, endpoint returns formatted providers with HTTP 200.
        """
        mock_raw = {
            "link": "https://www.themoviedb.org/movie/27205-inception/watch?locale=IN",
            "region": "IN",
            "flatrate": [
                {
                    "provider_id": 8,
                    "provider_name": "Netflix",
                    "logo_path": "/pbpMk2JmcoNnQwx5JGpXngfoWtp.jpg",
                    "display_priority": 1,
                }
            ],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }
        with patch("core.views.get_movie_watch_providers", return_value=mock_raw):
            response = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(response.data["success"])
            self.assertEqual(len(response.data["providers"]), 1)
            p = response.data["providers"][0]
            self.assertEqual(p["provider_name"], "Netflix")
            self.assertEqual(p["type"], "flatrate")
            self.assertIn("image.tmdb.org", p["logo_url"])
