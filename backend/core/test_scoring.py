import math
from datetime import date
from decimal import Decimal
from django.test import TestCase

from core.models import Movie, Genre
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    ScoringConfig,
    UserPreferenceData,
)


class ScoringServiceTestCase(TestCase):
    def setUp(self):
        self.config = ScoringConfig()
        self.scorer = IndividualRelevanceScorer(config=self.config)

    # -------------------------------------------------------------
    # 1. Normalization & Saturation Tests
    # -------------------------------------------------------------
    def test_normalization_bounds_and_saturation_prevention(self):
        # Exact maximum positive score
        self.assertAlmostEqual(self.scorer.normalize_score(115.0), 1.0, places=6)

        # High score below maximum (must NOT saturate to 1.0)
        norm_100 = self.scorer.normalize_score(100.0)
        self.assertAlmostEqual(norm_100, 100.0 / 115.0, places=6)
        self.assertLess(norm_100, 1.0)
        self.assertGreater(norm_100, 0.86)

        # Distinguish 100 from 115
        self.assertNotEqual(self.scorer.normalize_score(100.0), self.scorer.normalize_score(115.0))

        # Clamp lower bound
        self.assertEqual(self.scorer.normalize_score(0.0), 0.0)
        self.assertEqual(self.scorer.normalize_score(-15.0), 0.0)
        self.assertEqual(self.scorer.normalize_score(-30.0), 0.0)

        # Clamp upper bound (if score exceeds theoretical max)
        self.assertEqual(self.scorer.normalize_score(130.0), 1.0)

    # -------------------------------------------------------------
    # 2. Dimension-Specific Confidence Attenuation Tests
    # -------------------------------------------------------------
    def test_confidence_attenuation_cutoff(self):
        # At or below 0.35 cutoff, kappa is 0.0
        self.assertEqual(self.scorer.compute_attenuation(0.0), 0.0)
        self.assertEqual(self.scorer.compute_attenuation(0.20), 0.0)
        self.assertEqual(self.scorer.compute_attenuation(0.35), 0.0)

        # Above cutoff, kappa scales linearly to 1.0
        self.assertAlmostEqual(self.scorer.compute_attenuation(0.675), 0.5, places=6)
        self.assertAlmostEqual(self.scorer.compute_attenuation(1.0), 1.0, places=6)

    def test_tonality_score_confidence_attenuation(self):
        user_moods = ["uplifted"]
        movie_dist = {"uplifted": 1.0, "thrilled": 0.0}

        # Full confidence (1.0) -> full evidence score (30.0)
        score_full, kappa_full = self.scorer.calculate_tonality_score(user_moods, movie_dist, 1.0)
        self.assertAlmostEqual(score_full, 30.0, places=4)
        self.assertAlmostEqual(kappa_full, 1.0, places=4)

        # Zero / low confidence (0.20 <= 0.35) -> attenuates to neutral baseline (15.0)
        score_low, kappa_low = self.scorer.calculate_tonality_score(user_moods, movie_dist, 0.20)
        self.assertAlmostEqual(score_low, 15.0, places=4)
        self.assertEqual(kappa_low, 0.0)

    # -------------------------------------------------------------
    # 3. Optional Questions & Neutral Baseline Handling
    # -------------------------------------------------------------
    def test_narrative_skipped_q2_yields_neutral_baseline(self):
        # User skips Q2 (empty list) -> neutral baseline 10.0 pts regardless of movie distribution
        movie_dist = {"character": 1.0, "plot": 0.5}
        score, kappa = self.scorer.calculate_narrative_score([], movie_dist, 1.0)
        self.assertEqual(score, 10.0)

    def test_thematic_skipped_q3_yields_neutral_baseline(self):
        # User skips Q3 (empty list) -> neutral baseline 12.5 pts
        movie_dist = {"identity_growth": 1.0}
        score, kappa = self.scorer.calculate_thematic_score([], movie_dist, 1.0)
        self.assertEqual(score, 12.5)

    def test_pacing_q4_any_yields_neutral_baseline(self):
        # Q4 selected as 'any' -> neutral baseline 7.5 pts
        score, kappa = self.scorer.calculate_pacing_score("any", 0.9, 0.9, 1.0, 1.0)
        self.assertEqual(score, 7.5)

    # -------------------------------------------------------------
    # 4. Pacing-Vector Distance Mapping Tests
    # -------------------------------------------------------------
    def test_pacing_distance_mapping(self):
        # Target balanced: (0.50, 0.50)
        # Exact match (0.50, 0.50) -> dist = 0.0 -> max score 15.0
        score_perfect, _ = self.scorer.calculate_pacing_score("balanced", 0.50, 0.50, 1.0, 1.0)
        self.assertAlmostEqual(score_perfect, 15.0, places=4)

        # Opposite corner: (0.0, 0.0) from (1.0, 1.0) -> dist = sqrt(2) -> score = 0.0
        score_far, _ = self.scorer.calculate_pacing_score("balanced", 0.50 + 1.0, 0.50 + 1.0, 1.0, 1.0)
        # Clamped coordinates test
        score_zero, _ = self.scorer.calculate_pacing_score("light", 0.0, 1.0, 1.0, 1.0)
        self.assertGreaterEqual(score_zero, 0.0)
        self.assertLessEqual(score_zero, 15.0)

        # Composite confidence uses min(confidence_pacing, confidence_gravity)
        score_comp, kappa_comp = self.scorer.calculate_pacing_score(
            "balanced", 0.50, 0.50, confidence_pacing=1.0, confidence_gravity=0.10
        )
        # Since confidence_gravity is 0.10 <= 0.35, composite kappa is 0.0 -> reverts to 7.5
        self.assertEqual(score_comp, 7.5)
        self.assertEqual(kappa_comp, 0.0)

    # -------------------------------------------------------------
    # 5. Bayesian Quality Bonus Tests
    # -------------------------------------------------------------
    def test_bayesian_quality_bonus_general_and_classic(self):
        # General release (post-1990): m = 500, C = 0.68
        # v = 2400, R = 8.2
        # Expected: 10.0 * [(2400/2900) * 0.82 + (500/2900) * 0.68] = 7.95862...
        q_gen = self.scorer.calculate_quality_bonus(
            vote_average=8.2,
            vote_count=2400,
            release_date=date(2018, 5, 1)
        )
        expected_gen = 10.0 * ((2400.0 / 2900.0) * 0.82 + (500.0 / 2900.0) * 0.68)
        self.assertAlmostEqual(q_gen, expected_gen, places=4)
        self.assertAlmostEqual(q_gen, 7.9586, places=3)

        # Classic release (pre-1990): m = 100, C = 0.68
        # v = 80, R = 7.6, release_date = 1974
        # Expected: 10.0 * [(80/180) * 0.76 + (100/180) * 0.68] = 7.15555...
        q_classic = self.scorer.calculate_quality_bonus(
            vote_average=7.6,
            vote_count=80,
            release_date=date(1974, 11, 1)
        )
        expected_classic = 10.0 * ((80.0 / 180.0) * 0.76 + (100.0 / 180.0) * 0.68)
        self.assertAlmostEqual(q_classic, expected_classic, places=4)
        self.assertAlmostEqual(q_classic, 7.1556, places=3)

        # Zero votes returns prior baseline (6.8 pts)
        q_zero = self.scorer.calculate_quality_bonus(vote_average=0.0, vote_count=0)
        self.assertAlmostEqual(q_zero, 6.80, places=4)

    # -------------------------------------------------------------
    # 6. True 14-Day Fatigue Half-Life Tests
    # -------------------------------------------------------------
    def test_fatigue_penalty_true_14_day_half_life(self):
        # Single impression at t = 0 -> weight = 5.0
        p_0 = self.scorer.calculate_fatigue_penalty([0.0])
        self.assertAlmostEqual(p_0, 5.0, places=4)

        # Single impression at t = 14 days -> decay = 2^(-14/14) = 0.5 -> weight = 2.5
        p_14 = self.scorer.calculate_fatigue_penalty([14.0])
        self.assertAlmostEqual(p_14, 2.5, places=4)

        # Single impression at t = 28 days -> decay = 2^(-28/14) = 0.25 -> weight = 1.25
        p_28 = self.scorer.calculate_fatigue_penalty([28.0])
        self.assertAlmostEqual(p_28, 1.25, places=4)

        # Multiple impressions summed and clamped at 15.0
        p_huge = self.scorer.calculate_fatigue_penalty([0.0, 0.0, 0.0, 0.0])  # 4 * 5 = 20 -> clamped to 15.0
        self.assertEqual(p_huge, 15.0)

    # -------------------------------------------------------------
    # 7. Learned Feedback & 60-Day Half-Life Tests
    # -------------------------------------------------------------
    def test_learned_feedback_60_day_half_life_and_clamping(self):
        # Superlike (3.0) at t = 0 -> 3.0
        fb_0 = self.scorer.calculate_learned_feedback([(3.0, 0.0)])
        self.assertAlmostEqual(fb_0, 3.0, places=4)

        # Superlike (3.0) at t = 60 days -> 3.0 * 2^(-1) = 1.5
        fb_60 = self.scorer.calculate_learned_feedback([(3.0, 60.0)])
        self.assertAlmostEqual(fb_60, 1.5, places=4)

        # Clamping at +15.0
        fb_pos_clamp = self.scorer.calculate_learned_feedback([(10.0, 0.0), (10.0, 0.0)])
        self.assertEqual(fb_pos_clamp, 15.0)

        # Clamping at -15.0
        fb_neg_clamp = self.scorer.calculate_learned_feedback([(-12.0, 0.0), (-8.0, 0.0)])
        self.assertEqual(fb_neg_clamp, -15.0)

    # -------------------------------------------------------------
    # 8. All Six Worked Examples Tests
    # -------------------------------------------------------------
    def test_worked_example_1_full_confidence_strong_match(self):
        # Mood uplifted (cosine 28.5 / 30), story character (19.0 / 20), theme identity_growth (23.5 / 25),
        # pacing balanced (14.0 / 15), quality R=8.2, v=2400 (7.96 pts), learned +10.0, fatigue 0.0
        movie = MovieIntelligenceData(
            title="Full Confidence Match",
            vote_average=8.2,
            vote_count=2400,
            tonality_distribution={"uplifted": 0.95},
            narrative_distribution={"character": 0.95},
            thematic_distribution={"identity_growth": 0.94},
            pacing_score=0.50,
            emotional_gravity=0.50,
            confidence_tone=1.0,
            confidence_narrative=1.0,
            confidence_theme=1.0,
            confidence_pacing=1.0,
            confidence_gravity=1.0,
        )
        prefs = UserPreferenceData(
            moods=["uplifted"],
            narrative=["character"],
            themes=["identity_growth"],
            experience="balanced",
            direct_learned_score=10.0,
        )
        res = self.scorer.score(movie, prefs)
        self.assertGreater(res.relevance, 0.85)
        self.assertLessEqual(res.relevance, 1.0)
        self.assertGreater(res.raw_score, 95.0)

    def test_worked_example_2_missing_metadata(self):
        # Missing metadata: all confidences 0.0 -> all inferred dimensions attenuate to neutral baselines
        # Tone: 15.0, Narrative: 10.0, Theme: 12.5, Pace: 7.5
        # Quality: R=7.6, v=80, classic (1974) -> 7.1555...
        # Raw = 15.0 + 10.0 + 12.5 + 7.5 + 7.1555 = 52.1555...
        # Rel = 52.1555 / 115.0 = 0.4535...
        movie = MovieIntelligenceData(
            title="Sparse Classic",
            vote_average=7.6,
            vote_count=80,
            release_date=date(1974, 1, 1),
            confidence_tone=0.0,
            confidence_narrative=0.0,
            confidence_theme=0.0,
            confidence_pacing=0.0,
            confidence_gravity=0.0,
        )
        prefs = UserPreferenceData(
            moods=["uplifted"],
            narrative=["character"],
            themes=["identity_growth"],
            experience="balanced",
        )
        res = self.scorer.score(movie, prefs)
        self.assertAlmostEqual(res.s_tone, 15.0, places=4)
        self.assertAlmostEqual(res.s_narrative, 10.0, places=4)
        self.assertAlmostEqual(res.s_theme, 12.5, places=4)
        self.assertAlmostEqual(res.s_pace, 7.5, places=4)
        self.assertAlmostEqual(res.s_quality, 7.1556, places=3)
        self.assertAlmostEqual(res.raw_score, 52.1556, places=3)
        self.assertAlmostEqual(res.relevance, 52.1556 / 115.0, places=3)

    def test_worked_example_3_low_confidence_evidence(self):
        # Inferred evidence exists but confidence is 0.20 <= 0.35 -> kappa = 0.0 -> neutral baseline
        movie = MovieIntelligenceData(
            narrative_distribution={"character": 1.0},
            confidence_narrative=0.20,
        )
        prefs = UserPreferenceData(narrative=["character"])
        res = self.scorer.score(movie, prefs)
        self.assertEqual(res.s_narrative, 10.0)
        self.assertEqual(res.kappa_narrative, 0.0)

    def test_worked_example_4_skipped_q2_and_q3(self):
        # Q2 and Q3 skipped -> neutral baselines 10.0 and 12.5
        movie = MovieIntelligenceData(
            tonality_distribution={"thrilled": 1.0},
            confidence_tone=1.0,
            pacing_score=0.40,
            emotional_gravity=0.85,
            confidence_pacing=1.0,
            confidence_gravity=1.0,
            vote_average=8.0,
            vote_count=1000,
            release_date=date(2020, 1, 1),
        )
        prefs = UserPreferenceData(
            moods=["thrilled"],
            narrative=[],  # skipped
            themes=[],     # skipped
            experience="heavy",
        )
        res = self.scorer.score(movie, prefs)
        self.assertEqual(res.s_narrative, 10.0)
        self.assertEqual(res.s_theme, 12.5)
        self.assertAlmostEqual(res.s_tone, 30.0, places=4)
        self.assertAlmostEqual(res.s_pace, 15.0, places=4)

    def test_worked_example_5_q4_any(self):
        movie = MovieIntelligenceData(
            pacing_score=0.9,
            emotional_gravity=0.9,
            confidence_pacing=1.0,
            confidence_gravity=1.0,
        )
        prefs = UserPreferenceData(experience="any")
        res = self.scorer.score(movie, prefs)
        self.assertEqual(res.s_pace, 7.5)

    def test_worked_example_6_negative_learned_feedback_and_fatigue(self):
        movie = MovieIntelligenceData(
            vote_average=7.0,
            vote_count=500,
        )
        prefs = UserPreferenceData(
            direct_learned_score=-12.0,
            unswiped_impressions=[0.0, 14.0],  # 5.0 + 2.5 = 7.5 penalty
        )
        res = self.scorer.score(movie, prefs)
        self.assertEqual(res.s_learned, -12.0)
        self.assertAlmostEqual(res.p_fatigue, 7.5, places=4)
        self.assertLess(res.relevance, 0.5)

    # -------------------------------------------------------------
    # 9. Direct Django Movie Model Instance Scoring
    # -------------------------------------------------------------
    def test_direct_django_movie_model_scoring(self):
        genre = Genre.objects.create(tmdb_id=28, name="Action")
        movie = Movie.objects.create(
            tmdb_id=12345,
            title="Action Blast",
            rating=7.5,
            vote_count=1200,
            release_date=date(2021, 6, 1),
        )
        movie.genres.add(genre)

        prefs = UserPreferenceData(
            moods=["thrilled"],
            experience="balanced",
        )
        res = self.scorer.score(movie, prefs)
        self.assertIsInstance(res.relevance, float)
        self.assertGreaterEqual(res.relevance, 0.0)
        self.assertLessEqual(res.relevance, 1.0)
        self.assertEqual(res.details["movie_id"], movie.id)
        self.assertEqual(res.details["title"], "Action Blast")
