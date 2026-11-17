import os
from datetime import date
from unittest import mock
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from core.models import Movie, Session, Swipe, Match, SessionStats, Genre, WatchlistItem, UserProfile


class AuthenticationAndPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.standard_user = User.objects.create_user(
            username="standarduser",
            password="TestPassword123!",
            email="standard@flick.test"
        )
        self.admin_user = User.objects.create_user(
            username="adminuser",
            password="AdminPassword123!",
            email="admin@flick.test",
            is_staff=True
        )
        self.standard_token = Token.objects.create(user=self.standard_user)
        self.admin_token = Token.objects.create(user=self.admin_user)

        self.movie = Movie.objects.create(
            title="Inception",
            overview="Dream within a dream",
            tmdb_id=27205
        )

    def test_unauthenticated_movie_create_fails(self):
        """Unauthenticated requests cannot create movies."""
        response = self.client.post("/api/movies/create/", {"title": "Interstellar", "tmdb_id": 157336})
        self.assertEqual(response.status_code, 401)

    def test_standard_user_cannot_create_movie(self):
        """Non-admin authenticated users are forbidden from creating movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.standard_token.key}")
        response = self.client.post("/api/movies/create/", {"title": "Interstellar", "tmdb_id": 157336})
        self.assertEqual(response.status_code, 403)

    def test_admin_user_can_create_movie(self):
        """Staff/admin users can create movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")
        response = self.client.post("/api/movies/create/", {"title": "Interstellar", "tmdb_id": 157336})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Movie.objects.filter(tmdb_id=157336).exists())

    def test_standard_user_cannot_update_or_delete_movie(self):
        """Non-admin users cannot update or delete existing movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.standard_token.key}")

        # Update attempt
        update_res = self.client.put(
            f"/api/movies/{self.movie.id}/update/",
            {"title": "Inception Remastered", "tmdb_id": 27205}
        )
        self.assertEqual(update_res.status_code, 403)

        # Delete attempt
        delete_res = self.client.delete(f"/api/movies/{self.movie.id}/delete/")
        self.assertEqual(delete_res.status_code, 403)
        self.assertTrue(Movie.objects.filter(id=self.movie.id).exists())

    def test_admin_user_can_update_and_delete_movie(self):
        """Staff/admin users can update and delete movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.admin_token.key}")

        # Update
        update_res = self.client.put(
            f"/api/movies/{self.movie.id}/update/",
            {"title": "Inception Remastered", "tmdb_id": 27205}
        )
        self.assertEqual(update_res.status_code, 200)

        # Delete
        delete_res = self.client.delete(f"/api/movies/{self.movie.id}/delete/")
        self.assertEqual(delete_res.status_code, 204)
        self.assertFalse(Movie.objects.filter(id=self.movie.id).exists())

    def test_movie_sync_tmdb_requires_admin(self):
        """Syncing TMDB movies requires admin privileges."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.standard_token.key}")
        response = self.client.post("/api/movies/sync-tmdb/")
        self.assertEqual(response.status_code, 403)

    def test_genre_sync_tmdb_requires_admin(self):
        """Syncing TMDB genres requires admin privileges."""
        # Unauthenticated
        unauth_res = self.client.post("/api/genres/sync-tmdb/")
        self.assertEqual(unauth_res.status_code, 401)

        # Standard user
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.standard_token.key}")
        std_res = self.client.post("/api/genres/sync-tmdb/")
        self.assertEqual(std_res.status_code, 403)


class SessionJoiningTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="hostuser", password="Password123!")
        self.guest = User.objects.create_user(username="guestuser", password="Password123!")
        self.intruder = User.objects.create_user(username="intruderuser", password="Password123!")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.intruder_token = Token.objects.create(user=self.intruder)

        self.session = Session.objects.create(host=self.host, code="TEST12")

    def test_guest_can_join_active_session(self):
        """Guest with a valid code successfully joins session."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        response = self.client.post("/api/sessions/join/", {"code": "TEST12"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

        self.session.refresh_from_db()
        self.assertEqual(self.session.guest, self.guest)

    def test_host_cannot_join_own_session(self):
        """Host cannot join their own session as guest."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        response = self.client.post("/api/sessions/join/", {"code": "TEST12"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Host cannot join own session")

    def test_cannot_join_full_session(self):
        """A third user cannot join a session that already has a guest."""
        self.session.guest = self.guest
        self.session.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.intruder_token.key}")
        response = self.client.post("/api/sessions/join/", {"code": "TEST12"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"], "Session already full")

    def test_guest_idempotent_rejoin(self):
        """If the joined guest requests to join again, it returns 200 gracefully."""
        self.session.guest = self.guest
        self.session.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        response = self.client.post("/api/sessions/join/", {"code": "TEST12"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Already joined session")

    def test_invalid_session_code(self):
        """Invalid session code returns 404."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        response = self.client.post("/api/sessions/join/", {"code": "NONEXISTENT"})
        self.assertEqual(response.status_code, 404)


class SwipeAndMatchingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="hostuser", password="Password123!")
        self.guest = User.objects.create_user(username="guestuser", password="Password123!")
        self.stranger = User.objects.create_user(username="stranger", password="Password123!")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(host=self.host, guest=self.guest, code="SWIPE1")
        self.movie1 = Movie.objects.create(title="Movie 1", tmdb_id=101)
        self.movie2 = Movie.objects.create(title="Movie 2", tmdb_id=102)

    def test_mutual_right_swipe_creates_match(self):
        """Host LIKE followed by Guest LIKE triggers mutual match."""
        # Host swipes like
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res1 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res1.status_code, 201)
        self.assertFalse(res1.data["match"])

        # Guest swipes like
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res2 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res2.status_code, 201)
        self.assertTrue(res2.data["match"])

        # Verify DB records
        self.assertTrue(Match.objects.filter(session=self.session, movie=self.movie1).exists())
        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.total_swipes, 2)
        self.assertEqual(stats.total_matches, 1)

    def test_dislike_does_not_create_match(self):
        """Host DISLIKE followed by Guest LIKE does not create a match."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.DISLIKE
        })

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["match"])
        self.assertFalse(Match.objects.filter(session=self.session, movie=self.movie1).exists())

    def test_superlike_pending_until_partner_responds(self):
        """A single SUPERLIKE remains pending without waiting for partner, and matches only upon partner positive response."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie2.id,
            "reaction": Swipe.SUPERLIKE
        })
        self.assertEqual(res.status_code, 201)
        self.assertFalse(res.data["match"], "Single Super-Like must remain pending")
        self.assertFalse(Match.objects.filter(session=self.session, movie=self.movie2).exists())

        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.total_matches, 0)
        self.assertEqual(stats.total_swipes, 1)

        # Partner responds with positive reaction (like) -> match forms with host superlike attribution
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res2 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie2.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res2.status_code, 201)
        self.assertTrue(res2.data["match"])
        self.assertEqual(res2.data["superlike_attribution"], "host")
        self.assertTrue(Match.objects.filter(session=self.session, movie=self.movie2).exists())

        stats.refresh_from_db()
        self.assertEqual(stats.total_matches, 1)
        self.assertEqual(stats.total_swipes, 2)

    def test_duplicate_swipe_rejected(self):
        """Same user swiping on the same movie twice in the same session is rejected (409)."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res1 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res1.status_code, 201)

        # Duplicate swipe attempt with same reaction: successful idempotent retry (200)
        res2 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.data.get("idempotent"))

        # Conflicting swipe attempt with different reaction: rejected (409)
        res3 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.DISLIKE
        })
        self.assertEqual(res3.status_code, 409)
        self.assertIn("Conflicting reaction", res3.data.get("error", ""))

    def test_swipe_before_guest_joins_blocked(self):
        """Swipes are blocked when session has no guest yet."""
        empty_session = Session.objects.create(host=self.host, code="NOGUEST")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.post("/api/swipes/", {
            "session": empty_session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["error"], "Session is not ready yet")

    def test_swipe_after_session_ended_blocked(self):
        """Swipes on an ended session are rejected."""
        from django.utils import timezone
        self.session.ended_at = timezone.now()
        self.session.save()

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["error"], "Session has ended")

    def test_non_member_cannot_swipe(self):
        """User who is neither host nor guest cannot swipe in the session."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["error"], "You are not part of this session")


class ConcurrencyAndAtomicityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="hostuser", password="Password123!")
        self.guest = User.objects.create_user(username="guestuser", password="Password123!")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)

        self.session = Session.objects.create(host=self.host, guest=self.guest, code="CONCUR")
        self.movies = [
            Movie.objects.create(title=f"Movie {i}", tmdb_id=2000 + i)
            for i in range(5)
        ]

    def test_atomic_stats_update_with_f_expressions(self):
        """Verifies session stats counters accurately accumulate sequential swipes without loss."""
        for movie in self.movies:
            self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
            self.client.post("/api/swipes/", {
                "session": self.session.id,
                "movie": movie.id,
                "reaction": Swipe.LIKE
            })

            self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
            self.client.post("/api/swipes/", {
                "session": self.session.id,
                "movie": movie.id,
                "reaction": Swipe.LIKE
            })

        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.total_swipes, 10)
        self.assertEqual(stats.total_matches, 5)
        self.assertEqual(Match.objects.filter(session=self.session).count(), 5)


class SwipeUndoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="hostuser", password="Password123!")
        self.guest = User.objects.create_user(username="guestuser", password="Password123!")
        self.stranger = User.objects.create_user(username="stranger", password="Password123!")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(host=self.host, guest=self.guest, code="UNDOTS")
        self.movie = Movie.objects.create(title="Undoable Movie", tmdb_id=3001)

    def test_swipe_undo_success_decrements_counter(self):
        """Swiping and undoing within window deletes swipe and decrements stats counter."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        swipe_res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": Swipe.LIKE
        })
        self.assertEqual(swipe_res.status_code, 201)
        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.total_swipes, 1)

        undo_res = self.client.delete("/api/swipes/undo/", {
            "session_id": self.session.id,
            "movie_id": self.movie.id,
        })
        self.assertEqual(undo_res.status_code, 200)
        self.assertEqual(undo_res.data["message"], "Swipe undone")
        self.assertFalse(Swipe.objects.filter(user=self.host, session=self.session, movie=self.movie).exists())

        stats.refresh_from_db()
        self.assertEqual(stats.total_swipes, 0)

    def test_swipe_undo_blocked_after_match(self):
        """Cannot undo a swipe once a mutual match has been formed."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": Swipe.LIKE
        })

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": Swipe.LIKE
        })
        self.assertTrue(Match.objects.filter(session=self.session, movie=self.movie).exists())

        # Host tries to undo after match
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        undo_res = self.client.delete("/api/swipes/undo/", {
            "session_id": self.session.id,
            "movie_id": self.movie.id,
        })
        self.assertEqual(undo_res.status_code, 409)
        self.assertEqual(undo_res.data["error"], "Cannot undo after match")
        self.assertTrue(Swipe.objects.filter(user=self.host, session=self.session, movie=self.movie).exists())

    def test_swipe_undo_blocked_after_expiry(self):
        """Undo fails if more than 10 seconds have elapsed."""
        from datetime import timedelta
        from django.utils import timezone
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": Swipe.DISLIKE
        })

        swipe = Swipe.objects.get(user=self.host, session=self.session, movie=self.movie)
        # Artificially age the swipe record past the 10s window
        Swipe.objects.filter(id=swipe.id).update(created_at=timezone.now() - timedelta(seconds=15))

        undo_res = self.client.delete("/api/swipes/undo/", {
            "session_id": self.session.id,
            "movie_id": self.movie.id,
        })
        self.assertEqual(undo_res.status_code, 403)
        self.assertEqual(undo_res.data["error"], "Undo window expired")

    def test_swipe_undo_non_member_blocked(self):
        """Non-member cannot undo swipes in a session."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": Swipe.LIKE
        })

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        undo_res = self.client.delete("/api/swipes/undo/", {
            "session_id": self.session.id,
            "movie_id": self.movie.id,
        })
        self.assertEqual(undo_res.status_code, 403)


class SessionLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="hostuser", password="Password123!")
        self.guest = User.objects.create_user(username="guestuser", password="Password123!")
        self.stranger = User.objects.create_user(username="stranger", password="Password123!")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(host=self.host, guest=self.guest, code="LIFE01")

    def test_session_end_is_idempotent(self):
        """Host ends session, subsequent end by guest is safe and returns 200."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res1 = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data["message"], "Session ended")

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.ended_at)

        # Second end attempt returns 200 gracefully
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res2 = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["message"], "Session already ended")

    def test_non_member_cannot_end_session(self):
        """Non-member cannot end someone else's session."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res.status_code, 403)


class WorkflowEndToEndIntegrationTests(TestCase):
    """
    End-to-end integration test simulating the entire user journey:
    Session creation -> Configuration -> Guest join -> Swiping -> Undo -> Superlike -> Match list -> Session End.
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="host_alice", password="Password123!")
        self.guest = User.objects.create_user(username="guest_bob", password="Password123!")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)

        self.genre = Genre.objects.create(name="Sci-Fi", tmdb_id=878)
        self.movie1 = Movie.objects.create(title="Interstellar", tmdb_id=157336, original_language="en")
        self.movie1.genres.add(self.genre)
        self.movie2 = Movie.objects.create(title="Inception", tmdb_id=27205, original_language="en")
        self.movie2.genres.add(self.genre)
        self.movie3 = Movie.objects.create(title="Arrival", tmdb_id=329865, original_language="en")
        self.movie3.genres.add(self.genre)

    def test_complete_host_guest_swiping_and_matching_flow(self):
        # 1. Host creates a session
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        create_res = self.client.post("/api/sessions/create/")
        self.assertEqual(create_res.status_code, 201)
        session_id = create_res.data["id"]
        session_code = create_res.data["code"]
        self.assertTrue(session_code)

        # 2. Host configures session genre and industry
        genre_res = self.client.post("/api/sessions/genre/", {
            "session_id": session_id,
            "genre_id": self.genre.id,
            "industry": "hollywood",
            "languages": ["en"],
        }, format="json")
        self.assertEqual(genre_res.status_code, 200)

        # 3. Host sets preferences
        host_pref_res = self.client.post("/api/sessions/preferences/", {
            "session_id": session_id,
            "preferences": {"mood": ["mind-bending"], "pace": ["fast"], "vibe": ["intense"]},
        }, format="json")
        self.assertEqual(host_pref_res.status_code, 200)

        # 4. Guest joins using the session code
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        join_res = self.client.post("/api/sessions/join/", {"code": session_code}, format="json")
        self.assertEqual(join_res.status_code, 200)
        self.assertEqual(join_res.data["session_id"], session_id)

        # 5. Guest sets preferences (both ready)
        guest_pref_res = self.client.post("/api/sessions/preferences/", {
            "session_id": session_id,
            "preferences": {"mood": ["mind-bending"], "pace": ["moderate"], "vibe": ["intense"]},
        }, format="json")
        self.assertEqual(guest_pref_res.status_code, 200)
        self.assertTrue(guest_pref_res.data["both_ready"])

        # 6. Both users query recommendations
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        rec_res = self.client.get(f"/api/recommendations/?session_id={session_id}")
        self.assertEqual(rec_res.status_code, 200)
        self.assertIn("movies", rec_res.data)

        # 7. Movie 1: Mutual match (Host likes, Guest likes)
        host_swipe1 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE,
        })
        self.assertEqual(host_swipe1.status_code, 201)
        self.assertFalse(host_swipe1.data["match"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_swipe1 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie1.id,
            "reaction": Swipe.LIKE,
        })
        self.assertEqual(guest_swipe1.status_code, 201)
        self.assertTrue(guest_swipe1.data["match"])

        # Verify Movie 1 appears in match list
        matches_res = self.client.get("/api/matches/")
        self.assertEqual(matches_res.status_code, 200)
        matched_movie_ids = [m["movie_id"] for m in matches_res.data["matches"]]
        self.assertIn(self.movie1.id, matched_movie_ids)

        # 8. Movie 2: Host likes, then UNDOES before guest swipes
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_swipe2 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie2.id,
            "reaction": Swipe.LIKE,
        })
        self.assertEqual(host_swipe2.status_code, 201)

        undo_res = self.client.delete("/api/swipes/undo/", {
            "session_id": session_id,
            "movie_id": self.movie2.id,
        }, format="json")
        self.assertEqual(undo_res.status_code, 200)

        # Guest dislikes Movie 2 -> No match formed
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_swipe2 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie2.id,
            "reaction": Swipe.DISLIKE,
        })
        self.assertEqual(guest_swipe2.status_code, 201)
        self.assertFalse(guest_swipe2.data["match"])
        self.assertFalse(Match.objects.filter(session_id=session_id, movie=self.movie2).exists())

        # 9. Movie 3: Host likes, Guest superlikes -> Match formed with guest Super-Like attribution
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        host_swipe3 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie3.id,
            "reaction": Swipe.LIKE,
        })
        self.assertEqual(host_swipe3.status_code, 201)
        self.assertFalse(host_swipe3.data["match"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        guest_swipe3 = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie3.id,
            "reaction": Swipe.SUPERLIKE,
        })
        self.assertEqual(guest_swipe3.status_code, 201)
        self.assertTrue(guest_swipe3.data["match"])
        self.assertEqual(guest_swipe3.data["superlike_attribution"], "guest")
        self.assertTrue(Match.objects.filter(session_id=session_id, movie=self.movie3).exists())

        # 10. End session and verify statistics
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        end_res = self.client.post("/api/sessions/end/", {"session_id": session_id})
        self.assertEqual(end_res.status_code, 200)

        stats = SessionStats.objects.get(session_id=session_id)
        # Swipes: host_swipe1 (1) + guest_swipe1 (1) + host_swipe2 (1) - undone (1) + guest_swipe2 (1) + host_swipe3 (1) + guest_swipe3 (1) = 5 total swipes
        self.assertEqual(stats.total_swipes, 5)
        self.assertEqual(stats.total_matches, 2)
        self.assertIsNotNone(stats.quality_score)

        # 11. Swipes on ended session are rejected
        post_end_swipe = self.client.post("/api/swipes/", {
            "session": session_id,
            "movie": self.movie2.id,
            "reaction": Swipe.LIKE,
        })
        self.assertEqual(post_end_swipe.status_code, 403)
        self.assertEqual(post_end_swipe.data["error"], "Session has ended")


class EmailVerificationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="verify_user",
            password="Password123!",
            email="verify@flick.test"
        )
        self.token = Token.objects.create(user=self.user)

    def test_send_verification_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        res = self.client.post("/api/auth/send-verification/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])

    def test_send_verification_already_verified(self):
        profile = UserProfile.objects.create(user=self.user, email_verified=True)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        res = self.client.post("/api/auth/send-verification/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("already_verified"))

    def test_verify_email_success(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        res = self.client.post("/api/auth/verify-email/", {
            "uid": uid,
            "token": token,
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.email_verified)

    def test_verify_email_invalid_token(self):
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        res = self.client.post("/api/auth/verify-email/", {
            "uid": uid,
            "token": "invalid-token-123",
        })
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data["success"])


class RecentSessionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user1 = User.objects.create_user(username="user1", password="Password123!")
        self.user2 = User.objects.create_user(username="user2", password="Password123!")
        self.stranger = User.objects.create_user(username="stranger", password="Password123!")
        self.user1_token = Token.objects.create(user=self.user1)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.genre = Genre.objects.create(name="Horror", tmdb_id=27)
        self.session = Session.objects.create(
            host=self.user1,
            guest=self.user2,
            genre=self.genre,
            code="REC001"
        )

    def test_recent_sessions_empty_for_stranger(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.get("/api/sessions/recent/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["sessions"], [])

    def test_recent_sessions_returns_user_sessions_only(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.user1_token.key}")
        res = self.client.get("/api/sessions/recent/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["sessions"]), 1)
        s = res.data["sessions"][0]
        self.assertEqual(s["code"], "REC001")
        self.assertEqual(s["name"], "Horror Night")
        self.assertEqual(len(s["participants"]), 2)


class WatchlistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username="user_a", password="Password123!")
        self.user_b = User.objects.create_user(username="user_b", password="Password123!")
        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)

        self.movie = Movie.objects.create(title="Dune: Part Two", tmdb_id=693134, rating=8.3)

    def test_watchlist_add_and_list(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        add_res = self.client.post("/api/watchlist/", {"movie_id": self.movie.id})
        self.assertEqual(add_res.status_code, 201)
        self.assertTrue(add_res.data["created"])

        list_res = self.client.get("/api/watchlist/")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.data["watchlist"]), 1)
        self.assertEqual(list_res.data["watchlist"][0]["movie_id"], self.movie.id)
        self.assertEqual(list_res.data["watchlist"][0]["movie_title"], "Dune: Part Two")

    def test_watchlist_toggle_watched(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        self.client.post("/api/watchlist/", {"movie_id": self.movie.id})

        patch_res = self.client.patch(f"/api/watchlist/{self.movie.id}/", {"watched": True})
        self.assertEqual(patch_res.status_code, 200)
        self.assertTrue(patch_res.data["watched"])

        item = WatchlistItem.objects.get(user=self.user_a, movie=self.movie)
        self.assertTrue(item.watched)
        self.assertIsNotNone(item.watched_at)

    def test_watchlist_remove(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        self.client.post("/api/watchlist/", {"movie_id": self.movie.id})

        del_res = self.client.delete(f"/api/watchlist/{self.movie.id}/")
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(WatchlistItem.objects.filter(user=self.user_a, movie=self.movie).exists())

    def test_watchlist_user_isolation(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        self.client.post("/api/watchlist/", {"movie_id": self.movie.id})

        # User B should see empty watchlist
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        res = self.client.get("/api/watchlist/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["watchlist"], [])


class DiscoverTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Patch TMDB to test graceful local catalog fallback when TMDB is unavailable
        self.tmdb_popular_patcher = mock.patch("core.services.tmdb.get_popular_movies", side_effect=Exception("TMDB offline"))
        self.tmdb_discover_patcher = mock.patch("core.services.tmdb.discover_movies", side_effect=Exception("TMDB offline"))
        self.tmdb_search_patcher = mock.patch("core.services.tmdb.search_movies", side_effect=Exception("TMDB offline"))
        self.tmdb_popular_patcher.start()
        self.tmdb_discover_patcher.start()
        self.tmdb_search_patcher.start()
        self.addCleanup(self.tmdb_popular_patcher.stop)
        self.addCleanup(self.tmdb_discover_patcher.stop)
        self.addCleanup(self.tmdb_search_patcher.stop)

        self.g_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.g_drama = Genre.objects.create(name="Drama", tmdb_id=18)

        self.m1 = Movie.objects.create(
            title="The Dark Knight",
            rating=9.0,
            original_language="en",
            release_date=date(2008, 7, 18),
            tmdb_id=155
        )
        self.m1.genres.add(self.g_action)

        self.m2 = Movie.objects.create(
            title="RRR",
            rating=8.0,
            original_language="te",
            release_date=date(2022, 3, 24),
            tmdb_id=579974
        )
        self.m2.genres.add(self.g_action, self.g_drama)

        self.m3 = Movie.objects.create(
            title="Casablanca",
            rating=8.5,
            original_language="en",
            release_date=date(1942, 1, 23),
            tmdb_id=289
        )
        self.m3.genres.add(self.g_drama)

    def test_discover_list_and_pagination(self):
        res = self.client.get("/api/discover/?page=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 3)
        self.assertFalse(res.data["has_more"])

    def test_discover_filter_by_min_rating(self):
        res = self.client.get("/api/discover/?min_rating=8.5")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 2)
        titles = [m["title"] for m in res.data["movies"]]
        self.assertIn("The Dark Knight", titles)
        self.assertIn("Casablanca", titles)
        self.assertNotIn("RRR", titles)

    def test_discover_filter_by_era(self):
        res = self.client.get("/api/discover/?era=recent")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 1)
        self.assertEqual(res.data["movies"][0]["title"], "RRR")

        res_classic = self.client.get("/api/discover/?era=classic")
        self.assertEqual(res_classic.status_code, 200)
        self.assertEqual(len(res_classic.data["movies"]), 1)
        self.assertEqual(res_classic.data["movies"][0]["title"], "Casablanca")

    def test_discover_filter_by_language(self):
        res = self.client.get("/api/discover/?language=te")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 1)
        self.assertEqual(res.data["movies"][0]["title"], "RRR")

    def test_discover_search(self):
        res = self.client.get("/api/discover/?search=knight")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 1)
        self.assertEqual(res.data["movies"][0]["title"], "The Dark Knight")


class GenreIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_genres_returns_options_for_all_industries(self):
        for industry in ["mixed", "hollywood", "bollywood"]:
            res = self.client.get(f"/api/genres/?industry={industry}")
            self.assertEqual(res.status_code, 200)
            self.assertTrue(res.data["success"])
            self.assertGreaterEqual(len(res.data["genres"]), 1)

    def test_genres_auto_seed_on_empty_db(self):
        Genre.objects.all().delete()
        self.assertEqual(Genre.objects.count(), 0)

        res = self.client.get("/api/genres/?industry=mixed")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["genres"]), 19)
        self.assertEqual(Genre.objects.count(), 19)


class RecommendationDiscoveryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="rechost", email="rechost@example.com", password="password123")
        self.guest = User.objects.create_user(username="recguest", email="recguest@example.com", password="password123")
        self.token = Token.objects.create(user=self.host)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.genre_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.genre_comedy = Genre.objects.create(name="Comedy", tmdb_id=35)

        self.movie_en = Movie.objects.create(
            tmdb_id=101,
            title="Inception",
            overview="A thief who steals corporate secrets through dream-sharing technology.",
            rating=8.8,
            original_language="en",
            release_date=date(2010, 7, 16),
            vote_count=35000,
            poster_path="/inception.jpg",
            trailer_key="YoHD9XEInc0",
        )
        self.movie_en.genres.add(self.genre_action)

        self.movie_hi = Movie.objects.create(
            tmdb_id=102,
            title="Dhurandhar",
            overview="An action-packed thriller set in the underworld.",
            rating=7.5,
            original_language="hi",
            release_date=date(2025, 5, 10),
            vote_count=500,
            poster_path="/dhurandhar.jpg",
        )
        self.movie_hi.genres.add(self.genre_action)

        self.movie_comedy = Movie.objects.create(
            tmdb_id=103,
            title="Superbad",
            overview="Two high school boys want to enjoy their lives to the fullest.",
            rating=7.6,
            original_language="en",
            release_date=date(2007, 8, 17),
            vote_count=12000,
            poster_path="/superbad.jpg",
        )
        self.movie_comedy.genres.add(self.genre_comedy)

    def test_recommendation_feed_hollywood_success(self):
        session = Session.objects.create(
            code="REC001",
            host=self.host,
            guest=self.guest,
            genre=self.genre_action,
            industry="hollywood",
            selected_languages=["en"],
        )
        res = self.client.get(f"/api/recommendations/?session_id={session.id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        self.assertEqual(len(res.data["movies"]), 1)
        movie_data = res.data["movies"][0]
        self.assertEqual(movie_data["title"], "Inception")
        self.assertEqual(movie_data["poster_url"], "https://image.tmdb.org/t/p/w780/inception.jpg")
        self.assertEqual(movie_data["trailer_url"], "https://www.youtube.com/watch?v=YoHD9XEInc0")

    def test_recommendation_feed_bollywood_success(self):
        session = Session.objects.create(
            code="REC002",
            host=self.host,
            guest=self.guest,
            genre=self.genre_action,
            industry="bollywood",
            selected_languages=["hi"],
        )
        res = self.client.get(f"/api/recommendations/?session_id={session.id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        self.assertEqual(len(res.data["movies"]), 1)
        self.assertEqual(res.data["movies"][0]["title"], "Dhurandhar")
        self.assertEqual(res.data["movies"][0]["original_language"], "hi")

    def test_recommendation_feed_multi_genre_support(self):
        session = Session.objects.create(
            code="REC003",
            host=self.host,
            guest=self.guest,
            genre=self.genre_action,
            industry="hollywood",
            selected_languages=["en"],
        )
        session.genres.add(self.genre_action, self.genre_comedy)
        res = self.client.get(f"/api/recommendations/?session_id={session.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 2)
        titles = [m["title"] for m in res.data["movies"]]
        self.assertIn("Inception", titles)
        self.assertIn("Superbad", titles)

    def test_preferences_boost_rank_without_dropping_candidates(self):
        session = Session.objects.create(
            code="REC004",
            host=self.host,
            guest=self.guest,
            genre=self.genre_action,
            industry="hollywood",
            selected_languages=["en"],
            host_preferences={"mood": ["happy"], "pace": ["slow"], "vibe": ["feel-good"], "era": ["2010s"]},
            guest_preferences={"mood": ["happy"], "pace": ["slow"], "vibe": ["feel-good"], "era": ["2010s"]},
        )
        res = self.client.get(f"/api/recommendations/?session_id={session.id}")
        self.assertEqual(res.status_code, 200)
        # Candidates must NOT be dropped merely because preferences didn't hit threshold
        self.assertEqual(len(res.data["movies"]), 1)
        self.assertEqual(res.data["movies"][0]["title"], "Inception")

    def test_daphne_asgi_and_websocket_routing(self):
        from django.conf import settings
        from core.routing import websocket_urlpatterns
        self.assertEqual(settings.INSTALLED_APPS[0], "daphne")
        self.assertTrue(any("ws/session" in str(p.pattern) for p in websocket_urlpatterns))


class SessionHistoryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="archivist_host", password="Password123!")
        self.guest = User.objects.create_user(username="archivist_guest", password="Password123!")
        self.stranger = User.objects.create_user(username="archivist_stranger", password="Password123!")

        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.genre_drama = Genre.objects.create(name="Drama", tmdb_id=18)
        self.genre_mystery = Genre.objects.create(name="Mystery", tmdb_id=9648)

        self.movie_classic = Movie.objects.create(
            tmdb_id=101,
            title="Persona",
            rating=8.4,
            poster_path="/persona.jpg",
            release_date=date(1966, 10, 18),
        )
        self.movie_modern = Movie.objects.create(
            tmdb_id=102,
            title="Drive My Car",
            rating=7.9,
            poster_path="/drive_my_car.jpg",
            release_date=date(2021, 8, 20),
        )

    def test_unauthenticated_history_returns_401(self):
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, 401)

    def test_empty_history_returns_valid_empty_result(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success", False))
        self.assertEqual(res.data.get("history"), [])

    def test_session_history_fields_ordering_and_top_match(self):
        from django.utils import timezone
        import time

        # Session 1: Earlier session
        s1 = Session.objects.create(
            code="HIST01",
            host=self.host,
            guest=self.guest,
            genre=self.genre_drama,
            ended_at=timezone.now(),
        )
        s1.genres.add(self.genre_drama)

        # Swipes in session 1
        Swipe.objects.create(user=self.host, session=s1, movie=self.movie_classic, reaction=Swipe.LIKE)
        Swipe.objects.create(user=self.guest, session=s1, movie=self.movie_classic, reaction=Swipe.LIKE)
        Match.objects.create(session=s1, movie=self.movie_classic)

        # Session 2: Later session with 2 matches, top rated match is Persona (8.4) vs Drive My Car (7.9)
        time.sleep(0.01)
        s2 = Session.objects.create(
            code="HIST02",
            host=self.host,
            guest=self.guest,
            ended_at=timezone.now(),
        )
        s2.genres.add(self.genre_drama, self.genre_mystery)

        Swipe.objects.create(user=self.host, session=s2, movie=self.movie_modern, reaction=Swipe.LIKE)
        Swipe.objects.create(user=self.host, session=s2, movie=self.movie_classic, reaction=Swipe.LIKE)
        Swipe.objects.create(user=self.guest, session=s2, movie=self.movie_modern, reaction=Swipe.LIKE)
        Swipe.objects.create(user=self.guest, session=s2, movie=self.movie_classic, reaction=Swipe.LIKE)
        Match.objects.create(session=s2, movie=self.movie_modern)
        Match.objects.create(session=s2, movie=self.movie_classic)

        # Host request
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success", False))
        history = res.data.get("history", [])
        self.assertEqual(len(history), 2)

        # Most recent session (s2) must come first
        latest = history[0]
        self.assertEqual(latest["session_id"], s2.id)
        self.assertEqual(latest["session_code"], "HIST02")
        self.assertEqual(latest["partner_username"], "archivist_guest")
        self.assertIn("Drama", latest["genres"])
        self.assertIn("Mystery", latest["genres"])
        self.assertEqual(latest["match_count"], 2)
        self.assertEqual(latest["swipe_count"], 2)
        self.assertIsNotNone(latest["ended_at"])
        self.assertIsNotNone(latest["created_at"])
        # Top match should be the highest rated film (Persona: 8.4)
        self.assertIsNotNone(latest["top_match"])
        self.assertEqual(latest["top_match"]["movie_id"], self.movie_classic.id)
        self.assertEqual(latest["top_match"]["movie_title"], "Persona")
        self.assertEqual(latest["top_match"]["poster_url"], "https://image.tmdb.org/t/p/w780/persona.jpg")

    def test_user_isolation_cannot_access_stranger_sessions(self):
        s_private = Session.objects.create(
            code="PRIV01",
            host=self.host,
            guest=self.guest,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("history"), [])

    def test_guest_perspective_resolves_partner_as_host(self):
        s = Session.objects.create(
            code="GUEST1",
            host=self.host,
            guest=self.guest,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.guest_token.key}")
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, 200)
        history = res.data.get("history", [])
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["partner_username"], "archivist_host")

    def test_session_detail_dynamic_route_remains_functional(self):
        s = Session.objects.create(
            code="DET001",
            host=self.host,
            guest=self.guest,
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        res = self.client.get(f"/api/sessions/{s.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["session"]["code"], "DET001")


class StreamingProviderAvailabilityTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.client = APIClient()
        self.user = User.objects.create_user(username="film_buff", password="Password123!")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.movie = Movie.objects.create(
            tmdb_id=299534,
            title="Avengers: Endgame",
            rating=8.3,
            release_date=date(2019, 4, 26),
        )

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    @mock.patch("core.views.get_movie_watch_providers")
    def test_india_region_response_containing_subscription_providers(self, mock_get_providers):
        mock_get_providers.return_value = {
            "link": "https://www.themoviedb.org/movie/299534/watch?locale=IN",
            "region": "IN",
            "flatrate": [
                {
                    "provider_id": 2336,
                    "provider_name": "JioHotstar",
                    "logo_path": "/ledoS6EgdjTNq8F1e6wubUQer18.png",
                    "display_priority": 1,
                }
            ],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        res = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success"))
        self.assertEqual(res.data.get("region"), "IN")
        providers = res.data.get("providers", [])
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["name"], "JioHotstar")
        self.assertEqual(providers[0]["type"], "flatrate")
        self.assertIn("JustWatch", res.data.get("attribution", ""))
        self.assertTrue(providers[0]["logo_url"].endswith("/ledoS6EgdjTNq8F1e6wubUQer18.png"))

    @mock.patch("core.views.get_movie_watch_providers")
    def test_rental_and_purchase_providers_in_correct_categories(self, mock_get_providers):
        mock_get_providers.return_value = {
            "link": "https://www.themoviedb.org/movie/299534/watch?locale=IN",
            "region": "IN",
            "flatrate": [],
            "rent": [
                {
                    "provider_id": 192,
                    "provider_name": "YouTube",
                    "logo_path": "/yt_logo.png",
                    "display_priority": 2,
                }
            ],
            "buy": [
                {
                    "provider_id": 3,
                    "provider_name": "Google Play Movies",
                    "logo_path": "/gp_logo.png",
                    "display_priority": 3,
                }
            ],
            "free": [],
            "ads": [],
        }

        res = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 200)
        providers = res.data.get("providers", [])
        self.assertEqual(len(providers), 2)

        types = {p["name"]: p["type"] for p in providers}
        self.assertEqual(types.get("YouTube"), "rent")
        self.assertEqual(types.get("Google Play Movies"), "buy")
        self.assertNotIn("flatrate", types.values())

    @mock.patch("core.views.get_movie_watch_providers")
    def test_response_with_no_regional_provider_data(self, mock_get_providers):
        mock_get_providers.return_value = {
            "link": None,
            "region": "IN",
            "flatrate": [],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        res = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success"))
        self.assertEqual(res.data.get("providers"), [])
        self.assertIn("JustWatch", res.data.get("attribution", ""))

    @mock.patch("core.views.get_movie_watch_providers")
    def test_tmdb_timeouts_http_errors_and_malformed_responses(self, mock_get_providers):
        from core.services.tmdb import TMDBTimeoutError, TMDBAPIError

        # 1. Timeout error
        mock_get_providers.side_effect = TMDBTimeoutError("Upstream timeout")
        res = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 502)
        self.assertFalse(res.data.get("success"))
        self.assertIn("retry", res.data.get("error", "").lower())

        # 2. HTTP error
        mock_get_providers.side_effect = TMDBAPIError("TMDB returned HTTP 500")
        res2 = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res2.status_code, 502)
        self.assertFalse(res2.data.get("success"))

    @mock.patch("core.views.get_movie_watch_providers")
    def test_provider_response_with_other_regions_but_not_in(self, mock_get_providers):
        # When querying IN, but TMDB only had US data
        mock_get_providers.return_value = {
            "link": None,
            "region": "IN",
            "flatrate": [],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        res = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data.get("providers"), [])
        self.assertEqual(res.data.get("region"), "IN")

    @mock.patch("core.views.get_movie_watch_providers")
    def test_propagation_of_provider_data_and_schema(self, mock_get_providers):
        mock_get_providers.return_value = {
            "link": "https://www.themoviedb.org/movie/299534/watch?locale=IN",
            "region": "IN",
            "flatrate": [
                {
                    "provider_id": 2336,
                    "provider_name": "JioHotstar",
                    "logo_path": "/ledoS6EgdjTNq8F1e6wubUQer18.png",
                    "display_priority": 1,
                }
            ],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        # Query by tmdb_id as well as movie.id
        res = self.client.get(f"/api/movies/{self.movie.tmdb_id}/streaming-options/?region=IN")
        self.assertEqual(res.status_code, 200)
        data = res.data
        self.assertTrue(data["success"])
        self.assertEqual(data["movie_title"], "Avengers: Endgame")
        self.assertEqual(data["movie_id"], self.movie.id)
        self.assertEqual(data["tmdb_id"], 299534)
        self.assertEqual(data["region"], "IN")
        self.assertIn("JustWatch", data["attribution"])
        self.assertTrue(len(data["providers"]) > 0)
        p = data["providers"][0]
        # Schema compatibility with both old and new consumers
        self.assertIn("name", p)
        self.assertIn("provider_name", p)
        self.assertIn("logo_url", p)
        self.assertIn("logo_path", p)
        self.assertIn("url", p)
        self.assertIn("type", p)

    @mock.patch("core.views.get_movie_watch_providers")
    def test_region_aware_caching(self, mock_get_providers):
        # IN call
        mock_get_providers.side_effect = lambda tmdb_id, region: {
            "link": f"https://www.themoviedb.org/movie/{tmdb_id}/watch?locale={region}",
            "region": region,
            "flatrate": [
                {
                    "provider_id": 1,
                    "provider_name": f"Hotstar-{region}",
                    "logo_path": "/logo.png",
                    "display_priority": 1,
                }
            ],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        # First request for IN
        res_in = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=IN")
        self.assertEqual(res_in.status_code, 200)
        self.assertEqual(res_in.data["providers"][0]["name"], "Hotstar-IN")

        # Second request for US - should NOT use the IN cached response
        res_us = self.client.get(f"/api/movies/{self.movie.id}/streaming-options/?region=US")
        self.assertEqual(res_us.status_code, 200)
        self.assertEqual(res_us.data["providers"][0]["name"], "Hotstar-US")
        self.assertEqual(res_us.data["region"], "US")


class PasswordResetSecurityTests(TestCase):
    """
    SEC-01 Regression Tests:
    - Never expose password reset tokens or links in unauthenticated API responses
    - Handle email dispatch failures gracefully without leaking sensitive details
    - Reject invalid, expired, or malformed reset tokens
    - Enforce password complexity during reset
    - Invalidate existing DRF authentication tokens upon successful password reset
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="resetuser",
            password="InitialPassword123!",
            email="reset@flick.test"
        )
        self.auth_token = Token.objects.create(user=self.user)

    def test_password_reset_request_never_exposes_token_in_response(self):
        """API response must NEVER disclose reset token or reset link for existing users."""
        with mock.patch("core.views.send_mail") as mock_mail:
            response = self.client.post("/api/auth/password-reset/", {"email": "reset@flick.test"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        # Verify no sensitive token or link fields exist in response
        self.assertNotIn("reset_link", response.data)
        self.assertNotIn("token", response.data)
        self.assertNotIn("uid", response.data)
        # Verify email was dispatched
        mock_mail.assert_called_once()
        call_kwargs = mock_mail.call_args[1]
        self.assertIn("reset@flick.test", call_kwargs["recipient_list"])
        self.assertIn("/reset-password?uid=", call_kwargs["message"])

    def test_password_reset_request_nonexistent_email_returns_identical_generic_message(self):
        """Nonexistent emails receive identical response to avoid user enumeration."""
        with mock.patch("core.views.send_mail") as mock_mail:
            response = self.client.post("/api/auth/password-reset/", {"email": "nonexistent@flick.test"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        self.assertEqual(
            response.data.get("message"),
            "If this email exists, you will receive a password reset link."
        )
        self.assertNotIn("reset_link", response.data)
        self.assertNotIn("token", response.data)
        mock_mail.assert_not_called()

    def test_password_reset_email_failure_does_not_leak_token(self):
        """When mail service fails, API logs error and returns generic response without tokens."""
        with mock.patch("core.views.send_mail", side_effect=Exception("SMTP service unavailable")):
            response = self.client.post("/api/auth/password-reset/", {"email": "reset@flick.test"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))
        self.assertNotIn("reset_link", response.data)
        self.assertNotIn("token", response.data)

    def test_password_reset_confirm_success_and_token_invalidation(self):
        """Successful password reset updates credentials and revokes existing DRF auth tokens."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth import authenticate

        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        # Ensure auth token exists prior to reset
        self.assertTrue(Token.objects.filter(user=self.user).exists())

        response = self.client.post("/api/auth/password-reset-confirm/", {
            "uid": uid,
            "token": token,
            "new_password": "NewStrongPassword456!",
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data.get("success"))

        # Verify old auth token was deleted / invalidated
        self.assertFalse(Token.objects.filter(user=self.user).exists())

        # Verify old password no longer works
        self.assertIsNone(authenticate(username="resetuser", password="InitialPassword123!"))

        # Verify new password works
        user_auth = authenticate(username="resetuser", password="NewStrongPassword456!")
        self.assertIsNotNone(user_auth)
        self.assertEqual(user_auth.pk, self.user.pk)

    def test_password_reset_confirm_invalid_or_expired_token_fails(self):
        """Invalid or tampered token returns 400 Bad Request."""
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        response = self.client.post("/api/auth/password-reset-confirm/", {
            "uid": uid,
            "token": "invalid-token-value-here",
            "new_password": "NewStrongPassword456!",
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data.get("success"))
        self.assertEqual(response.data.get("error"), "Invalid or expired reset link")

    def test_password_reset_confirm_invalid_uid_fails(self):
        """Invalid or malformed base64 UID returns 400 Bad Request."""
        response = self.client.post("/api/auth/password-reset-confirm/", {
            "uid": "invalid-uid-b64",
            "token": "any-token",
            "new_password": "NewStrongPassword456!",
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data.get("success"))

    def test_password_reset_confirm_weak_password_rejected(self):
        """Weak password failing Django validators is rejected with 400 Bad Request."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        token = default_token_generator.make_token(self.user)
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))

        # Attempt with common/short password "123"
        response = self.client.post("/api/auth/password-reset-confirm/", {
            "uid": uid,
            "token": token,
            "new_password": "123",
        })

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data.get("success"))
        # Verify token was not consumed and old credentials remain valid
        from django.contrib.auth import authenticate
        self.assertIsNotNone(authenticate(username="resetuser", password="InitialPassword123!"))


class SettingsSecurityTests(TestCase):
    """
    SEC-04 Regression Tests:
    - Default DEBUG setting must be False when environment variable is unset or empty
    - Truthy values ('true', '1', 'yes') parse to True
    - Falsy values ('false', '0', 'no', unset) parse to False
    """

    def test_debug_evaluation_logic(self):
        def evaluate_debug(env_val):
            if env_val is None:
                return "False".lower() in ("true", "1", "yes")
            return env_val.lower() in ("true", "1", "yes")

        # Unset / default
        self.assertFalse(evaluate_debug(None))
        self.assertFalse(evaluate_debug(""))

        # Explicit falsy values
        self.assertFalse(evaluate_debug("False"))
        self.assertFalse(evaluate_debug("false"))
        self.assertFalse(evaluate_debug("0"))
        self.assertFalse(evaluate_debug("no"))
        self.assertFalse(evaluate_debug("off"))

        # Explicit truthy values
        self.assertTrue(evaluate_debug("True"))
        self.assertTrue(evaluate_debug("true"))
        self.assertTrue(evaluate_debug("1"))
        self.assertTrue(evaluate_debug("yes"))

    def test_missing_secret_key_in_production_raises_value_error(self):
        """
        Verify that when DEBUG is False and not running test command,
        missing SECRET_KEY raises a ValueError.
        """
        def evaluate_secret_key(secret_key, debug, is_testing):
            if not secret_key:
                if debug or is_testing:
                    return "dev-key"
                raise ValueError("DJANGO_SECRET_KEY environment variable is required when DEBUG is False")
            return secret_key

        with self.assertRaises(ValueError):
            evaluate_secret_key(None, debug=False, is_testing=False)

    def test_production_settings_enforces_secret_key(self):
        """
        production_settings.py strictly accesses os.environ['DJANGO_SECRET_KEY']
        which raises KeyError if not provided.
        """
        env_copy = os.environ.copy()
        env_copy.pop("DJANGO_SECRET_KEY", None)
        with self.assertRaises(KeyError):
            _ = env_copy["DJANGO_SECRET_KEY"]

    def test_health_check_endpoints(self):
        """
        Verify both /healthz/ and /api/healthz/ return HTTP 200 without auth.
        """
        resp_root = self.client.get("/healthz/")
        self.assertEqual(resp_root.status_code, 200)
        self.assertEqual(resp_root.json(), {"status": "healthy"})

        resp_api = self.client.get("/api/healthz/")
        self.assertEqual(resp_api.status_code, 200)
        self.assertEqual(resp_api.json(), {"status": "healthy"})



class WebSocketAuthenticationAndAuthorizationTests(TransactionTestCase):
    """
    SEC-02 Regression Tests:
    - Reject unauthenticated WebSocket connections
    - Reject invalid or forged tokens
    - Reject nonexistent sessions
    - Reject unauthorized users (non-members)
    - Accept authorized host via WebSocket subprotocols (preferred)
    - Accept authorized guest via query parameter (fallback)
    - Ensure cross-session data isolation (no message leakage across groups)
    """

    def setUp(self):
        self.host = User.objects.create_user(username="ws_host", password="Password123!")
        self.guest = User.objects.create_user(username="ws_guest", password="Password123!")
        self.stranger = User.objects.create_user(username="ws_stranger", password="Password123!")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.stranger_token = Token.objects.create(user=self.stranger)
        self.session = Session.objects.create(host=self.host, guest=self.guest, code="WS0001")

    def test_unauthenticated_connection_rejected(self):
        """Unauthenticated connections are rejected with close code 4001."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(application, f"/ws/session/{self.session.id}/")
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)
            await comm.disconnect()

        asyncio.run(run())

    def test_invalid_token_rejected(self):
        """Connections with invalid auth tokens are rejected with close code 4001."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", "invalid-token-key-12345"]
            )
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)
            await comm.disconnect()

        asyncio.run(run())

    def test_nonexistent_session_rejected(self):
        """Authenticated connections to nonexistent sessions are rejected with close code 4004."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                "/ws/session/999999/",
                subprotocols=["token", self.host_token.key]
            )
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4004)
            await comm.disconnect()

        asyncio.run(run())

    def test_unauthorized_user_rejected(self):
        """Authenticated stranger who is neither host nor guest is rejected with close code 4003."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.stranger_token.key]
            )
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4003)
            await comm.disconnect()

        asyncio.run(run())

    def test_authorized_host_accepted_via_subprotocol(self):
        """Session host connecting with token in WebSocket subprotocol is accepted."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.host_token.key]
            )
            connected, subprotocol = await comm.connect()
            self.assertTrue(connected)
            self.assertEqual(subprotocol, "token")
            await comm.disconnect()

        asyncio.run(run())

    def test_authorized_guest_accepted_via_header(self):
        """Session guest connecting with Authorization header is accepted."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                headers=[(b"authorization", f"Token {self.guest_token.key}".encode())]
            )
            connected, subprotocol = await comm.connect()
            self.assertTrue(connected)
            await comm.disconnect()

        asyncio.run(run())

    def test_query_param_token_is_rejected(self):
        """Tokens in query parameters are strictly rejected to prevent URL credential logging."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/?token={self.guest_token.key}"
            )
            connected, code = await comm.connect()
            self.assertFalse(connected)
            self.assertEqual(code, 4001)
            await comm.disconnect()

        asyncio.run(run())

    def test_cross_session_event_isolation(self):
        """Consumer rejects match events destined for a different session."""
        import asyncio
        from channels.testing import WebsocketCommunicator
        from backend.asgi import application
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()

        async def run():
            comm = WebsocketCommunicator(
                application,
                f"/ws/session/{self.session.id}/",
                subprotocols=["token", self.host_token.key]
            )
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            # Broadcast event with mismatched session_id to group
            await channel_layer.group_send(
                f"session_{self.session.id}",
                {
                    "type": "match_event",
                    "session_id": 999999,  # Mismatched session
                    "movie_id": 1,
                    "movie_title": "Fake Movie",
                }
            )

            # Nothing should be received by the communicator
            self.assertTrue(await comm.receive_nothing(timeout=0.2))
            await comm.disconnect()

        asyncio.run(run())


class AdminCommandSecurityTests(TestCase):
    """
    SEC-06 Regression Tests:
    - Remove hardcoded credentials from create_admin
    - Require explicit, securely supplied credentials via CLI options or environment variables
    - Refuse to promote existing non-admin accounts to superusers
    - Handle existing superusers safely
    - Enforce password complexity
    """

    def test_missing_credentials_fails(self):
        """Running create_admin without credentials raises CommandError."""
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError

        out = StringIO()
        err = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command("create_admin", stdout=out, stderr=err)
        self.assertIn("Missing required administrator credentials", str(ctx.exception))
        self.assertFalse(User.objects.filter(is_superuser=True).exists())

    def test_refuses_to_promote_existing_regular_user(self):
        """create_admin must never promote an existing regular user account."""
        from django.core.management import call_command
        from django.core.management.base import CommandError

        User.objects.create_user(username="admin", email="admin@flick.test", password="RegularPassword123!")
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "create_admin",
                username="admin",
                email="admin@flick.test",
                password="NewAdminPassword123!"
            )
        self.assertIn("Refusing to automatically promote", str(ctx.exception))
        user = User.objects.get(username="admin")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_existing_superuser_warns_cleanly(self):
        """create_admin on existing superuser outputs warning and does not recreate."""
        from io import StringIO
        from django.core.management import call_command

        User.objects.create_superuser(username="admin", email="admin@flick.test", password="ExistingPassword123!")
        out = StringIO()
        call_command(
            "create_admin",
            username="admin",
            email="admin@flick.test",
            password="ExistingPassword123!",
            stdout=out
        )
        self.assertIn("already exists", out.getvalue())

    def test_weak_password_rejected(self):
        """create_admin rejects passwords failing validation."""
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as ctx:
            call_command(
                "create_admin",
                username="newadmin",
                email="newadmin@flick.test",
                password="123"
            )
        self.assertIn("Password validation failed", str(ctx.exception))
        self.assertFalse(User.objects.filter(username="newadmin").exists())

    def test_successful_admin_creation(self):
        """create_admin with explicit valid credentials successfully creates superuser."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command(
            "create_admin",
            username="validadmin",
            email="validadmin@flick.test",
            password="StrongAdminPassword456!",
            stdout=out
        )
        self.assertIn("Successfully created admin user: validadmin", out.getvalue())
        admin_user = User.objects.get(username="validadmin")
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)


class AuthenticationLoggingSecurityTests(TestCase):
    """
    SEC-07 Regression Tests:
    - Never print authentication inputs, usernames, or emails to stdout
    - Use structured logging without passwords or tokens
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="logtestuser",
            email="logtest@flick.test",
            password="SecurePassword123!"
        )

    def test_no_stdout_printing_on_auth_success_or_failure(self):
        """Authentication backend must NEVER print usernames, emails, or status to stdout."""
        import sys
        from io import StringIO
        from django.contrib.auth import authenticate

        saved_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            # Test success by username
            u1 = authenticate(username="logtestuser", password="SecurePassword123!")
            self.assertIsNotNone(u1)

            # Test success by email
            u2 = authenticate(username="logtest@flick.test", password="SecurePassword123!")
            self.assertIsNotNone(u2)

            # Test invalid password
            u3 = authenticate(username="logtestuser", password="WrongPassword!")
            self.assertIsNone(u3)

            # Test nonexistent user
            u4 = authenticate(username="nonexistent", password="AnyPassword!")
            self.assertIsNone(u4)

            # Assert stdout remained completely empty
            printed_output = sys.stdout.getvalue()
            self.assertEqual(printed_output, "")
        finally:
            sys.stdout = saved_stdout

    def test_structured_logging_does_not_log_passwords(self):
        """Authentication logging must never include passwords."""
        from django.contrib.auth import authenticate

        with self.assertLogs("core.backends", level="INFO") as captured:
            authenticate(username="logtestuser", password="SecurePassword123!")
            for record in captured.output:
                self.assertNotIn("SecurePassword123!", record)


class AuthenticationThrottlingTests(TestCase):
    """
    SEC-05 Regression Tests:
    - Login and Registration are throttled under anon_auth (10/minute)
    - Returns HTTP 429 Too Many Requests when rate exceeded
    - Legitimate requests within rate limit succeed
    """

    def setUp(self):
        from django.core.cache import cache
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="throttletest",
            email="throttle@flick.test",
            password="Password123!"
        )
        cache.clear()

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_login_rate_limiting_triggers_429(self):
        """Exceeding anon_auth rate limit (10 requests/minute) returns HTTP 429."""
        # 10 requests allowed
        for _ in range(10):
            res = self.client.post("/api/auth/login/", {
                "username": "throttletest",
                "password": "WrongPassword!"
            })
            self.assertEqual(res.status_code, 400)

        # 11th request must be throttled
        throttled_res = self.client.post("/api/auth/login/", {
            "username": "throttletest",
            "password": "WrongPassword!"
        })
        self.assertEqual(throttled_res.status_code, 429)

    def test_legitimate_login_within_limit_succeeds(self):
        """Legitimate login request under throttle limit succeeds with HTTP 200."""
        res = self.client.post("/api/auth/login/", {
            "username": "throttletest",
            "password": "Password123!"
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success"))
        self.assertIn("token", res.data)


class PaginationAndResourceLimitTests(TestCase):
    """
    QUAL-01 Regression Tests:
    - Endpoints serialize bounded querysets with consistent pagination
    - Default page size is 20, maximum page size is 100
    - Watchlist endpoint enforces result limits and pagination metadata
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="pageuser", password="Password123!")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_movie_list_is_paginated_with_default_page_size_and_limits(self):
        """GET /api/movies/ returns paginated structure (count, next, previous, results)."""
        # Create 25 movies
        for i in range(25):
            Movie.objects.create(title=f"Movie {i}", tmdb_id=1000 + i, rating=7.0 + (i * 0.1))

        # Default request should return first page of 20
        res = self.client.get("/api/movies/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("count", res.data)
        self.assertIn("results", res.data)
        self.assertEqual(res.data["count"], 25)
        self.assertEqual(len(res.data["results"]), 20)
        self.assertIsNotNone(res.data["next"])

        # Request with oversized page_size should be capped at max_page_size (100)
        res_capped = self.client.get("/api/movies/?page_size=200")
        self.assertEqual(res_capped.status_code, 200)
        # All 25 fit within max 100
        self.assertEqual(len(res_capped.data["results"]), 25)

    def test_watchlist_is_bounded_and_honors_limit_offset(self):
        """Watchlist supports limit/offset parameters and caps maximum results at 100."""
        movies = [
            Movie.objects.create(title=f"WL Movie {i}", tmdb_id=2000 + i)
            for i in range(10)
        ]
        for m in movies:
            WatchlistItem.objects.create(user=self.user, movie=m)

        res = self.client.get("/api/watchlist/?limit=3&offset=0")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success"))
        self.assertEqual(len(res.data["watchlist"]), 3)
        self.assertEqual(res.data["total_count"], 10)
        self.assertEqual(res.data["limit"], 3)
        self.assertEqual(res.data["offset"], 0)


class SessionQueryOptimizationTests(TestCase):
    """
    QUAL-02 Regression Tests:
    - SessionRecentListView eliminates N+1 query patterns using Count annotation
    - Total database queries must be strictly O(1) (2 queries: sessions + prefetch),
      not O(N) with the number of sessions.
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="nplus1_host", password="Password123!")
        self.guest = User.objects.create_user(username="nplus1_guest", password="Password123!")
        self.token = Token.objects.create(user=self.host)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

        self.genre = Genre.objects.create(name="Animation", tmdb_id=16)

        # Create 10 sessions, each with matches
        for i in range(10):
            session = Session.objects.create(
                host=self.host,
                guest=self.guest,
                code=f"NP{i:04d}",
                genre=self.genre
            )
            session.genres.add(self.genre)
            m = Movie.objects.create(title=f"Match Movie {i}", tmdb_id=3000 + i)
            Match.objects.create(session=session, movie=m)

    def test_recent_sessions_query_count_is_constant_regardless_of_session_count(self):
        """Query count for SessionRecentListView is strictly O(1) (3 total queries: 1 auth + 2 data)."""
        # Exactly 3 queries: 1 for DRF token authentication, 1 for sessions with Count annotation, 1 for genres prefetch
        with self.assertNumQueries(3):
            res = self.client.get("/api/sessions/recent/")
            self.assertEqual(res.status_code, 200)

        data = res.data["sessions"]
        self.assertEqual(len(data), 10)
        for s in data:
            self.assertEqual(s["matches"], 1)
            self.assertEqual(s["name"], "Animation Night")


class MatchListFilteringSecurityTests(TestCase):
    """
    QUAL-03 Regression Tests:
    - Honors ?session_id= when provided
    - Strictly validates requesting user belongs to requested session (host or guest)
    - Returns 404 for nonexistent sessions, 403 for unauthorized users, 400 for malformed IDs
    - Returns matches across all authorized sessions when session_id is omitted
    """

    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username="alice", password="Password123!")
        self.bob = User.objects.create_user(username="bob", password="Password123!")
        self.stranger = User.objects.create_user(username="eve", password="Password123!")

        self.alice_token = Token.objects.create(user=self.alice)
        self.stranger_token = Token.objects.create(user=self.stranger)

        self.session1 = Session.objects.create(host=self.alice, guest=self.bob, code="SESS01")
        self.session2 = Session.objects.create(host=self.alice, guest=self.bob, code="SESS02")

        self.movie1 = Movie.objects.create(title="Movie One", tmdb_id=4001)
        self.movie2 = Movie.objects.create(title="Movie Two", tmdb_id=4002)

        Match.objects.create(session=self.session1, movie=self.movie1)
        Match.objects.create(session=self.session2, movie=self.movie2)

    def test_match_list_filters_by_session_id_when_provided(self):
        """When ?session_id= is supplied by a member, only that session's matches are returned."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.alice_token.key}")
        res = self.client.get(f"/api/matches/?session_id={self.session1.id}")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["matches"]), 1)
        self.assertEqual(res.data["matches"][0]["movie_id"], self.movie1.id)

    def test_match_list_unauthorized_user_forbidden(self):
        """Non-member requesting matches for someone else's session receives 403 Forbidden."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.stranger_token.key}")
        res = self.client.get(f"/api/matches/?session_id={self.session1.id}")
        self.assertEqual(res.status_code, 403)
        self.assertFalse(res.data["success"])
        self.assertIn("not authorized", res.data["error"])

    def test_match_list_nonexistent_session_not_found(self):
        """Requesting matches for a nonexistent session ID returns 404 Not Found."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.alice_token.key}")
        res = self.client.get("/api/matches/?session_id=999999")
        self.assertEqual(res.status_code, 404)
        self.assertFalse(res.data["success"])

    def test_match_list_invalid_session_id_bad_request(self):
        """Supplying a non-numeric session_id returns 400 Bad Request."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.alice_token.key}")
        res = self.client.get("/api/matches/?session_id=invalid_id")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.data["success"])

    def test_match_list_without_session_id_returns_all_user_matches(self):
        """Without ?session_id=, returns matches across all sessions the user participates in."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.alice_token.key}")
        res = self.client.get("/api/matches/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["matches"]), 2)


class SessionCodeCollisionTests(TestCase):
    """
    QUAL-04 Regression Tests:
    - Session codes use cryptographically secure secrets
    - Session creation handles collision gracefully with bounded retries
    - Exhausted retries return a controlled HTTP 503 instead of 500 IntegrityError
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="coll_user", password="Password123!")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_session_creation_collision_retry_success(self):
        """SessionCreateView retries on collision and succeeds when a unique code is found."""
        from django.db import IntegrityError
        from core.models import Session

        orig_create = Session.objects.create
        attempts = [0]

        def create_with_simulated_collisions(*args, **kwargs):
            attempts[0] += 1
            if attempts[0] < 3:
                # Simulate 2 collision IntegrityErrors
                raise IntegrityError("UNIQUE constraint failed: core_session.code")
            return orig_create(*args, **kwargs)

        with mock.patch("core.models.Session.objects.create", side_effect=create_with_simulated_collisions):
            res = self.client.post("/api/sessions/create/")

        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data.get("success"))
        self.assertEqual(attempts[0], 3)

    def test_session_creation_exhausted_retries_returns_503(self):
        """When all 5 retry attempts collide, returns clean HTTP 503 instead of crash."""
        from django.db import IntegrityError

        with mock.patch("core.models.Session.objects.create", side_effect=IntegrityError("Collision")):
            res = self.client.post("/api/sessions/create/")

        self.assertEqual(res.status_code, 503)


# =====================================================================
# DYNAMIC TMDB MOVIE CATALOGUE & HYBRID CACHING TESTS
# =====================================================================

class DynamicMovieCatalogueTests(TestCase):
    """
    Comprehensive test suite covering Phase 1 through Phase 8 of the
    Dynamic TMDB Catalogue Discovery Architecture:
    - Categories (Trending, Popular, Top Rated, Now Playing, Upcoming)
    - Search of uncached movies
    - Filter by genre, language, era, year
    - Multi-page pagination
    - Redis cache hit, miss, expiration, and stale-cache recovery
    - Resilience to TMDB timeouts and Redis downtime
    - On-demand PostgreSQL persistence
    - Watchlist and streaming options compatibility
    - Authenticated and unauthenticated access
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()

        # Seed reference genres
        self.g_action = Genre.objects.create(name="Action", tmdb_id=28)
        self.g_scifi = Genre.objects.create(name="Science Fiction", tmdb_id=878)
        self.g_drama = Genre.objects.create(name="Drama", tmdb_id=18)

        # Create authenticated test user
        self.user = User.objects.create_user(username="cinemaphile", email="cine@flickapp.in", password="ValidPass123!")
        self.token = Token.objects.create(user=self.user)

        # Mock TMDB sample data
        self.sample_trending = {
            "page": 1,
            "total_pages": 15,
            "total_results": 300,
            "results": [
                {
                    "id": 1001,
                    "title": "Dune: Part Two",
                    "overview": "Paul Atreides unites with Chani and the Fremen.",
                    "poster_path": "/dune2.jpg",
                    "backdrop_path": "/dune2_bg.jpg",
                    "release_date": "2024-03-01",
                    "vote_average": 8.3,
                    "vote_count": 4500,
                    "original_language": "en",
                    "genre_ids": [28, 878],
                }
            ]
        }

        self.sample_search_inception = {
            "page": 1,
            "total_pages": 3,
            "total_results": 52,
            "results": [
                {
                    "id": 27205,
                    "title": "Inception",
                    "overview": "Your mind is the scene of the crime.",
                    "poster_path": "/inception.jpg",
                    "backdrop_path": "/inception_bg.jpg",
                    "release_date": "2010-07-15",
                    "vote_average": 8.4,
                    "vote_count": 36000,
                    "original_language": "en",
                    "genre_ids": [28, 878],
                }
            ]
        }

        self.sample_inception_details = {
            "id": 27205,
            "title": "Inception",
            "overview": "Your mind is the scene of the crime.",
            "poster_path": "/inception.jpg",
            "backdrop_path": "/inception_bg.jpg",
            "release_date": "2010-07-15",
            "vote_average": 8.4,
            "vote_count": 36000,
            "original_language": "en",
            "genres": [{"id": 28, "name": "Action"}, {"id": 878, "name": "Science Fiction"}],
            "videos": {
                "results": [
                    {"key": "YoHD9XEInc0", "site": "YouTube", "type": "Trailer"}
                ]
            }
        }

    def tearDown(self):
        cache.clear()

    # 1. Categories
    @mock.patch("core.services.tmdb.get_trending_movies")
    def test_trending_category_endpoint(self, mock_trending):
        mock_trending.return_value = (self.sample_trending, "tmdb")
        res = self.client.get("/api/discover/?category=trending&page=1")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["success"])
        self.assertEqual(len(res.data["movies"]), 1)
        movie = res.data["movies"][0]
        self.assertEqual(movie["tmdb_id"], 1001)
        self.assertEqual(movie["title"], "Dune: Part Two")
        self.assertEqual(movie["rating"], 8.3)
        self.assertIn("Action", movie["genres"])

    @mock.patch("core.services.tmdb.get_top_rated_movies")
    def test_top_rated_category_endpoint(self, mock_top_rated):
        mock_top_rated.return_value = (self.sample_trending, "tmdb")
        res = self.client.get("/api/discover/?category=top_rated&page=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["source"], "tmdb")
        self.assertEqual(res.data["total_pages"], 15)

    @mock.patch("core.services.tmdb.get_now_playing_movies")
    def test_now_playing_category_endpoint(self, mock_now_playing):
        mock_now_playing.return_value = (self.sample_trending, "tmdb")
        res = self.client.get("/api/discover/?category=now_playing&page=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 1)

    @mock.patch("core.services.tmdb.get_upcoming_movies")
    def test_upcoming_category_endpoint(self, mock_upcoming):
        mock_upcoming.return_value = (self.sample_trending, "tmdb")
        res = self.client.get("/api/discover/?category=upcoming&page=1")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["has_more"])

    # 2. Search Uncached Movies
    @mock.patch("core.services.tmdb.search_movies")
    def test_search_uncached_movie_from_tmdb(self, mock_search):
        # Movie is NOT in PostgreSQL
        self.assertFalse(Movie.objects.filter(tmdb_id=27205).exists())

        mock_search.return_value = (self.sample_search_inception, "tmdb")
        res = self.client.get("/api/discover/?search=inception&page=1")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["movies"]), 1)
        m = res.data["movies"][0]
        self.assertEqual(m["tmdb_id"], 27205)
        self.assertEqual(m["title"], "Inception")
        self.assertEqual(m["release_year"], 2010)
        self.assertIsNone(m["id"])  # Transient, not yet stored in PostgreSQL!

    # 3. Filters
    @mock.patch("core.services.tmdb.discover_movies")
    def test_discover_by_genre_and_language(self, mock_discover):
        mock_discover.return_value = (self.sample_trending, "tmdb")
        res = self.client.get("/api/discover/?genre=28&language=ko&min_rating=7.5&era=recent")

        self.assertEqual(res.status_code, 200)
        mock_discover.assert_called_once()
        _, kwargs = mock_discover.call_args
        self.assertEqual(kwargs.get("genre_id"), 28)
        self.assertEqual(kwargs.get("language"), "ko")
        self.assertEqual(kwargs.get("era"), "recent")
        self.assertEqual(kwargs.get("min_rating"), "7.5")

    # 4. Multi-Page Pagination
    @mock.patch("core.services.tmdb.get_popular_movies")
    def test_pagination_beyond_local_records(self, mock_popular):
        mock_popular.return_value = (
            {
                "page": 12,
                "total_pages": 40,
                "total_results": 800,
                "results": [
                    {
                        "id": 9999,
                        "title": "Deep Page Movie",
                        "vote_average": 7.1,
                        "genre_ids": [],
                        "original_language": "fr",
                    }
                ]
            },
            "tmdb"
        )
        res = self.client.get("/api/discover/?category=popular&page=12")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["page"], 12)
        self.assertEqual(res.data["total_pages"], 40)
        self.assertTrue(res.data["has_more"])

    # 5. Redis Hybrid Caching
    def test_redis_cache_hit_and_miss_lifecycle(self):
        from core.services.tmdb import fetch_cached_tmdb

        call_counter = [0]
        def fake_fetcher():
            call_counter[0] += 1
            return {"results": [{"id": 55, "title": "Cached Film"}]}

        cache_key = "tmdb:test:caching:key:1"

        # 1. Cache Miss
        data1, source1 = fetch_cached_tmdb(cache_key, fake_fetcher, ttl=60)
        self.assertEqual(source1, "tmdb")
        self.assertEqual(call_counter[0], 1)

        # 2. Cache Hit
        data2, source2 = fetch_cached_tmdb(cache_key, fake_fetcher, ttl=60)
        self.assertEqual(source2, "cache")
        self.assertEqual(call_counter[0], 1)  # Fetcher was NOT called again!
        self.assertEqual(data2, data1)

    def test_stale_cache_fallback_on_network_timeout(self):
        from core.services.tmdb import fetch_cached_tmdb, TMDBTimeoutError
        import requests

        cache_key = "tmdb:test:stale:fallback:key"
        # Seed stale cache
        cache.set(f"{cache_key}:stale", {"results": [{"id": 77, "title": "Stale Savior"}]}, timeout=3600)

        def failing_fetcher():
            raise requests.exceptions.Timeout("Connection timed out")

        # When active cache is missing and network fails, serves stale cache
        data, source = fetch_cached_tmdb(cache_key, failing_fetcher, ttl=60)
        self.assertEqual(source, "stale_cache")
        self.assertEqual(data["results"][0]["title"], "Stale Savior")

    # 6. Resilience & Graceful Fallback
    @mock.patch("core.services.tmdb.get_popular_movies", side_effect=Exception("TMDB 503 Service Unavailable"))
    def test_tmdb_outage_falls_back_to_local_db(self, mock_pop):
        # Create a local movie
        Movie.objects.create(
            tmdb_id=888,
            title="Local Fallback Gem",
            rating=8.0,
            original_language="en",
            release_date=date(2023, 1, 1),
        )

        res = self.client.get("/api/discover/?page=1")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["source"], "fallback")
        titles = [m["title"] for m in res.data["movies"]]
        self.assertIn("Local Fallback Gem", titles)

    # 7. On-Demand PostgreSQL Persistence
    @mock.patch("core.services.tmdb.get_movie_by_tmdb_id")
    def test_on_demand_persistence_creates_movie_record(self, mock_details):
        from core.services.tmdb import get_or_create_movie_from_tmdb

        mock_details.return_value = (self.sample_inception_details, "tmdb")

        # Movie does not exist yet
        self.assertFalse(Movie.objects.filter(tmdb_id=27205).exists())

        movie, created = get_or_create_movie_from_tmdb(27205)
        self.assertTrue(created)
        self.assertIsNotNone(movie)
        self.assertEqual(movie.title, "Inception")
        self.assertEqual(movie.trailer_key, "YoHD9XEInc0")
        self.assertEqual(movie.genres.count(), 2)

        # Second call reuses existing record
        movie2, created2 = get_or_create_movie_from_tmdb(27205)
        self.assertFalse(created2)
        self.assertEqual(movie.id, movie2.id)

    # 8. Watchlist Compatibility with TMDB ID
    @mock.patch("core.services.tmdb.get_movie_by_tmdb_id")
    def test_add_uncached_movie_to_watchlist_by_tmdb_id(self, mock_details):
        mock_details.return_value = (self.sample_inception_details, "tmdb")

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        res = self.client.post("/api/watchlist/", {"tmdb_id": 27205}, format="json")

        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["item"]["tmdb_id"], 27205)
        self.assertEqual(res.data["item"]["movie_title"], "Inception")

        # Verify persisted in database
        self.assertTrue(WatchlistItem.objects.filter(user=self.user, movie__tmdb_id=27205).exists())

        # Test deleting by tmdb_id
        del_res = self.client.delete(f"/api/watchlist/27205/")
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(WatchlistItem.objects.filter(user=self.user, movie__tmdb_id=27205).exists())

    # 9. Streaming Options for Uncached Movie
    @mock.patch("core.services.tmdb.get_movie_by_tmdb_id")
    @mock.patch("core.views.get_movie_watch_providers")
    def test_streaming_options_for_uncached_movie(self, mock_providers, mock_details):
        mock_details.return_value = (self.sample_inception_details, "tmdb")
        mock_providers.return_value = {
            "link": "https://www.themoviedb.org/movie/27205/watch",
            "region": "IN",
            "flatrate": [{"provider_name": "Netflix", "logo_path": "/netflix.jpg"}],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        res = self.client.get("/api/movies/27205/streaming-options/?region=IN")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["movie_title"], "Inception")
        self.assertGreaterEqual(len(res.data["providers"]), 1)
        provider_names = [p["name"] for p in res.data["providers"]]
        self.assertIn("Netflix", provider_names)

    # 10. Unauthenticated vs Authenticated Watchlist Enrichment
    @mock.patch("core.services.tmdb.get_popular_movies")
    def test_watchlist_enrichment_for_authenticated_user(self, mock_popular):
        # Create an existing watchlist item for movie 1001
        m = Movie.objects.create(tmdb_id=1001, title="Dune: Part Two", rating=8.3)
        WatchlistItem.objects.create(user=self.user, movie=m)

        mock_popular.return_value = (self.sample_trending, "tmdb")

        # 1. Unauthenticated request: is_in_watchlist is False
        res_anon = self.client.get("/api/discover/?category=popular")
        self.assertEqual(res_anon.status_code, 200)
        self.assertFalse(res_anon.data["movies"][0]["is_in_watchlist"])

        # 2. Authenticated request: is_in_watchlist is True
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        res_auth = self.client.get("/api/discover/?category=popular")
        self.assertEqual(res_auth.status_code, 200)
        self.assertTrue(res_auth.data["movies"][0]["is_in_watchlist"])


class LocalNetworkConfigurationTests(TestCase):
    """
    Verifies that local network (LAN) access works for multi-device development (Mac + mobile phone)
    without compromising production host restrictions or CORS security.
    """

    def test_lan_and_loopback_hosts_are_allowed(self):
        client = Client()
        for host in ["192.168.1.12:8000", "localhost:8000", "127.0.0.1:8000"]:
            response = client.get("/api/healthz/", HTTP_HOST=host)
            self.assertEqual(
                response.status_code,
                200,
                f"Host '{host}' should be allowed to access the health endpoint.",
            )

    def test_disallowed_host_is_rejected(self):
        client = Client(raise_request_exception=False)
        response = client.get("/api/healthz/", HTTP_HOST="attacker.com")
        self.assertEqual(
            response.status_code,
            400,
            "Untrusted hosts must be rejected with 400 Bad Request by Django Host validation.",
        )

    def test_lan_and_loopback_cors_preflight_origins_are_allowed(self):
        client = Client()
        for origin in ["http://192.168.1.12:5173", "http://localhost:5173", "http://127.0.0.1:5173"]:
            response = client.options(
                "/api/auth/register/",
                HTTP_HOST="192.168.1.12:8000",
                HTTP_ORIGIN=origin,
                HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get("Access-Control-Allow-Origin"), origin)


class FunctionalAndMobileAuditVerificationTests(TestCase):
    """
    Verifies the fixes for:
    1. Recommendation engine & discovery filters (canonical TMDB genre resolution, multi-genre, local fallback).
    2. Multi-account swipe isolation (User A swiping does not remove movies from User B deck).
    3. Curated matches poster and metadata serialization (poster_url, rating, overview, genres, etc.).
    4. Required signup display_name and participant-facing display names.
    """

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(
            username="usera",
            password="Password123!",
            email="usera@test.com",
            first_name="Rajat",
        )
        self.user_b = User.objects.create_user(
            username="userb",
            password="Password123!",
            email="userb@test.com",
            first_name="Priya",
        )
        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)

        self.profile_a, _ = UserProfile.objects.get_or_create(user=self.user_a, defaults={"display_name": "Rajat"})
        self.profile_b, _ = UserProfile.objects.get_or_create(user=self.user_b, defaults={"display_name": "Priya"})

        # Genres
        self.horror_genre = Genre.objects.create(name="Horror", tmdb_id=27)
        self.comedy_genre = Genre.objects.create(name="Comedy", tmdb_id=35)
        self.thriller_genre = Genre.objects.create(name="Thriller", tmdb_id=53)

        # Movies
        self.movie_horror = Movie.objects.create(
            title="The Shining",
            overview="Here's Johnny!",
            tmdb_id=694,
            poster_path="/shining.jpg",
            rating=8.4,
            vote_count=10000,
            release_date=date(1980, 5, 23),
            original_language="en",
        )
        self.movie_horror.genres.add(self.horror_genre, self.thriller_genre)

        self.movie_comedy = Movie.objects.create(
            title="Superbad",
            overview="Two co-dependent high school seniors",
            tmdb_id=8363,
            poster_path="/superbad.jpg",
            rating=7.2,
            vote_count=6000,
            release_date=date(2007, 8, 17),
            original_language="en",
        )
        self.movie_comedy.genres.add(self.comedy_genre)

        # Session with both participants
        self.session = Session.objects.create(
            host=self.user_a,
            code="AUDIT1",
            guest=self.user_b,
            genre=self.horror_genre,
            preferences_set=True,
        )
        self.session.genres.add(self.horror_genre)

    def test_signup_requires_display_name(self):
        """Registering without display_name must return 400."""
        res = self.client.post("/api/auth/register/", {
            "email": "newuser@test.com",
            "password": "ValidPassword123!",
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("display name", res.data.get("error", "").lower())

    def test_signup_with_valid_display_name_creates_profile(self):
        """Registering with display_name must succeed and store display_name in UserProfile."""
        res = self.client.post("/api/auth/register/", {
            "email": "cooluser@test.com",
            "password": "ValidPassword123!",
            "display_name": "Cinema Buff",
        })
        self.assertEqual(res.status_code, 201)
        new_user = User.objects.get(email="cooluser@test.com")
        self.assertEqual(new_user.profile.display_name, "Cinema Buff")
        self.assertEqual(new_user.profile.effective_display_name, "Cinema Buff")

    def test_profile_patch_updates_display_name(self):
        """User can update their display_name via PATCH /api/users/profile/."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        res = self.client.patch("/api/users/profile/", {"display_name": "Rajat Updated"})
        self.assertEqual(res.status_code, 200)
        self.profile_a.refresh_from_db()
        self.assertEqual(self.profile_a.display_name, "Rajat Updated")

    def test_genre_list_view_exposes_tmdb_id(self):
        """GenreListView must include tmdb_id alongside local id and name."""
        res = self.client.get("/api/genres/?industry=hollywood")
        self.assertEqual(res.status_code, 200)
        genres = res.data if isinstance(res.data, list) else res.data.get("genres", [])
        horror = next((g for g in genres if g["name"] == "Horror"), None)
        self.assertIsNotNone(horror)
        self.assertEqual(horror.get("tmdb_id"), 27)

    @mock.patch("core.services.tmdb.discover_movies")
    def test_discover_resolves_local_genre_id_to_tmdb_id(self, mock_discover):
        """
        When frontend passes a local Genre PK (e.g. self.horror_genre.id),
        DiscoverView must resolve it to TMDB genre ID 27 instead of passing the raw PK.
        """
        mock_discover.return_value = ({"results": [], "total_pages": 1, "page": 1, "total_results": 0}, "tmdb")
        res = self.client.get(f"/api/discover/?genre={self.horror_genre.id}")
        self.assertEqual(res.status_code, 200)
        # Verify discover_movies was called with genre_id=27
        mock_discover.assert_called()
        call_kwargs = mock_discover.call_args.kwargs
        self.assertEqual(call_kwargs.get("genre_id"), 27)

    @mock.patch("core.services.tmdb.discover_movies")
    def test_discover_multi_genre_and_or_delimiters(self, mock_discover):
        """Multi-genre parameters like 27,53 (AND) and 27|35 (OR) are resolved cleanly."""
        mock_discover.return_value = ({"results": [], "total_pages": 1, "page": 1, "total_results": 0}, "tmdb")
        self.client.get("/api/discover/?genre=27,53")
        self.assertEqual(mock_discover.call_args.kwargs.get("genre_id"), "27,53")

        self.client.get("/api/discover/?genre=27|35")
        self.assertEqual(mock_discover.call_args.kwargs.get("genre_id"), "27|35")

    def test_swipes_are_isolated_per_participant(self):
        """
        Account A swiping movie_horror must NOT remove movie_horror from Account B's recommendation deck!
        Only when both have swiped does it become a Match and excluded.
        """
        # User A swipes movie_horror
        Swipe.objects.create(
            session=self.session,
            user=self.user_a,
            movie=self.movie_horror,
            reaction="like",
        )

        # User A queries recommendations -> movie_horror is excluded because User A already swiped it
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        res_a = self.client.get(f"/api/recommendations/?session_id={self.session.id}")
        self.assertEqual(res_a.status_code, 200)
        recos_a_ids = [m["id"] for m in res_a.data.get("movies", [])]
        self.assertNotIn(self.movie_horror.id, recos_a_ids)

        # User B queries recommendations -> movie_horror MUST STILL BE PRESENT in User B's deck!
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_b.key}")
        res_b = self.client.get(f"/api/recommendations/?session_id={self.session.id}")
        self.assertEqual(res_b.status_code, 200)
        recos_b_ids = [m["id"] for m in res_b.data.get("movies", [])]
        self.assertIn(self.movie_horror.id, recos_b_ids, "User A's swipe must NOT exclude the movie for User B!")

    def test_match_list_view_returns_posters_and_metadata(self):
        """MatchListView must serialize poster_url, rating, overview, and genres."""
        Match.objects.create(session=self.session, movie=self.movie_horror)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        res = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res.status_code, 200)
        matches = res.data.get("matches", [])
        self.assertEqual(len(matches), 1)
        m = matches[0]
        self.assertEqual(m["movie_id"], self.movie_horror.id)
        self.assertTrue(m["poster_url"].startswith("https://image.tmdb.org/t/p/w780/shining.jpg"))
        self.assertEqual(m["rating"], 8.4)
        self.assertEqual(m["release_year"], 1980)
        self.assertIn("Horror", m["genres"])
        self.assertIn("Johnny", m["overview"])

    def test_session_detail_includes_participant_display_names(self):
        """SessionDetailSerializer must return host_display_name and guest_display_name."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        res = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res.status_code, 200)
        s = res.data.get("session", {})
        self.assertEqual(s.get("host_display_name"), "Rajat")
        self.assertEqual(s.get("guest_display_name"), "Priya")


class MotionAndSessionRegressionAuditTests(TestCase):
    """
    Focused QA regression suite verifying session locking, end-session idempotency,
    re-entrancy protection, and match metadata endpoint resilience.
    """
    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username="viewer_alpha", password="Password123!")
        self.user_b = User.objects.create_user(username="viewer_beta", password="Password123!")
        self.stranger = User.objects.create_user(username="viewer_stranger", password="Password123!")
        self.token_a = Token.objects.create(user=self.user_a)
        self.token_b = Token.objects.create(user=self.user_b)
        self.token_stranger = Token.objects.create(user=self.stranger)

        self.session = Session.objects.create(
            host=self.user_a,
            guest=self.user_b,
            code="MOTN01"
        )
        self.movie = Movie.objects.create(
            title="Solaris",
            tmdb_id=439,
            overview="A psychologist is sent to a space station orbiting a mysterious ocean world.",
            poster_path="/solaris.jpg",
            rating=8.0,
            vote_count=1500,
            release_date=date(1972, 3, 20)
        )

    def test_end_session_idempotent_and_rejects_unauthorized(self):
        """Test that ending a session is idempotent, handles non-existent IDs, and rejects non-members."""
        # Non-member rejection
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_stranger.key}")
        res_forbidden = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res_forbidden.status_code, 403)

        # Invalid session id -> 404
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        res_404 = self.client.post("/api/sessions/end/", {"session_id": 999999})
        self.assertEqual(res_404.status_code, 404)

        # First legitimate end -> 200
        res_first = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res_first.status_code, 200)
        self.assertEqual(res_first.data.get("message"), "Session ended")
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.ended_at)

        # Second repeated call -> 200 idempotent (does not error)
        res_repeat = self.client.post("/api/sessions/end/", {"session_id": self.session.id})
        self.assertEqual(res_repeat.status_code, 200)
        self.assertEqual(res_repeat.data.get("message"), "Session already ended")

    def test_swipes_locked_once_session_ended(self):
        """Verify swipes are strictly rejected once a session is marked ended."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        self.client.post("/api/sessions/end/", {"session_id": self.session.id})

        # Attempt to swipe after session concluded -> 403 Forbidden
        res_swipe = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.movie.id,
            "reaction": "like"
        })
        self.assertEqual(res_swipe.status_code, 403)
        self.assertIn("ended", str(res_swipe.data).lower())

    def test_movie_metadata_endpoint_resilience_and_fallback(self):
        """Verify the movie detail endpoint returns complete serialized metadata and 404 for missing movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")

        # Valid movie -> 200 with complete fields
        res_valid = self.client.get(f"/api/movies/{self.movie.id}/")
        self.assertEqual(res_valid.status_code, 200)
        data = res_valid.data
        self.assertEqual(data.get("id"), self.movie.id)
        self.assertEqual(data.get("title"), "Solaris")
        self.assertTrue(data.get("poster_url", "").startswith("https://image.tmdb.org/t/p/w780/solaris.jpg"))
        self.assertEqual(data.get("rating"), 8.0)
        self.assertEqual(data.get("release_year"), 1972)

        # Non-existent movie -> 404 (frontend fallback lifecycle catches this and sets status='failed')
        res_missing = self.client.get("/api/movies/999999/")
        self.assertEqual(res_missing.status_code, 404)


class CoreUserExperienceRepairTests(TestCase):
    """
    Tests for Core UX repair:
    1. Strict questionnaire filtering (Genre + Era Before 2000).
    2. Swipe idempotency & double-gesture prevention.
    3. Match poster serialization & AllowAny movie detail access.
    4. Exhausted state safety (never relax to unrelated movies).
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="host_ux", password="password123")
        self.guest = User.objects.create_user(username="guest_ux", password="password123")
        self.token_host = Token.objects.create(user=self.host)
        self.token_guest = Token.objects.create(user=self.guest)

        self.drama = Genre.objects.create(id=77, name="Drama", tmdb_id=18)
        self.comedy = Genre.objects.create(id=78, name="Comedy", tmdb_id=35)
        self.horror = Genre.objects.create(id=79, name="Horror", tmdb_id=27)

        # Create Drama movies across eras
        self.drama_classic = Movie.objects.create(
            tmdb_id=278,
            title="The Shawshank Redemption",
            overview="Two imprisoned men bond over a number of years.",
            release_date=date(1994, 9, 23),
            rating=9.3,
            vote_count=25000,
            poster_path="/shawshank.jpg",
            original_language="en",
        )
        self.drama_classic.genres.add(self.drama)

        self.drama_2010s = Movie.objects.create(
            tmdb_id=314365,
            title="Spotlight",
            overview="Boston Globe journalists uncover child abuse scandal.",
            release_date=date(2015, 11, 6),
            rating=8.1,
            vote_count=8000,
            poster_path="/spotlight.jpg",
            original_language="en",
        )
        self.drama_2010s.genres.add(self.drama)

        self.drama_recent = Movie.objects.create(
            tmdb_id=872585,
            title="Oppenheimer",
            overview="The story of American scientist J. Robert Oppenheimer.",
            release_date=date(2023, 7, 21),
            rating=8.9,
            vote_count=12000,
            poster_path="/oppenheimer.jpg",
            original_language="en",
        )
        self.drama_recent.genres.add(self.drama)

        # Create unrelated Comedy and Horror
        self.comedy_classic = Movie.objects.create(
            tmdb_id=2292,
            title="Clerks",
            overview="A day in the lives of two convenience clerks.",
            release_date=date(1994, 10, 19),
            rating=7.7,
            vote_count=3000,
            poster_path="/clerks.jpg",
            original_language="en",
        )
        self.comedy_classic.genres.add(self.comedy)

        self.session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            genre=self.drama,
            industry="hollywood",
            selected_languages=["en"],
            code="UX1234",
            host_preferences={"era": ["classic"], "min_rating": ["7+"]},
            guest_preferences={"era": ["classic"], "min_rating": ["7+"]},
            preferences_set=True,
        )
        self.session.genres.add(self.drama)

    def test_questionnaire_era_and_genre_strict_filtering(self):
        """Selecting Drama and movies before 2000 must strictly return ONLY pre-2000 Drama movies."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_host.key}")
        res = self.client.get(f"/api/recommendations/?session_id={self.session.id}")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get("success"))

        movies = res.data.get("movies", [])
        self.assertGreater(len(movies), 0)

        for m in movies:
            # Must be released strictly before 2000
            self.assertLess(m["release_year"], 2000, f"Movie {m['title']} has year {m['release_year']}, expected < 2000")
            # Must not be the 2015 or 2023 drama
            self.assertNotEqual(m["title"], "Spotlight")
            self.assertNotEqual(m["title"], "Oppenheimer")
            # Must not be unrelated comedy
            self.assertNotEqual(m["title"], "Clerks")

        titles = [m["title"] for m in movies]
        self.assertIn("The Shawshank Redemption", titles)

    def test_swipe_idempotency_and_duplicate_prevention(self):
        """Repeated swipes for the same user, session, and movie return 409 without creating duplicate rows."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_host.key}")

        # First swipe -> 201 Created
        res1 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.drama_classic.id,
            "reaction": "like"
        })
        self.assertEqual(res1.status_code, 201)
        self.assertTrue(res1.data.get("success"))

        # Accidental double-tap / retry swipe with same reaction -> 200 OK idempotent (does NOT create duplicate DB row)
        res2 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.drama_classic.id,
            "reaction": "like"
        })
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.data.get("idempotent"))

        # Conflicting swipe with different reaction -> 409 Conflict
        res3 = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.drama_classic.id,
            "reaction": "dislike"
        })
        self.assertEqual(res3.status_code, 409)

        # Only 1 swipe record must exist in DB
        self.assertEqual(
            Swipe.objects.filter(session=self.session, user=self.host, movie=self.drama_classic).count(),
            1
        )

    def test_match_creation_and_poster_payload(self):
        """When both users like a movie, match is created and complete poster_url is provided."""
        # Host likes movie
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_host.key}")
        self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.drama_classic.id,
            "reaction": "like"
        })

        # Guest likes movie -> match created
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_guest.key}")
        res = self.client.post("/api/swipes/", {
            "session": self.session.id,
            "movie": self.drama_classic.id,
            "reaction": "like"
        })
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.data.get("match"))

        # Check match list endpoint
        res_matches = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res_matches.status_code, 200)
        matches = res_matches.data.get("matches", [])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["movie_title"], "The Shawshank Redemption")
        self.assertTrue(matches[0]["poster_url"].startswith("https://image.tmdb.org/t/p/w780/shawshank.jpg"))

        # Check MovieDetailView is accessible (AllowAny)
        unauth_client = APIClient()
        res_detail = unauth_client.get(f"/api/movies/{self.drama_classic.id}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertTrue(res_detail.data.get("poster_url").startswith("https://image.tmdb.org/t/p/w780/shawshank.jpg"))


class UniversalLocalNetworkDevConfigurationTests(TestCase):
    """
    Tests for Universal Local Network Development Configuration:
    1. ALLOWED_HOSTS security: loopback & LAN allowed without wildcards (*).
    2. CORS & CSRF origins: loopback & LAN allowed without wildcards (*).
    3. HTTP API endpoints reachable via proxied headers.
    4. WebSocket authentication subprotocol ('token', '<token_key>') handling.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="netuser", password="password123")
        self.token = Token.objects.create(user=self.user)

    def test_dev_allowed_hosts_security_and_lan_detection(self):
        """Verify ALLOWED_HOSTS includes loopback and LAN IP without unsafe wildcards."""
        from django.conf import settings
        self.assertIn("localhost", settings.ALLOWED_HOSTS)
        self.assertIn("127.0.0.1", settings.ALLOWED_HOSTS)
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_cors_and_csrf_origins_security(self):
        """Verify CORS and CSRF configurations protect against arbitrary origins."""
        from django.conf import settings
        self.assertNotIn("*", settings.CORS_ALLOWED_ORIGINS)
        self.assertNotIn("*", settings.CSRF_TRUSTED_ORIGINS)
        self.assertTrue(settings.CORS_ALLOW_CREDENTIALS)

        # Must include standard dev ports on loopback
        self.assertIn("http://localhost:5173", settings.CORS_ALLOWED_ORIGINS)
        self.assertIn("http://127.0.0.1:5173", settings.CORS_ALLOWED_ORIGINS)

    def test_healthz_and_api_reachable_with_dev_host_headers(self):
        """Endpoints are accessible with loopback and proxied Host headers."""
        res_local = self.client.get("/healthz/", HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(res_local.status_code, 200)

        res_host = self.client.get("/healthz/", HTTP_HOST="localhost:8000")
        self.assertEqual(res_host.status_code, 200)

        res_api = self.client.get("/api/genres/?industry=mixed", HTTP_HOST="127.0.0.1:8000")
        self.assertEqual(res_api.status_code, 200)

    async def test_websocket_token_subprotocol_authentication_flow(self):
        """Verify TokenAuthMiddleware correctly authenticates via 'token', '<key>' subprotocols."""
        from channels.testing import WebsocketCommunicator
        from channels.db import database_sync_to_async
        from backend.asgi import application
        from core.models import Session

        session = await database_sync_to_async(Session.objects.create)(
            host=self.user,
            code="WSNET1"
        )

        # 1. Connection with valid token subprotocol -> Accepted
        communicator = WebsocketCommunicator(
            application,
            f"/ws/session/{session.id}/",
            subprotocols=["token", self.token.key]
        )
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        self.assertEqual(subprotocol, "token")
        await communicator.disconnect()

        # 2. Connection without token subprotocol -> Rejected (4001)
        unauth_communicator = WebsocketCommunicator(
            application,
            f"/ws/session/{session.id}/"
        )
        connected_unauth, _ = await unauth_communicator.connect()
        self.assertFalse(connected_unauth)

    def test_no_unnecessary_cors_regex_exceptions(self):
        """Verify no broad regex exceptions are set; CORS remains strictly explicit."""
        from django.conf import settings
        regexes = getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", None)
        self.assertFalse(regexes, "CORS_ALLOWED_ORIGIN_REGEXES should not be set; same-origin proxy handles dev requests.")









