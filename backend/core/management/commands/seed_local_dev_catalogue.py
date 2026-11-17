"""
LOCAL DEVELOPMENT ONLY — Controlled catalogue fixture for functional testing.

Promotes a bounded selection of existing legacy movies from 'needs_review' to
'tmdb_catalogue' ONLY after verifying their identities against TMDB using the
existing Batch 2 classification and enrichment pipeline.

PROVENANCE & VERIFICATION ARCHITECTURE:
- Never promotes records solely on local metadata quality checks.
- sync_movies.py did not preserve per-record source evidence; therefore,
  candidate identity MUST be verified against TMDB upstream.
- Uses handle_catalogue_classification() from core.services.enrichment_handlers:
  * Acquires rate-limit token via acquire_tmdb_token('background').
  * Queries TMDB via _tmdb_api_get('/movie/{tmdb_id}').
  * Validates TMDB status in ('Released', 'Post Production').
  * Performs deterministic title/year verification (exact or Levenshtein >= 0.85 + year +/- 1).
  * On match: transitions to 'tmdb_catalogue' via transition_movie_classification()
    with full metadata evidence and audit logging. Downstream enrichment enqueueing is
    explicitly suppressed (enqueue_downstream=False) to avoid queue churn and background worker
    dependencies; verified candidates immediately become display_ready=True and recommendable=True.
  * On 404 or mismatch: retains 'needs_review' with audit log.
  * On synthetic patterns: transitions to 'synthetic_fixture'.
- If TMDB connectivity is unavailable (e.g., in a sandboxed execution environment),
  verification fails closed. The command records the failure, retains 'needs_review',
  and exits with a non-zero status. It NEVER falls back to unverified local promotion.

Safety guarantees enforced unconditionally:
1. DEBUG=True is required.
2. The database engine must be django.db.backends.sqlite3.
3. The resolved database file path must be the canonical local dev database
   (BASE_DIR/db.sqlite3). Any other path is rejected.
4. Requires explicit --confirm flag; --dry-run makes zero database changes and zero API calls.
5. Only 'needs_review' records are candidates. 'manual_curated' is never touched.
6. Invalid --limit values are rejected rather than silently clamped.
7. Idempotent: re-running skips already-classified records safely.

Invocation:
  python manage.py seed_local_dev_catalogue --dry-run            # preview only
  python manage.py seed_local_dev_catalogue --limit 150 --confirm  # execute
"""

import logging
import types
import uuid
from pathlib import Path
from typing import Any, List, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import Movie
from core.services.catalogue_eligibility import evaluate_eligibility_predicates
from core.services.enrichment_handlers import handle_catalogue_classification

logger = logging.getLogger(__name__)

WORKER_ID = "local_dev_fixture"

LIMIT_MIN = 1
LIMIT_MAX = 557


# ---------------------------------------------------------------------------
# Safety guards
# ---------------------------------------------------------------------------

def _resolve_canonical_db_path() -> Path:
    """Return the canonical local dev SQLite path: BASE_DIR/db.sqlite3."""
    return Path(settings.BASE_DIR) / "db.sqlite3"


def _assert_safe_local_database() -> Tuple[str, str]:
    """
    Enforce the three-layer local database safety guard:
    1. DEBUG must be True.
    2. Engine must be django.db.backends.sqlite3.
    3. Resolved DB file path must equal BASE_DIR/db.sqlite3.

    Returns (engine, resolved_path_str) on success.
    Raises CommandError on any violation.
    """
    if not getattr(settings, "DEBUG", False):
        raise CommandError(
            "REJECTED: DEBUG=False. seed_local_dev_catalogue is a local development "
            "tool and refuses to run outside DEBUG mode. Use the production "
            "classification pipeline instead."
        )

    db_config = settings.DATABASES.get("default", {})
    engine: str = db_config.get("ENGINE", "")

    if engine != "django.db.backends.sqlite3":
        raise CommandError(
            f"REJECTED: Database engine is '{engine}'. "
            "seed_local_dev_catalogue requires django.db.backends.sqlite3. "
            "Never run this command against PostgreSQL, staging, or production databases."
        )

    raw_name = db_config.get("NAME", "")
    try:
        resolved = Path(raw_name).resolve()
    except (TypeError, ValueError) as exc:
        raise CommandError(
            f"REJECTED: Cannot resolve database path from NAME={raw_name!r}: {exc}"
        ) from exc

    canonical = _resolve_canonical_db_path().resolve()

    if resolved != canonical:
        raise CommandError(
            f"REJECTED: Resolved database path '{resolved}' does not match the "
            f"expected local development database '{canonical}'. "
            "seed_local_dev_catalogue only operates on the canonical local dev database."
        )

    return engine, str(resolved)


# ---------------------------------------------------------------------------
# Candidate pre-filtering
# ---------------------------------------------------------------------------

def _validate_candidate(movie: Movie) -> Tuple[bool, str]:
    """
    Pre-validate candidate before submitting to TMDB classification pipeline.

    Rejects:
    - Provenance other than 'needs_review'.
    - Invalid TMDB ID (<= 0 or non-integer).
    - Whitespace-only title or poster_path.
    - Missing release date.
    - Whitespace-only or invalid language code.
    - Records with zero genres.
    """
    if movie.provenance != "needs_review":
        return False, f"provenance is '{movie.provenance}', not 'needs_review'"

    tmdb_id = movie.tmdb_id
    if not isinstance(tmdb_id, int) or tmdb_id <= 0:
        return False, f"invalid tmdb_id={tmdb_id!r}"

    title = movie.title or ""
    if not title.strip():
        return False, "title is empty or whitespace-only"

    poster = movie.poster_path or ""
    if not poster.strip():
        return False, "poster_path is empty or whitespace-only"

    if movie.release_date is None:
        return False, "release_date is None"

    lang = movie.original_language or ""
    if not lang.strip():
        return False, "original_language is empty or whitespace-only"

    has_genres = movie.genres.exists()
    display_ready, recommendable = evaluate_eligibility_predicates(
        title=title,
        poster_path=poster,
        provenance="tmdb_catalogue",
        release_date=movie.release_date,
        original_language=movie.original_language,
        has_genres=has_genres,
    )
    if not display_ready:
        return False, "would not be display_ready under tmdb_catalogue provenance"

    if not recommendable:
        return False, "would not be recommendable under tmdb_catalogue provenance (check language, release_date, genres)"

    return True, ""


def _build_candidate_queryset(limit: int):
    """
    Returns the ORM queryset for legacy records eligible for TMDB verification.
    Ordered by rating desc, vote_count desc to prioritize high-confidence titles.
    """
    return (
        Movie.objects.filter(
            provenance="needs_review",
            tmdb_id__gt=0,
        )
        .exclude(poster_path__isnull=True)
        .exclude(poster_path="")
        .exclude(title__isnull=True)
        .exclude(title="")
        .exclude(release_date__isnull=True)
        .exclude(original_language__isnull=True)
        .exclude(original_language="")
        .filter(genres__isnull=False)
        .distinct()
        .prefetch_related("genres")
        .order_by("-rating", "-vote_count", "id")[:limit]
    )


# ---------------------------------------------------------------------------
# Management Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = (
        "LOCAL DEVELOPMENT ONLY. Verifies legacy movie identities against TMDB using the "
        "Batch 2 classification pipeline and promotes verified records to 'tmdb_catalogue'. "
        "Requires DEBUG=True, SQLite at BASE_DIR/db.sqlite3, and --confirm to execute."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview which movies would be submitted for verification without making API calls or DB changes.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=150,
            help=(
                f"Number of movies to verify ({LIMIT_MIN}–{LIMIT_MAX}). "
                "Invalid values are rejected."
            ),
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Required to execute. Omit for dry-run preview.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]
        confirm: bool = options["confirm"]

        # Reject invalid --limit immediately
        if not isinstance(limit, int) or limit < LIMIT_MIN or limit > LIMIT_MAX:
            raise CommandError(
                f"Invalid --limit {limit!r}. Must be an integer between "
                f"{LIMIT_MIN} and {LIMIT_MAX} inclusive."
            )

        # Enforce safety guard before any database read
        engine, db_path = _assert_safe_local_database()

        # Require explicit --confirm for execution
        if not dry_run and not confirm:
            self.stderr.write(
                self.style.ERROR(
                    "This command makes database changes and queries TMDB.\n"
                    "  Pass --confirm to execute, or --dry-run to preview without changes.\n"
                    "  Example: python manage.py seed_local_dev_catalogue "
                    f"--limit {limit} --confirm"
                )
            )
            raise SystemExit(1)

        # Display resolved database info
        self.stdout.write(f"Database engine: {engine}")
        self.stdout.write(f"Database path:   {db_path}")
        if dry_run:
            self.stdout.write(self.style.NOTICE("Mode: DRY-RUN — no database changes and no TMDB calls will be made"))
        else:
            self.stdout.write(self.style.WARNING("Mode: EXECUTE (verifying candidates against TMDB)"))

        # Baseline counts
        total_movies = Movie.objects.count()
        total_needs_review = Movie.objects.filter(provenance="needs_review").count()
        total_tmdb_catalogue = Movie.objects.filter(provenance="tmdb_catalogue").count()
        total_synthetic = Movie.objects.filter(provenance="synthetic_fixture").count()
        total_manual = Movie.objects.filter(provenance="manual_curated").count()
        already_display_ready = Movie.objects.filter(display_ready=True).count()
        already_recommendable = Movie.objects.filter(recommendable=True).count()

        self.stdout.write("")
        self.stdout.write("Current database state:")
        self.stdout.write(f"  Total movies:              {total_movies}")
        self.stdout.write(f"  needs_review:              {total_needs_review}")
        self.stdout.write(f"  tmdb_catalogue:            {total_tmdb_catalogue}")
        self.stdout.write(f"  synthetic_fixture:         {total_synthetic}")
        self.stdout.write(f"  manual_curated:            {total_manual}")
        self.stdout.write(f"  display_ready=True:        {already_display_ready}")
        self.stdout.write(f"  recommendable=True:        {already_recommendable}")

        # Provenance verification notice
        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                "VERIFICATION POLICY: Candidates will be submitted to the existing Batch 2 "
                "classification pipeline (handle_catalogue_classification). Identity is verified "
                "against TMDB upstream with rate-limiting. Records with TMDB 404, title mismatch, "
                "or API failures will REMAIN 'needs_review'. Zero records are promoted on local "
                "metadata alone."
            )
        )

        # Build and pre-validate candidates
        candidates_qs = _build_candidate_queryset(limit)
        candidates: List[Movie] = list(candidates_qs)
        candidate_count = len(candidates)

        valid_candidates: List[Movie] = []
        pre_rejected: List[Tuple[int, str, str]] = []
        for movie in candidates:
            ok, reason = _validate_candidate(movie)
            if ok:
                valid_candidates.append(movie)
            else:
                pre_rejected.append((movie.id, movie.title or "", reason))

        self.stdout.write("")
        self.stdout.write(f"Candidates from ORM query (limit={limit}): {candidate_count}")
        self.stdout.write(f"Passed pre-validation checks:              {len(valid_candidates)}")
        if pre_rejected:
            self.stdout.write(
                self.style.WARNING(f"Pre-rejected by validation:                {len(pre_rejected)}")
            )
            for mid, mtitle, reason in pre_rejected[:5]:
                self.stdout.write(f"  Movie {mid} {mtitle!r}: {reason}")

        if dry_run:
            self.stdout.write("")
            self.stdout.write("Dry-run preview (first 10 candidates queued for TMDB verification):")
            for m in valid_candidates[:10]:
                title_preview = repr(m.title[:50] if m.title else "")
                self.stdout.write(
                    f"  [{m.id:>5}] {title_preview:<52} "
                    f"({m.release_date}) lang={m.original_language} "
                    f"rating={m.rating} tmdb_id={m.tmdb_id}"
                )
            self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DRY-RUN COMPLETE] {len(valid_candidates)} candidates ready for TMDB verification. "
                    "Zero API calls made. Zero database changes made."
                )
            )
            self.stdout.write(
                f"To execute: python manage.py seed_local_dev_catalogue "
                f"--limit {limit} --confirm"
            )
            return

        # -------------------------------------------------------------------
        # EXECUTE — Process candidates through Batch 2 Classification Pipeline
        # -------------------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"Submitting {len(valid_candidates)} candidates to Batch 2 TMDB classification pipeline..."
            )
        )

        promoted: List[Tuple[int, str]] = []        # (movie_id, match_reason)
        unverified_404: List[Tuple[int, str]] = []  # (movie_id, title)
        unverified_mismatch: List[Tuple[int, str, str]] = []  # (movie_id, title, reason)
        synthetic_marked: List[Tuple[int, str]] = [] # (movie_id, title)
        skipped: List[Tuple[int, str]] = []         # (movie_id, reason)
        failed: List[Tuple[int, str, str]] = []      # (movie_id, title, error)

        for movie in valid_candidates:
            job_shim = types.SimpleNamespace(entity_id=str(movie.id))
            lease_token = uuid.uuid4()

            try:
                # 1. Run through existing Batch 2 classification handler with downstream enqueue suppressed
                class_result = handle_catalogue_classification(
                    job=job_shim,
                    worker_id=WORKER_ID,
                    lease_token=lease_token,
                    generation=1,
                    enqueue_downstream=False,
                )

                classification = class_result.get("classification")

                if classification == "tmdb_catalogue":
                    match_reason = class_result.get("match_reason", "Verified")
                    promoted.append((movie.id, match_reason))

                elif classification == "synthetic_fixture":
                    synthetic_marked.append((movie.id, movie.title or ""))

                elif classification == "needs_review":
                    reason = class_result.get("reason", "")
                    if "404" in reason:
                        unverified_404.append((movie.id, movie.title or ""))
                    else:
                        unverified_mismatch.append((movie.id, movie.title or "", reason))

                else:
                    skipped.append((movie.id, f"Unhandled classification status: {classification}"))

            except ValueError as val_err:
                # State machine rejection (e.g. wrong source provenance)
                skipped.append((movie.id, str(val_err)))
                logger.debug(f"Skipped Movie {movie.id}: {val_err}")

            except Exception as exc:
                # Network error, rate limit timeout, or unexpected exception
                failed.append((movie.id, movie.title or "", str(exc)))
                self.stderr.write(
                    self.style.ERROR(
                        f"ERROR verifying Movie {movie.id} ({movie.title!r}) against TMDB: {exc}"
                    )
                )

            processed = (
                len(promoted)
                + len(unverified_404)
                + len(unverified_mismatch)
                + len(synthetic_marked)
                + len(skipped)
                + len(failed)
            )
            if processed % 10 == 0 or processed == len(valid_candidates):
                self.stdout.write(
                    f"  Progress: {processed}/{len(valid_candidates)} "
                    f"(verified={len(promoted)}, 404={len(unverified_404)}, "
                    f"mismatch={len(unverified_mismatch)}, synth={len(synthetic_marked)}, "
                    f"failed={len(failed)})"
                )

        # Final state
        final_needs_review = Movie.objects.filter(provenance="needs_review").count()
        final_tmdb_catalogue = Movie.objects.filter(provenance="tmdb_catalogue").count()
        final_synthetic = Movie.objects.filter(provenance="synthetic_fixture").count()
        final_manual = Movie.objects.filter(provenance="manual_curated").count()
        final_display_ready = Movie.objects.filter(display_ready=True).count()
        final_recommendable = Movie.objects.filter(recommendable=True).count()

        self.stdout.write("")
        self.stdout.write("=" * 65)
        self.stdout.write(self.style.SUCCESS("seed_local_dev_catalogue execution complete"))
        self.stdout.write(f"  Verified & Promoted to tmdb_catalogue: {len(promoted)}")
        self.stdout.write(f"  Unverified (TMDB 404, kept needs_review): {len(unverified_404)}")
        self.stdout.write(f"  Unverified (Identity mismatch, kept needs_review): {len(unverified_mismatch)}")
        self.stdout.write(f"  Identified as synthetic_fixture:       {len(synthetic_marked)}")
        self.stdout.write(f"  Skipped (state machine / pre-existing): {len(skipped)}")
        self.stdout.write(f"  Failed (TMDB API / network errors):    {len(failed)}")

        if unverified_404:
            self.stdout.write("  Sample 404 unverified:")
            for mid, mtitle in unverified_404[:3]:
                self.stdout.write(f"    Movie {mid} {mtitle!r}: TMDB returned 404 (retained needs_review)")

        if unverified_mismatch:
            self.stdout.write("  Sample identity mismatches:")
            for mid, mtitle, mreason in unverified_mismatch[:3]:
                self.stdout.write(f"    Movie {mid} {mtitle!r}: {mreason} (retained needs_review)")

        if failed:
            self.stdout.write(self.style.ERROR("  Sample API / network failures:"))
            for fid, ftitle, ferr in failed[:3]:
                self.stdout.write(self.style.ERROR(f"    Movie {fid} {ftitle!r}: {ferr} (retained needs_review)"))

        self.stdout.write("")
        self.stdout.write("Database state after:")
        self.stdout.write(f"  needs_review:       {final_needs_review}")
        self.stdout.write(f"  tmdb_catalogue:     {final_tmdb_catalogue}")
        self.stdout.write(f"  synthetic_fixture:  {final_synthetic}")
        self.stdout.write(f"  manual_curated:     {final_manual}")
        self.stdout.write(f"  display_ready=True: {final_display_ready}")
        self.stdout.write(f"  recommendable=True: {final_recommendable}")
        self.stdout.write("=" * 65)

        if failed:
            self.stderr.write(
                self.style.ERROR(
                    f"\n{len(failed)} candidate(s) failed during TMDB verification. "
                    "Unverified records were NOT promoted and remain 'needs_review'. "
                    "Exiting with non-zero status."
                )
            )
            raise SystemExit(1)
