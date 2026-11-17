"""
Tests for correct_synthetic_m1_records management command.

Validates:
1. Safety guard enforcement (DEBUG=True, SQLite, canonical path).
2. Staff user resolution and permission requirements.
3. Dry-run immutability (zero changes made).
4. Atomic two-step administrative transition (tmdb_catalogue -> needs_review -> synthetic_fixture).
5. Audit trail preservation (_classification_audit contains both entries).
6. Recalculation of eligibility (display_ready=False, recommendable=False).
7. Exclusion from fixture candidate queryset and pre-validation.
"""

from io import StringIO
from pathlib import Path
from unittest import mock
import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.management.commands.correct_synthetic_m1_records import (
    _inspect_target_records,
    _resolve_staff_user,
)
from core.management.commands.seed_local_dev_catalogue import (
    _build_candidate_queryset,
    _validate_candidate,
)
from core.models import Genre, Movie

User = get_user_model()


def _guard_pass():
    return ("django.db.backends.sqlite3", "/test/db.sqlite3")


@override_settings(DEBUG=True)
class CorrectSyntheticM1RecordsTest(TestCase):
    def setUp(self):
        # Create genres
        self.scifi, _ = Genre.objects.get_or_create(tmdb_id=878, defaults={"name": "Science Fiction"})
        self.mystery, _ = Genre.objects.get_or_create(tmdb_id=9648, defaults={"name": "Mystery"})

        # Create exact replicas of Movies 724 and 725
        self.m724 = Movie.objects.create(
            id=724,
            tmdb_id=8001,
            title="M1",
            provenance="tmdb_catalogue",
            display_ready=False,
            recommendable=False,
            poster_path=None,
            release_date=datetime.date(2020, 1, 1),
            original_language=None,
            rating=8.0,
            vote_count=5000,
            field_provenance={},
        )
        self.m724.genres.add(self.scifi)

        self.m725 = Movie.objects.create(
            id=725,
            tmdb_id=7001,
            title="M1",
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
            poster_path="/p1.jpg",
            release_date=datetime.date(2020, 1, 1),
            original_language="en",
            rating=8.0,
            vote_count=5000,
            field_provenance={},
        )
        self.m725.genres.add(self.mystery, self.scifi)

        # Create staff user
        self.staff_user = User.objects.create_superuser(
            username="rajat",
            email="rgohil27@gmail.com",
            password="testpassword",
        )

        # Create non-staff user
        self.normal_user = User.objects.create_user(
            username="normal_user",
            email="user@flick.test",
            password="testpassword",
        )

    # -----------------------------------------------------------------------
    # 1. Staff user resolution
    # -----------------------------------------------------------------------
    def test_resolve_staff_user_default(self):
        resolved = _resolve_staff_user()
        self.assertEqual(resolved.id, self.staff_user.id)
        self.assertTrue(resolved.is_staff)

    def test_resolve_staff_user_by_username(self):
        resolved = _resolve_staff_user("rajat")
        self.assertEqual(resolved.username, "rajat")

    def test_resolve_non_staff_user_rejected(self):
        with self.assertRaisesRegex(CommandError, "does not have is_staff=True"):
            _resolve_staff_user("normal_user")

    def test_resolve_unknown_user_rejected(self):
        with self.assertRaisesRegex(CommandError, "not found or is inactive"):
            _resolve_staff_user("nonexistent_user")

    # -----------------------------------------------------------------------
    # 2. Safety guard and parameter validation
    # -----------------------------------------------------------------------
    @override_settings(DEBUG=False)
    def test_debug_false_rejected(self):
        with self.assertRaises((CommandError, SystemExit)):
            call_command("correct_synthetic_m1_records", dry_run=True, stdout=StringIO(), stderr=StringIO())

    def test_missing_confirm_and_dry_run_exits_nonzero(self):
        err = StringIO()
        with mock.patch("core.management.commands.correct_synthetic_m1_records._assert_safe_local_database", return_value=_guard_pass()):
            with self.assertRaises(SystemExit) as ctx:
                call_command("correct_synthetic_m1_records", dry_run=False, confirm=False, stdout=StringIO(), stderr=err)
            self.assertNotEqual(ctx.exception.code, 0)

        # DB unchanged
        self.m724.refresh_from_db()
        self.m725.refresh_from_db()
        self.assertEqual(self.m724.provenance, "tmdb_catalogue")
        self.assertEqual(self.m725.provenance, "tmdb_catalogue")

    # -----------------------------------------------------------------------
    # 3. Dry-run immutability
    # -----------------------------------------------------------------------
    def test_dry_run_makes_zero_changes(self):
        out = StringIO()
        with mock.patch("core.management.commands.correct_synthetic_m1_records._assert_safe_local_database", return_value=_guard_pass()):
            call_command("correct_synthetic_m1_records", dry_run=True, stdout=out, stderr=StringIO())

        self.m724.refresh_from_db()
        self.m725.refresh_from_db()
        self.assertEqual(self.m724.provenance, "tmdb_catalogue")
        self.assertEqual(self.m725.provenance, "tmdb_catalogue")
        self.assertFalse(self.m724.display_ready)
        self.assertTrue(self.m725.display_ready)
        self.assertTrue(self.m725.recommendable)
        self.assertEqual(self.m724.field_provenance, {})
        self.assertEqual(self.m725.field_provenance, {})

        output = out.getvalue()
        self.assertIn("[DRY-RUN COMPLETE]", output)
        self.assertIn("Movie 724 (M1):", output)
        self.assertIn("Movie 725 (M1):", output)

    # -----------------------------------------------------------------------
    # 4. Target record spec validation
    # -----------------------------------------------------------------------
    def test_target_mismatch_detected(self):
        self.m724.title = "Wrong Title"
        self.m724.save()
        with self.assertRaisesRegex(CommandError, "expected 'M1'"):
            _inspect_target_records()

    # -----------------------------------------------------------------------
    # 5. Execution with --confirm
    # -----------------------------------------------------------------------
    def test_execution_transitions_records_and_preserves_audit(self):
        out = StringIO()
        with mock.patch("core.management.commands.correct_synthetic_m1_records._assert_safe_local_database", return_value=_guard_pass()):
            call_command("correct_synthetic_m1_records", confirm=True, dry_run=False, stdout=out, stderr=StringIO())

        self.m724.refresh_from_db()
        self.m725.refresh_from_db()

        # Both records must end in synthetic_fixture
        self.assertEqual(self.m724.provenance, "synthetic_fixture")
        self.assertEqual(self.m725.provenance, "synthetic_fixture")

        # Both records must have display_ready=False and recommendable=False
        self.assertFalse(self.m724.display_ready)
        self.assertFalse(self.m724.recommendable)
        self.assertFalse(self.m725.display_ready)
        self.assertFalse(self.m725.recommendable)

        # Verify audit history on Movie 724
        audit_724 = self.m724.field_provenance.get("_classification_audit", [])
        self.assertEqual(len(audit_724), 2)
        self.assertEqual(audit_724[0]["from_provenance"], "tmdb_catalogue")
        self.assertEqual(audit_724[0]["to_provenance"], "needs_review")
        self.assertEqual(audit_724[0]["actor"], "rajat")
        self.assertEqual(audit_724[0]["actor_type"], "user")
        self.assertEqual(audit_724[1]["from_provenance"], "needs_review")
        self.assertEqual(audit_724[1]["to_provenance"], "synthetic_fixture")
        self.assertEqual(audit_724[1]["actor"], "rajat")
        self.assertEqual(audit_724[1]["actor_type"], "user")

        # Verify audit history on Movie 725
        audit_725 = self.m725.field_provenance.get("_classification_audit", [])
        self.assertEqual(len(audit_725), 2)
        self.assertEqual(audit_725[0]["from_provenance"], "tmdb_catalogue")
        self.assertEqual(audit_725[0]["to_provenance"], "needs_review")
        self.assertEqual(audit_725[0]["actor"], "rajat")
        self.assertEqual(audit_725[0]["actor_type"], "user")
        self.assertEqual(audit_725[1]["from_provenance"], "needs_review")
        self.assertEqual(audit_725[1]["to_provenance"], "synthetic_fixture")
        self.assertEqual(audit_725[1]["actor"], "rajat")
        self.assertEqual(audit_725[1]["actor_type"], "user")

    # -----------------------------------------------------------------------
    # 6. Exclusion from fixture candidate pool
    # -----------------------------------------------------------------------
    def test_post_correction_exclusion_from_fixture_candidates(self):
        with mock.patch("core.management.commands.correct_synthetic_m1_records._assert_safe_local_database", return_value=_guard_pass()):
            call_command("correct_synthetic_m1_records", confirm=True, dry_run=False, stdout=StringIO(), stderr=StringIO())

        self.m724.refresh_from_db()
        self.m725.refresh_from_db()

        # 1. Candidate queryset filter (provenance='needs_review') strictly excludes them
        candidates = list(_build_candidate_queryset(limit=100))
        candidate_ids = [m.id for m in candidates]
        self.assertNotIn(724, candidate_ids)
        self.assertNotIn(725, candidate_ids)

        # 2. _validate_candidate explicitly rejects them
        ok_724, reason_724 = _validate_candidate(self.m724)
        self.assertFalse(ok_724)
        self.assertIn("synthetic_fixture", reason_724)

        ok_725, reason_725 = _validate_candidate(self.m725)
        self.assertFalse(ok_725)
        self.assertIn("synthetic_fixture", reason_725)
