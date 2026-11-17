from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    CollaborativeAgreement,
    Genre,
    InteractionLog,
    Match,
    Movie,
    MovieKeyword,
    MovieTag,
    Session,
    SessionOccasionState,
    Swipe,
    UserTasteProfile,
    WatchlistItem,
)
from core.services.retrieval import (
    CandidatePool,
    CandidateRetrievalService,
    EligibilityPolicyEngine,
    FilmNoirClassifier,
    HardConstraintFilter,
    HardConstraints,
    WorldCinemaClassifier,
    compute_learned_feedback_from_logs,
    normalize_candidate_metadata,
    rank_candidates_for_user,
)
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    ScoringConfig,
    UserPreferenceData,
)

User = get_user_model()


class CandidateRetrievalAndEligibilityTests(TestCase):
    """
    Workstream 3 Test Suite: Candidate Retrieval, Experience Eligibility,
    Hard Constraint Enforcement, Pool Classification, and Classifiers.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")
        self.session = Session.objects.create(
            code="WS3TEST",
            host=self.host,
            guest=self.guest,
        )
        self.genre_drama = Genre.objects.create(name="Drama", tmdb_id=18)
        self.genre_horror = Genre.objects.create(name="Horror", tmdb_id=27)
        self.genre_comedy = Genre.objects.create(name="Comedy", tmdb_id=35)
        self.genre_mystery = Genre.objects.create(name="Mystery", tmdb_id=9648)

    # -----------------------------------------------------------------
    # 1. Experience Eligibility Policy Tests
    # -----------------------------------------------------------------

    def test_screening_experience_excludes_swiped_and_matched(self):
        """Screening deck strictly excludes movies already swiped or matched in the session."""
        m1 = Movie.objects.create(tmdb_id=101, title="Swiped Movie", rating=7.5, release_date=date(2021, 1, 1), original_language="en")
        m2 = Movie.objects.create(tmdb_id=102, title="Matched Movie", rating=7.8, release_date=date(2021, 1, 1), original_language="en")
        m3 = Movie.objects.create(tmdb_id=103, title="Eligible Movie", rating=8.0, release_date=date(2021, 1, 1), original_language="en")
        m4 = Movie.objects.create(tmdb_id=104, title="Watchlisted Movie", rating=8.2, release_date=date(2021, 1, 1), original_language="en")

        # Record a swipe by host on m1
        Swipe.objects.create(session=self.session, user=self.host, movie=m1, reaction=Swipe.LIKE)
        # Record a match on m2
        Match.objects.create(session=self.session, movie=m2)
        # Record a watchlist item on m4 (should remain eligible)
        WatchlistItem.objects.create(user=self.host, movie=m4)

        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            experience_type=EligibilityPolicyEngine.EXPERIENCE_SCREENING,
            auto_replenish=False,
        )

        candidate_ids = {m.id for m in pool.candidates}
        self.assertNotIn(m1.id, candidate_ids, "Swiped movie must be strictly excluded from screening deck")
        self.assertNotIn(m2.id, candidate_ids, "Matched movie must be strictly excluded from screening deck")
        self.assertIn(m3.id, candidate_ids, "Unswiped movie must be eligible")
        self.assertIn(m4.id, candidate_ids, "Watchlisted movie must remain eligible")

    def test_discovery_experience_allows_swiped_and_matched(self):
        """Individual Discovery does not exclude movies swiped or matched in screening sessions."""
        m1 = Movie.objects.create(tmdb_id=201, title="Swiped in Session", rating=7.5, release_date=date(2021, 1, 1), original_language="en")
        Swipe.objects.create(session=self.session, user=self.host, movie=m1, reaction=Swipe.DISLIKE)

        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            experience_type=EligibilityPolicyEngine.EXPERIENCE_DISCOVERY,
            auto_replenish=False,
        )

        candidate_ids = {m.id for m in pool.candidates}
        self.assertIn(m1.id, candidate_ids, "Discovery experience must allow swiped movies")

    def test_archive_experience_allows_all(self):
        """Cinema Archives are permanent collections and remain 100% browseable."""
        m1 = Movie.objects.create(tmdb_id=301, title="Archive Classic", rating=8.5, release_date=date(1975, 1, 1), original_language="en")
        Swipe.objects.create(session=self.session, user=self.host, movie=m1, reaction=Swipe.DISLIKE)

        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            experience_type=EligibilityPolicyEngine.EXPERIENCE_ARCHIVE,
            auto_replenish=False,
        )

        candidate_ids = {m.id for m in pool.candidates}
        self.assertIn(m1.id, candidate_ids, "Cinema Archive experience must allow all movies regardless of swipe history")

    # -----------------------------------------------------------------
    # 2. Hard-Constraint Enforcement & Missing Metadata Rules
    # -----------------------------------------------------------------

    def test_min_rating_enforcement_and_missing_metadata(self):
        """Missing rating is NEVER treated as satisfying min_rating constraint."""
        m_pass = Movie(rating=7.5)
        m_fail = Movie(rating=7.4)
        m_missing = Movie(rating=None)

        self.assertTrue(HardConstraintFilter.satisfies_min_rating(m_pass, 7.5))
        self.assertFalse(HardConstraintFilter.satisfies_min_rating(m_fail, 7.5))
        self.assertFalse(HardConstraintFilter.satisfies_min_rating(m_missing, 7.5), "Missing rating must fail constraint")
        self.assertTrue(HardConstraintFilter.satisfies_min_rating(m_missing, None), "None constraint passes all")

    def test_max_runtime_enforcement_and_missing_metadata(self):
        """Missing runtime is NEVER treated as satisfying max_runtime constraint."""
        class MockMovieRuntime:
            def __init__(self, runtime):
                self.runtime = runtime

        m_pass = MockMovieRuntime(runtime=90)
        m_fail = MockMovieRuntime(runtime=120)
        m_missing = MockMovieRuntime(runtime=None)
        m_zero = MockMovieRuntime(runtime=0)

        self.assertTrue(HardConstraintFilter.satisfies_max_runtime(m_pass, 100))
        self.assertFalse(HardConstraintFilter.satisfies_max_runtime(m_fail, 100))
        self.assertFalse(HardConstraintFilter.satisfies_max_runtime(m_missing, 100), "Missing runtime must fail constraint")
        self.assertFalse(HardConstraintFilter.satisfies_max_runtime(m_zero, 100), "Zero runtime must fail constraint")
        self.assertTrue(HardConstraintFilter.satisfies_max_runtime(m_missing, None))

    def test_era_enforcement_and_missing_metadata(self):
        """Era checks respect boundaries; missing release date is rejected."""
        m_classic = Movie(release_date=date(1985, 5, 20))
        m_90s = Movie(release_date=date(1994, 9, 23))
        m_2000s = Movie(release_date=date(2004, 11, 15))
        m_2010s = Movie(release_date=date(2015, 6, 12))
        m_recent = Movie(release_date=date(2023, 7, 21))
        m_missing = Movie(release_date=None)

        # Single era checks
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_classic, ["classic"]))
        self.assertFalse(HardConstraintFilter.satisfies_eras(m_classic, ["90s"]))
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_90s, ["90s"]))
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_2000s, ["2000s"]))
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_2010s, ["2010s"]))
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_recent, ["recent"]))

        # Multi-era check
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_90s, ["classic", "90s"]))
        self.assertFalse(HardConstraintFilter.satisfies_eras(m_recent, ["classic", "90s"]))

        # Missing date
        self.assertFalse(HardConstraintFilter.satisfies_eras(m_missing, ["recent"]), "Missing date must fail era constraint")
        self.assertTrue(HardConstraintFilter.satisfies_eras(m_missing, []), "No era constraint passes all")

    def test_language_enforcement_and_missing_metadata(self):
        """Language constraint requires exact match; missing language fails."""
        m_en = Movie(original_language="en")
        m_fr = Movie(original_language="fr")
        m_missing = Movie(original_language="")

        self.assertTrue(HardConstraintFilter.satisfies_languages(m_en, ["en", "fr"]))
        self.assertTrue(HardConstraintFilter.satisfies_languages(m_fr, ["fr"]))
        self.assertFalse(HardConstraintFilter.satisfies_languages(m_en, ["ja", "ko"]))
        self.assertFalse(HardConstraintFilter.satisfies_languages(m_missing, ["en"]))
        self.assertTrue(HardConstraintFilter.satisfies_languages(m_missing, []))

    def test_excluded_genres_enforcement(self):
        """Movies with excluded genre IDs are strictly rejected."""
        m = Movie.objects.create(tmdb_id=401, title="Spooky Movie", rating=7.0, tmdb_genre_ids=[27, 18])
        m.genres.add(self.genre_horror, self.genre_drama)

        # Exclude Horror (27)
        self.assertFalse(HardConstraintFilter.satisfies_excluded_genres(m, [27]))
        # Exclude Comedy (35) -> passes
        self.assertTrue(HardConstraintFilter.satisfies_excluded_genres(m, [35]))

    def test_collaborative_agreement_rating_arithmetic_average(self):
        """Host and Guest ratings are averaged; single selection governs; both none = no filter."""
        # Case 1: Both select
        occ1 = SessionOccasionState.objects.create(
            session=self.session,
            host_occasion={"boundaries": {"min_rating": 7.0, "max_runtime": 120, "eras": ["recent", "2010s"]}},
            guest_occasion={"boundaries": {"min_rating": 8.0, "max_runtime": 100, "eras": ["recent"]}},
        )
        c1 = HardConstraints.from_occasion_state(occ1)
        self.assertEqual(c1.min_rating, 7.5, "Host 7.0 and Guest 8.0 must average to 7.5")
        self.assertEqual(c1.max_runtime, 100, "Runtime must take min(120, 100)")
        self.assertEqual(c1.eras, ["recent"], "Eras must take intersection")

        # Case 2: Only host selects
        occ2 = SessionOccasionState(
            session=self.session,
            host_occasion={"boundaries": {"min_rating": 7.2}},
            guest_occasion={"boundaries": {}},
        )
        c2 = HardConstraints.from_occasion_state(occ2)
        self.assertEqual(c2.min_rating, 7.2)

        # Case 3: Neither selects
        occ3 = SessionOccasionState(
            session=self.session,
            host_occasion={},
            guest_occasion={},
        )
        c3 = HardConstraints.from_occasion_state(occ3)
        self.assertIsNone(c3.min_rating)

    def test_collaborative_era_constraints_intersection_and_disjoint(self):
        """
        Architecture v1.2.2 Rule 9 & Section 2.2 Table 1:
        - Single selection governs if other is unset/any.
        - Overlapping selections take strict intersection.
        - Disjoint selections are contradictory (no silent relaxation; 0 movies satisfy).
        """
        # Overlapping intersection
        occ_overlap = SessionOccasionState(
            session=self.session,
            host_occasion={"boundaries": {"eras": ["before_1990", "classic"]}},
            guest_occasion={"boundaries": {"eras": ["before_1990"]}},
        )
        c_overlap = HardConstraints.from_occasion_state(occ_overlap)
        self.assertEqual(c_overlap.eras, ["before_1990"])

        # Single selection governs
        occ_single = SessionOccasionState(
            session=self.session,
            host_occasion={"boundaries": {"eras": ["before_1990"]}},
            guest_occasion={"boundaries": {"eras": ["any"]}},
        )
        c_single = HardConstraints.from_occasion_state(occ_single)
        self.assertEqual(c_single.eras, ["before_1990"])

        # Disjoint selections produce contradictory constraint marker
        occ_disjoint = SessionOccasionState(
            session=self.session,
            host_occasion={"boundaries": {"eras": ["before_1990"]}},
            guest_occasion={"boundaries": {"eras": ["recent"]}},
        )
        c_disjoint = HardConstraints.from_occasion_state(occ_disjoint)
        self.assertEqual(c_disjoint.eras, ["__CONTRADICTORY_EMPTY_ERA__"])

        # Evaluator rejects all movies under contradictory constraint (0 candidates)
        m_old = Movie(release_date=date(1985, 5, 20))
        m_new = Movie(release_date=date(2023, 7, 21))
        self.assertFalse(HardConstraintFilter.satisfies_eras(m_old, c_disjoint.eras))
        self.assertFalse(HardConstraintFilter.satisfies_eras(m_new, c_disjoint.eras))

    # -----------------------------------------------------------------
    # 3. Candidate Pool Hierarchy & Categorization Tests
    # -----------------------------------------------------------------

    def test_candidate_pool_classification_thresholds(self):
        """Verifies exact threshold boundaries: >=40 Normal, 16-39 Boutique, <16 Exhausted."""
        self.assertEqual(CandidateRetrievalService.classify_pool(45), "normal")
        self.assertEqual(CandidateRetrievalService.classify_pool(40), "normal")
        self.assertEqual(CandidateRetrievalService.classify_pool(39), "boutique")
        self.assertEqual(CandidateRetrievalService.classify_pool(16), "boutique")
        self.assertEqual(CandidateRetrievalService.classify_pool(15), "exhausted")
        self.assertEqual(CandidateRetrievalService.classify_pool(0), "exhausted")

    def test_candidate_retrieval_pool_categorization(self):
        """Retrieves and classifies candidates across the three pool states."""
        # Create 18 eligible movies -> Boutique Pool
        for i in range(18):
            Movie.objects.create(
                tmdb_id=500 + i,
                title=f"Boutique Film {i}",
                rating=7.5,
                release_date=date(2022, 1, 1),
                original_language="en",
            )

        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            constraints={"min_rating": 7.0},
            auto_replenish=False,
        )

        self.assertEqual(pool.total_count, 18)
        self.assertEqual(pool.pool_type, "boutique")
        self.assertFalse(pool.proposal_required, "Boutique pool does not require expansion proposal")

    def test_exhausted_pool_triggers_proposal_requirement(self):
        """When candidates < 16, proposal_required is set to True."""
        # Create only 5 eligible movies
        for i in range(5):
            Movie.objects.create(
                tmdb_id=600 + i,
                title=f"Rare Film {i}",
                rating=9.0,
                release_date=date(2022, 1, 1),
                original_language="en",
            )

        pool = CandidateRetrievalService.retrieve_candidates(
            session=self.session,
            constraints={"min_rating": 8.5},
            auto_replenish=False,
        )

        self.assertEqual(pool.total_count, 5)
        self.assertEqual(pool.pool_type, "exhausted")
        self.assertTrue(pool.proposal_required, "Exhausted pool (<16) must flag proposal_required = True")

    # -----------------------------------------------------------------
    # 4. TMDB Replenishment Logic Tests
    # -----------------------------------------------------------------

    @patch("core.services.retrieval.discover_movies")
    def test_replenishment_called_only_when_pool_under_40(self, mock_discover):
        """TMDB replenishment is triggered when local pool < 40 and capped at 3 pages."""
        # Return 2 mock results per page
        mock_discover.return_value = ({
            "results": [
                {"id": 7001, "title": "TMDB Movie 1", "vote_average": 8.0, "release_date": "2023-01-01", "original_language": "en"},
                {"id": 7002, "title": "TMDB Movie 2", "vote_average": 8.1, "release_date": "2023-01-01", "original_language": "en"},
            ]
        }, "tmdb")

        # With setting configured
        with self.settings(TMDB_API_KEY="test_key"):
            pool = CandidateRetrievalService.retrieve_candidates(
                session=self.session,
                constraints={"min_rating": 7.5, "languages": ["en"]},
                max_tmdb_pages=2,
                auto_replenish=True,
            )

        self.assertTrue(mock_discover.called, "discover_movies must be called when local candidates < 40")
        # Ensure discovery parameters respected
        call_kwargs = mock_discover.call_args[1]
        self.assertEqual(call_kwargs.get("language"), "en")
        self.assertEqual(call_kwargs.get("min_rating"), 7.5)

    @patch("core.services.retrieval.discover_movies")
    def test_replenishment_not_called_when_pool_at_or_above_40(self, mock_discover):
        """TMDB replenishment is skipped when local pool >= 40."""
        # Create 40 local movies
        for i in range(40):
            Movie.objects.create(
                tmdb_id=800 + i,
                title=f"Abundant Movie {i}",
                rating=8.0,
                release_date=date(2022, 1, 1),
                original_language="en",
            )

        with self.settings(TMDB_API_KEY="test_key"):
            pool = CandidateRetrievalService.retrieve_candidates(
                session=self.session,
                constraints={"min_rating": 7.0},
                auto_replenish=True,
            )

        self.assertEqual(pool.total_count, 40)
        self.assertEqual(pool.pool_type, "normal")
        mock_discover.assert_not_called()

    @patch("core.services.retrieval.discover_movies")
    def test_concurrent_replenishment_protection(self, mock_discover):
        """Concurrent replenishment with identical criteria is gated by cache lock."""
        with patch("core.services.retrieval.cache.add", return_value=False):
            with self.settings(TMDB_API_KEY="test_key"):
                count = CandidateRetrievalService._replenish_from_tmdb(HardConstraints(languages=["en"]))
                self.assertEqual(count, 0)
                mock_discover.assert_not_called()

    def test_tier_a_taste_profile_reaches_candidate_retrieval(self):
        """Tier A UserTasteProfile preferences govern when passed or user is retrieved."""
        profile = UserTasteProfile.objects.create(
            user=self.host,
            default_min_rating=Decimal("8.20"),
            default_max_runtime=95,
            default_eras=["recent"],
            hard_exclusions={"excluded_genre_ids": [27]},
        )
        constraints = HardConstraints.from_taste_profile(profile)
        self.assertEqual(constraints.min_rating, 8.20)
        self.assertEqual(constraints.max_runtime, 95)
        self.assertEqual(constraints.eras, ["recent"])
        self.assertEqual(constraints.excluded_genre_ids, [27])

        # Test resolution via user
        resolved = CandidateRetrievalService.resolve_constraints(user=self.host)
        self.assertEqual(resolved.min_rating, 8.20)
        self.assertEqual(resolved.max_runtime, 95)

    # -----------------------------------------------------------------
    # 5. Defensible Editorial Classifiers (Section 13)
    # -----------------------------------------------------------------

    def test_world_cinema_authoritative_decision_table(self):
        """Tests the 7-case World Cinema classification decision table."""
        # Case 1 & 5: Standard Non-English
        is_wc, reason = WorldCinemaClassifier.classify(original_language="ko")
        self.assertTrue(is_wc, "Korean film must qualify automatically")
        self.assertIn("Case 1/5", reason)

        # Case 2: Anglophone Non-US/UK sovereign cinema (e.g. Ireland, Australia)
        is_wc, reason = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=["IE"],
        )
        self.assertTrue(is_wc, "Irish English-dialogue film must qualify")
        self.assertIn("Case 2", reason)

        # Case 3: Hollywood domestic studio production (US)
        is_wc, reason = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=["US"],
        )
        self.assertFalse(is_wc, "US studio film must be excluded from World Cinema Vault")
        self.assertIn("Case 3", reason)

        # Case 4: International co-production with auteur lead tag
        is_wc, reason = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=["US", "GR"],
            curation_tags=["international_coproduction"],
        )
        self.assertTrue(is_wc, "Verified international co-production must qualify")
        self.assertIn("Case 4", reason)

        # Case 6: Sparse English metadata (production_countries empty)
        is_wc, reason = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=[],
        )
        self.assertFalse(is_wc, "Sparse English metadata must NOT be assumed domestic or world cinema")
        self.assertIn("Case 6", reason)

        # Case 7: International Festival Laureate (supersedes incomplete country metadata)
        is_wc, reason = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=[],
            is_festival_laureate=True,
            curation_tags=["palme_d_or"],
        )
        self.assertTrue(is_wc, "Festival laureate with incomplete country metadata must qualify under Case 7")
        self.assertIn("Case 7", reason)

        # Verification 3: US domestic studio film with festival award CANNOT qualify solely due to award
        is_wc_us, reason_us = WorldCinemaClassifier.classify(
            original_language="en",
            production_countries=["US"],
            is_festival_laureate=True,
            curation_tags=["palme_d_or"],
        )
        self.assertFalse(is_wc_us, "US domestic film winning award must be excluded from World Cinema Vault")
        self.assertIn("Case 3", reason_us)

    def test_film_noir_classification_independence(self):
        """Film Noir classification is independent of TMDB Mystery 9648."""
        # 1. Mainstream mystery film with TMDB 9648 alone -> Excluded
        is_noir, reason = FilmNoirClassifier.classify(
            curation_tags=[],
            keywords=["detective", "whodunit", "mansion"],
        )
        self.assertFalse(is_noir, "Mainstream mystery without noir aesthetic markers must be excluded")

        # 2. Movie with explicit editorial noir tag -> Film Noir
        is_noir, reason = FilmNoirClassifier.classify(
            curation_tags=["film_noir_canon"],
            keywords=[],
        )
        self.assertTrue(is_noir, "Editorial noir tag must qualify")

        # 3. Movie with >= 2 validated noir keywords -> Film Noir
        is_noir, reason = FilmNoirClassifier.classify(
            curation_tags=[],
            keywords=["femme_fatale", "hardboiled"],
        )
        self.assertTrue(is_noir, ">= 2 validated noir keywords must qualify")

    # -----------------------------------------------------------------
    # 6. Carry-Forward Verifications
    # -----------------------------------------------------------------

    def test_exact_confidence_attenuation_formula_above_cutoff(self):
        """
        Carry-Forward Verification 1:
        Verifies exact formula kappa_d = max(0.0, (conf - 0.35) / 0.65)
        across the entire domain and boundaries.
        """
        scorer = IndividualRelevanceScorer()

        # At or below 0.35 cutoff: kappa is 0.0
        self.assertEqual(scorer.compute_attenuation(0.0), 0.0)
        self.assertEqual(scorer.compute_attenuation(0.20), 0.0)
        self.assertEqual(scorer.compute_attenuation(0.35), 0.0)

        # Immediately above cutoff (0.3501)
        expected_3501 = (0.3501 - 0.35) / 0.65
        self.assertAlmostEqual(scorer.compute_attenuation(0.3501), expected_3501, places=6)

        # Intermediate points
        # c = 0.48 -> (0.48 - 0.35) / 0.65 = 0.13 / 0.65 = 0.20
        self.assertAlmostEqual(scorer.compute_attenuation(0.48), 0.20, places=6)

        # c = 0.61 -> (0.61 - 0.35) / 0.65 = 0.26 / 0.65 = 0.40
        self.assertAlmostEqual(scorer.compute_attenuation(0.61), 0.40, places=6)

        # c = 0.675 -> 0.325 / 0.65 = 0.50
        self.assertAlmostEqual(scorer.compute_attenuation(0.675), 0.50, places=6)

        # c = 0.74 -> 0.39 / 0.65 = 0.60
        self.assertAlmostEqual(scorer.compute_attenuation(0.74), 0.60, places=6)

        # c = 0.87 -> 0.52 / 0.65 = 0.80
        self.assertAlmostEqual(scorer.compute_attenuation(0.87), 0.80, places=6)

        # c = 1.0 -> 1.0
        self.assertAlmostEqual(scorer.compute_attenuation(1.0), 1.0, places=6)

    def test_learned_feedback_event_semantics_and_duplicate_protection(self):
        """
        Carry-Forward Verification 2:
        Verifies interaction event weights, duplicate event protection,
        undo cancellation, 60-day half-life decay, and [-15, +15] clamping.
        """
        m = Movie.objects.create(tmdb_id=901, title="Signal Movie", rating=7.0)

        # 1. Standard weights verification
        logs_single = [
            InteractionLog(movie=m, movie_id=m.id, event_type="superlike", created_at=datetime.now()),
        ]
        self.assertAlmostEqual(compute_learned_feedback_from_logs(logs_single), 3.0, places=4)

        # 2. Duplicate event protection: Duplicate swipes on same movie do NOT multiply
        logs_duplicates = [
            InteractionLog(movie=m, movie_id=m.id, event_type="swipe_like", created_at=datetime.now() - timedelta(days=2)),
            InteractionLog(movie=m, movie_id=m.id, event_type="swipe_like", created_at=datetime.now()),
        ]
        # Should count only once (1.0 weight at delta_t=0)
        self.assertAlmostEqual(compute_learned_feedback_from_logs(logs_duplicates), 1.0, places=4)

        # 3. Undo semantics: Undo neutralizes previous swipe in the same session without erasing historical feedback from another session
        logs_undone = [
            # Historical session 1: swipe_like (+1.0)
            InteractionLog(session_id=1, movie=m, movie_id=m.id, event_type="swipe_like", created_at=datetime.now() - timedelta(days=5)),
            # Current session 2: swipe_dislike (-1.2) followed by undo (0.0)
            InteractionLog(session_id=2, movie=m, movie_id=m.id, event_type="swipe_dislike", created_at=datetime.now() - timedelta(minutes=5)),
            InteractionLog(session_id=2, movie=m, movie_id=m.id, event_type="undo", created_at=datetime.now()),
        ]
        # Session 2's dislike is neutralized, but Session 1's like is preserved (at decay ~1.0)
        self.assertAlmostEqual(compute_learned_feedback_from_logs(logs_undone, half_life_days=60.0), 0.9438, places=3)

        # 4. Half-life decay at 60 days
        logs_decay = [
            InteractionLog(movie=m, movie_id=m.id, event_type="superlike", created_at=datetime.now() - timedelta(days=60)),
        ]
        # At 60 days, decay is 2 ** (-60/60) = 0.5 -> 3.0 * 0.5 = 1.5
        self.assertAlmostEqual(compute_learned_feedback_from_logs(logs_decay), 1.5, places=4)

        # 5. Clamping to [-15.0, +15.0]
        many_movies = []
        for i in range(20):
            m_i = Movie.objects.create(tmdb_id=1000 + i, title=f"Film {i}")
            many_movies.append(InteractionLog(movie=m_i, movie_id=m_i.id, event_type="superlike", created_at=datetime.now()))
        self.assertEqual(compute_learned_feedback_from_logs(many_movies), 15.0, "Feedback must be clamped at +15.0")

    # -----------------------------------------------------------------
    # 7. Integration with IndividualRelevanceScorer
    # -----------------------------------------------------------------

    def test_rank_candidates_for_user(self):
        """Ranks candidates for a participant, returning sorted (Movie, ScoringResult)."""
        m_high = Movie.objects.create(tmdb_id=1101, title="High Match", rating=8.5, vote_count=1000, release_date=date(2021, 1, 1))
        m_low = Movie.objects.create(tmdb_id=1102, title="Low Match", rating=6.0, vote_count=200, release_date=date(2021, 1, 1))

        profile = UserPreferenceData(
            moods=["uplifted"],
            narrative=["character"],
            themes=["identity_growth"],
            experience="balanced",
        )

        ranked = rank_candidates_for_user([m_low, m_high], profile)

        self.assertEqual(len(ranked), 2)
        # High match should rank first due to higher Bayesian quality bonus
        self.assertEqual(ranked[0][0].id, m_high.id)
        self.assertGreaterEqual(ranked[0][1].normalized_relevance, ranked[1][1].normalized_relevance)
        self.assertTrue(0.0 <= ranked[0][1].normalized_relevance <= 1.0)
