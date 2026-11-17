import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import (
    Session,
    Movie,
    Genre,
    CollaborativeAgreement,
    SessionOccasionState,
)
from core.services.retrieval import (
    CandidateRetrievalService,
    HardConstraints,
    HardConstraintFilter,
)
from core.services.manifest import (
    ManifestCompilerService,
    InsufficientCandidatesError,
    UserPreferenceData,
)
from core.services.deck_state import DeckAdvancementService

User = get_user_model()


class PreferenceAndManifestCorrectnessTests(TestCase):
    """
    Regression test suite for Phase 3.1 Slice A:
    Enforcing strict candidate retrieval and manifest compilation filtering.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_user", password="password123")
        self.guest = User.objects.create_user(username="guest_user", password="password123")

        # Genres
        self.genre_comedy, _ = Genre.objects.get_or_create(id=4, tmdb_id=35, name="Comedy")
        self.genre_drama, _ = Genre.objects.get_or_create(id=5, tmdb_id=18, name="Drama")
        self.genre_animation, _ = Genre.objects.get_or_create(id=6, tmdb_id=16, name="Animation")
        self.genre_family, _ = Genre.objects.get_or_create(id=7, tmdb_id=10751, name="Family")
        self.genre_romance, _ = Genre.objects.get_or_create(id=8, tmdb_id=10749, name="Romance")

        # Actual movie metadata examples from Session 63
        # 1. English-language drama (The Shawshank Redemption - 1994)
        self.m_shawshank = Movie.objects.create(
            tmdb_id=278,
            title="The Shawshank Redemption",
            original_language="en",
            release_date=date(1994, 9, 23),
            rating=9.3,
            vote_count=26000,
        )
        self.m_shawshank.genres.add(self.genre_drama)

        # 2. English-language animated family film (Toy Story - 1995)
        self.m_toystory = Movie.objects.create(
            tmdb_id=862,
            title="Toy Story",
            original_language="en",
            release_date=date(1995, 11, 22),
            rating=8.0,
            vote_count=18000,
        )
        self.m_toystory.genres.add(self.genre_animation, self.genre_family)

        # 3. Hindi comedy within 2000-2010 (3 Idiots - 2009)
        self.m_3idiots = Movie.objects.create(
            tmdb_id=20453,
            title="3 Idiots",
            original_language="hi",
            release_date=date(2009, 12, 23),
            rating=8.4,
            vote_count=4500,
        )
        self.m_3idiots.genres.add(self.genre_comedy, self.genre_drama)

        # 4. Hindi comedy outside 2000-2010 (DDLJ - 1995)
        self.m_ddlj = Movie.objects.create(
            tmdb_id=19404,
            title="Dilwale Dulhania Le Jayenge",
            original_language="hi",
            release_date=date(1995, 10, 20),
            rating=8.6,
            vote_count=4300,
        )
        self.m_ddlj.genres.add(self.genre_comedy, self.genre_drama, self.genre_romance)

        # 5. Hindi film outside Comedy genre (Like Stars on Earth - 2007)
        self.m_taare = Movie.objects.create(
            tmdb_id=7508,
            title="Like Stars on Earth",
            original_language="hi",
            release_date=date(2007, 12, 20),
            rating=8.5,
            vote_count=2100,
        )
        self.m_taare.genres.add(self.genre_drama)

    def test_english_drama_rejected_for_hindi_comedy_2000s(self):
        """English drama must be rejected when Hindi, Comedy, 2000s is selected."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        self.assertFalse(HardConstraintFilter.matches_all(self.m_shawshank, constraints))

    def test_english_animation_family_rejected_for_hindi_comedy_2000s(self):
        """English animated family film must be rejected."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        self.assertFalse(HardConstraintFilter.matches_all(self.m_toystory, constraints))

    def test_hindi_comedy_within_selected_period_accepted(self):
        """Hindi comedy released in 2009 satisfies Hindi, Comedy, 2000s."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        self.assertTrue(HardConstraintFilter.matches_all(self.m_3idiots, constraints))

    def test_comedy_outside_selected_period_rejected(self):
        """Hindi comedy released in 1995 must be rejected when era is 2000s."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        self.assertFalse(HardConstraintFilter.matches_all(self.m_ddlj, constraints))

    def test_film_outside_selected_genre_rejected(self):
        """Hindi drama from 2007 without comedy genre must be rejected when genre is Comedy."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        self.assertFalse(HardConstraintFilter.matches_all(self.m_taare, constraints))

    def test_insufficient_eligible_candidates_triggers_exhaustion(self):
        """When fewer than 16 candidates satisfy constraints, InsufficientCandidatesError must be raised."""
        constraints = HardConstraints(
            languages=["hi"],
            required_genre_ids=[35],
            eras=["2000s"],
        )
        # Only 1 candidate (3 Idiots) exists in local DB
        pool = CandidateRetrievalService.retrieve_candidates(
            constraints=constraints,
            auto_replenish=False,
        )
        self.assertEqual(pool.pool_type, "exhausted")
        self.assertTrue(pool.proposal_required)
        self.assertEqual(len(pool.candidates), 1)

        host_prefs = UserPreferenceData(moods=["amused"], experience="balanced")
        guest_prefs = UserPreferenceData(moods=["amused"], experience="balanced")

        with self.assertRaises(InsufficientCandidatesError):
            ManifestCompilerService.compile_manifest(
                candidates=pool.candidates,
                host_prefs=host_prefs,
                guest_prefs=guest_prefs,
            )

    @patch("core.services.retrieval.discover_movies", return_value=({"results": []}, "mock"))
    def test_session_63_actual_payload_populates_collaborative_agreement_and_retrieval(self, mock_discover):
        """
        Tests the actual saved preference payload from Session 63:
        Session has language=['hi'], genre=Comedy, host_prefs era=['2000s', '2010s'], guest_prefs era=['2010s', '2000s'].
        Verifies CollaborativeAgreement is initialized with correct hard constraints and soft preferences,
        and retrieval strictly filters by these constraints.
        """
        session = Session.objects.create(
            host=self.host,
            guest=self.guest,
            code="R682TY",
            genre=self.genre_comedy,
            industry="bollywood",
            selected_languages=["hi"],
            host_preferences={
                "mood": ["happy"],
                "pace": ["slow", "balanced"],
                "vibe": ["feel-good"],
                "era": ["2000s", "2010s"],
                "min_rating": ["4+"],
                "tone": ["uplifted", "amused"],
                "intensity": "light",
                "themes": ["love_relationships", "friendship"],
                "narrative": ["ensemble"],
            },
            guest_preferences={
                "mood": ["happy", "exciting"],
                "pace": ["balanced"],
                "vibe": ["feel-good", "escapist"],
                "era": ["2010s", "2000s"],
                "min_rating": ["4+"],
                "tone": ["amused", "thrilled"],
                "intensity": "medium",
                "themes": ["love_relationships", "friendship"],
                "narrative": ["ensemble"],
            },
            preferences_set=True,
        )

        try:
            agreement = DeckAdvancementService.get_or_initialize_agreement(session)
        except InsufficientCandidatesError:
            agreement = CollaborativeAgreement.objects.get(session=session)

        # Verification of CollaborativeAgreement synthesis
        self.assertEqual(agreement.shared_languages, ["hi"])
        self.assertIn(35, agreement.mutual_hard_exclusions.get("required_genre_ids", []))
        self.assertIn("2000s", agreement.shared_eras)
        self.assertIn("2010s", agreement.shared_eras)
        self.assertIsNotNone(agreement.shared_min_rating)
        self.assertEqual(float(agreement.shared_min_rating), 4.0)

        # Candidate retrieval with agreement constraints
        resolved = CandidateRetrievalService.resolve_constraints(constraints=agreement, session=session)
        self.assertEqual(resolved.languages, ["hi"])
        self.assertEqual(resolved.required_genre_ids, [35])
        self.assertIn("2000s", resolved.eras)

        # Candidates retrieved must NOT include Shawshank, Toy Story, or non-comedies
        pool = CandidateRetrievalService.retrieve_candidates(session=session, constraints=agreement, auto_replenish=False)
        candidate_ids = [m.id for m in pool.candidates]
        self.assertNotIn(self.m_shawshank.id, candidate_ids)
        self.assertNotIn(self.m_toystory.id, candidate_ids)
        self.assertNotIn(self.m_taare.id, candidate_ids)
        self.assertIn(self.m_3idiots.id, candidate_ids)

    def test_tmdb_credential_hygiene_redaction(self):
        """Verifies that TMDB API keys are strictly redacted from errors and log strings."""
        from core.services.tmdb import redact_sensitive_params
        leak_input = "Failed to connect: https://api.themoviedb.org/3/discover/movie?api_key=SECRET_TMDB_KEY_12345&language=hi"
        redacted = redact_sensitive_params(leak_input)
        self.assertNotIn("SECRET_TMDB_KEY_12345", redacted)
        self.assertIn("api_key=[REDACTED]", redacted)

        bearer_input = "Authorization: Bearer secret_bearer_token_xyz"
        redacted_bearer = redact_sensitive_params(bearer_input)
        self.assertNotIn("secret_bearer_token_xyz", redacted_bearer)
        self.assertIn("Bearer [REDACTED]", redacted_bearer)
