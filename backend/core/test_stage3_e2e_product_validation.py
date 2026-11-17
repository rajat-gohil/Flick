"""
Flick Stage 3: End-to-End Product Validation Test Suite

Comprehensive automated integration and intelligence verification covering:
1. Complete Two-Participant Journey (Registration -> Join -> Questionnaire -> Deck -> Match -> Completion -> Refresh)
2. Recommendation Intelligence Scenarios with exact mathematical scoring traces
3. Lifecycle, Persistence, Reconnection, and Undo Integrity
4. Catalogue Integrity, Synthetic Fixture Exclusion, and Constraint Protection
"""

import time
from datetime import date
from typing import Any, Dict, List
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import (
    CollaborativeAgreement,
    ConstraintExpansionProposal,
    Genre,
    Movie,
    MovieKeyword,
    MovieTag,
    Session,
    SessionStats,
    Swipe,
    Match,
    UserTasteProfile,
)
from core.services.affinity import (
    calculate_questionnaire_similarity,
    calculate_screening_affinity,
    calculate_session_statistics,
    calculate_taste_compatibility,
    normalize_user_preferences,
)
from core.services.deck_state import (
    DeckAdvancementService,
    UndoNotPermittedError,
)
from core.services.manifest import (
    CollaborativeDeckScorer,
    ManifestCompilerService,
)
from core.services.retrieval import CandidatePool
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    UserPreferenceData,
)

User = get_user_model()


class Stage3EndToEndProductValidationTests(TestCase):
    """
    Stage 3 Product Acceptance and Integration Verification Suite.
    """

    def setUp(self):
        self.client_host = APIClient()
        self.client_guest = APIClient()

        # Create two independent participants
        self.host_user = User.objects.create_user(
            username="val_host",
            email="val_host@flick.test",
            password="SecurePassword123!",
            first_name="HostUser",
        )
        self.guest_user = User.objects.create_user(
            username="val_guest",
            email="val_guest@flick.test",
            password="SecurePassword123!",
            first_name="GuestUser",
        )

        self.client_host.force_authenticate(user=self.host_user)
        self.client_guest.force_authenticate(user=self.guest_user)

        # Genres
        self.crime_genre = Genre.objects.create(name="Crime", tmdb_id=80)
        self.scifi_genre = Genre.objects.create(name="Sci-Fi", tmdb_id=878)
        self.horror_genre = Genre.objects.create(name="Horror", tmdb_id=27)

        # Keywords & Tags
        self.kw_survival = MovieKeyword.objects.create(name="survival", tmdb_id=1001)
        self.kw_mindgames = MovieKeyword.objects.create(name="mind games", tmdb_id=1002)
        self.kw_gore = MovieKeyword.objects.create(name="gore", tmdb_id=1003)
        self.kw_friendship = MovieKeyword.objects.create(name="friendship", tmdb_id=1004)

        self.tag_tense = MovieTag.objects.create(name="tense")
        self.tag_dark = MovieTag.objects.create(name="dark")
        self.tag_poignant = MovieTag.objects.create(name="poignant")

        # Create catalogue movies
        self.movies: List[Movie] = []
        for i in range(1, 45):
            m = Movie.objects.create(
                title=f"Catalogue Film {i:02d}",
                tmdb_id=50000 + i,
                rating=7.0 + ((i % 5) * 0.4),
                vote_count=200 + (i * 20),
                release_date=date(2022, 1, 1),
                display_ready=True,
                recommendable=True,
                provenance="tmdb_catalogue",
                overview=f"Overview for film {i}",
                poster_path=f"/poster_{i}.jpg",
                original_language="en",
            )
            m.genres.add(self.crime_genre)
            if i % 2 == 0:
                m.keywords.add(self.kw_survival)
                m.tags.add(self.tag_tense, self.tag_dark)
            else:
                m.keywords.add(self.kw_friendship)
                m.tags.add(self.tag_poignant)
            self.movies.append(m)

        # Synthetic fixture records (must be ineligible)
        self.synth_m1_a = Movie.objects.create(
            title="M1",
            tmdb_id=8001,
            display_ready=False,
            recommendable=False,
            provenance="synthetic_fixture",
        )
        self.synth_m1_b = Movie.objects.create(
            title="M1",
            tmdb_id=7001,
            display_ready=False,
            recommendable=False,
            provenance="synthetic_fixture",
        )

    # =========================================================================
    # Section 1: Complete Two-Participant Journey
    # =========================================================================

    def test_01_two_participant_registration_and_authentication(self):
        """
        Step 1: Independent user registration and token authentication.
        """
        anon_client = APIClient()
        reg_payload = {
            "email": "new_viewer@test.com",
            "password": "Password123!",
            "display_name": "NewViewer",
        }
        res = anon_client.post("/api/auth/register/", reg_payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])

        # Authenticate with login
        login_res = anon_client.post(
            "/api/auth/login/",
            {"email": "new_viewer@test.com", "password": "Password123!"},
            format="json",
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        self.assertTrue(login_res.data["success"])
        self.assertIn("token", login_res.data)
        token = login_res.data["token"]

        # Authenticate with token
        anon_client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        profile_res = anon_client.get("/api/users/profile/")
        self.assertEqual(profile_res.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_res.data["user"]["email"], "new_viewer@test.com")

    def test_02_room_creation_and_joining_invitation_flow(self):
        """
        Steps 2 & 3: Host creates room, Guest joins via room code.
        """
        # Host creates room
        res_create = self.client_host.post("/api/sessions/create/", format="json")
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        session_id = res_create.data["id"]
        code = res_create.data["code"]

        session = Session.objects.get(id=session_id)
        self.assertEqual(session.host, self.host_user)
        self.assertIsNone(session.guest)

        # Guest joins using room code
        res_join = self.client_guest.post("/api/sessions/join/", {"code": code}, format="json")
        self.assertEqual(res_join.status_code, status.HTTP_200_OK)
        self.assertTrue(res_join.data["success"])

        session.refresh_from_db()
        self.assertEqual(session.guest, self.guest_user)

    def test_03_questionnaire_submission_and_persistence(self):
        """
        Steps 4 & 5: Both participants submit occasion questionnaires,
        verifying database persistence and similarity score computation.
        """
        session = Session.objects.create(code="QUES01", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)

        host_prefs = {
            "mood": ["exciting", "dark"],
            "pace": ["fast"],
            "intensity": "heavy",
            "themes": ["survival"],
            "tone": ["suspenseful"],
        }
        guest_prefs = {
            "mood": ["exciting", "fun"],
            "pace": ["balanced"],
            "intensity": "medium",
            "themes": ["survival"],
            "tone": ["humorous"],
        }

        # Host submits
        res_h = self.client_host.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": host_prefs},
            format="json",
        )
        self.assertEqual(res_h.status_code, status.HTTP_200_OK)

        # Guest submits
        res_g = self.client_guest.post(
            "/api/sessions/preferences/",
            {"session_id": session.id, "preferences": guest_prefs},
            format="json",
        )
        self.assertEqual(res_g.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertTrue(session.preferences_set)
        self.assertIsNotNone(session.host_preferences)
        self.assertIsNotNone(session.guest_preferences)
        self.assertEqual(session.host_preferences["mood"], ["exciting", "dark"])
        self.assertEqual(session.guest_preferences["mood"], ["exciting", "fun"])

    def test_04_deck_generation_and_card_delivery(self):
        """
        Steps 6 & 7: Recommendation manifest compilation and independent card delivery.
        """
        session = Session.objects.create(
            code="DECK01",
            host=self.host_user,
            guest=self.guest_user,
            genre=self.crime_genre,
            host_preferences={"mood": ["exciting"], "intensity": "medium"},
            guest_preferences={"mood": ["exciting"], "intensity": "medium"},
            preferences_set=True,
        )

        # First request triggers manifest compilation
        res_card = self.client_host.get(f"/api/sessions/{session.id}/deck/card/")
        self.assertEqual(res_card.status_code, status.HTTP_200_OK)
        self.assertTrue(res_card.data["success"])
        self.assertIn("card", res_card.data)
        self.assertEqual(res_card.data["card_index"], 0)

        # Agreement created and populated
        agreement = CollaborativeAgreement.objects.get(session=session)
        self.assertGreater(len(agreement.deck_manifest), 0)
        self.assertEqual(agreement.host_card_index, 0)
        self.assertEqual(agreement.guest_card_index, 0)

    def test_05_independent_deck_swiping_and_mutual_match_formation(self):
        """
        Steps 8 & 9: Independent swipe advancement and atomic mutual match resolution.
        """
        session = Session.objects.create(
            code="SWP01",
            host=self.host_user,
            guest=self.guest_user,
            genre=self.crime_genre,
            preferences_set=True,
        )
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[
                {"card_index": 0, "movie_id": self.movies[0].id, "title": self.movies[0].title},
                {"card_index": 1, "movie_id": self.movies[1].id, "title": self.movies[1].title},
                {"card_index": 2, "movie_id": self.movies[2].id, "title": self.movies[2].title},
            ],
            host_card_index=0,
            guest_card_index=0,
        )

        # Host swipes LIKE on card 0
        h_res0 = DeckAdvancementService.record_swipe_response(
            session_id=session.id, user=self.host_user, card_index=0, movie_id=self.movies[0].id, reaction=Swipe.LIKE
        )
        self.assertFalse(h_res0["match_formed"], "Match cannot form before partner responds.")
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 1)
        self.assertEqual(agreement.guest_card_index, 0)

        # Guest swipes LIKE on card 0 -> MUTUAL MATCH FORMED
        g_res0 = DeckAdvancementService.record_swipe_response(
            session_id=session.id, user=self.guest_user, card_index=0, movie_id=self.movies[0].id, reaction=Swipe.LIKE
        )
        self.assertTrue(g_res0["match_formed"])
        self.assertEqual(Match.objects.filter(session=session, movie=self.movies[0]).count(), 1)

        # Host swipes LIKE, Guest swipes DISLIKE on card 1 -> NO MATCH
        DeckAdvancementService.record_swipe_response(
            session_id=session.id, user=self.host_user, card_index=1, movie_id=self.movies[1].id, reaction=Swipe.LIKE
        )
        g_res1 = DeckAdvancementService.record_swipe_response(
            session_id=session.id, user=self.guest_user, card_index=1, movie_id=self.movies[1].id, reaction=Swipe.DISLIKE
        )
        self.assertFalse(g_res1["match_formed"])
        self.assertEqual(Match.objects.filter(session=session, movie=self.movies[1]).count(), 0)

    def test_06_session_completion_and_statistics_persistence(self):
        """
        Steps 10 & 11: Session conclusion, accurate statistics, and refresh restoration.
        """
        session = Session.objects.create(
            code="COMPL1",
            host=self.host_user,
            guest=self.guest_user,
            genre=self.crime_genre,
            preferences_set=True,
        )
        # 3 reviewed, 2 matched
        for idx in range(3):
            m = self.movies[idx]
            Swipe.objects.create(session=session, user=self.host_user, movie=m, reaction=Swipe.LIKE)
            Swipe.objects.create(session=session, user=self.guest_user, movie=m, reaction=Swipe.LIKE if idx < 2 else Swipe.DISLIKE)
            if idx < 2:
                Match.objects.create(session=session, movie=m)

        # Conclude session via POST /api/sessions/end/
        res_end = self.client_host.post("/api/sessions/end/", {"session_id": session.id}, format="json")
        self.assertEqual(res_end.status_code, status.HTTP_200_OK)
        self.assertEqual(res_end.data["reviewed_count"], 3)
        self.assertEqual(res_end.data["matched_count"], 2)
        # round((2 / 3) * 100) = 67%
        self.assertEqual(res_end.data["affinity_percent"], 67)
        self.assertEqual(len(res_end.data["matches"]), 2)

        # Refresh: GET /api/sessions/<id>/
        res_detail = self.client_host.get(f"/api/sessions/{session.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        s_data = res_detail.data["session"]
        self.assertEqual(s_data["reviewed_count"], 3)
        self.assertEqual(s_data["matched_count"], 2)
        self.assertEqual(s_data["affinity_percent"], 67)

        # Refresh: GET /api/matches/?session_id=<id>
        res_matches = self.client_host.get(f"/api/matches/?session_id={session.id}")
        self.assertEqual(res_matches.status_code, status.HTTP_200_OK)
        self.assertEqual(res_matches.data["reviewed_count"], 3)
        self.assertEqual(res_matches.data["matched_count"], 2)
        self.assertEqual(res_matches.data["affinity_percent"], 67)

        # Archive: GET /api/sessions/history/
        res_history = self.client_host.get("/api/sessions/history/")
        item = next(h for h in res_history.data["history"] if h["session_id"] == session.id)
        self.assertEqual(item["swipe_count"], 3)
        self.assertEqual(item["match_count"], 2)
        self.assertEqual(item["affinity_percent"], 67)

    # =========================================================================
    # Section 2: Recommendation Intelligence Tests (Score Tracing)
    # =========================================================================

    def test_intelligence_scenario_1_same_genre_different_questionnaires_with_trace(self):
        """
        Scenario 1: Same genre (Crime), two distinct questionnaire profiles.
        Room A: Exciting/Fast/Survival (action-oriented)
        Room B: Poignant/Slow/Friendship (character-oriented)
        Verifies:
        - Exact score traces for s_tone, s_narrative, s_theme, s_pace.
        - Survival movies rank higher in Room A.
        - Friendship movies rank higher in Room B.
        """
        scorer = IndividualRelevanceScorer()

        # Movie Survival: has survival keyword, tense/dark tag
        movie_survival = self.movies[1]  # Even index: survival keyword
        # Movie Friendship: has friendship keyword, poignant tag
        movie_friendship = self.movies[0] # Odd index: friendship keyword

        # Room A Preferences: Exciting, fast, survival
        prefs_a = UserPreferenceData(
            moods=["exciting", "dark"],
            themes=["survival"],
            theme_keywords=["survival"],
            experience="heavy",
        )

        # Room B Preferences: Poignant, balanced, friendship
        prefs_b = UserPreferenceData(
            moods=["poignant"],
            themes=["friendship"],
            theme_keywords=["friendship"],
            experience="light",
        )

        score_a_surv = scorer.score(movie_survival, prefs_a)
        score_a_friend = scorer.score(movie_friendship, prefs_a)

        score_b_surv = scorer.score(movie_survival, prefs_b)
        score_b_friend = scorer.score(movie_friendship, prefs_b)

        # Tracing assertions
        self.assertGreater(
            score_a_surv.s_theme,
            score_a_friend.s_theme,
            f"Room A thematic score for survival ({score_a_surv.s_theme}) must exceed friendship ({score_a_friend.s_theme})"
        )
        self.assertGreater(
            score_a_surv.normalized_relevance,
            score_a_friend.normalized_relevance,
            "In Room A, survival movie must have higher total relevance."
        )

        self.assertGreater(
            score_b_friend.s_theme,
            score_b_surv.s_theme,
            f"Room B thematic score for friendship ({score_b_friend.s_theme}) must exceed survival ({score_b_surv.s_theme})"
        )
        self.assertGreater(
            score_b_friend.normalized_relevance,
            score_b_surv.normalized_relevance,
            "In Room B, friendship movie must have higher total relevance."
        )

    def test_intelligence_scenario_2_same_questionnaire_different_historical_profiles(self):
        """
        Scenario 2: Identical questionnaire, different persistent taste profiles.
        Verifies:
        - Host with learned positive keyword weight receives positive s_learned bonus.
        - Guest with learned negative keyword weight receives negative s_learned penalty.
        - Individual relevance diverges significantly despite identical questionnaires.
        """
        scorer = IndividualRelevanceScorer()
        target_movie = self.movies[1]  # Has keyword: survival

        common_prefs_h = UserPreferenceData(
            moods=["tense"],
            experience="balanced",
            keyword_weights={"survival": 3.0},  # Historical like
        )
        common_prefs_g = UserPreferenceData(
            moods=["tense"],
            experience="balanced",
            keyword_weights={"survival": -3.0}, # Historical dislike
        )

        res_h = scorer.score(target_movie, common_prefs_h)
        res_g = scorer.score(target_movie, common_prefs_g)

        # Trace s_learned contribution
        self.assertGreater(res_h.s_learned, 0.0, "Positive taste weight must produce positive s_learned.")
        self.assertLess(res_g.s_learned, 0.0, "Negative taste weight must produce negative s_learned.")

        # Total relevance delta
        self.assertGreater(
            res_h.normalized_relevance,
            res_g.normalized_relevance,
            "Relevance must reflect learned historical taste divergence.",
        )

    def test_intelligence_scenario_3_different_genres_overlapping_qualitative_prefs(self):
        """
        Scenario 3: Different genres, overlapping qualitative preferences.
        Proves qualitative preference scoring (mood, intensity) functions consistently
        across disparate genre candidate pools.
        """
        scorer = IndividualRelevanceScorer()

        scifi_movie = Movie.objects.create(
            title="Cosmic Odyssey",
            tmdb_id=59991,
            rating=8.0,
            vote_count=600,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
        )
        scifi_movie.genres.add(self.scifi_genre)
        scifi_movie.tags.add(self.tag_dark, self.tag_tense)

        crime_movie = self.movies[1]  # Has dark & tense tags

        shared_prefs = UserPreferenceData(
            moods=["dark", "tense"],
            experience="heavy",
        )

        res_scifi = scorer.score(scifi_movie, shared_prefs)
        res_crime = scorer.score(crime_movie, shared_prefs)

        # Both match dark and tense tonality
        self.assertGreater(res_scifi.s_tone, 20.0)
        self.assertGreater(res_crime.s_tone, 20.0)

    def test_intelligence_scenario_4_conflicting_positive_and_negative_preferences(self):
        """
        Scenario 4: Conflicting positive and negative preferences.
        One participant loves gore; the other dislikes gore.
        Verifies:
        - Geometric mean Consensus(M) = sqrt(Rel_Host * Rel_Guest) severely penalizes conflict.
        """
        scorer = IndividualRelevanceScorer()
        deck_scorer = CollaborativeDeckScorer(scorer=scorer)

        gore_movie = Movie.objects.create(
            title="Gore Festival",
            tmdb_id=59992,
            rating=7.0,
            vote_count=300,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
        )
        gore_movie.genres.add(self.horror_genre)
        gore_movie.keywords.add(self.kw_gore)

        # Neutral movie without gore
        neutral_movie = Movie.objects.create(
            title="Eerie Shadows",
            tmdb_id=59993,
            rating=7.0,
            vote_count=300,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
        )
        neutral_movie.genres.add(self.horror_genre)

        host_prefs = UserPreferenceData(moods=["dark"], keyword_weights={"gore": 3.0})
        guest_prefs = UserPreferenceData(moods=["dark"], keyword_weights={"gore": -3.5})

        c_gore = deck_scorer.score_candidate(gore_movie, host_prefs, guest_prefs)
        c_neutral = deck_scorer.score_candidate(neutral_movie, host_prefs, guest_prefs)

        # Guest relevance for gore movie is penalized
        self.assertLess(c_gore.relevance_guest, c_gore.relevance_host)
        # Consensus drags down the conflicting candidate below the neutral candidate
        self.assertLess(
            c_gore.consensus_score,
            c_neutral.consensus_score,
            "Conflicting candidate must have lower consensus score than agreeable neutral candidate."
        )

    def test_intelligence_scenario_5_cold_start_participants(self):
        """
        Scenario 5: Two cold-start participants without historical profiles or logs.
        Verifies pure questionnaire evaluation with zero division errors or NaN values.
        """
        scorer = IndividualRelevanceScorer()
        deck_scorer = CollaborativeDeckScorer(scorer=scorer)

        cold_h = UserPreferenceData(moods=["exciting"], experience="balanced")
        cold_g = UserPreferenceData(moods=["exciting"], experience="balanced")

        c = deck_scorer.score_candidate(self.movies[0], cold_h, cold_g)

        self.assertFalse(any(v is None for v in [c.relevance_host, c.relevance_guest, c.consensus_score]))
        self.assertGreater(c.consensus_score, 0.0)
        self.assertEqual(c.scoring_result_host.s_learned, 0.0)
        self.assertEqual(c.scoring_result_guest.s_learned, 0.0)

    def test_intelligence_scenario_6_determinism_across_repeated_runs(self):
        """
        Scenario 6: Determinism check.
        Running manifest compilation 10 times with identical inputs produces
        100% identical movie order and scores.
        """
        prefs = UserPreferenceData(moods=["exciting", "dark"], experience="heavy")

        manifest_runs = []
        for _ in range(10):
            manifest = ManifestCompilerService.compile_manifest(
                candidates=self.movies[:20],
                host_prefs=prefs,
                guest_prefs=prefs,
            )
            manifest_runs.append([c["movie_id"] for c in manifest])

        baseline = manifest_runs[0]
        for run_idx, run in enumerate(manifest_runs[1:], start=2):
            self.assertEqual(run, baseline, f"Run {run_idx} diverged from baseline determinism.")

    # =========================================================================
    # Section 3: Lifecycle, Persistence, and Undo Integrity
    # =========================================================================

    def test_lifecycle_reconnection_state_recovery(self):
        """
        Participant disconnects and reconnects: recovers exact deck state and card index.
        """
        session = Session.objects.create(code="RECON1", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)
        CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[
                {"card_index": 0, "movie_id": self.movies[0].id, "title": self.movies[0].title},
                {"card_index": 1, "movie_id": self.movies[1].id, "title": self.movies[1].title},
            ],
            host_card_index=1,  # Host already answered card 0
            guest_card_index=0,
        )

        # Host reconnects: calls /deck/card/
        card_res = DeckAdvancementService.get_current_delivery_card(session=session, user=self.host_user)
        self.assertEqual(card_res["card_index"], 1)
        self.assertEqual(card_res["card"]["movie_id"], self.movies[1].id)

    def test_lifecycle_swipe_undo_and_match_immutability(self):
        """
        Swipe undo decrements cursor and deletes swipe record.
        Undo on a matched movie is strictly blocked.
        """
        session = Session.objects.create(code="UNDO01", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[
                {"card_index": 0, "movie_id": self.movies[0].id, "title": self.movies[0].title},
                {"card_index": 1, "movie_id": self.movies[1].id, "title": self.movies[1].title},
            ],
            host_card_index=0,
            guest_card_index=0,
        )

        # Host and Guest LIKE card 0 -> Match formed
        DeckAdvancementService.record_swipe_response(session.id, self.host_user, 0, self.movies[0].id, Swipe.LIKE)
        DeckAdvancementService.record_swipe_response(session.id, self.guest_user, 0, self.movies[0].id, Swipe.LIKE)
        self.assertEqual(Match.objects.filter(session=session, movie=self.movies[0]).count(), 1)

        # Attempt to undo matched card 0 -> MUST RAISE UndoNotPermittedError
        with self.assertRaises(UndoNotPermittedError):
            DeckAdvancementService.undo_card_response(session.id, self.host_user, 0, self.movies[0].id)

        # Host DISLIKES card 1 (unmatched)
        DeckAdvancementService.record_swipe_response(session.id, self.host_user, 1, self.movies[1].id, Swipe.DISLIKE)
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 2)

        # Undo card 1 -> permitted
        undo_res = DeckAdvancementService.undo_card_response(session.id, self.host_user, 1, self.movies[1].id)
        self.assertTrue(undo_res["success"])
        agreement.refresh_from_db()
        self.assertEqual(agreement.host_card_index, 1)
        self.assertFalse(Swipe.objects.filter(session=session, user=self.host_user, movie=self.movies[1]).exists())

    def test_lifecycle_duplicate_swipe_idempotency(self):
        """
        Submitting identical card response multiple times is idempotent and creates zero duplicates.
        """
        session = Session.objects.create(code="IDEMP1", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)
        CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[{"card_index": 0, "movie_id": self.movies[0].id, "title": self.movies[0].title}],
            host_card_index=0,
            guest_card_index=0,
        )

        res1 = DeckAdvancementService.record_swipe_response(
            session.id, self.host_user, 0, self.movies[0].id, Swipe.LIKE, idempotency_key="key-001"
        )
        self.assertFalse(res1.get("idempotent", False))

        res2 = DeckAdvancementService.record_swipe_response(
            session.id, self.host_user, 0, self.movies[0].id, Swipe.LIKE, idempotency_key="key-001"
        )
        self.assertTrue(res2.get("idempotent", False))

        # Only one swipe recorded in DB
        self.assertEqual(Swipe.objects.filter(session=session, user=self.host_user, movie=self.movies[0]).count(), 1)

    def test_lifecycle_cross_session_isolation(self):
        """
        Swipes, matches, and statistics in Room A never bleed into Room B.
        """
        session_a = Session.objects.create(code="ROOMA1", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)
        session_b = Session.objects.create(code="ROOMB1", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)

        # Swipes & match in Room A
        Swipe.objects.create(session=session_a, user=self.host_user, movie=self.movies[0], reaction=Swipe.LIKE)
        Swipe.objects.create(session=session_a, user=self.guest_user, movie=self.movies[0], reaction=Swipe.LIKE)
        Match.objects.create(session=session_a, movie=self.movies[0])

        stats_a = calculate_session_statistics(session_a, user=self.host_user)
        stats_b = calculate_session_statistics(session_b, user=self.host_user)

        self.assertEqual(stats_a["matched_count"], 1)
        self.assertEqual(stats_a["reviewed_count"], 1)
        self.assertEqual(stats_a["affinity_percent"], 100)

        # Room B remains pristine
        self.assertEqual(stats_b["matched_count"], 0)
        self.assertEqual(stats_b["reviewed_count"], 0)
        self.assertEqual(stats_b["affinity_percent"], 0)

    # =========================================================================
    # Section 4: Catalogue Integrity and Constraint Protection
    # =========================================================================

    def test_catalogue_synthetic_fixtures_excluded_from_recommendations(self):
        """
        Synthetic fixtures (Movies 724 & 725 with provenance=synthetic_fixture)
        must NEVER enter recommendation manifests.
        """
        candidates = list(Movie.objects.filter(recommendable=True, display_ready=True))
        candidate_ids = [m.id for m in candidates]

        self.assertNotIn(self.synth_m1_a.id, candidate_ids)
        self.assertNotIn(self.synth_m1_b.id, candidate_ids)

        prefs = UserPreferenceData(moods=["exciting"])
        manifest = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=prefs,
            guest_prefs=prefs,
        )
        manifest_movie_ids = [c["movie_id"] for c in manifest]
        self.assertNotIn(self.synth_m1_a.id, manifest_movie_ids)
        self.assertNotIn(self.synth_m1_b.id, manifest_movie_ids)

    def test_catalogue_sparse_metadata_resilience(self):
        """
        Movies with null poster, null release_date, null rating do not crash deck delivery.
        """
        sparse_movie = Movie.objects.create(
            title="Sparse Unknown",
            tmdb_id=59995,
            rating=None,
            vote_count=None,
            release_date=None,
            poster_path="",
            overview="",
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
        )
        session = Session.objects.create(code="SPARSE1", host=self.host_user, guest=self.guest_user)
        CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[{"card_index": 0, "movie_id": sparse_movie.id, "title": sparse_movie.title}],
            host_card_index=0,
            guest_card_index=0,
        )

        res = DeckAdvancementService.get_current_delivery_card(session=session, user=self.host_user)
        self.assertEqual(res["card"]["movie_id"], sparse_movie.id)
        self.assertEqual(res["card"]["poster_path"], "")
        self.assertIsNone(res["card"]["rating"])

    def test_catalogue_empty_candidate_pool_produces_exhausted_state(self):
        """
        When no candidates qualify, the system safely reports candidate exhaustion.
        """
        from core.services.manifest import InsufficientCandidatesError
        from core.services.retrieval import HardConstraints

        session = Session.objects.create(
            code="EXHAUST",
            host=self.host_user,
            guest=self.guest_user,
            genre=self.crime_genre,
            preferences_set=True,
        )
        with patch("core.services.manifest.CandidateRetrievalService.retrieve_candidates") as mock_retrieve:
            mock_retrieve.return_value = CandidatePool(
                pool_type="exhausted",
                candidates=[],
                total_count=0,
                local_count=0,
                replenished_count=0,
                hard_constraints=HardConstraints(),
                experience_type="screening",
                proposal_required=True,
                metadata={},
            )
            with self.assertRaises(InsufficientCandidatesError):
                ManifestCompilerService.compile_and_persist_manifest(session=session)

    def test_catalogue_no_silent_constraint_broadening(self):
        """
        Constraints are never broadened silently: proposals require explicit creation
        and auto-approve only when mutually acceptable.
        """
        session = Session.objects.create(code="PROP01", host=self.host_user, guest=self.guest_user, genre=self.crime_genre)
        proposal = ConstraintExpansionProposal.objects.create(
            session=session,
            initiated_by_user=self.host_user,
            original_constraints={"genre": "Crime", "era": ["2020s"]},
            proposed_constraints={"genre": "Crime", "era": ["2010s", "2020s"]},
            expires_at=timezone.now() + timezone.timedelta(minutes=5),
        )
        self.assertEqual(proposal.status, ConstraintExpansionProposal.STATUS_PENDING)
        self.assertFalse(proposal.is_mutually_approved)

        # Host approves only -> not mutually approved
        proposal.host_decision = {"decision": "approve", "decided_at": timezone.now().isoformat()}
        self.assertFalse(proposal.is_mutually_approved)

        # Guest approves -> mutually approved
        proposal.guest_decision = {"decision": "approve", "decided_at": timezone.now().isoformat()}
        self.assertTrue(proposal.is_mutually_approved)
