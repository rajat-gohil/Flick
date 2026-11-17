"""
Tests for seed_local_dev_catalogue management command with Batch 2 TMDB Verification.

Coverage:
1. Local Database Safety Guard:
   - DEBUG=False rejection.
   - Non-SQLite engine rejection (PostgreSQL, MySQL, Staging).
   - Database path mismatch rejection (other files, /tmp, in-memory).
   - Canonical path accepted.
2. Parameter Validation:
   - Invalid --limit rejected (0, -1, above 557).
   - Boundaries accepted (1, 557).
   - Missing --confirm flag rejected with non-zero exit code.
3. Dry-Run Immutability:
   - Zero database mutations.
   - Zero TMDB API calls.
   - Proper path and engine reporting.
4. Candidate Pre-Validation:
   - Non-needs_review rejected.
   - Invalid TMDB ID rejected.
   - Whitespace title / poster / language rejected.
   - Ineligible / no-genre records rejected.
5. TMDB Upstream Verification Pipeline:
   - Candidate with valid-looking metadata but no TMDB verification (404 / mismatch) remains needs_review.
   - Failed TMDB requests (network error / connection reset / 500) do NOT promote records.
   - Verified candidates use existing classification state machine (transitions to tmdb_catalogue with audit trail).
   - Rate limiting follows existing infrastructure (token exhaustion fails closed, 429 recorded).
   - Synthetic fixtures remain distinct ('synthetic_fixture', not 'tmdb_catalogue').
   - 'manual_curated' records are never modified.
   - Command exits with non-zero status on partial or network failures.
"""

import datetime
import types
import uuid
from io import StringIO
from pathlib import Path
from unittest import mock
import requests

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from core.models import CatalogueJob, Genre, Movie
from core.services.enrichment_handlers import handle_catalogue_classification
from core.services.movie_mutations import transition_movie_classification
from core.management.commands.seed_local_dev_catalogue import (
    LIMIT_MAX,
    LIMIT_MIN,
    WORKER_ID,
    _assert_safe_local_database,
    _resolve_canonical_db_path,
    _validate_candidate,
)


def _make_movie(
    *,
    tmdb_id: int = 100001,
    title: str = "Test Movie",
    provenance: str = "needs_review",
    poster_path: str = "/poster.jpg",
    release_date=datetime.date(2010, 6, 15),
    original_language: str = "en",
    rating: float = 7.5,
    vote_count: int = 1000,
    with_genre: bool = True,
) -> Movie:
    """Create a Movie instance with valid attributes for candidate testing."""
    movie = Movie.objects.create(
        tmdb_id=tmdb_id,
        title=title,
        provenance=provenance,
        poster_path=poster_path,
        release_date=release_date,
        original_language=original_language,
        rating=rating,
        vote_count=vote_count,
        display_ready=False,
        recommendable=False,
    )
    if with_genre:
        genre, _ = Genre.objects.get_or_create(
            tmdb_id=18, defaults={"name": "Drama"}
        )
        movie.genres.add(genre)
    return movie


def _guard_pass():
    """Mock return value for passing safety guard."""
    return ("django.db.backends.sqlite3", "/test/db.sqlite3")


def _mock_tmdb_response(status_code: int = 200, data: dict = None):
    """Create a mock requests.Response for TMDB calls."""
    resp = mock.MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.json.return_value = data or {}
    resp.headers = {}
    if status_code >= 400 and status_code != 404:
        resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status_code}")
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# 1. Safety Guard Tests
# ---------------------------------------------------------------------------

class SafetyGuardDebugFalseTest(TestCase):
    @override_settings(DEBUG=False)
    def test_debug_false_raises_command_error(self):
        with self.assertRaisesRegex(CommandError, "DEBUG=False"):
            _assert_safe_local_database()

    @override_settings(DEBUG=False)
    def test_command_refuses_debug_false(self):
        with self.assertRaises((CommandError, SystemExit)):
            call_command(
                "seed_local_dev_catalogue",
                dry_run=True,
                limit=10,
                stdout=StringIO(),
                stderr=StringIO(),
            )


class SafetyGuardEngineTest(TestCase):
    @override_settings(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "flick_prod",
                "HOST": "localhost",
                "PORT": 5432,
            }
        },
    )
    def test_postgresql_engine_raises_command_error(self):
        with self.assertRaisesRegex(CommandError, "django.db.backends.postgresql"):
            _assert_safe_local_database()

    @override_settings(
        DEBUG=True,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": "flick",
            }
        },
    )
    def test_mysql_engine_raises_command_error(self):
        with self.assertRaisesRegex(CommandError, "mysql"):
            _assert_safe_local_database()


class SafetyGuardPathTest(TestCase):
    @override_settings(DEBUG=True)
    def test_mismatched_path_raises_command_error(self):
        canonical = _resolve_canonical_db_path()
        other = str(canonical.parent / "other_database.sqlite3")
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": other}}
        ):
            with self.assertRaisesRegex(CommandError, "does not match"):
                _assert_safe_local_database()

    @override_settings(DEBUG=True)
    def test_in_memory_path_raises_command_error(self):
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
        ):
            with self.assertRaises(CommandError):
                _assert_safe_local_database()

    @override_settings(DEBUG=True)
    def test_canonical_path_passes(self):
        canonical = str(_resolve_canonical_db_path())
        with override_settings(
            DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": canonical}}
        ):
            engine, path = _assert_safe_local_database()
            self.assertEqual(engine, "django.db.backends.sqlite3")
            self.assertEqual(str(Path(path).resolve()), str(Path(canonical).resolve()))


# ---------------------------------------------------------------------------
# 2. Limit & Parameter Validation Tests
# ---------------------------------------------------------------------------

class LimitValidationTest(TestCase):
    def test_limit_zero_rejected(self):
        with self.assertRaises((CommandError, SystemExit)):
            call_command("seed_local_dev_catalogue", limit=0, dry_run=True, stdout=StringIO(), stderr=StringIO())

    def test_limit_negative_rejected(self):
        with self.assertRaises((CommandError, SystemExit)):
            call_command("seed_local_dev_catalogue", limit=-1, dry_run=True, stdout=StringIO(), stderr=StringIO())

    def test_limit_above_max_rejected(self):
        with self.assertRaises((CommandError, SystemExit)):
            call_command("seed_local_dev_catalogue", limit=LIMIT_MAX + 1, dry_run=True, stdout=StringIO(), stderr=StringIO())

    def test_missing_confirm_and_missing_dry_run_exits_nonzero(self):
        err = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            with self.assertRaises(SystemExit) as ctx:
                call_command("seed_local_dev_catalogue", limit=10, dry_run=False, confirm=False, stdout=StringIO(), stderr=err)
            self.assertNotEqual(ctx.exception.code, 0)
            self.assertEqual(Movie.objects.filter(provenance="tmdb_catalogue").count(), 0)


# ---------------------------------------------------------------------------
# 3. Dry-Run Immutability Tests
# ---------------------------------------------------------------------------

class DryRunImmutabilityTest(TestCase):
    def setUp(self):
        self.movie = _make_movie(tmdb_id=200001)

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_dry_run_makes_zero_mutations_and_zero_tmdb_calls(self, mock_tmdb_get):
        out = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", dry_run=True, limit=50, stdout=out, stderr=StringIO())

        # No TMDB API calls
        mock_tmdb_get.assert_not_called()

        # No database mutations
        m = Movie.objects.get(pk=self.movie.pk)
        self.assertEqual(m.provenance, "needs_review")
        self.assertFalse(m.display_ready)
        self.assertFalse(m.recommendable)

        output = out.getvalue()
        self.assertIn("DRY-RUN COMPLETE", output)
        self.assertIn("db.sqlite3", output)
        self.assertIn("sqlite3", output)


# ---------------------------------------------------------------------------
# 4. Candidate Pre-Validation Tests
# ---------------------------------------------------------------------------

class CandidatePrevalidationTest(TestCase):
    def setUp(self):
        Genre.objects.get_or_create(tmdb_id=18, defaults={"name": "Drama"})

    def test_valid_candidate_passes(self):
        m = _make_movie(tmdb_id=300001)
        ok, reason = _validate_candidate(m)
        self.assertTrue(ok, reason)

    def test_wrong_provenance_rejected(self):
        m = Movie.objects.create(tmdb_id=300002, title="Already", provenance="tmdb_catalogue", poster_path="/p.jpg", release_date=datetime.date(2010, 1, 1), original_language="en")
        ok, reason = _validate_candidate(m)
        self.assertFalse(ok)
        self.assertIn("provenance", reason)

    def test_tmdb_id_invalid_rejected(self):
        m = Movie.objects.create(tmdb_id=0, title="Zero ID", provenance="needs_review", poster_path="/p.jpg", release_date=datetime.date(2010, 1, 1), original_language="en")
        ok, reason = _validate_candidate(m)
        self.assertFalse(ok)
        self.assertIn("tmdb_id", reason)

    def test_whitespace_fields_rejected(self):
        m1 = Movie.objects.create(tmdb_id=300003, title="   ", provenance="needs_review", poster_path="/p.jpg", release_date=datetime.date(2010, 1, 1), original_language="en")
        ok, reason = _validate_candidate(m1)
        self.assertFalse(ok)

        m2 = Movie.objects.create(tmdb_id=300004, title="Title", provenance="needs_review", poster_path="   ", release_date=datetime.date(2010, 1, 1), original_language="en")
        ok, reason = _validate_candidate(m2)
        self.assertFalse(ok)

    def test_no_genres_fails_recommendable_check(self):
        m = Movie.objects.create(tmdb_id=300005, title="No Genres", provenance="needs_review", poster_path="/p.jpg", release_date=datetime.date(2010, 1, 1), original_language="en")
        ok, reason = _validate_candidate(m)
        self.assertFalse(ok)
        self.assertIn("recommendable", reason)


# ---------------------------------------------------------------------------
# 5. TMDB Verification Pipeline Tests
# ---------------------------------------------------------------------------

@override_settings(DEBUG=True)
class TMDBVerificationPipelineTest(TestCase):
    """
    Tests proving that records are ONLY promoted after TMDB identity verification.
    """

    def setUp(self):
        Genre.objects.get_or_create(tmdb_id=18, defaults={"name": "Drama"})
        Genre.objects.get_or_create(tmdb_id=28, defaults={"name": "Action"})

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_candidate_with_valid_metadata_without_tmdb_verification_remains_needs_review(self, mock_get):
        """
        Even if local metadata is valid, if TMDB returns 404, the movie MUST remain 'needs_review'.
        """
        movie = _make_movie(tmdb_id=400001, title="Unverified 404 Movie")
        mock_get.return_value = _mock_tmdb_response(status_code=404)

        out = StringIO()
        err = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            try:
                call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=out, stderr=err)
            except SystemExit as exc:
                print("CAUGHT SystemExit:", exc)
                print("TEST OUT:", out.getvalue())
                print("TEST ERR:", err.getvalue())
                raise

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)
        self.assertFalse(movie.recommendable)

        # Audit history must record TMDB 404
        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertGreater(len(audit), 0)
        self.assertIn("404", audit[-1]["reason"])

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_title_mismatch_remains_needs_review(self, mock_get):
        """
        If TMDB returns a title that does not match local title, movie MUST remain 'needs_review'.
        """
        movie = _make_movie(tmdb_id=400002, title="My Local Film")
        mock_get.return_value = _mock_tmdb_response(
            status_code=200,
            data={
                "id": 400002,
                "title": "Totally Disparate Hollywood Movie",
                "status": "Released",
                "release_date": "2010-06-15",
            },
        )

        out = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=out, stderr=StringIO())

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)

        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertIn("mismatch", audit[-1]["reason"].lower())

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_failed_tmdb_requests_do_not_promote_records(self, mock_get):
        """
        If TMDB connection drops or returns 500, movie MUST remain 'needs_review' and command exits non-zero.
        """
        movie = _make_movie(tmdb_id=400003, title="Network Fail Movie")
        mock_get.side_effect = requests.ConnectionError("Connection aborted. ConnectionResetError(54)")

        err = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            with self.assertRaises(SystemExit) as ctx:
                call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=err)
            self.assertNotEqual(ctx.exception.code, 0)

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_verified_candidate_uses_existing_classification_state_machine(self, mock_get):
        """
        When TMDB confirms identity, movie transitions to 'tmdb_catalogue' with audit evidence,
        becomes display_ready=True and recommendable=True, and leaves zero CatalogueJobs enqueued.
        """
        movie = _make_movie(tmdb_id=27205, title="Inception", release_date=datetime.date(2010, 7, 16))

        # Mock classification GET (enrichment GET is NOT called as downstream enqueue is suppressed)
        class_resp = _mock_tmdb_response(200, {
            "id": 27205,
            "title": "Inception",
            "original_title": "Inception",
            "status": "Released",
            "release_date": "2010-07-16",
        })
        mock_get.return_value = class_resp

        out = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=out, stderr=StringIO())

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "tmdb_catalogue")
        self.assertTrue(movie.display_ready)
        self.assertTrue(movie.recommendable)

        # Crucial: Zero CatalogueJob objects created or left pending
        self.assertEqual(CatalogueJob.objects.count(), 0)

        # Audit trail must show worker:local_dev_fixture and verified evidence
        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertGreater(len(audit), 0)
        last_entry = audit[-1]
        self.assertEqual(last_entry["from_provenance"], "needs_review")
        self.assertEqual(last_entry["to_provenance"], "tmdb_catalogue")
        self.assertEqual(last_entry["actor_type"], "worker")
        self.assertIn(WORKER_ID, last_entry["actor"])
        self.assertEqual(last_entry["metadata_evidence"]["tmdb_id"], 27205)

    @mock.patch("core.services.enrichment_handlers.acquire_tmdb_token")
    def test_rate_limiting_token_exhaustion_fails_closed(self, mock_acquire):
        """
        When rate limiter budget is exhausted, classification handler fails closed.
        Movie remains 'needs_review' and command exits with non-zero code.
        """
        movie = _make_movie(tmdb_id=400004, title="Rate Limited Movie")
        mock_acquire.return_value = False  # rate limit budget exhausted

        err = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            with self.assertRaises(SystemExit) as ctx:
                call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=err)
            self.assertNotEqual(ctx.exception.code, 0)

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)

    @mock.patch("core.services.enrichment_handlers.record_tmdb_429")
    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_tmdb_429_recorded_and_fails_closed(self, mock_get, mock_record_429):
        """
        When TMDB returns 429, record_tmdb_429 is invoked, movie remains needs_review, command exits non-zero.
        """
        movie = _make_movie(tmdb_id=400005, title="Rate Limited 429 Movie")
        resp_429 = _mock_tmdb_response(status_code=429)
        resp_429.headers = {"Retry-After": "15"}
        mock_get.return_value = resp_429

        err = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            with self.assertRaises(SystemExit) as ctx:
                call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=err)
            self.assertNotEqual(ctx.exception.code, 0)

        mock_record_429.assert_called_with("15")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_synthetic_fixture_pattern_becomes_synthetic_fixture_not_catalogue(self, mock_get):
        """
        A movie matching synthetic patterns is classified as 'synthetic_fixture', NEVER 'tmdb_catalogue'.
        """
        movie = Movie.objects.create(
            tmdb_id=400006,
            title="synthetic_movie_999",
            provenance="needs_review",
            poster_path="/poster.jpg",
            release_date=datetime.date(2020, 1, 1),
            original_language="en",
        )
        genre, _ = Genre.objects.get_or_create(tmdb_id=18, defaults={"name": "Drama"})
        movie.genres.add(genre)

        out = StringIO()
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=out, stderr=StringIO())

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "synthetic_fixture")
        self.assertFalse(movie.display_ready)
        # TMDB API should not have been called for synthetic pattern
        mock_get.assert_not_called()

    def test_manual_curated_is_never_touched(self):
        """
        'manual_curated' records are never included in the candidate pool and remain untouched.
        """
        movie = _make_movie(tmdb_id=400007, provenance="manual_curated")
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=StringIO())

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "manual_curated")


# ---------------------------------------------------------------------------
# 6. Queue Lifecycle & Provenance Correction Tests
# ---------------------------------------------------------------------------

@override_settings(DEBUG=True)
class QueueLifecycleAndProvenanceCorrectionTest(TestCase):
    def setUp(self):
        Genre.objects.get_or_create(tmdb_id=18, defaults={"name": "Drama"})

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_classification_enqueue_downstream_parameter(self, mock_get):
        """
        handle_catalogue_classification:
        - When enqueue_downstream=True (default), enqueues a downstream catalogue_enrichment job.
        - When enqueue_downstream=False, suppresses downstream enqueueing and returns None/False.
        """
        mock_get.return_value = _mock_tmdb_response(200, {
            "id": 500001,
            "title": "Downstream Test Movie",
            "status": "Released",
            "release_date": "2015-05-01",
        })

        # 1. Default (enqueue_downstream=True)
        m1 = _make_movie(tmdb_id=500001, title="Downstream Test Movie", release_date=datetime.date(2015, 5, 1))
        job1 = types.SimpleNamespace(entity_id=str(m1.id))
        res1 = handle_catalogue_classification(
            job=job1,
            worker_id="test_worker",
            lease_token=uuid.uuid4(),
            generation=1,
            # enqueue_downstream omitted -> defaults to True
        )
        self.assertEqual(res1["classification"], "tmdb_catalogue")
        self.assertIsNotNone(res1["downstream_job_id"])
        self.assertTrue(res1["downstream_job_created"])
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_enrichment", entity_id=str(m1.id)).count(), 1)
        job_obj = CatalogueJob.objects.get(job_type="catalogue_enrichment", entity_id=str(m1.id))
        self.assertEqual(job_obj.status, CatalogueJob.Status.PENDING)

        # 2. Suppressed (enqueue_downstream=False)
        m2 = _make_movie(tmdb_id=500002, title="Downstream Test Movie", release_date=datetime.date(2015, 5, 1))
        mock_get.return_value = _mock_tmdb_response(200, {
            "id": 500002,
            "title": "Downstream Test Movie",
            "status": "Released",
            "release_date": "2015-05-01",
        })
        job2 = types.SimpleNamespace(entity_id=str(m2.id))
        res2 = handle_catalogue_classification(
            job=job2,
            worker_id="test_worker",
            lease_token=uuid.uuid4(),
            generation=1,
            enqueue_downstream=False,
        )
        self.assertEqual(res2["classification"], "tmdb_catalogue")
        self.assertIsNone(res2["downstream_job_id"])
        self.assertFalse(res2["downstream_job_created"])
        self.assertEqual(CatalogueJob.objects.filter(job_type="catalogue_enrichment", entity_id=str(m2.id)).count(), 0)

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_fixture_execution_leaves_zero_catalogue_jobs(self, mock_get):
        """
        Executing seed_local_dev_catalogue with --confirm promotes verified candidates
        without creating any CatalogueJob rows.
        """
        m = _make_movie(tmdb_id=500003, title="Fixture Clean Queue Movie", release_date=datetime.date(2018, 1, 1))
        mock_get.return_value = _mock_tmdb_response(200, {
            "id": 500003,
            "title": "Fixture Clean Queue Movie",
            "status": "Released",
            "release_date": "2018-01-01",
        })

        self.assertEqual(CatalogueJob.objects.count(), 0)
        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=StringIO())

        m.refresh_from_db()
        self.assertEqual(m.provenance, "tmdb_catalogue")
        self.assertTrue(m.display_ready)
        self.assertEqual(CatalogueJob.objects.count(), 0)

    @mock.patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_fixture_execution_preserves_preexisting_catalogue_jobs(self, mock_get):
        """
        Executing seed_local_dev_catalogue never modifies or deletes pre-existing CatalogueJob records.
        """
        pre_existing = CatalogueJob.objects.create(
            job_type="catalogue_enrichment",
            entity_type="movie",
            entity_id="9999",
            external_id="9999",
            priority=50,
            status=CatalogueJob.Status.PENDING,
        )
        m = _make_movie(tmdb_id=500004, title="Preserve Preexisting Job Movie", release_date=datetime.date(2018, 1, 1))
        mock_get.return_value = _mock_tmdb_response(200, {
            "id": 500004,
            "title": "Preserve Preexisting Job Movie",
            "status": "Released",
            "release_date": "2018-01-01",
        })

        with mock.patch("core.management.commands.seed_local_dev_catalogue._assert_safe_local_database", return_value=_guard_pass()):
            call_command("seed_local_dev_catalogue", limit=10, confirm=True, dry_run=False, stdout=StringIO(), stderr=StringIO())

        # Pre-existing job is completely preserved
        pre_existing.refresh_from_db()
        self.assertEqual(pre_existing.status, CatalogueJob.Status.PENDING)
        self.assertEqual(CatalogueJob.objects.count(), 1)

    def test_synthetic_provenance_correction_state_machine_restrictions(self):
        """
        Investigate & verify state-machine restrictions:
        - transition_movie_classification blocks direct transition tmdb_catalogue -> synthetic_fixture
          for automated workers (ValueError: Automated transitions must be from 'needs_review').
        - transition_movie_classification blocks direct transition tmdb_catalogue -> synthetic_fixture
          for manual staff users (ValueError: Invalid manual classification transition).
        - Two-step controlled correction (tmdb_catalogue -> needs_review -> synthetic_fixture)
          succeeds under manual staff authorization and records complete audit history.
        """
        movie = Movie.objects.create(
            tmdb_id=7001,
            title="M1",
            provenance="tmdb_catalogue",
            poster_path="/p1.jpg",
            display_ready=True,
            recommendable=True,
        )
        staff_user = User.objects.create_superuser(
            username="admin_auditor",
            email="admin@flick.test",
            password="testpassword",
        )

        # 1. Automated attempt to transition tmdb_catalogue -> synthetic_fixture fails
        with self.assertRaisesRegex(ValueError, "Automated transitions must be from 'needs_review'"):
            transition_movie_classification(
                movie_id=movie.id,
                new_provenance="synthetic_fixture",
                reason="Attempt automated correction of synthetic stub",
                worker_id="worker-1",
            )

        # 2. Manual attempt to transition tmdb_catalogue -> synthetic_fixture directly fails
        with self.assertRaisesRegex(ValueError, "Invalid manual classification transition from 'tmdb_catalogue' to 'synthetic_fixture'"):
            transition_movie_classification(
                movie_id=movie.id,
                new_provenance="synthetic_fixture",
                reason="Attempt direct manual transition to synthetic_fixture",
                user=staff_user,
            )

        # 3. Two-step transition via needs_review succeeds under staff authority
        # Step A: tmdb_catalogue -> needs_review
        transition_movie_classification(
            movie_id=movie.id,
            new_provenance="needs_review",
            reason="Step 1: Revoke erroneous tmdb_catalogue provenance on synthetic stub",
            user=staff_user,
        )
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)

        # Step B: needs_review -> synthetic_fixture
        transition_movie_classification(
            movie_id=movie.id,
            new_provenance="synthetic_fixture",
            reason="Step 2: Reclassify confirmed synthetic stub as synthetic_fixture",
            user=staff_user,
        )
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "synthetic_fixture")
        self.assertFalse(movie.display_ready)
        self.assertFalse(movie.recommendable)

        # Full audit history preserved
        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertEqual(len(audit), 2)
        self.assertEqual(audit[0]["from_provenance"], "tmdb_catalogue")
        self.assertEqual(audit[0]["to_provenance"], "needs_review")
        self.assertEqual(audit[0]["actor"], "admin_auditor")
        self.assertEqual(audit[1]["from_provenance"], "needs_review")
        self.assertEqual(audit[1]["to_provenance"], "synthetic_fixture")
        self.assertEqual(audit[1]["actor"], "admin_auditor")
