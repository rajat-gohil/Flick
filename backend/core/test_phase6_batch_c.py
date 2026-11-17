import threading
from datetime import date
from unittest.mock import MagicMock, patch
import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from core.models import CollaborativeAgreement, Movie, MovieStreamingAvailability, Session, StreamingProvider
from core.services.tmdb import (
    TIMEOUT,
    get_tmdb_session,
    reset_tmdb_session,
    _get_tmdb_request_headers,
    redact_sensitive_params,
    get_movie_watch_providers,
    TMDBTimeoutError,
    TMDBServiceError,
)
from core.views import SessionRecentListView, MovieStreamingOptionsView


class Phase6BatchCTMDBReliabilityTests(TestCase):
    """
    Requirement 8: TMDB connection pooling, thread-local isolation, retry strategy, and security.
    """

    def setUp(self):
        reset_tmdb_session()
        cache.clear()

    def tearDown(self):
        reset_tmdb_session()
        cache.clear()

    def test_tmdb_session_thread_local_pooling_and_reuse(self):
        """
        Verifies that get_tmdb_session() reuses the same Session instance within the same thread,
        preserving connection pooling and avoiding connection churn.
        """
        s1 = get_tmdb_session()
        s2 = get_tmdb_session()
        self.assertIs(s1, s2, "Same thread must reuse the thread-local session instance.")

        # Test multi-threading safety: different threads must receive distinct session instances
        thread_sessions = []

        def worker():
            thread_sessions.append(get_tmdb_session())

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertEqual(len(thread_sessions), 2)
        self.assertIsNot(thread_sessions[0], thread_sessions[1], "Different threads must maintain isolated sessions.")
        self.assertIsNot(s1, thread_sessions[0])

    def test_tmdb_retry_strategy_and_timeout_configuration(self):
        """
        Verifies retry configuration:
        - Bounded total retries
        - Backoff factor and jitter configured
        - Transient HTTP codes in status_forcelist
        - Permanent client errors NOT in status_forcelist
        - respect_retry_after_header enabled
        - Connect and read split timeout tuple
        """
        session = get_tmdb_session()
        adapter = session.adapters.get("https://")
        self.assertIsNotNone(adapter)
        retry = adapter.max_retries

        self.assertEqual(retry.total, 3)
        self.assertEqual(retry.backoff_factor, 0.5)
        self.assertTrue(getattr(retry, "respect_retry_after_header", False))
        self.assertEqual(getattr(retry, "backoff_jitter", None), 0.5)

        # Retryable transient status codes
        self.assertIn(429, retry.status_forcelist)
        self.assertIn(500, retry.status_forcelist)
        self.assertIn(502, retry.status_forcelist)
        self.assertIn(503, retry.status_forcelist)
        self.assertIn(504, retry.status_forcelist)

        # Non-retryable permanent client errors
        self.assertNotIn(400, retry.status_forcelist)
        self.assertNotIn(401, retry.status_forcelist)
        self.assertNotIn(403, retry.status_forcelist)
        self.assertNotIn(404, retry.status_forcelist)

        # Split timeout configuration: (connect_timeout, read_timeout)
        self.assertIsInstance(TIMEOUT, tuple)
        self.assertEqual(len(TIMEOUT), 2)
        self.assertEqual(TIMEOUT[0], 3.05)
        self.assertEqual(TIMEOUT[1], 12.0)

    def test_tmdb_request_headers_isolation_and_redaction(self):
        """
        Verifies that outbound TMDB correlation headers are per-request and do not mutate
        shared session defaults, and credentials are never stored in mutable session headers.
        """
        session = get_tmdb_session()
        self.assertNotIn("Authorization", session.headers)
        self.assertNotIn("X-Request-ID", session.headers)

        # Per request correlation header helper
        with patch("core.services.tmdb.get_correlation_id", return_value="req-corr-uuid-123"):
            headers = _get_tmdb_request_headers()
            self.assertEqual(headers.get("X-Request-ID"), "req-corr-uuid-123")
            self.assertEqual(headers.get("X-Correlation-ID"), "req-corr-uuid-123")

        # Session defaults remain immutable
        self.assertNotIn("X-Request-ID", session.headers)

        # Verify sensitive redaction
        secret_url = "https://api.themoviedb.org/3/movie/550?api_key=secret_tmdb_key_12345&region=IN"
        redacted = redact_sensitive_params(secret_url)
        self.assertNotIn("secret_tmdb_key_12345", redacted)
        self.assertIn("api_key=[REDACTED]", redacted)


class Phase6BatchCRecentSessionsAndStreamingTests(TestCase):
    """
    Requirement 9: Recent sessions N+1 query elimination, response correctness, and streaming options caching.
    """

    def setUp(self):
        cache.clear()
        self.host = User.objects.create_user(username="host_recent", password="password123")
        self.guest = User.objects.create_user(username="guest_recent", password="password123")
        self.stranger = User.objects.create_user(username="stranger_recent", password="password123")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")

        self.movie = Movie.objects.create(
            tmdb_id=88888,
            title="Streaming Test Film",
            rating=8.2,
            release_date=date(2022, 5, 20),
        )

    def tearDown(self):
        cache.clear()

    def test_recent_sessions_n_plus_one_elimination_small_and_large(self):
        """
        Requirement 9: Verify that SessionRecentListView executes exactly 2 queries
        (Session + JOINs and prefetched genres) regardless of the number of ended sessions,
        completely eliminating N+1 queries.
        """
        factory = APIRequestFactory()

        # 1. Test Small Collection: 5 ended sessions
        for i in range(5):
            s = Session.objects.create(
                code=f"REC0{i}",
                host=self.host,
                guest=self.guest,
                ended_at=timezone.now(),
            )
            CollaborativeAgreement.objects.create(session=s, host_card_index=10, guest_card_index=10)

        req_small = factory.get("/api/sessions/recent/")
        force_authenticate(req_small, user=self.host)
        view = SessionRecentListView.as_view()

        from django.db import connection
        with CaptureQueriesContext(connection) as ctx_small:
            resp_small = view(req_small)

        self.assertEqual(resp_small.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_small.data["sessions"]), 5)
        # Exactly 2 queries: 1 for Session + host/guest/genre/collaborative_agreement, 1 for prefetched genres
        self.assertEqual(len(ctx_small), 2, f"Expected 2 queries for 5 ended sessions, got {len(ctx_small)}")

        # 2. Test Larger Collection: 25 ended sessions total
        for i in range(5, 25):
            s = Session.objects.create(
                code=f"REC{i:02d}",
                host=self.host,
                guest=self.guest,
                ended_at=timezone.now(),
            )
            CollaborativeAgreement.objects.create(session=s, host_card_index=10, guest_card_index=10)

        req_large = factory.get("/api/sessions/recent/")
        force_authenticate(req_large, user=self.host)

        with CaptureQueriesContext(connection) as ctx_large:
            resp_large = view(req_large)

        self.assertEqual(resp_large.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_large.data["sessions"]), 25)
        # Must STILL be exactly 2 queries for 25 sessions (constant O(1) query count)
        self.assertEqual(len(ctx_large), 2, f"Expected 2 queries for 25 ended sessions, got {len(ctx_large)}")

    def test_recent_sessions_response_correctness_and_permissions(self):
        """
        Verifies contract and permissions:
        - Host sees role="host", is_host=True
        - Guest sees role="guest", is_host=False
        - Stranger sees empty sessions list
        - Required fields (id, code, name, matches, status, participants) present
        """
        s = Session.objects.create(
            code=f"CORR01",
            host=self.host,
            guest=self.guest,
        )
        CollaborativeAgreement.objects.create(session=s)

        # Host view
        resp_host = self.client.get("/api/sessions/recent/")
        self.assertEqual(resp_host.status_code, status.HTTP_200_OK)
        data_host = resp_host.json()
        self.assertTrue(data_host["success"])
        self.assertEqual(len(data_host["sessions"]), 1)
        sess_item = data_host["sessions"][0]
        self.assertEqual(sess_item["code"], "CORR01")
        self.assertTrue(sess_item["is_host"])
        self.assertEqual(sess_item["user_role"], "host")
        self.assertEqual(sess_item["status"], "active")
        self.assertEqual(len(sess_item["participants"]), 2)

        # Guest view
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        resp_guest = self.client.get("/api/sessions/recent/")
        self.assertEqual(resp_guest.status_code, status.HTTP_200_OK)
        sess_guest = resp_guest.json()["sessions"][0]
        self.assertFalse(sess_guest["is_host"])
        self.assertEqual(sess_guest["user_role"], "guest")

        # Stranger view
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        resp_stranger = self.client.get("/api/sessions/recent/")
        self.assertEqual(resp_stranger.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp_stranger.json()["sessions"]), 0)

    def test_movie_streaming_options_caching_and_region_isolation(self):
        """
        Verifies streaming options:
        - Regional separation in Redis cache (IN vs US cached under separate keys)
        - Cache hits avoid upstream service calls
        - Upstream failure falls back to local database records
        """
        mock_in_data = {
            "link": "https://www.justwatch.com/in/movie/test",
            "region": "IN",
            "flatrate": [{"provider_id": 8, "provider_name": "Netflix", "logo_path": "/n.jpg"}],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }
        mock_us_data = {
            "link": "https://www.justwatch.com/us/movie/test",
            "region": "US",
            "flatrate": [{"provider_id": 9, "provider_name": "Prime Video", "logo_path": "/p.jpg"}],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        with patch("core.views.get_movie_watch_providers") as mock_providers:
            mock_providers.side_effect = lambda tid, region="IN": mock_in_data if region == "IN" else mock_us_data

            # 1. Initial request for region IN
            resp_in = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(resp_in.status_code, status.HTTP_200_OK)
            data_in = resp_in.json()
            self.assertEqual(data_in["region"], "IN")
            self.assertEqual(data_in["providers"][0]["name"], "Netflix")

            # 2. Initial request for region US
            resp_us = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=US")
            self.assertEqual(resp_us.status_code, status.HTTP_200_OK)
            data_us = resp_us.json()
            self.assertEqual(data_us["region"], "US")
            self.assertEqual(data_us["providers"][0]["name"], "Prime Video")

            self.assertEqual(mock_providers.call_count, 2)

            # 3. Second request for region IN - must hit Redis cache, call_count stays 2
            resp_in_cached = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(resp_in_cached.status_code, status.HTTP_200_OK)
            self.assertEqual(resp_in_cached.json()["providers"][0]["name"], "Netflix")
            self.assertEqual(mock_providers.call_count, 2, "Second request must hit cache without upstream fetch.")

    def test_movie_streaming_options_database_fallback_on_upstream_failure(self):
        """
        Verifies that if upstream TMDB fails and cache is empty, the endpoint falls back
        to pre-seeded MovieStreamingAvailability database records without caching failure.
        """
        # Pre-seed database streaming availability
        provider = StreamingProvider.objects.create(
            name="Hotstar",
            country_code="IN",
            website_url="https://www.hotstar.com",
            is_active=True,
        )
        MovieStreamingAvailability.objects.create(
            movie=self.movie,
            provider=provider,
            url="https://www.hotstar.com/movies/test",
            monetization_type="flatrate",
        )

        with patch("core.views.get_movie_watch_providers", side_effect=TMDBTimeoutError("Upstream timeout")):
            resp = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            data = resp.json()
            self.assertTrue(data["success"])
            self.assertEqual(len(data["providers"]), 1)
            self.assertEqual(data["providers"][0]["name"], "Hotstar")
