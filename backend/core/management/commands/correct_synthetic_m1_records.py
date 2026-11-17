"""
LOCAL DEVELOPMENT ONLY — Administrative correction of synthetic test stubs M1 (IDs 724 and 725).

Transitions Movies 724 and 725 from 'tmdb_catalogue' to 'synthetic_fixture' using the
existing classification state machine via the permitted two-step administrative path:
  Step 1: 'tmdb_catalogue' -> 'needs_review'
  Step 2: 'needs_review'   -> 'synthetic_fixture'

Requirements enforced:
1. Reuses the 3-layer local database safety guard (_assert_safe_local_database):
   - DEBUG=True required.
   - Database engine must be django.db.backends.sqlite3.
   - Database path must match BASE_DIR/db.sqlite3 canonically.
2. Requires an authenticated staff user (defaulting to first active is_staff=True user,
   or specified via --staff-user).
3. Executes both transitions for each record atomically inside transaction.atomic().
4. Uses transition_movie_classification() so:
   - State-machine constraints are strictly validated.
   - Full audit history (_classification_audit) is preserved with actor, timestamp,
     reasons, and metadata evidence.
   - recalculate_movie_eligibility() is invoked atomically on each transition.
5. Verifies post-condition: both records end with:
   - provenance = 'synthetic_fixture'
   - display_ready = False
   - recommendable = False
6. Requires explicit --confirm flag to execute; --dry-run makes zero changes.

Invocation:
  python manage.py correct_synthetic_m1_records --dry-run
  python manage.py correct_synthetic_m1_records --confirm
"""

from __future__ import annotations

import logging
from typing import Any, List, Tuple

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.management.commands.seed_local_dev_catalogue import _assert_safe_local_database
from core.models import Movie
from core.services.movie_mutations import transition_movie_classification

logger = logging.getLogger(__name__)
User = get_user_model()

TARGET_RECORD_SPECS: List[dict] = [
    {"id": 724, "expected_tmdb_id": 8001, "expected_title": "M1"},
    {"id": 725, "expected_tmdb_id": 7001, "expected_title": "M1"},
]


def _resolve_staff_user(username: str | None = None) -> Any:
    """
    Resolve an active staff user to perform administrative classification transitions.
    If username is provided, look up that user and ensure is_staff=True and is_active=True.
    Otherwise, look up the first active is_staff=True user in the local database.
    """
    if username:
        user = User.objects.filter(username=username, is_active=True).first()
        if not user:
            raise CommandError(f"Specified staff user '{username}' not found or is inactive.")
        if not user.is_staff:
            raise CommandError(f"User '{username}' does not have is_staff=True permission.")
        return user

    user = User.objects.filter(is_staff=True, is_active=True).order_by("id").first()
    if not user:
        raise CommandError(
            "No active staff user found in local database. "
            "Create a staff user (e.g. python manage.py create_admin or createsuperuser) "
            "or pass --staff-user <username>."
        )
    return user


def _inspect_target_records() -> List[Tuple[Movie, dict]]:
    """
    Inspect target records 724 and 725 and verify they exist and match expected specs.
    Returns list of (movie_instance, spec).
    """
    targets: List[Tuple[Movie, dict]] = []
    for spec in TARGET_RECORD_SPECS:
        mid = spec["id"]
        movie = Movie.objects.filter(pk=mid).first()
        if not movie:
            raise CommandError(f"Target movie ID {mid} not found in database.")

        if movie.tmdb_id != spec["expected_tmdb_id"]:
            raise CommandError(
                f"Movie ID {mid} has tmdb_id={movie.tmdb_id!r}, "
                f"expected {spec['expected_tmdb_id']!r}."
            )

        if movie.title != spec["expected_title"]:
            raise CommandError(
                f"Movie ID {mid} has title={movie.title!r}, "
                f"expected {spec['expected_title']!r}."
            )

        targets.append((movie, spec))
    return targets


class Command(BaseCommand):
    help = (
        "LOCAL DEVELOPMENT ONLY. Corrects synthetic M1 test records (IDs 724 and 725) "
        "by transitioning from 'tmdb_catalogue' to 'synthetic_fixture' via permitted "
        "administrative two-step state machine transitions under staff authority."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview the correction and audit entries without making database changes.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Required to execute the correction. Omit for dry-run preview.",
        )
        parser.add_argument(
            "--staff-user",
            type=str,
            default=None,
            help="Username of the staff user to attribute administrative transitions to.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        confirm: bool = options["confirm"]
        staff_username: str | None = options["staff_user"]

        # Enforce three-layer local database safety guard
        engine, db_path = _assert_safe_local_database()

        if not dry_run and not confirm:
            self.stderr.write(
                self.style.ERROR(
                    "This command modifies local movie provenance.\n"
                    "  Pass --confirm to execute, or --dry-run to preview without changes.\n"
                    "  Example: python manage.py correct_synthetic_m1_records --confirm"
                )
            )
            raise SystemExit(1)

        staff_user = _resolve_staff_user(staff_username)
        targets = _inspect_target_records()

        self.stdout.write(f"Database engine: {engine}")
        self.stdout.write(f"Database path:   {db_path}")
        self.stdout.write(f"Staff actor:     {staff_user.username} (ID: {staff_user.id}, is_staff={staff_user.is_staff})")
        if dry_run:
            self.stdout.write(self.style.NOTICE("Mode: DRY-RUN — no database changes will be committed"))
        else:
            self.stdout.write(self.style.WARNING("Mode: EXECUTE — performing two-step atomic transitions"))

        self.stdout.write("")
        self.stdout.write("Target records before correction:")
        for movie, _ in targets:
            self.stdout.write(
                f"  Movie [{movie.id:>3}] {movie.title!r:<6} tmdb_id={movie.tmdb_id:<6} "
                f"provenance={movie.provenance:<16} display_ready={movie.display_ready!s:<5} "
                f"recommendable={movie.recommendable!s:<5}"
            )

        if dry_run:
            self.stdout.write("")
            self.stdout.write("Dry-run preview of planned two-step transitions:")
            for movie, _ in targets:
                self.stdout.write(f"  Movie {movie.id} ({movie.title}):")
                self.stdout.write(f"    Step 1: {movie.provenance} -> needs_review")
                self.stdout.write(f"            Reason: 'Step 1/2: Revoke erroneous tmdb_catalogue provenance on synthetic test stub M1'")
                self.stdout.write(f"            Actor:  {staff_user.username} (staff)")
                self.stdout.write(f"    Step 2: needs_review -> synthetic_fixture")
                self.stdout.write(f"            Reason: 'Step 2/2: Reclassify confirmed synthetic test stub M1 as synthetic_fixture'")
                self.stdout.write(f"            Actor:  {staff_user.username} (staff)")
                self.stdout.write(f"    Expected final state: provenance='synthetic_fixture', display_ready=False, recommendable=False")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("[DRY-RUN COMPLETE] Zero changes made. All preconditions satisfied."))
            self.stdout.write("To execute: python manage.py correct_synthetic_m1_records --confirm")
            return

        # EXECUTE — Atomic two-step transition per record
        self.stdout.write("")
        self.stdout.write("Executing atomic transitions...")
        corrected: List[Movie] = []

        for movie, _ in targets:
            with transaction.atomic():
                # Step 1: tmdb_catalogue -> needs_review
                m_step1 = transition_movie_classification(
                    movie_id=movie.id,
                    new_provenance="needs_review",
                    reason="Step 1/2: Revoke erroneous tmdb_catalogue provenance on synthetic test stub M1",
                    user=staff_user,
                    metadata_evidence={
                        "correction_step": 1,
                        "prior_provenance": movie.provenance,
                        "remedy": "administrative_synthetic_correction",
                    },
                )

                # Step 2: needs_review -> synthetic_fixture
                m_final = transition_movie_classification(
                    movie_id=movie.id,
                    new_provenance="synthetic_fixture",
                    reason="Step 2/2: Reclassify confirmed synthetic test stub M1 as synthetic_fixture",
                    user=staff_user,
                    metadata_evidence={
                        "correction_step": 2,
                        "synthetic_marker": "M1_test_stub",
                        "remedy": "administrative_synthetic_correction",
                    },
                )
                corrected.append(m_final)

        self.stdout.write("")
        self.stdout.write("=" * 65)
        self.stdout.write(self.style.SUCCESS("correct_synthetic_m1_records execution complete"))
        self.stdout.write("=" * 65)
        self.stdout.write("Target records after correction:")
        for m in corrected:
            m.refresh_from_db()
            self.stdout.write(
                f"  Movie [{m.id:>3}] {m.title!r:<6} tmdb_id={m.tmdb_id:<6} "
                f"provenance={m.provenance:<17} display_ready={m.display_ready!s:<5} "
                f"recommendable={m.recommendable!s:<5}"
            )

            # Display audit trail
            audit = m.field_provenance.get("_classification_audit", [])
            self.stdout.write(f"    Audit entries ({len(audit)}):")
            for entry in audit[-2:]:
                self.stdout.write(
                    f"      - {entry.get('from_provenance')} -> {entry.get('to_provenance')} "
                    f"by {entry.get('actor')} at {entry.get('timestamp')}: {entry.get('reason')}"
                )

        # Final assertion check
        for m in corrected:
            assert m.provenance == "synthetic_fixture", f"Movie {m.id} provenance is {m.provenance}"
            assert m.display_ready is False, f"Movie {m.id} display_ready is {m.display_ready}"
            assert m.recommendable is False, f"Movie {m.id} recommendable is {m.recommendable}"
            audit = m.field_provenance.get("_classification_audit", [])
            assert len(audit) >= 2, f"Movie {m.id} audit length is {len(audit)}"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("All post-conditions verified successfully."))
