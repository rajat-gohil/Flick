"""
Tests for movie mutation services, classification state transitions,
manual override protection, and management commands.
"""

import datetime
from django.contrib.auth.models import AnonymousUser, Permission, User
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from core.models import CatalogueJob, Genre, Movie
from core.services.movie_mutations import (
    PERMITTED_METADATA_FIELDS,
    PERMITTED_PROVENANCE_KEYS,
    PERMITTED_PROVENANCE_VALUES,
    transition_movie_classification,
    update_movie_metadata,
)


class MovieMutationsTestCase(TestCase):
    def setUp(self):
        super().setUp()
        self.movie = Movie.objects.create(
            tmdb_id=10101,
            title="Inception",
            overview="A thief who steals corporate secrets through the use of dream-sharing technology.",
            poster_path="/inception.jpg",
            release_date=datetime.date(2010, 7, 16),
            original_language="en",
            provenance="needs_review",
            field_provenance={},
        )
        self.genre = Genre.objects.create(tmdb_id=28, name="Action")
        self.movie.genres.add(self.genre)

        # Standard non-staff user
        self.regular_user = User.objects.create_user(
            username="regular_joe", password="password123"
        )

        # Staff user
        self.staff_user = User.objects.create_user(
            username="admin_jane", password="password123", is_staff=True
        )

        # Non-staff user with core.change_movie permission
        self.perm_user = User.objects.create_user(
            username="perm_pete", password="password123", is_staff=False
        )
        change_perm = Permission.objects.get(codename="change_movie", content_type__app_label="core")
        self.perm_user.user_permissions.add(change_perm)

    def test_update_movie_metadata_whitelist_rejection(self):
        """Test update_movie_metadata rejects unpermitted fields, including 'provenance'."""
        # 'provenance' is strictly forbidden in update_movie_metadata
        with self.assertRaises(ValueError) as ctx:
            update_movie_metadata(self.movie.id, {"provenance": "tmdb_catalogue"})
        self.assertIn("Unpermitted metadata fields", str(ctx.exception))
        self.assertIn("provenance", str(ctx.exception))

        # Arbitrary / non-existent fields are rejected
        with self.assertRaises(ValueError) as ctx:
            update_movie_metadata(self.movie.id, {"malicious_column": "drop table", "vote_count": 50})
        self.assertIn("Unpermitted metadata fields", str(ctx.exception))
        self.assertIn("malicious_column", str(ctx.exception))

        # Verify movie in DB was not modified
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.provenance, "needs_review")

    def test_update_movie_metadata_success_automated(self):
        """Test valid automated metadata update sets fields, provenance, and recalculates eligibility."""
        updates = {
            "title": "Inception (2010)",
            "overview": "Updated overview.",
            "vote_count": 35000,
            "rating": 8.8,
            "trailer_key": "YoHD9XEInc0",
        }
        updated = update_movie_metadata(
            movie_id=self.movie.id,
            updates=updates,
            is_automated=True,
            actor="worker:enricher-1",
        )

        self.assertEqual(updated.title, "Inception (2010)")
        self.assertEqual(updated.overview, "Updated overview.")
        self.assertEqual(updated.vote_count, 35000)
        self.assertEqual(updated.trailer_key, "YoHD9XEInc0")

        # Check field_provenance
        fp = updated.field_provenance
        self.assertIn("title", fp)
        self.assertEqual(fp["title"]["source"], "tmdb")
        self.assertEqual(fp["title"]["updated_by"], "worker:enricher-1")
        self.assertIn("updated_at", fp["title"])

    def test_manual_override_protection(self):
        """Test that automated updates cannot overwrite manually curated fields and record divergence."""
        # 1. Establish a manual override on 'title'
        self.movie.field_provenance = {
            "title": {
                "source": "manual",
                "updated_at": "2026-01-01T00:00:00Z",
                "updated_by": "editor_bob",
            }
        }
        self.movie.title = "Inception: Director's Preferred Title"
        self.movie.save()

        # 2. Automated worker attempts to update title to TMDB value
        automated_updates = {
            "title": "Inception (TMDB Standard)",
            "overview": "New TMDB overview.",
        }
        updated = update_movie_metadata(
            movie_id=self.movie.id,
            updates=automated_updates,
            is_automated=True,
            actor="worker:auto-sync",
        )

        # Title column MUST remain the manual value
        self.assertEqual(updated.title, "Inception: Director's Preferred Title")
        # Overview (not manual) SHOULD be updated
        self.assertEqual(updated.overview, "New TMDB overview.")

        # Divergent TMDB value recorded in field_provenance
        title_meta = updated.field_provenance.get("title", {})
        self.assertEqual(title_meta.get("source"), "manual")
        self.assertEqual(title_meta.get("divergent_tmdb_value"), "Inception (TMDB Standard)")
        self.assertIn("diverged_at", title_meta)

        # 3. Manual update (is_automated=False) CAN overwrite the manual column
        manual_updates = {"title": "Inception: Final Director Cut"}
        manual_result = update_movie_metadata(
            movie_id=self.movie.id,
            updates=manual_updates,
            is_automated=False,
            actor="admin_jane",
        )
        self.assertEqual(manual_result.title, "Inception: Final Director Cut")
        self.assertEqual(manual_result.field_provenance["title"]["source"], "manual")
        self.assertEqual(manual_result.field_provenance["title"]["updated_by"], "admin_jane")
        self.assertNotIn("divergent_tmdb_value", manual_result.field_provenance["title"])

    def test_field_provenance_updates_reserved_keys_rejection(self):
        """Test field_provenance_updates rejects keys starting with '_' or unpermitted keys."""
        with self.assertRaises(ValueError) as ctx:
            update_movie_metadata(
                movie_id=self.movie.id,
                updates={"title": "New Title"},
                field_provenance_updates={"_classification_audit": [{"fake": "audit"}]},
            )
        self.assertIn("Cannot overwrite reserved audit key", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            update_movie_metadata(
                movie_id=self.movie.id,
                updates={"title": "New Title"},
                field_provenance_updates={"title": {"_hidden_hack": True}},
            )
        self.assertIn("Cannot overwrite reserved audit key", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            update_movie_metadata(
                movie_id=self.movie.id,
                updates={"title": "New Title"},
                field_provenance_updates={"title": {"invalid_provenance_key": 123}},
            )
        self.assertIn("Unpermitted provenance key", str(ctx.exception))

    def test_transition_movie_classification_unauthorized_user(self):
        """Test unauthorized user raises PermissionDenied."""
        # Unauthenticated user
        with self.assertRaises(PermissionDenied):
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="tmdb_catalogue",
                reason="Manual review",
                user=AnonymousUser(),
            )

        # Regular authenticated user without change_movie permission
        with self.assertRaises(PermissionDenied):
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="tmdb_catalogue",
                reason="Manual review",
                user=self.regular_user,
            )

    def test_transition_movie_classification_authorized_users(self):
        """Test staff user and user with core.change_movie permission can transition."""
        # Staff user
        res1 = transition_movie_classification(
            movie_id=self.movie.id,
            new_provenance="tmdb_catalogue",
            reason="Verified against TMDB official catalogue",
            user=self.staff_user,
            metadata_evidence={"tmdb_match_score": 1.0},
        )
        self.assertEqual(res1.provenance, "tmdb_catalogue")
        self.assertEqual(len(res1.field_provenance["_classification_audit"]), 1)
        audit1 = res1.field_provenance["_classification_audit"][0]
        self.assertEqual(audit1["from_provenance"], "needs_review")
        self.assertEqual(audit1["to_provenance"], "tmdb_catalogue")
        self.assertEqual(audit1["actor"], "admin_jane")
        self.assertEqual(audit1["actor_type"], "user")
        self.assertEqual(audit1["metadata_evidence"]["tmdb_match_score"], 1.0)

        # Perm user transitions from tmdb_catalogue -> manual_curated
        res2 = transition_movie_classification(
            movie_id=self.movie.id,
            new_provenance="manual_curated",
            reason="Curated by editorial board",
            user=self.perm_user,
        )
        self.assertEqual(res2.provenance, "manual_curated")
        self.assertEqual(len(res2.field_provenance["_classification_audit"]), 2)
        audit2 = res2.field_provenance["_classification_audit"][1]
        self.assertEqual(audit2["from_provenance"], "tmdb_catalogue")
        self.assertEqual(audit2["to_provenance"], "manual_curated")
        self.assertEqual(audit2["actor"], "perm_pete")

    def test_invalid_manual_transition_raises_value_error(self):
        """Test invalid transition raises ValueError without modifying movie or audit history."""
        # Destination not in PERMITTED_PROVENANCE_VALUES
        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="totally_bogus_status",
                reason="Testing invalid state",
                user=self.staff_user,
            )
        self.assertIn("Invalid provenance", str(ctx.exception))

        # Transitioning to the same state (needs_review -> needs_review) is not allowed
        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="needs_review",
                reason="No-op transition",
                user=self.staff_user,
            )
        self.assertIn("Invalid manual classification transition", str(ctx.exception))

        # Verify movie and field_provenance are unmodified
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.provenance, "needs_review")
        self.assertNotIn("_classification_audit", self.movie.field_provenance)

    def test_automated_classification_success(self):
        """Test automated worker can transition from needs_review to tmdb_catalogue."""
        updated = transition_movie_classification(
            movie_id=self.movie.id,
            new_provenance="tmdb_catalogue",
            reason="Automated title and year match verified",
            worker_id="worker-99",
            metadata_evidence={"match_method": "title_year_exact"},
        )
        self.assertEqual(updated.provenance, "tmdb_catalogue")
        # Inception has title, poster_path, provenance='tmdb_catalogue', release_date 2010, genres, lang 'en'
        # so it should now be display_ready=True and recommendable=True!
        self.assertTrue(updated.display_ready)
        self.assertTrue(updated.recommendable)

        audit = updated.field_provenance["_classification_audit"][0]
        self.assertEqual(audit["actor"], "worker:worker-99")
        self.assertEqual(audit["actor_type"], "worker")
        self.assertEqual(audit["reason"], "Automated title and year match verified")

    def test_automated_classification_requires_worker_id(self):
        """Test automated classification fails if worker_id is missing or blank."""
        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="tmdb_catalogue",
                reason="Automated test",
                worker_id="",
            )
        self.assertIn("worker_id", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="tmdb_catalogue",
                reason="Automated test",
                worker_id=None,
            )
        self.assertIn("worker_id", str(ctx.exception))

    def test_automated_worker_cannot_modify_manual_curated(self):
        """Test automated worker cannot touch movie with manual_curated provenance."""
        # Set movie to manual_curated
        self.movie.provenance = "manual_curated"
        self.movie.save()

        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="tmdb_catalogue",
                reason="Automated reclassification attempt",
                worker_id="worker-42",
            )
        self.assertIn("cannot modify movie with 'manual_curated' provenance", str(ctx.exception))

        # Verify DB unchanged
        self.movie.refresh_from_db()
        self.assertEqual(self.movie.provenance, "manual_curated")

    def test_automated_worker_cannot_perform_invalid_transition(self):
        """Automated transitions can only be needs_review -> tmdb_catalogue or synthetic_fixture."""
        # Already tmdb_catalogue
        self.movie.provenance = "tmdb_catalogue"
        self.movie.save()

        with self.assertRaises(ValueError) as ctx:
            transition_movie_classification(
                movie_id=self.movie.id,
                new_provenance="synthetic_fixture",
                reason="Invalid automated jump",
                worker_id="worker-42",
            )
        self.assertIn("Automated transitions must be from 'needs_review'", str(ctx.exception))

    def test_hardened_audit_initialization_preserves_malformed_prior_audit(self):
        """Test hardened audit initialization wraps malformed prior audit dict/string/int."""
        # Set field_provenance with malformed _classification_audit (e.g. string or dict instead of list)
        self.movie.field_provenance = {
            "_classification_audit": "LEGACY_CORRUPTED_STRING_AUDIT_LOG",
            "other_field": {"source": "tmdb"},
        }
        self.movie.save()

        updated = transition_movie_classification(
            movie_id=self.movie.id,
            new_provenance="synthetic_fixture",
            reason="Synthetic test movie detected",
            worker_id="worker-audit-test",
        )

        audit_history = updated.field_provenance.get("_classification_audit")
        self.assertIsInstance(audit_history, list)
        self.assertEqual(len(audit_history), 2)
        # First entry preserves prior corrupt audit
        self.assertEqual(
            audit_history[0],
            {"malformed_prior_audit": "LEGACY_CORRUPTED_STRING_AUDIT_LOG"}
        )
        # Second entry is the new audit entry
        self.assertEqual(audit_history[1]["to_provenance"], "synthetic_fixture")
        self.assertEqual(audit_history[1]["actor"], "worker:worker-audit-test")

    def test_hardened_audit_initialization_handles_non_dict_field_provenance(self):
        """Test transition handles movie.field_provenance being non-dict (e.g. string or None)."""
        self.movie.field_provenance = "malformed_string_field_provenance"
        self.movie.save()

        updated = transition_movie_classification(
            movie_id=self.movie.id,
            new_provenance="synthetic_fixture",
            reason="Fixed provenance test",
            worker_id="worker-fp-fix",
        )

        self.assertIsInstance(updated.field_provenance, dict)
        self.assertEqual(
            updated.field_provenance.get("_raw_malformed_provenance"),
            "malformed_string_field_provenance"
        )
        self.assertEqual(len(updated.field_provenance["_classification_audit"]), 1)

    def test_enqueue_initial_catalogue_classification_command(self):
        """Test enqueue_initial_catalogue_classification management command with dry-run and limit."""
        # Create a second movie for limit testing
        movie2 = Movie.objects.create(
            tmdb_id=20202,
            title="The Matrix",
            poster_path="/matrix.jpg",
            release_date=datetime.date(1999, 3, 31),
            original_language="en",
        )

        # 1. Dry run
        out_dry = StringIO()
        call_command("enqueue_initial_catalogue_classification", dry_run=True, stdout=out_dry)
        self.assertIn("[DRY-RUN]", out_dry.getvalue())
        self.assertIn("No database modifications performed", out_dry.getvalue())
        # Ensure no jobs were actually created
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_classification").count(), 0)

        # 2. Limit = 1
        out_limit = StringIO()
        call_command("enqueue_initial_catalogue_classification", limit=1, stdout=out_limit)
        self.assertIn("1 movies processed", out_limit.getvalue())
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_classification").count(), 1)

        # 3. Full run: should enqueue the second movie and deduplicate the first
        out_full = StringIO()
        call_command("enqueue_initial_catalogue_classification", stdout=out_full)
        output = out_full.getvalue()
        self.assertIn("1 newly enqueued", output)
        self.assertIn("1 deduplicated", output)
        # Total jobs should now be 2
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_classification").count(), 2)

        # 4. Re-run: both should be deduplicated
        out_rerun = StringIO()
        call_command("enqueue_initial_catalogue_classification", stdout=out_rerun)
        output_rerun = out_rerun.getvalue()
        self.assertIn("0 newly enqueued", output_rerun)
        self.assertIn("2 deduplicated", output_rerun)
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_classification").count(), 2)
