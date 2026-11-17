"""
Tests for language validation and catalogue eligibility predicates,
MovieQuerySet update protections, and m2m_changed genre signal recalculations.
"""

import datetime
from django.test import TestCase

from core.constants.languages import (
    ISO_639_1_CODES,
    TMDB_NO_LANGUAGE_SENTINEL,
    validate_movie_language,
)
from core.models import Genre, Movie, MovieQuerySet
from core.services.catalogue_eligibility import (
    ELIGIBLE_PROVENANCE_VALUES,
    evaluate_eligibility_predicates,
    recalculate_movie_eligibility,
)


class LanguageValidationTests(TestCase):
    """Unit tests for ISO 639-1 code set and language validator."""

    def test_iso_639_1_codes_count_and_content(self):
        self.assertEqual(len(ISO_639_1_CODES), 184)
        self.assertIn("en", ISO_639_1_CODES)
        self.assertIn("hi", ISO_639_1_CODES)
        self.assertIn("fr", ISO_639_1_CODES)
        self.assertIn("es", ISO_639_1_CODES)
        self.assertIn("ja", ISO_639_1_CODES)
        self.assertNotIn("xx", ISO_639_1_CODES)
        self.assertNotIn("zz", ISO_639_1_CODES)

    def test_validate_movie_language_valid_codes(self):
        self.assertEqual(validate_movie_language("en"), (True, "iso_639_1"))
        self.assertEqual(validate_movie_language("hi"), (True, "iso_639_1"))
        self.assertEqual(validate_movie_language("ja"), (True, "iso_639_1"))
        self.assertEqual(validate_movie_language("EN"), (True, "iso_639_1"))
        self.assertEqual(validate_movie_language("  hi  "), (True, "iso_639_1"))

    def test_validate_movie_language_sentinel(self):
        self.assertEqual(validate_movie_language("xx"), (True, "tmdb_sentinel"))
        self.assertEqual(validate_movie_language("XX"), (True, "tmdb_sentinel"))
        self.assertEqual(validate_movie_language(" xx "), (True, "tmdb_sentinel"))
        self.assertEqual(TMDB_NO_LANGUAGE_SENTINEL, "xx")

    def test_validate_movie_language_invalid_codes(self):
        self.assertEqual(validate_movie_language("zz"), (False, "invalid"))
        self.assertEqual(validate_movie_language("abc"), (False, "invalid"))
        self.assertEqual(validate_movie_language(None), (False, "invalid"))
        self.assertEqual(validate_movie_language(""), (False, "invalid"))
        self.assertEqual(validate_movie_language("   "), (False, "invalid"))
        self.assertEqual(validate_movie_language(123), (False, "invalid"))


class EligibilityPredicatesOptionBTests(TestCase):
    """Unit tests for eligibility predicates under Option B rules."""

    def test_eligible_provenance_values(self):
        self.assertEqual(ELIGIBLE_PROVENANCE_VALUES, frozenset({"tmdb_catalogue", "manual_curated"}))

    def test_full_eligible_movie(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Inception",
            poster_path="/inception.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(2010, 7, 16),
            original_language="en",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertTrue(recommendable)

    def test_manual_curated_is_eligible(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Curated Masterpiece",
            poster_path="/curated.jpg",
            provenance="manual_curated",
            release_date=datetime.date(2022, 1, 1),
            original_language="hi",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertTrue(recommendable)

    def test_sentinel_language_xx_is_recommendable(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Silent Film",
            poster_path="/silent.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(1925, 1, 1),
            original_language="xx",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertTrue(recommendable)

    def test_empty_overview_does_not_block_under_option_b(self):
        # Empty overview does NOT block display_ready or recommendable
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="No Overview Film",
            poster_path="/poster.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(2020, 5, 20),
            original_language="en",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertTrue(recommendable)

    def test_missing_poster_blocks_display_ready_and_recommendable(self):
        for empty_poster in [None, "", "   "]:
            display_ready, recommendable = evaluate_eligibility_predicates(
                title="Missing Poster Film",
                poster_path=empty_poster,
                provenance="tmdb_catalogue",
                release_date=datetime.date(2020, 5, 20),
                original_language="en",
                has_genres=True,
            )
            self.assertFalse(display_ready)
            self.assertFalse(recommendable)

    def test_missing_title_blocks_display_ready_and_recommendable(self):
        for empty_title in [None, "", "   "]:
            display_ready, recommendable = evaluate_eligibility_predicates(
                title=empty_title,
                poster_path="/poster.jpg",
                provenance="tmdb_catalogue",
                release_date=datetime.date(2020, 5, 20),
                original_language="en",
                has_genres=True,
            )
            self.assertFalse(display_ready)
            self.assertFalse(recommendable)

    def test_needs_review_blocks_both(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Under Review",
            poster_path="/poster.jpg",
            provenance="needs_review",
            release_date=datetime.date(2020, 5, 20),
            original_language="en",
            has_genres=True,
        )
        self.assertFalse(display_ready)
        self.assertFalse(recommendable)

    def test_synthetic_fixture_blocks_both(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Synthetic Fixture",
            poster_path="/poster.jpg",
            provenance="synthetic_fixture",
            release_date=datetime.date(2020, 5, 20),
            original_language="en",
            has_genres=True,
        )
        self.assertFalse(display_ready)
        self.assertFalse(recommendable)

    def test_missing_release_date_allows_display_ready_blocks_recommendable(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Unreleased or Unknown Date",
            poster_path="/poster.jpg",
            provenance="tmdb_catalogue",
            release_date=None,
            original_language="en",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertFalse(recommendable)

    def test_release_date_before_1888_blocks_recommendable(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Ancient History Film",
            poster_path="/poster.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(1887, 12, 31),
            original_language="en",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertFalse(recommendable)

        # 1888 is allowed (Roundhay Garden Scene was 1888)
        display_ready_1888, recommendable_1888 = evaluate_eligibility_predicates(
            title="Roundhay Garden Scene",
            poster_path="/roundhay.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(1888, 10, 14),
            original_language="en",
            has_genres=True,
        )
        self.assertTrue(display_ready_1888)
        self.assertTrue(recommendable_1888)

    def test_missing_genres_blocks_recommendable(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Genre-less Film",
            poster_path="/poster.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(2020, 1, 1),
            original_language="en",
            has_genres=False,
        )
        self.assertTrue(display_ready)
        self.assertFalse(recommendable)

    def test_invalid_language_blocks_recommendable(self):
        display_ready, recommendable = evaluate_eligibility_predicates(
            title="Invalid Language Film",
            poster_path="/poster.jpg",
            provenance="tmdb_catalogue",
            release_date=datetime.date(2020, 1, 1),
            original_language="zz",
            has_genres=True,
        )
        self.assertTrue(display_ready)
        self.assertFalse(recommendable)


class MovieQuerySetRestrictionTests(TestCase):
    """Tests for MovieQuerySet bulk update restrictions and trusted bypass."""

    def setUp(self):
        self.movie = Movie.objects.create(
            tmdb_id=99001,
            title="Test Movie",
            poster_path="/test.jpg",
            release_date=datetime.date(2021, 1, 1),
            original_language="en",
            provenance="needs_review",
        )

    def test_direct_bulk_update_restricted_fields_raises_runtime_error(self):
        for field in MovieQuerySet.RESTRICTED_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(RuntimeError) as ctx:
                    Movie.objects.filter(pk=self.movie.pk).update(**{field: True if "able" in field or "ready" in field else "tmdb_catalogue"})
                self.assertIn("prohibited", str(ctx.exception))

    def test_movie_objects_update_raises_runtime_error(self):
        with self.assertRaises(RuntimeError) as ctx:
            Movie.objects.update(display_ready=True)
        self.assertIn("prohibited", str(ctx.exception))

    def test_unrestricted_field_update_succeeds(self):
        count = Movie.objects.filter(pk=self.movie.pk).update(title="Updated Title")
        self.assertEqual(count, 1)
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.title, "Updated Title")

    def test_trusted_update_eligibility_bypasses_restriction_without_recursion(self):
        rows_updated = Movie.objects._trusted_update_eligibility(
            movie_pk=self.movie.pk,
            display_ready=True,
            recommendable=True,
        )
        self.assertEqual(rows_updated, 1)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertTrue(self.movie.recommendable)


class MovieEligibilityModelAndSignalTests(TestCase):
    """Tests for recalculate_movie_eligibility and m2m_changed genre signal."""

    def setUp(self):
        self.genre_action = Genre.objects.create(tmdb_id=28, name="Action")
        self.genre_comedy = Genre.objects.create(tmdb_id=35, name="Comedy")
        self.movie = Movie.objects.create(
            tmdb_id=99002,
            title="Blockbuster",
            poster_path="/blockbuster.jpg",
            release_date=datetime.date(2022, 6, 1),
            original_language="en",
            provenance="tmdb_catalogue",
            display_ready=False,
            recommendable=False,
        )

    def test_recalculate_movie_eligibility_commit_false_and_true(self):
        # Without commit
        disp, rec = recalculate_movie_eligibility(self.movie, commit=False)
        self.assertTrue(disp)
        self.assertFalse(rec)  # No genres yet
        self.assertTrue(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)

        # Refresh from db: still False in DB
        self.movie.refresh_from_db()
        self.assertFalse(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)

        # With commit=True
        disp, rec = recalculate_movie_eligibility(self.movie, commit=True)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)

    def test_m2m_changed_genre_addition_and_removal_immediately_updates_db(self):
        # 1. Initially without genres, movie is display_ready=True, recommendable=False
        self.movie.recalculate_eligibility(commit=True)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)

        # 2. Add genre: m2m_changed post_add triggers recalculation and commit
        self.movie.genres.add(self.genre_action)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertTrue(self.movie.recommendable)

        # 3. Add second genre: remains recommendable
        self.movie.genres.add(self.genre_comedy)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.recommendable)

        # 4. Remove one genre: still has one genre -> still recommendable
        self.movie.genres.remove(self.genre_comedy)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.recommendable)

        # 5. Remove last genre: immediately downgrades recommendable to False
        self.movie.genres.remove(self.genre_action)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)

    def test_m2m_changed_genre_clear_immediately_downgrades_recommendable(self):
        # Add genre
        self.movie.genres.add(self.genre_action)
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.recommendable)

        # Clear genres
        self.movie.genres.clear()
        self.movie.refresh_from_db()
        self.assertTrue(self.movie.display_ready)
        self.assertFalse(self.movie.recommendable)
