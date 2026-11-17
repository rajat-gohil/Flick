"""
Test suite for Flick Room Recommendation Intelligence (Stage 2).
Covers:
- Part A: 10 Affinity & Compatibility evaluation tests
- Part E: Scenarios A through G (controlled evaluation fixtures)
- Part F: Performance & determinism benchmarks
"""

import time
from datetime import date
from typing import Any, Dict, List
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    CollaborativeAgreement,
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
    calculate_taste_compatibility,
    normalize_user_preferences,
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


class AffinityEvaluationTests(TestCase):
    """
    Part A: Comprehensive unit tests for affinity, similarity, and compatibility.
    Requirements:
    1. Both participants submit identical complete answers.
    2. Both participants submit completely different answers.
    3. Both participants submit partially matching answers.
    4. Same answers are submitted repeatedly.
    5. Same answers are submitted in a different order.
    6. One participant has missing answers.
    7. Both participants are cold-start users.
    8. Different individual taste profiles but identical questionnaires.
    9. Identical complete inputs produce identical results across repeated calculations.
    10. Refreshing and reopening a completed session restores the same Affinity value.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")

    def test_01_both_submit_identical_complete_answers(self):
        """1. Identical complete questionnaire answers yield exactly 100% similarity."""
        host_prefs = {
            "mood": ["tense", "dark"],
            "tone": ["suspenseful", "dark"],
            "intensity": "heavy",
            "pace": ["fast", "slow"],
            "themes": ["psychological", "supernatural"],
            "theme_keywords": ["mind games", "ghost"],
            "setting": ["isolated"],
            "setting_keywords": ["cabin", "woods"],
            "narrative": ["linear", "slow burn"],
            "era": ["2010s", "2020s"],
            "min_rating": [7.0],
        }
        guest_prefs = dict(host_prefs)

        score = calculate_questionnaire_similarity(host_prefs, guest_prefs)
        self.assertEqual(score, 100)

    def test_02_both_submit_completely_different_answers(self):
        """2. Completely disjoint questionnaire answers yield 0% similarity."""
        host_prefs = {
            "mood": ["tense"],
            "tone": ["dark"],
            "intensity": "heavy",
            "themes": ["slasher"],
            "theme_keywords": ["chainsaw", "gore"],
            "setting": ["suburbia"],
            "setting_keywords": ["neighborhood"],
            "narrative": ["linear"],
            "era": ["1980s"],
        }
        guest_prefs = {
            "mood": ["lighthearted"],
            "tone": ["fun"],
            "intensity": "light",
            "themes": ["comedy"],
            "theme_keywords": ["slapstick", "parody"],
            "setting": ["space"],
            "setting_keywords": ["spaceship"],
            "narrative": ["twist"],
            "era": ["2020s"],
        }

        score = calculate_questionnaire_similarity(host_prefs, guest_prefs)
        self.assertEqual(score, 0)

    def test_03_partially_matching_answers(self):
        """3. Partially matching answers yield intermediate percentage strictly in (0%, 100%)."""
        host_prefs = {
            "mood": ["tense", "dark"],
            "themes": ["psychological", "supernatural"],
            "intensity": "heavy",
            "setting": ["isolated"],
            "era": ["2010s"],
        }
        guest_prefs = {
            "mood": ["tense", "fun"],  # partial mood match (1 of 3 union)
            "themes": ["psychological", "slasher"],  # partial theme match (1 of 3 union)
            "intensity": "heavy",  # full pace match
            "setting": ["space"],  # disjoint setting
            "era": ["2010s"],  # full era match
        }

        score = calculate_questionnaire_similarity(host_prefs, guest_prefs)
        self.assertGreater(score, 0)
        self.assertLess(score, 100)
        self.assertIsInstance(score, int)

    def test_04_repeated_identical_submissions(self):
        """4. Repeated evaluations with identical inputs produce identical percentage."""
        prefs_a = {
            "mood": ["tense", "mysterious"],
            "themes": ["survival"],
            "intensity": "medium",
            "era": ["2000s"],
        }
        prefs_b = {
            "mood": ["tense", "dark"],
            "themes": ["survival"],
            "intensity": "medium",
            "era": ["2000s"],
        }

        first_eval = calculate_questionnaire_similarity(prefs_a, prefs_b)
        for _ in range(10):
            self.assertEqual(calculate_questionnaire_similarity(prefs_a, prefs_b), first_eval)

    def test_05_order_invariance(self):
        """5. Same answers submitted in different ordering yield identical percentage."""
        prefs_order_1 = {
            "mood": ["tense", "dark", "bleak"],
            "themes": ["isolation", "psychological", "supernatural"],
            "setting": ["isolated", "cabin"],
            "era": ["1990s", "2000s"],
        }
        prefs_order_2 = {
            "mood": ["bleak", "tense", "dark"],
            "themes": ["supernatural", "isolation", "psychological"],
            "setting": ["cabin", "isolated"],
            "era": ["2000s", "1990s"],
        }
        partner_prefs = {
            "mood": ["dark", "atmospheric"],
            "themes": ["psychological"],
            "setting": ["isolated"],
            "era": ["2000s"],
        }

        score_1 = calculate_questionnaire_similarity(prefs_order_1, partner_prefs)
        score_2 = calculate_questionnaire_similarity(prefs_order_2, partner_prefs)
        self.assertEqual(score_1, score_2)

    def test_06_missing_answers_penalized(self):
        """6. One participant having missing answers is not treated as compatibility."""
        full_prefs = {
            "mood": ["tense", "dark"],
            "themes": ["psychological"],
            "setting": ["space"],
            "narrative": ["mind-bending"],
            "intensity": "heavy",
            "era": ["2020s"],
        }
        empty_prefs: Dict[str, Any] = {}

        score = calculate_questionnaire_similarity(full_prefs, empty_prefs)
        self.assertEqual(score, 0)

        partial_prefs = {
            "mood": ["tense", "dark"],
            # missing themes, setting, narrative, era
        }
        score_partial = calculate_questionnaire_similarity(full_prefs, partial_prefs)
        # Should be strictly lower than complete match
        self.assertLess(score_partial, 100)

    def test_07_cold_start_empty_answers(self):
        """7. Cold start with empty answers returns 0% without fabricated numbers."""
        score = calculate_questionnaire_similarity({}, {})
        self.assertEqual(score, 0)

        score_none = calculate_questionnaire_similarity(None, None)
        self.assertEqual(score_none, 0)

    def test_08_different_taste_profiles_identical_questionnaires(self):
        """
        8. Different individual taste profiles with identical questionnaires:
        Questionnaire similarity is 100%, but taste compatibility honestly distinguishes them.
        """
        identical_questionnaire = {
            "mood": ["tense", "dark"],
            "themes": ["psychological"],
            "intensity": "medium",
            "era": ["2010s"],
        }
        q_sim = calculate_questionnaire_similarity(identical_questionnaire, identical_questionnaire)
        self.assertEqual(q_sim, 100)

        # Different learned weights in UserTasteProfile
        host_weights = {
            "genres": {"Horror": 3.0, "Mystery": 2.0},
            "keywords": {"ghost": 2.5, "haunted": 2.0},
        }
        guest_weights = {
            "genres": {"Comedy": 3.0, "Romance": 2.0},
            "keywords": {"slapstick": 2.5, "parody": 2.0},
        }

        taste_comp = calculate_taste_compatibility(host_weights, guest_weights)
        self.assertIsNotNone(taste_comp)
        # Disjoint weights should produce 50% (neutral zero-cosine baseline) or lower
        self.assertLessEqual(taste_comp, 50)

        # Cold start user with no taste weights returns None honestly
        cold_comp = calculate_taste_compatibility(host_weights, None)
        self.assertIsNone(cold_comp)

    def test_09_deterministic_calculations_on_same_inputs(self):
        """9. Identical complete inputs produce identical results across repeated evaluations."""
        h = {"mood": ["dark"], "themes": ["gore"], "intensity": "heavy"}
        g = {"mood": ["dark"], "themes": ["gore"], "intensity": "heavy"}
        scores = [calculate_questionnaire_similarity(h, g) for _ in range(25)]
        self.assertTrue(all(s == scores[0] for s in scores))

    def test_10_screening_affinity_restoration_on_completed_session(self):
        """
        10. Refreshing and reopening a completed session restores the same Affinity value.
        Matches / Reviewed is persisted on SessionStats and restored authoritatively.
        """
        session = Session.objects.create(code="AFFTEST", host=self.host, guest=self.guest)
        genre = Genre.objects.create(name="Horror", tmdb_id=27)
        movies = [
            Movie.objects.create(title=f"Movie {i}", tmdb_id=90000 + i, rating=7.5, vote_count=200)
            for i in range(10)
        ]

        # Host and Guest review 9 movies
        for m in movies[:9]:
            Swipe.objects.create(session=session, user=self.host, movie=m, reaction="like")
            Swipe.objects.create(session=session, user=self.guest, movie=m, reaction="like")

        # 3 of them become mutual matches
        for m in movies[:3]:
            Match.objects.create(session=session, movie=m)

        # End session
        session.ended_at = timezone.now()
        session.save()

        # SessionStats stores total_swipes and total_matches
        stats = SessionStats.objects.create(
            session=session,
            total_swipes=18,
            total_matches=3,
        )

        from core.serializers import SessionDetailSerializer
        serializer = SessionDetailSerializer(session)
        data = serializer.data

        expected_affinity = round((3 / 9) * 100)  # 33%
        self.assertEqual(data["affinity_percent"], expected_affinity)
        self.assertEqual(data["reviewed_count"], 9)
        self.assertEqual(data["matched_count"], 3)

        # Verify recalculation/restoration yields exact same percentage
        restored = calculate_screening_affinity(reviewed_count=9, matched_count=3)
        self.assertEqual(restored, data["affinity_percent"])


class RoomRecommendationScenariosTestCase(TestCase):
    """
    Part E: Controlled Evaluation Fixtures (Scenarios A through G).
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_rec", password="password123")
        self.guest = User.objects.create_user(username="guest_rec", password="password123")
        self.scorer = IndividualRelevanceScorer()

        # Create Horror genre
        self.horror_genre = Genre.objects.create(name="Horror", tmdb_id=27)

        # Keywords
        self.kw_ghost = MovieKeyword.objects.create(name="ghost", tmdb_id=101)
        self.kw_mindgames = MovieKeyword.objects.create(name="mind games", tmdb_id=102)
        self.kw_paranoia = MovieKeyword.objects.create(name="paranoia", tmdb_id=103)
        self.kw_slasher = MovieKeyword.objects.create(name="slasher", tmdb_id=201)
        self.kw_chainsaw = MovieKeyword.objects.create(name="chainsaw", tmdb_id=202)
        self.kw_gore = MovieKeyword.objects.create(name="gore", tmdb_id=203)

        # Tags
        self.tag_psych = MovieTag.objects.create(name="psychological")
        self.tag_slasher = MovieTag.objects.create(name="slasher")

        # Movie A: Psychological Horror
        self.movie_psych = Movie.objects.create(
            title="Psychological Haunting",
            tmdb_id=71001,
            rating=7.5,
            vote_count=500,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
            release_date=date(2021, 5, 10),
        )
        self.movie_psych.genres.add(self.horror_genre)
        self.movie_psych.keywords.add(self.kw_ghost, self.kw_mindgames, self.kw_paranoia)
        self.movie_psych.tags.add(self.tag_psych)

        # Movie B: Slasher Gore Horror
        self.movie_slasher = Movie.objects.create(
            title="Camp Slasher Chainsaw",
            tmdb_id=71002,
            rating=7.5,
            vote_count=500,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
            release_date=date(2021, 5, 10),
        )
        self.movie_slasher.genres.add(self.horror_genre)
        self.movie_slasher.keywords.add(self.kw_slasher, self.kw_chainsaw, self.kw_gore)
        self.movie_slasher.tags.add(self.tag_slasher)

    def test_scenario_a_same_genre_different_questionnaires(self):
        """
        Scenario A: Two rooms select Horror.
        Room A prefers psychological/supernatural horror.
        Room B prefers slasher/survival/gore horror.
        Expected: Movie rankings reflect these questionnaire differences.
        """
        # Room A preferences
        prefs_room_a = normalize_user_preferences({
            "themes": ["psychological", "supernatural"],
            "theme_keywords": ["ghost", "mind games", "paranoia"],
            "tone": ["dark", "suspenseful"],
            "intensity": "light",
        })
        user_prefs_a = UserPreferenceData(
            moods=prefs_room_a["moods"],
            themes=prefs_room_a["themes"],
            theme_keywords=prefs_room_a["theme_keywords"],
            experience=prefs_room_a["experience"],
        )

        # Room B preferences
        prefs_room_b = normalize_user_preferences({
            "themes": ["slasher", "survival"],
            "theme_keywords": ["chainsaw", "gore", "slasher"],
            "tone": ["dark", "scary"],
            "intensity": "heavy",
        })
        user_prefs_b = UserPreferenceData(
            moods=prefs_room_b["moods"],
            themes=prefs_room_b["themes"],
            theme_keywords=prefs_room_b["theme_keywords"],
            experience=prefs_room_b["experience"],
        )

        res_a_psych = self.scorer.score(self.movie_psych, user_prefs_a)
        res_a_slasher = self.scorer.score(self.movie_slasher, user_prefs_a)

        res_b_psych = self.scorer.score(self.movie_psych, user_prefs_b)
        res_b_slasher = self.scorer.score(self.movie_slasher, user_prefs_b)

        # In Room A: Psychological Haunting must outscore Camp Slasher
        self.assertGreater(
            res_a_psych.normalized_relevance,
            res_a_slasher.normalized_relevance,
            "Room A (psychological preference) must rank psychological movie higher."
        )

        # In Room B: Camp Slasher must outscore Psychological Haunting
        self.assertGreater(
            res_b_slasher.normalized_relevance,
            res_b_psych.normalized_relevance,
            "Room B (slasher preference) must rank slasher movie higher."
        )

    def test_scenario_b_same_questionnaire_different_participants(self):
        """
        Scenario B: Same questionnaire, different historical taste profiles.
        Expected: Individual participant relevance and priority rankings differ.
        """
        common_questionnaire = normalize_user_preferences({
            "mood": ["tense"],
            "intensity": "balanced",
            "era": ["2020s"],
        })

        # Host loves psychological horror (high keyword weight)
        host_prefs = UserPreferenceData(
            moods=common_questionnaire["moods"],
            experience=common_questionnaire["experience"],
            keyword_weights={"ghost": 3.0, "mind games": 2.5, "paranoia": 2.0},
        )

        # Guest loves slasher horror (high keyword weight)
        guest_prefs = UserPreferenceData(
            moods=common_questionnaire["moods"],
            experience=common_questionnaire["experience"],
            keyword_weights={"slasher": 3.0, "chainsaw": 2.5, "gore": 2.0},
        )

        deck_scorer = CollaborativeDeckScorer(scorer=self.scorer)
        c_psych = deck_scorer.score_candidate(self.movie_psych, host_prefs, guest_prefs)
        c_slasher = deck_scorer.score_candidate(self.movie_slasher, host_prefs, guest_prefs)

        # Host relevance for psychological movie should be significantly higher than Guest relevance
        self.assertGreater(c_psych.relevance_host, c_psych.relevance_guest)

        # Guest relevance for slasher movie should be significantly higher than Host relevance
        self.assertGreater(c_slasher.relevance_guest, c_slasher.relevance_host)

    def test_scenario_c_conflicting_preferences_and_negative_penalty(self):
        """
        Scenario C: Conflicting preferences.
        One participant likes gore; the other dislikes gore (negative weight).
        Expected: Negative penalty suppresses individual relevance and group consensus.
        """
        host_prefs = UserPreferenceData(
            moods=["tense"],
            keyword_weights={"gore": 2.5, "slasher": 2.0},  # Host likes gore
        )
        guest_prefs = UserPreferenceData(
            moods=["tense"],
            keyword_weights={"gore": -3.0},  # Guest strongly dislikes gore
        )

        deck_scorer = CollaborativeDeckScorer(scorer=self.scorer)
        c_slasher = deck_scorer.score_candidate(self.movie_slasher, host_prefs, guest_prefs)

        # Guest relevance should be penalized heavily
        self.assertLess(
            c_slasher.relevance_guest,
            c_slasher.relevance_host,
            "Disliked attribute must penalize guest relevance."
        )

        # Consensus (geometric mean) must be dragged down by guest dislike
        self.assertLess(
            c_slasher.consensus_score,
            c_slasher.relevance_host,
            "Consensus must be dragged down when one participant dislikes the movie."
        )

        # Verify negative attribute match is tracked transparently
        self.assertIn("keyword:gore", c_slasher.scoring_result_guest.details["matched_negative_attributes"])

    def test_scenario_d_cold_start_users(self):
        """
        Scenario D: Cold-start users without historical taste data.
        Expected: Recommendations rely purely on questionnaire preferences and movie quality
        without fabricated taste signals.
        """
        cold_prefs = UserPreferenceData(
            moods=["tense"],
            themes=["psychological"],
            theme_keywords=["ghost"],
            experience="balanced",
            # Zero learned weights
            genre_weights={},
            tag_weights={},
            keyword_weights={},
        )

        res = self.scorer.score(self.movie_psych, cold_prefs)
        self.assertEqual(res.s_learned, 0.0, "Cold start taste score must be exactly 0.0.")
        self.assertEqual(res.details["taste_contribution"], 0.0)
        self.assertGreater(res.relevance, 0.0)

    def test_scenario_e_identical_inputs_determinism(self):
        """
        Scenario E: Identical inputs produce identical scores and deterministic manifest.
        """
        session = Session.objects.create(code="DETTEST", host=self.host, guest=self.guest)
        agreement = CollaborativeAgreement.objects.create(session=session)

        # Create 20 candidate movies
        candidates = []
        for i in range(20):
            m = Movie.objects.create(
                title=f"Determinism Film {i:02d}",
                tmdb_id=88000 + i,
                rating=7.0 + (i % 3) * 0.5,
                vote_count=300 + i * 10,
                display_ready=True,
                recommendable=True,
                provenance="tmdb_catalogue",
                release_date=date(2020, 1, 1),
            )
            m.genres.add(self.horror_genre)
            candidates.append(m)

        prefs = UserPreferenceData(moods=["tense"], experience="balanced")

        manifest_1 = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=prefs,
            guest_prefs=prefs,
        )
        manifest_2 = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=prefs,
            guest_prefs=prefs,
        )

        self.assertEqual(len(manifest_1), len(manifest_2))
        movie_ids_1 = [c["movie_id"] for c in manifest_1]
        movie_ids_2 = [c["movie_id"] for c in manifest_2]
        self.assertEqual(movie_ids_1, movie_ids_2, "Manifest ordering must be 100% deterministic.")

    def test_scenario_f_missing_movie_metadata(self):
        """
        Scenario F: Missing movie metadata safely falls back to neutral baseline without crashing.
        """
        sparse_movie = Movie.objects.create(
            title="Sparse Movie",
            tmdb_id=79999,
            rating=None,
            vote_count=None,
            release_date=None,
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
        )
        prefs = UserPreferenceData(
            moods=["dark", "tense"],
            themes=["haunting"],
            experience="heavy",
            genre_weights={"Horror": 2.0},
        )

        res = self.scorer.score(sparse_movie, prefs)
        self.assertGreaterEqual(res.relevance, 0.0)
        self.assertLessEqual(res.relevance, 1.0)
        self.assertEqual(res.s_tone, 15.0, "Missing mood metadata falls back to neutral 15.0")
        self.assertEqual(res.s_theme, 12.5, "Missing theme metadata falls back to neutral 12.5")
        self.assertEqual(res.s_narrative, 10.0, "Missing narrative metadata falls back to neutral 10.0")

    def test_scenario_g_affinity_consistency(self):
        """
        Scenario G: Repeatedly calculate affinity with identical inputs.
        Expected: Exact same percentage every single time.
        """
        h_prefs = {"mood": ["dark", "tense"], "themes": ["supernatural"], "intensity": "medium"}
        g_prefs = {"mood": ["dark", "fun"], "themes": ["supernatural"], "intensity": "light"}

        initial = calculate_questionnaire_similarity(h_prefs, g_prefs)
        for _ in range(50):
            repeated = calculate_questionnaire_similarity(h_prefs, g_prefs)
            self.assertEqual(repeated, initial)

    def test_scoring_performance_benchmark(self):
        """
        Section 14: Scoring 40 candidates executes well under 50ms without N+1 queries.
        """
        candidates = [
            Movie(
                id=i,
                title=f"Perf Movie {i}",
                tmdb_id=60000 + i,
                rating=7.2,
                vote_count=450,
                release_date=date(2021, 1, 1),
            )
            for i in range(40)
        ]
        host_prefs = UserPreferenceData(moods=["tense", "dark"], themes=["psychological"])
        guest_prefs = UserPreferenceData(moods=["tense", "fun"], themes=["slasher"])

        deck_scorer = CollaborativeDeckScorer(scorer=self.scorer)
        start_time = time.perf_counter()
        scored = deck_scorer.score_candidate_pool(candidates, host_prefs, guest_prefs)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        self.assertEqual(len(scored), 40)
        # Bounded performance: 40 candidates in memory should score in under 30ms
        self.assertLess(elapsed_ms, 30.0, f"Scoring 40 candidates took {elapsed_ms:.2f}ms (threshold: 30ms)")
