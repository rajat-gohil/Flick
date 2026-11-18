import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import (
    Session,
    Movie,
    Swipe,
    Match,
    SessionStats,
    Genre,
    CollaborativeAgreement,
)


class ScreeningSessionResultsAndStatsPersistenceTests(TestCase):
    """
    Test suite verifying screening session completion, results retrieval,
    and statistics persistence/restoration (Reviewed, Matched, Affinity).
    """

    def setUp(self):
        self.client = APIClient()
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")
        self.genre = Genre.objects.create(name="Sci-Fi", tmdb_id=878)

        # Create 9 distinct test movies
        self.movies = []
        for i in range(1, 10):
            m = Movie.objects.create(
                tmdb_id=1000 + i,
                title=f"Movie {i}",
                rating=8.0 + (i * 0.1),
                vote_count=100,
                release_date="2020-01-01",
                poster_path=f"/poster_{i}.jpg",
                overview=f"Overview for Movie {i}",
                display_ready=True,
                recommendable=True,
            )
            m.genres.add(self.genre)
            self.movies.append(m)

        # Create active screening session
        self.session = Session.objects.create(
            code="SCN900",
            host=self.host,
            guest=self.guest,
            genre=self.genre,
        )
        self.session.genres.add(self.genre)

    def test_session_completes_with_nine_reviewed_and_zero_matches(self):
        """
        Req 1, 4, 5, 6:
        Session completes with 9 reviewed movies and 0 matches.
        Statistics: Reviewed=9, Matched=0, Affinity=0%.
        """
        # Both host and guest review all 9 movies with non-matching reactions (all dislikes)
        for m in self.movies:
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
            Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertTrue(res.data["ended"])
        self.assertEqual(res.data["reviewed_count"], 9)
        self.assertEqual(res.data["matched_count"], 0)
        self.assertEqual(res.data["affinity_percent"], 0)
        self.assertEqual(len(res.data["matches"]), 0)

        # Verify SessionStats in database
        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.total_swipes, 18)
        self.assertEqual(stats.total_matches, 0)
        self.assertEqual(stats.ended_by, "host")

    def test_session_detail_restores_accurate_statistics_after_refresh(self):
        """
        Req 3, 4, 5, 6:
        When refreshing or fetching session detail, statistics are reliably
        restored from authoritative backend session data.
        """
        # Host reviewed 9 movies, 0 matches
        for m in self.movies:
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
            Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])
        SessionStats.objects.create(session=self.session, total_swipes=18, total_matches=0)

        # Host fetches detail
        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        s_data = res.data["session"]
        self.assertTrue(s_data["ended"])
        self.assertEqual(s_data["reviewed_count"], 9)
        self.assertEqual(s_data["matched_count"], 0)
        self.assertEqual(s_data["affinity_percent"], 0)

        # Guest fetches detail
        self.client.force_authenticate(user=self.guest)
        res_guest = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_guest.status_code, status.HTTP_200_OK)
        sg_data = res_guest.data["session"]
        self.assertTrue(sg_data["ended"])
        self.assertEqual(sg_data["reviewed_count"], 9)
        self.assertEqual(sg_data["matched_count"], 0)
        self.assertEqual(sg_data["affinity_percent"], 0)

    def test_session_matches_endpoint_restores_results_and_statistics(self):
        """
        Req 2, 7:
        /api/matches/?session_id=<id> returns matches list along with
        reviewed_count, matched_count, and affinity_percent.
        """
        # 2 mutual matches out of 9 reviewed
        for idx, m in enumerate(self.movies):
            if idx < 2:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])

        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(len(res.data["matches"]), 2)
        self.assertEqual(res.data["reviewed_count"], 9)
        self.assertEqual(res.data["matched_count"], 2)
        # 2 / 9 * 100 = 22%
        self.assertEqual(res.data["affinity_percent"], 22)
        self.assertEqual(res.data["matches"][0]["movie_title"], "Movie 2")
        self.assertEqual(res.data["matches"][1]["movie_title"], "Movie 1")

    def test_end_session_immediately_returns_results_and_statistics(self):
        """
        Req 2, 7:
        Calling POST /api/sessions/end/ immediately provides matches and statistics
        so the frontend does not require a page refresh.
        """
        # 3 mutual matches out of 9 reviewed
        for idx, m in enumerate(self.movies):
            if idx < 3:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["matches"]), 3)
        self.assertEqual(res.data["reviewed_count"], 9)
        self.assertEqual(res.data["matched_count"], 3)
        # 3 / 9 * 100 = 33%
        self.assertEqual(res.data["affinity_percent"], 33)

    def test_idempotent_repeated_end_requests_do_not_duplicate_or_inflate(self):
        """
        Req 9:
        Repeated calls to /api/sessions/end/ are idempotent and do not
        duplicate matches or inflate counters.
        """
        for idx, m in enumerate(self.movies[:4]):
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
            Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
            Match.objects.create(session=self.session, movie=m)

        self.client.force_authenticate(user=self.host)
        res1 = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertEqual(res1.data["reviewed_count"], 4)
        self.assertEqual(res1.data["matched_count"], 4)
        self.assertEqual(res1.data["affinity_percent"], 100)

        # Second call
        res2 = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["reviewed_count"], 4)
        self.assertEqual(res2.data["matched_count"], 4)
        self.assertEqual(res2.data["affinity_percent"], 100)
        self.assertEqual(len(res2.data["matches"]), 4)

        # Match count in DB must remain 4
        self.assertEqual(Match.objects.filter(session=self.session).count(), 4)

    def test_screening_archive_retrieval_displays_correct_information(self):
        """
        Req 8:
        Archive endpoint (/api/sessions/history/) displays the correct historical session info.
        """
        for idx, m in enumerate(self.movies[:9]):
            if idx < 2:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])

        self.client.force_authenticate(user=self.host)
        res = self.client.get("/api/sessions/history/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        history = res.data["history"]
        self.assertTrue(len(history) >= 1)
        item = next(h for h in history if h["session_id"] == self.session.id)
        self.assertEqual(item["swipe_count"], 9)
        self.assertEqual(item["match_count"], 2)
        self.assertEqual(item["affinity_percent"], 22)
        self.assertEqual(item["partner_username"], "guest_user")
        self.assertIsNotNone(item["top_match"])

    def test_interrupted_session_is_not_marked_completed(self):
        """
        Req 11:
        Interrupted or active sessions are not incorrectly marked completed.
        """
        # Session has not ended
        self.assertIsNone(self.session.ended_at)
        self.assertTrue(self.session.is_active())

        # Recent sessions view reports status as "active"
        self.client.force_authenticate(user=self.host)
        res = self.client.get("/api/sessions/recent/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        item = next(s for s in res.data["sessions"] if s["id"] == self.session.id)
        self.assertFalse(item["ended"])
        self.assertEqual(item["status"], "active")

        # Guest leaves session voluntarily
        self.client.force_authenticate(user=self.guest)
        leave_res = self.client.post("/api/sessions/leave/", {"session_id": self.session.id}, format="json")
        self.assertEqual(leave_res.status_code, status.HTTP_200_OK)

        # Refresh session from DB: ended_at remains None!
        self.session.refresh_from_db()
        self.assertIsNone(self.session.ended_at)
        self.assertTrue(self.session.is_active())

    # =========================================================================
    # Phase 4 Targeted Regression Suite: 10 Comprehensive Cases
    # =========================================================================

    def test_case_1_three_reviewed_three_matched_100_percent_affinity(self):
        """
        Targeted Case 1: 3/3 (100% affinity).
        3 movies reviewed, 3 mutual matches formed.
        Reviewed = 3, Matched = 3, Affinity = 100%.
        """
        for m in self.movies[:3]:
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
            Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
            Match.objects.create(session=self.session, movie=m)

        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["reviewed_count"], 3)
        self.assertEqual(res.data["matched_count"], 3)
        self.assertEqual(res.data["affinity_percent"], 100)

        # Confirm on session detail
        res_detail = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_detail.data["session"]["reviewed_count"], 3)
        self.assertEqual(res_detail.data["session"]["matched_count"], 3)
        self.assertEqual(res_detail.data["session"]["affinity_percent"], 100)

    def test_case_2_five_reviewed_three_matched_60_percent_affinity(self):
        """
        Targeted Case 2: 5/3 (60% affinity).
        5 movies reviewed, 3 mutual matches, 2 non-matches.
        Reviewed = 5, Matched = 3, Affinity = 60%.
        """
        for idx, m in enumerate(self.movies[:5]):
            if idx < 3:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["reviewed_count"], 5)
        self.assertEqual(res.data["matched_count"], 3)
        # round((3 / 5) * 100) = 60
        self.assertEqual(res.data["affinity_percent"], 60)

        # Confirm on matches endpoint
        res_matches = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res_matches.data["reviewed_count"], 5)
        self.assertEqual(res_matches.data["matched_count"], 3)
        self.assertEqual(res_matches.data["affinity_percent"], 60)

    def test_case_3_zero_reviewed_zero_matched_0_percent_affinity(self):
        """
        Targeted Case 3: 0/0 (0% affinity).
        0 movies reviewed, 0 matches.
        Reviewed = 0, Matched = 0, Affinity = 0%.
        """
        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["reviewed_count"], 0)
        self.assertEqual(res.data["matched_count"], 0)
        self.assertEqual(res.data["affinity_percent"], 0)

        res_detail = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_detail.data["session"]["reviewed_count"], 0)
        self.assertEqual(res_detail.data["session"]["matched_count"], 0)
        self.assertEqual(res_detail.data["session"]["affinity_percent"], 0)

    def test_case_4_missing_reviewed_recovery_invariant(self):
        """
        Targeted Case 4: Missing reviewed recovery.
        3 mutual matches formed, but swipe records were deleted, missing, or undercounted.
        Invariant guarantees: Reviewed >= Matched (must be recovered to at least 3, never 0).
        Affinity = 100% (never 0% when 3 consensus films exist).
        """
        # Create 3 matches with NO Swipe rows in the database
        for m in self.movies[:3]:
            Match.objects.create(session=self.session, movie=m)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])

        # Swipe table is completely empty for this session
        self.assertEqual(Swipe.objects.filter(session=self.session).count(), 0)
        self.assertEqual(Match.objects.filter(session=self.session).count(), 3)

        self.client.force_authenticate(user=self.host)

        # 1. Session detail endpoint recovers reviewed count to 3
        res_detail = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        s_data = res_detail.data["session"]
        self.assertEqual(s_data["matched_count"], 3)
        self.assertEqual(s_data["reviewed_count"], 3)
        self.assertEqual(s_data["affinity_percent"], 100)

        # 2. Match list endpoint also recovers reviewed count to 3
        res_matches = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res_matches.status_code, status.HTTP_200_OK)
        self.assertEqual(res_matches.data["matched_count"], 3)
        self.assertEqual(res_matches.data["reviewed_count"], 3)
        self.assertEqual(res_matches.data["affinity_percent"], 100)

        # 3. Session history/archive endpoint also recovers reviewed count to 3
        res_history = self.client.get("/api/sessions/history/")
        self.assertEqual(res_history.status_code, status.HTTP_200_OK)
        item = next(h for h in res_history.data["history"] if h["session_id"] == self.session.id)
        self.assertEqual(item["match_count"], 3)
        self.assertEqual(item["swipe_count"], 3)
        self.assertEqual(item["affinity_percent"], 100)

    def test_case_5_refresh_consistency_across_endpoints(self):
        """
        Targeted Case 5: Refresh consistency.
        Initial completion vs page refresh (subsequent GET /api/sessions/<id>/
        and GET /api/matches/?session_id=<id>).
        Statistics must remain strictly identical before and after refresh.
        """
        # 3 matches out of 7 reviewed
        for idx, m in enumerate(self.movies[:7]):
            if idx < 3:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.client.force_authenticate(user=self.host)

        # Initial End
        res_end = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        initial_reviewed = res_end.data["reviewed_count"]
        initial_matched = res_end.data["matched_count"]
        initial_affinity = res_end.data["affinity_percent"]

        self.assertEqual(initial_reviewed, 7)
        self.assertEqual(initial_matched, 3)
        self.assertEqual(initial_affinity, 43)  # round(3/7 * 100) = 43

        # Simulate Page Refresh: Fetch detail
        res_detail = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_detail.data["session"]["reviewed_count"], initial_reviewed)
        self.assertEqual(res_detail.data["session"]["matched_count"], initial_matched)
        self.assertEqual(res_detail.data["session"]["affinity_percent"], initial_affinity)

        # Simulate Page Refresh: Fetch matches history
        res_matches = self.client.get(f"/api/matches/?session_id={self.session.id}")
        self.assertEqual(res_matches.data["reviewed_count"], initial_reviewed)
        self.assertEqual(res_matches.data["matched_count"], initial_matched)
        self.assertEqual(res_matches.data["affinity_percent"], initial_affinity)

    def test_case_6_archive_consistency_matches_session_detail(self):
        """
        Targeted Case 6: Archive consistency.
        GET /api/sessions/history/ returns exact same Reviewed (swipe_count),
        Matched (match_count), and Affinity (affinity_percent) as the session detail.
        """
        for idx, m in enumerate(self.movies[:6]):
            if idx < 2:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)
            else:
                Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.DISLIKE)
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.DISLIKE)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])

        self.client.force_authenticate(user=self.host)
        detail_res = self.client.get(f"/api/sessions/{self.session.id}/")
        d_session = detail_res.data["session"]

        history_res = self.client.get("/api/sessions/history/")
        item = next(h for h in history_res.data["history"] if h["session_id"] == self.session.id)

        self.assertEqual(item["swipe_count"], d_session["reviewed_count"])
        self.assertEqual(item["match_count"], d_session["matched_count"])
        self.assertEqual(item["affinity_percent"], d_session["affinity_percent"])

    def test_case_7_deduplication_duplicate_swipes_do_not_inflate(self):
        """
        Targeted Case 7: Deduplication.
        Multiple duplicate swipes or idempotency retries for the same movie
        do NOT inflate the reviewed count.
        """
        # User submits multiple swipes for the same movie (e.g. idempotency retry or network glitch)
        m = self.movies[0]
        Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
        Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
        Match.objects.create(session=self.session, movie=m)

        # Second movie reviewed normally
        m2 = self.movies[1]
        Swipe.objects.create(session=self.session, user=self.host, movie=m2, reaction=Swipe.DISLIKE)
        Swipe.objects.create(session=self.session, user=self.guest, movie=m2, reaction=Swipe.DISLIKE)

        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/")
        # Distinct movies reviewed must be 2, not 3 or 4
        self.assertEqual(res.data["session"]["reviewed_count"], 2)
        self.assertEqual(res.data["session"]["matched_count"], 1)
        self.assertEqual(res.data["session"]["affinity_percent"], 50)

    def test_case_8_undo_operations_update_reviewed_and_block_on_matched(self):
        """
        Targeted Case 8: Undo operations.
        Undoing a non-matched swipe decrements reviewed count and adjusts affinity.
        Attempting to undo a matched movie is blocked.
        """
        from core.services.deck_state import DeckAdvancementService, UndoNotPermittedError

        # Setup CollaborativeAgreement
        agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            deck_manifest=[
                {"card_index": 0, "movie_id": self.movies[0].id, "title": self.movies[0].title},
                {"card_index": 1, "movie_id": self.movies[1].id, "title": self.movies[1].title},
            ],
            host_card_index=0,
            guest_card_index=0,
        )

        # Host and Guest swipe on movie 0 -> Match formed
        DeckAdvancementService.record_swipe_response(
            session_id=self.session.id, user=self.host, card_index=0, movie_id=self.movies[0].id, reaction=Swipe.LIKE
        )
        DeckAdvancementService.record_swipe_response(
            session_id=self.session.id, user=self.guest, card_index=0, movie_id=self.movies[0].id, reaction=Swipe.LIKE
        )
        self.assertEqual(Match.objects.filter(session=self.session, movie=self.movies[0]).count(), 1)

        # Attempt to undo movie 0 -> MUST be rejected because match already formed
        with self.assertRaises(UndoNotPermittedError):
            DeckAdvancementService.undo_card_response(
                session_id=self.session.id, user=self.host, card_index=0, movie_id=self.movies[0].id
            )

        # Host swipes on movie 1 (unmatched)
        DeckAdvancementService.record_swipe_response(
            session_id=self.session.id, user=self.host, card_index=1, movie_id=self.movies[1].id, reaction=Swipe.DISLIKE
        )
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 2)

        # Undo movie 1 -> permitted
        undo_res = DeckAdvancementService.undo_card_response(
            session_id=self.session.id, user=self.host, card_index=1, movie_id=self.movies[1].id
        )
        self.assertTrue(undo_res["success"])
        self.assertEqual(Swipe.objects.filter(session=self.session, user=self.host).count(), 1)

        # Check statistics via API
        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res.data["session"]["reviewed_count"], 1)
        self.assertEqual(res.data["session"]["matched_count"], 1)
        self.assertEqual(res.data["session"]["affinity_percent"], 100)

    def test_case_9_incomplete_and_active_session_statistics(self):
        """
        Targeted Case 9: Incomplete and active sessions.
        An active session prior to completion calculates live reviewed and matched metrics
        without prematurely marking ended or corrupting statistics.
        """
        # Session is ongoing, 4 movies swiped by host, 2 matches
        for idx, m in enumerate(self.movies[:4]):
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
            if idx < 2:
                Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE)
                Match.objects.create(session=self.session, movie=m)

        self.assertIsNone(self.session.ended_at)

        self.client.force_authenticate(user=self.host)
        res = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        s_data = res.data["session"]
        self.assertFalse(s_data["ended"])
        self.assertEqual(s_data["reviewed_count"], 4)
        self.assertEqual(s_data["matched_count"], 2)
        self.assertEqual(s_data["affinity_percent"], 50)

    def test_case_10_session_cross_talk_isolation(self):
        """
        Targeted Case 10: Session cross-talk isolation.
        Swipes and matches in Session A never leak into or affect statistics of Session B.
        """
        # Create session B
        session_b = Session.objects.create(
            code="SCN999",
            host=self.host,
            guest=self.guest,
            genre=self.genre,
        )

        # Session A: 3 reviewed, 1 match
        for idx, m in enumerate(self.movies[:3]):
            Swipe.objects.create(session=self.session, user=self.host, movie=m, reaction=Swipe.LIKE)
            Swipe.objects.create(session=self.session, user=self.guest, movie=m, reaction=Swipe.LIKE if idx == 0 else Swipe.DISLIKE)
            if idx == 0:
                Match.objects.create(session=self.session, movie=m)

        # Session B: 8 reviewed, 4 matches
        for idx, m in enumerate(self.movies[:8]):
            Swipe.objects.create(session=session_b, user=self.host, movie=m, reaction=Swipe.LIKE)
            Swipe.objects.create(session=session_b, user=self.guest, movie=m, reaction=Swipe.LIKE if idx < 4 else Swipe.DISLIKE)
            if idx < 4:
                Match.objects.create(session=session_b, movie=m)

        self.session.ended_at = timezone.now()
        self.session.save(update_fields=["ended_at"])
        session_b.ended_at = timezone.now()
        session_b.save(update_fields=["ended_at"])

        self.client.force_authenticate(user=self.host)

        # Query Session A
        res_a = self.client.get(f"/api/sessions/{self.session.id}/")
        self.assertEqual(res_a.data["session"]["reviewed_count"], 3)
        self.assertEqual(res_a.data["session"]["matched_count"], 1)
        self.assertEqual(res_a.data["session"]["affinity_percent"], 33)

        # Query Session B
        res_b = self.client.get(f"/api/sessions/{session_b.id}/")
        self.assertEqual(res_b.data["session"]["reviewed_count"], 8)
        self.assertEqual(res_b.data["session"]["matched_count"], 4)
        self.assertEqual(res_b.data["session"]["affinity_percent"], 50)

    def test_end_session_clamps_duration_ms_for_old_sessions(self):
        """Ending a session older than 24.85 days must clamp duration_ms instead of overflowing 32-bit int."""
        from datetime import timedelta

        Session.objects.filter(id=self.session.id).update(
            created_at=timezone.now() - timedelta(days=40)
        )
        self.client.force_authenticate(user=self.host)
        res = self.client.post("/api/sessions/end/", {"session_id": self.session.id}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["ended"])
        stats = SessionStats.objects.get(session=self.session)
        self.assertEqual(stats.duration_ms, 2_147_483_647)
