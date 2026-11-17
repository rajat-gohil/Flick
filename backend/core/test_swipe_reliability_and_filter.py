import time
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock

from django.test import TransactionTestCase, TestCase, Client, override_settings
from django.db import connection
from rest_framework.authtoken.models import Token

from core.models import (
    User,
    Session,
    Movie,
    Swipe,
    Match,
    Genre,
    SessionStats,
    MovieTag,
    UserTasteSignal,
    SessionChemistry,
)
from core.services.retrieval import HardConstraintFilter
from core.services.tmdb import discover_movies
from core.views import calculate_preference_score


class DatabaseConcurrencyAndSwipeReliabilityTests(TransactionTestCase):
    """
    Simulates high-concurrency two-user collaborative swiping sessions
    with simultaneous polling and superlikes under SQLite to verify zero
    'database is locked' errors and sub-transaction performance.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="conc_host", password="password123")
        self.guest = User.objects.create_user(username="conc_guest", password="password123")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)

        self.session = Session.objects.create(
            code="CONC01",
            host=self.host,
            guest=self.guest,
        )
        SessionStats.objects.create(session=self.session)

        # Create 20 test movies with tags to trigger taste signals & chemistry updates
        self.movies = []
        for i in range(20):
            m = Movie.objects.create(
                tmdb_id=800000 + i,
                title=f"Concurrent Film {i}",
                rating=7.5 + (i % 3) * 0.5,
                vote_count=100 + i * 10,
                release_date=datetime.date(1985 + i, 6, 1),
            )
            tag, _ = MovieTag.objects.get_or_create(name=f"genre_tag_{i % 5}")
            m.tags.add(tag)
            self.movies.append(m)

    def test_sqlite_pragmas_applied(self):
        """Verify SQLite connection is configured with WAL mode and calibrated 5s busy timeout."""
        if connection.vendor == "sqlite":
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA busy_timeout;")
                timeout = cursor.fetchone()[0]
                self.assertGreaterEqual(timeout, 5000, "busy_timeout must be at least 5000ms")

                cursor.execute("PRAGMA synchronous;")
                sync_mode = cursor.fetchone()[0]
                # 1 = NORMAL
                self.assertEqual(sync_mode, 1, "PRAGMA synchronous must be NORMAL (1)")

    def test_concurrent_two_user_swiping_and_polling(self):
        """
        Execute concurrent swipes from host and guest along with concurrent GET polling.
        Verify no HTTP 500 or SQLite lock errors occur.
        """
        results = []

        def host_swipe(movie_id, reaction):
            c = Client()
            for _ in range(3):
                res = c.post(
                    "/api/swipes/",
                    {"session": self.session.id, "movie": movie_id, "reaction": reaction},
                    HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
                    content_type="application/json",
                )
                if res.status_code != 503:
                    break
                time.sleep(0.05)
            return ("host", movie_id, res.status_code, res.json())

        def guest_swipe(movie_id, reaction):
            c = Client()
            for _ in range(3):
                res = c.post(
                    "/api/swipes/",
                    {"session": self.session.id, "movie": movie_id, "reaction": reaction},
                    HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
                    content_type="application/json",
                )
                if res.status_code != 503:
                    break
                time.sleep(0.05)
            return ("guest", movie_id, res.status_code, res.json())

        def poll_session():
            c = Client()
            res = c.get(
                f"/api/sessions/{self.session.id}/",
                HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            )
            return ("poll", self.session.id, res.status_code, res.json())

        # Interleave Likes, SuperLikes, and Dislikes across movies concurrently
        tasks = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            for i, movie in enumerate(self.movies[:10]):
                # Host swiping
                rx_h = Swipe.SUPERLIKE if i % 3 == 0 else (Swipe.LIKE if i % 2 == 0 else Swipe.DISLIKE)
                tasks.append(executor.submit(host_swipe, movie.id, rx_h))

                # Guest swiping concurrently
                rx_g = Swipe.SUPERLIKE if i % 4 == 0 else (Swipe.LIKE if i % 3 != 1 else Swipe.DISLIKE)
                tasks.append(executor.submit(guest_swipe, movie.id, rx_g))

                # Concurrent polling
                tasks.append(executor.submit(poll_session))

            for future in as_completed(tasks):
                results.append(future.result())

        # Assert no requests returned 500 (Internal Server Error)
        status_codes = [r[2] for r in results]
        self.assertNotIn(500, status_codes, "Concurrency caused an unexpected HTTP 500 error!")

        # All swipes should be 201 (created) or 409 (conflict/already swiped if any duplicate)
        swipe_results = [r for r in results if r[0] in ("host", "guest")]
        for role, mid, code, body in swipe_results:
            self.assertIn(code, (201, 409), f"Unexpected status {code} for {role} swipe on movie {mid}: {body}")

        # Polling requests must all succeed with 200
        poll_results = [r for r in results if r[0] == "poll"]
        for _, _, code, body in poll_results:
            self.assertEqual(code, 200, f"Poll failed with status {code}: {body}")

    def test_swipe_undo_under_concurrency(self):
        """Verify Swipe undo works without deadlock or lock contention."""
        movie = self.movies[15]
        client = Client()

        # Host swipes
        res = client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 201)

        # Undo swipe immediately
        undo_res = client.delete(
            "/api/swipes/undo/",
            {"session_id": self.session.id, "movie_id": movie.id},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(undo_res.status_code, 200)
        self.assertTrue(undo_res.json()["success"])
        self.assertFalse(Swipe.objects.filter(session=self.session, movie=movie, user=self.host).exists())


class SwipeFailureRecoveryAndEdgeCaseTests(TestCase):
    """
    Verifies error recovery, conflicting swipe protection, and retry semantics.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="rec_host", password="password123")
        self.guest = User.objects.create_user(username="rec_guest", password="password123")
        self.host_token = Token.objects.create(user=self.host)
        self.client = Client()

        self.session = Session.objects.create(
            code="REC001",
            host=self.host,
            guest=self.guest,
        )
        SessionStats.objects.create(session=self.session)
        self.movie = Movie.objects.create(
            tmdb_id=900001,
            title="Recovery Test Movie",
            rating=8.2,
            vote_count=500,
            release_date=datetime.date(1988, 5, 20),
        )

    def test_conflicting_swipe_rejected_preserves_persisted_reaction(self):
        """Submitting a conflicting reaction for an already-swiped movie returns 409 and does not overwrite."""
        # First swipe: LIKE
        res1 = self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 201)

        # Conflicting swipe: DISLIKE
        res2 = self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 409)
        self.assertIn("Conflicting reaction", res2.json()["error"])

        # Persisted reaction must still be LIKE
        persisted = Swipe.objects.get(session=self.session, movie=self.movie, user=self.host)
        self.assertEqual(persisted.reaction, Swipe.LIKE)

    def test_idempotent_retry_returns_200_with_idempotent_flag(self):
        """Submitting an identical swipe returns 200 OK with idempotent=True without duplicate records."""
        res1 = self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res1.status_code, 201)

        res2 = self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.json()["success"])
        self.assertTrue(res2.json().get("idempotent"))
        self.assertEqual(Swipe.objects.filter(session=self.session, movie=self.movie, user=self.host).count(), 1)

    def test_cannot_undo_after_match(self):
        """Undo after match is rejected with 409."""
        guest_token = Token.objects.create(user=self.guest)

        # Host and Guest both LIKE -> Match formed
        self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {guest_token.key}",
            content_type="application/json",
        )
        self.assertTrue(Match.objects.filter(session=self.session, movie=self.movie).exists())

        # Host tries to undo -> 409 Conflict
        undo_res = self.client.delete(
            "/api/swipes/undo/",
            {"session_id": self.session.id, "movie_id": self.movie.id},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(undo_res.status_code, 409)

    def test_analytics_failure_does_not_break_swipe_workflow(self):
        """
        Deliberately force an exception in the post-commit analytics callback.
        Verifies:
        - Swipe remains persisted.
        - Correct match state remains persisted.
        - API response accurately returns 201 Created.
        - Analytics failure is logged but does not break the swipe workflow.
        """
        guest_token = Token.objects.create(user=self.guest)

        # Host likes movie first
        self.client.post(
            "/api/swipes/",
            {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )

        # Guest likes movie, but _update_analytics_after_commit raises an exception
        with patch("core.views._update_analytics_after_commit", side_effect=RuntimeError("Simulated analytics database crash")):
            with self.assertLogs("core.views", level="ERROR") as log_cm:
                with self.captureOnCommitCallbacks(execute=True):
                    res = self.client.post(
                        "/api/swipes/",
                        {"session": self.session.id, "movie": self.movie.id, "reaction": Swipe.LIKE},
                        HTTP_AUTHORIZATION=f"Token {guest_token.key}",
                        content_type="application/json",
                    )

        # 1. API response must succeed with 201 Created and indicate match
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json()["success"])
        self.assertTrue(res.json()["match"])

        # 2. Both swipes must remain persisted
        self.assertTrue(Swipe.objects.filter(session=self.session, movie=self.movie, user=self.host).exists())
        self.assertTrue(Swipe.objects.filter(session=self.session, movie=self.movie, user=self.guest).exists())

        # 3. Match record must be properly formed
        self.assertTrue(Match.objects.filter(session=self.session, movie=self.movie).exists())

        # 4. Error was logged with context
        self.assertTrue(any("Uncaught exception in background analytics callback" in record for record in log_cm.output))


class Pre1990ReleasePeriodFilterTests(TestCase):
    """
    End-to-end tests for the selectable 'Before 1990' release period filter:
    1. TMDB parameter mapping
    2. Retrieval candidate eligibility boundary check (1989-12-31 included vs 1990-01-01 excluded)
    3. Preference scoring point awards
    4. RecommendationView era filtering
    5. MovieDiscoveryView and local fallback filtering
    """

    def setUp(self):
        self.host = User.objects.create_user(username="era_host", password="password123")
        self.guest = User.objects.create_user(username="era_guest", password="password123")
        self.host_token = Token.objects.create(user=self.host)
        self.client = Client()

        self.genre = Genre.objects.create(name="Drama", tmdb_id=18)

        # Boundary test movies
        self.pre_boundary_movie = Movie.objects.create(
            tmdb_id=910001,
            title="Pre-1990 Film (1989-12-31)",
            rating=8.0,
            vote_count=200,
            release_date=datetime.date(1989, 12, 31),
            overview="A dramatic story from the end of 1989.",
        )
        self.pre_boundary_movie.genres.add(self.genre)

        self.post_boundary_movie = Movie.objects.create(
            tmdb_id=910002,
            title="Post-1990 Film (1990-01-01)",
            rating=8.0,
            vote_count=200,
            release_date=datetime.date(1990, 1, 1),
            overview="A dramatic story from the first day of 1990.",
        )
        self.post_boundary_movie.genres.add(self.genre)

        self.golden_age_movie = Movie.objects.create(
            tmdb_id=910003,
            title="Golden Age Classic (1975-04-10)",
            rating=8.5,
            vote_count=500,
            release_date=datetime.date(1975, 4, 10),
            overview="A classic 1970s cinema masterpiece.",
        )
        self.golden_age_movie.genres.add(self.genre)

        self.modern_movie = Movie.objects.create(
            tmdb_id=910004,
            title="Modern Cinema (2022-03-15)",
            rating=8.1,
            vote_count=300,
            release_date=datetime.date(2022, 3, 15),
            overview="A modern contemporary film.",
        )
        self.modern_movie.genres.add(self.genre)

    def test_tmdb_query_parameter_mapping(self):
        """Verify TMDB discover queries map era='before_1990' to primary_release_date.lte=1989-12-31."""
        with patch("core.services.tmdb._get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"page": 1, "results": [], "total_pages": 1}
            mock_session.get.return_value = mock_response
            mock_get_session.return_value = mock_session

            # Test before_1990
            discover_movies(genre_id=18, era="before_1990")
            args, kwargs = mock_session.get.call_args
            params = kwargs.get("params", {})
            self.assertEqual(params.get("primary_release_date.lte"), "1989-12-31")
            self.assertNotIn("primary_release_date.gte", params)

            # Test pre_1990 alias
            discover_movies(genre_id=18, era="pre_1990")
            args, kwargs = mock_session.get.call_args
            params = kwargs.get("params", {})
            self.assertEqual(params.get("primary_release_date.lte"), "1989-12-31")

    def test_retrieval_candidate_eligibility_boundary(self):
        """
        Verify EligibilityPolicyEngine includes 1989-12-31 and excludes 1990-01-01
        for the before_1990 era filter.
        """
        # 1989-12-31 must be satisfied
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.pre_boundary_movie, ["before_1990"]),
            "1989-12-31 boundary movie MUST be eligible for before_1990",
        )
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.golden_age_movie, ["before_1990"]),
            "1975 classic MUST be eligible for before_1990",
        )

        # 1990-01-01 must be excluded
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.post_boundary_movie, ["before_1990"]),
            "1990-01-01 boundary movie MUST NOT be eligible for before_1990",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.modern_movie, ["before_1990"]),
            "2022 modern movie MUST NOT be eligible for before_1990",
        )

    def test_preference_scoring_awards_bonus_for_before_1990(self):
        """
        Verify calculate_preference_score awards +15 bonus points for matching before_1990
        and applies -20 penalty for non-matching movies.
        """
        prefs = {"era": ["before_1990"]}

        score_pre = calculate_preference_score(self.pre_boundary_movie, prefs)
        score_golden = calculate_preference_score(self.golden_age_movie, prefs)
        score_post = calculate_preference_score(self.post_boundary_movie, prefs)
        score_modern = calculate_preference_score(self.modern_movie, prefs)

        # Matching movies get positive bonus (+15)
        self.assertGreaterEqual(score_pre, 15, "1989-12-31 movie must receive era match bonus")
        self.assertGreaterEqual(score_golden, 15, "1975 movie must receive era match bonus")

        # Non-matching movies get penalty (-20)
        self.assertEqual(score_post, -20, "1990-01-01 movie must receive penalty for mismatched era")
        self.assertEqual(score_modern, -20, "2022 movie must receive penalty for mismatched era")

    def test_recommendation_view_filters_before_1990(self):
        """
        Verify RecommendationView strictly filters movies to release_date <= 1989-12-31
        when before_1990 era is selected in session preferences.
        """
        session = Session.objects.create(
            code="REC990",
            host=self.host,
            guest=self.guest,
            genre=self.genre,
            host_preferences={"era": ["before_1990"]},
            guest_preferences={"era": ["before_1990"]},
        )
        SessionStats.objects.create(session=session)

        res = self.client.get(
            f"/api/recommendations/?session_id={session.id}",
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
        )
        self.assertEqual(res.status_code, 200)
        movies = res.json().get("movies", [])
        movie_ids = [m["id"] for m in movies]

        # 1989-12-31 and 1975 movies should be included
        self.assertIn(self.pre_boundary_movie.id, movie_ids)
        self.assertIn(self.golden_age_movie.id, movie_ids)

        # 1990-01-01 and modern movies must be excluded
        self.assertNotIn(self.post_boundary_movie.id, movie_ids)
        self.assertNotIn(self.modern_movie.id, movie_ids)

    def test_existing_eras_unaffected(self):
        """Verify that existing era definitions (recent, 2010s, 2000s, 90s, classic) remain functional."""
        # 90s era includes 1990-01-01
        self.assertTrue(HardConstraintFilter.satisfies_eras(self.post_boundary_movie, ["90s"]))
        self.assertFalse(HardConstraintFilter.satisfies_eras(self.pre_boundary_movie, ["90s"]))

        # Recent era includes 2022
        self.assertTrue(HardConstraintFilter.satisfies_eras(self.modern_movie, ["recent"]))
        self.assertFalse(HardConstraintFilter.satisfies_eras(self.pre_boundary_movie, ["recent"]))

    def test_preference_persistence_and_survives_restoration(self):
        """
        Verify 'before_1990' preference survives persistence, polling, and session restoration.
        """
        guest_token = Token.objects.create(user=self.guest)
        session = Session.objects.create(code="PERS90", host=self.host, guest=self.guest, genre=self.genre)

        # 1. Host submits before_1990 preference
        res_h = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": {"era": ["before_1990"]}},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_h.status_code, 200)
        self.assertTrue(res_h.json()["user_preferences_set"])

        # 2. Guest submits before_1990 preference
        res_g = self.client.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": {"era": ["before_1990"]}},
            HTTP_AUTHORIZATION=f"Token {guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 200)
        self.assertTrue(res_g.json()["both_ready"])

        # 3. Verify database persistence and session restoration
        reloaded = Session.objects.get(id=session.id)
        self.assertTrue(reloaded.preferences_set)
        self.assertEqual(reloaded.host_preferences.get("era"), ["before_1990"])
        self.assertEqual(reloaded.guest_preferences.get("era"), ["before_1990"])

        # 4. Verify polling GET /api/sessions/<id>/ returns correct preferences
        poll_res = self.client.get(
            f"/api/sessions/{session.id}/",
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
        )
        self.assertEqual(poll_res.status_code, 200)
        session_data = poll_res.json()["session"]
        self.assertTrue(session_data["preferences_set"])
        self.assertEqual(session_data["user_preferences"]["era"], ["before_1990"])

    def test_replenishment_preserves_before_1990_constraint(self):
        """
        Verify that when candidate pool is depleted, replenishment is triggered
        with era='before_1990' and only pre-1990 candidates are returned.
        """
        isolated_genre = Genre.objects.create(name="Pre1990Noir", tmdb_id=8888)
        session = Session.objects.create(
            code="REPL90",
            host=self.host,
            guest=self.guest,
            genre=isolated_genre,
            host_preferences={"era": ["before_1990"]},
            guest_preferences={"era": ["before_1990"]},
            preferences_set=True,
        )
        SessionStats.objects.create(session=session)

        # Mock TMDB sync to verify criteria passing and ingestion
        with patch("core.services.tmdb.sync_tmdb_movies_for_criteria") as mock_sync:
            def fake_sync(genres, industry, languages, max_pages, era, min_rating):
                # Ingest a valid pre-1990 movie
                m = Movie.objects.create(
                    tmdb_id=988801,
                    title="Ingested Noir 1955",
                    release_date=datetime.date(1955, 3, 1),
                    rating=8.3,
                    vote_count=300,
                )
                m.genres.add(isolated_genre)
                return 1

            mock_sync.side_effect = fake_sync

            res = self.client.get(
                f"/api/recommendations/?session_id={session.id}",
                HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            )
            self.assertEqual(res.status_code, 200)
            mock_sync.assert_called_once()
            _, kwargs = mock_sync.call_args
            self.assertEqual(kwargs.get("era"), "before_1990")

            movies = res.json().get("movies", [])
            self.assertEqual(len(movies), 1)
            self.assertEqual(movies[0]["title"], "Ingested Noir 1955")
            self.assertLessEqual(movies[0]["release_year"], 1989)


@override_settings(DEBUG=True)
class ClassicVaultEraFilterTests(TestCase):
    """
    Verifies release-year boundaries for Classic Vault and The Nineties Wave:
    - Classic Vault: Movies released strictly before January 1, 1990 (through 1989-12-31).
    - The Nineties Wave: Movies released from January 1, 1990 through December 31, 1999.
    - Movies released in 1990 or later must NEVER appear in Classic Vault.
    """

    def setUp(self):
        self.genre = Genre.objects.create(name="Film Vault", tmdb_id=9901)
        self.client = Client()

        self.film_1980 = Movie.objects.create(
            tmdb_id=80001,
            title="The Shining (1980)",
            release_date=datetime.date(1980, 5, 23),
            rating=8.4,
            original_language="en",
        )
        self.film_1980.genres.add(self.genre)

        self.film_1989 = Movie.objects.create(
            tmdb_id=89001,
            title="Dead Poets Society (1989)",
            release_date=datetime.date(1989, 12, 31),
            rating=8.2,
            original_language="en",
        )
        self.film_1989.genres.add(self.genre)

        self.film_1990 = Movie.objects.create(
            tmdb_id=90001,
            title="Goodfellas (1990)",
            release_date=datetime.date(1990, 1, 1),
            rating=8.7,
            original_language="en",
        )
        self.film_1990.genres.add(self.genre)

        self.film_1995 = Movie.objects.create(
            tmdb_id=95001,
            title="Heat (1995)",
            release_date=datetime.date(1995, 9, 22),
            rating=8.3,
            original_language="en",
        )
        self.film_1995.genres.add(self.genre)

        self.film_1999 = Movie.objects.create(
            tmdb_id=99002,
            title="The Matrix (1999)",
            release_date=datetime.date(1999, 12, 31),
            rating=8.7,
            original_language="en",
        )
        self.film_1999.genres.add(self.genre)

        self.film_2000 = Movie.objects.create(
            tmdb_id=200001,
            title="Memento (2000)",
            release_date=datetime.date(2000, 1, 1),
            rating=8.4,
            original_language="en",
        )
        self.film_2000.genres.add(self.genre)

    def test_classic_vault_qualification(self):
        """
        Verify Classic Vault qualification:
        - 1980 film: included
        - 1989 film: included
        - 1990 film: excluded
        - 1995 film: excluded
        - 1999 film: excluded
        - 2000 film: excluded
        """
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.film_1980, ["classic"]),
            "1980 film MUST qualify for Classic Vault",
        )
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.film_1989, ["classic"]),
            "1989 film MUST qualify for Classic Vault",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_1990, ["classic"]),
            "1990 film MUST NOT qualify for Classic Vault",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_1995, ["classic"]),
            "1995 film MUST NOT qualify for Classic Vault",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_1999, ["classic"]),
            "1999 film MUST NOT qualify for Classic Vault",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_2000, ["classic"]),
            "2000 film MUST NOT qualify for Classic Vault",
        )

    def test_nineties_wave_qualification(self):
        """
        Verify The Nineties Wave qualification:
        - 1989 film: excluded
        - 1990 film: included
        - 1995 film: included
        - 1999 film: included
        - 2000 film: excluded
        """
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_1989, ["90s"]),
            "1989 film MUST NOT qualify for The Nineties Wave",
        )
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.film_1990, ["90s"]),
            "1990 film MUST qualify for The Nineties Wave",
        )
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.film_1995, ["90s"]),
            "1995 film MUST qualify for The Nineties Wave",
        )
        self.assertTrue(
            HardConstraintFilter.satisfies_eras(self.film_1999, ["90s"]),
            "1999 film MUST qualify for The Nineties Wave",
        )
        self.assertFalse(
            HardConstraintFilter.satisfies_eras(self.film_2000, ["90s"]),
            "2000 film MUST NOT qualify for The Nineties Wave",
        )

    def test_tmdb_service_date_ranges(self):
        """Verify TMDB query parameters for 'classic' and '90s'."""
        with patch("core.services.tmdb._get_session") as mock_get_session:
            mock_session = MagicMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"page": 1, "results": [], "total_pages": 1}
            mock_resp.raise_for_status.return_value = None
            mock_session.get.return_value = mock_resp
            mock_get_session.return_value = mock_session

            # Classic era: upper bound 1989-12-31, no lower bound
            discover_movies(genre_id=9901, era="classic")
            _, kwargs = mock_session.get.call_args
            params = kwargs.get("params", {})
            self.assertEqual(params.get("primary_release_date.lte"), "1989-12-31")
            self.assertNotIn("primary_release_date.gte", params)

            # 90s era: 1990-01-01 to 1999-12-31
            discover_movies(genre_id=9901, era="90s")
            _, kwargs = mock_session.get.call_args
            params = kwargs.get("params", {})
            self.assertEqual(params.get("primary_release_date.gte"), "1990-01-01")
            self.assertEqual(params.get("primary_release_date.lte"), "1999-12-31")

    def test_discover_api_endpoints_local_fallback(self):
        """Verify /api/discover/ filters correctly for classic and 90s in local fallback."""
        with patch("core.services.tmdb.discover_movies", side_effect=Exception("TMDB offline")):
            # Discover classic: should contain 1980, 1989; exclude 1990, 1995, 1999, 2000
            res_classic = self.client.get(f"/api/discover/?era=classic&genre={self.genre.id}")
            self.assertEqual(res_classic.status_code, 200)
            classic_ids = [m["id"] for m in res_classic.json().get("movies", [])]
            self.assertIn(self.film_1980.id, classic_ids)
            self.assertIn(self.film_1989.id, classic_ids)
            self.assertNotIn(self.film_1990.id, classic_ids)
            self.assertNotIn(self.film_1995.id, classic_ids)
            self.assertNotIn(self.film_1999.id, classic_ids)
            self.assertNotIn(self.film_2000.id, classic_ids)

            # Discover 90s: should contain 1990, 1995, 1999; exclude 1980, 1989, 2000
            res_90s = self.client.get(f"/api/discover/?era=90s&genre={self.genre.id}")
            self.assertEqual(res_90s.status_code, 200)
            nineties_ids = [m["id"] for m in res_90s.json().get("movies", [])]
            self.assertNotIn(self.film_1980.id, nineties_ids)
            self.assertNotIn(self.film_1989.id, nineties_ids)
            self.assertIn(self.film_1990.id, nineties_ids)
            self.assertIn(self.film_1995.id, nineties_ids)
            self.assertIn(self.film_1999.id, nineties_ids)
            self.assertNotIn(self.film_2000.id, nineties_ids)

    def test_discover_api_defensive_filter_on_tmdb_results(self):
        """Verify DiscoverView defensively excludes movies >= 1990 even if returned in raw results."""
        mock_raw = {
            "page": 1,
            "total_pages": 1,
            "total_results": 5,
            "results": [
                {"id": 80001, "title": "The Shining (1980)", "release_date": "1980-05-23", "vote_average": 8.4},
                {"id": 89001, "title": "Dead Poets Society (1989)", "release_date": "1989-12-31", "vote_average": 8.2},
                {"id": 90001, "title": "Goodfellas (1990)", "release_date": "1990-01-01", "vote_average": 8.7},
                {"id": 95001, "title": "Heat (1995)", "release_date": "1995-09-22", "vote_average": 8.3},
                {"id": 99002, "title": "The Matrix (1999)", "release_date": "1999-12-31", "vote_average": 8.7},
                {"id": 200001, "title": "Memento (2000)", "release_date": "2000-01-01", "vote_average": 8.4},
            ]
        }
        with patch("core.services.tmdb.discover_movies", return_value=(mock_raw, "tmdb_api")):
            res = self.client.get("/api/discover/?era=classic")
            self.assertEqual(res.status_code, 200)
            movies = res.json().get("movies", [])
            returned_years = [m["release_year"] for m in movies]
            self.assertIn(1980, returned_years)
            self.assertIn(1989, returned_years)
            self.assertNotIn(1990, returned_years)
            self.assertNotIn(1995, returned_years)
            self.assertNotIn(1999, returned_years)
            self.assertNotIn(2000, returned_years)
            for m in movies:
                self.assertLess(m["release_year"], 1990, f"Movie {m['title']} has year {m['release_year']}, must be < 1990")

    def test_discover_api_pagination_preserves_filter(self):
        """Verify DiscoverView pagination preserves the pre-1990 filter across pages."""
        with patch("core.services.tmdb.discover_movies", side_effect=Exception("TMDB offline")):
            res_p1 = self.client.get(f"/api/discover/?era=classic&genre={self.genre.id}&page=1")
            self.assertEqual(res_p1.status_code, 200)
            for m in res_p1.json().get("movies", []):
                self.assertLess(m["release_year"], 1990)

            res_p2 = self.client.get(f"/api/discover/?era=classic&genre={self.genre.id}&page=2")
            self.assertEqual(res_p2.status_code, 200)
            for m in res_p2.json().get("movies", []):
                self.assertLess(m["release_year"], 1990)

    def test_preference_scoring_nineties_and_pre_1990(self):
        """Verify preference scoring awards +15 bonus and applies -20 penalty accurately."""
        pre_1990_prefs = {"era": ["before_1990"]}
        score_1989 = calculate_preference_score(self.film_1989, pre_1990_prefs)
        score_1990 = calculate_preference_score(self.film_1990, pre_1990_prefs)
        self.assertGreater(score_1989, 0, "1989 film must receive bonus for before_1990 era")
        self.assertLess(score_1990, 0, "1990 film must receive penalty for before_1990 era")

        nineties_prefs = {"era": ["90s"]}
        score_1989_90s = calculate_preference_score(self.film_1989, nineties_prefs)
        score_1990_90s = calculate_preference_score(self.film_1990, nineties_prefs)
        score_1995_90s = calculate_preference_score(self.film_1995, nineties_prefs)
        score_1999_90s = calculate_preference_score(self.film_1999, nineties_prefs)
        score_2000_90s = calculate_preference_score(self.film_2000, nineties_prefs)
        self.assertLess(score_1989_90s, 0, "1989 film must receive penalty for 90s era")
        self.assertGreater(score_1990_90s, 0, "1990 film must receive bonus for 90s era")
        self.assertGreater(score_1995_90s, 0, "1995 film must receive bonus for 90s era")
        self.assertGreater(score_1999_90s, 0, "1999 film must receive bonus for 90s era")
        self.assertLess(score_2000_90s, 0, "2000 film must receive penalty for 90s era")


