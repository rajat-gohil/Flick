"""
Job handlers for Flick Batch 2 catalogue intelligence processing.

Handlers:
- handle_catalogue_classification: Validates movie identity against TMDB or marks synthetic fixtures,
  updating movie classification provenance and enqueuing downstream enrichment.
- handle_catalogue_enrichment: Fetches full movie metadata (details, credits, keywords) from TMDB,
  persists changes via update_movie_metadata with manual override protection, updates genres/keywords M2M,
  and recalculates eligibility.
"""

from __future__ import annotations

import difflib
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import CatalogueJob, Genre, Movie, MovieKeyword
from core.services.catalogue_queue import CatalogueQueueService, StaleLeaseOwnershipError
from core.services.movie_mutations import (
    transition_movie_classification,
    update_movie_metadata,
)
from core.services.catalogue_eligibility import recalculate_movie_eligibility
from core.services.tmdb import get_tmdb_session

try:
    from core.services.tmdb_rate_limiter import acquire_tmdb_token, record_tmdb_429
except ImportError:
    # Fallback placeholder until tmdb_rate_limiter is authored by ratelimit agent
    def acquire_tmdb_token(traffic_type: str = "background", cost: float = 1.0, timeout: float = 5.0) -> bool:
        return True

    def record_tmdb_429(retry_after_header: Optional[str] = None) -> float:
        return 12.0

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_HTTP_TIMEOUT = (3.05, 12.0)

# Precompiled regex patterns for synthetic fixtures
SYNTHETIC_PATTERNS = [
    re.compile(r"^synthetic_movie_\d+", re.IGNORECASE),
    re.compile(r"^mock_movie_\d+", re.IGNORECASE),
    re.compile(r"^test_fixture_", re.IGNORECASE),
    re.compile(r"^fixture_", re.IGNORECASE),
]


def is_synthetic_movie(movie: Movie) -> bool:
    """
    Check if a movie matches known synthetic fixture patterns.
    - Title matches synthetic regex patterns
    - tmdb_id < 0 or tmdb_id is None
    - Explicit synthetic markers in field_provenance
    """
    if movie.tmdb_id is None or movie.tmdb_id < 0:
        return True

    title = movie.title or ""
    for pattern in SYNTHETIC_PATTERNS:
        if pattern.search(title):
            return True

    raw_fp = getattr(movie, "field_provenance", None)
    if isinstance(raw_fp, dict) and raw_fp.get("synthetic"):
        return True

    return False


def normalize_title(title: Optional[str]) -> str:
    """Normalize title for fuzzy / deterministic identity matching."""
    if not title:
        return ""
    # Lowercase, strip, replace multiple whitespaces and punctuation
    cleaned = title.lower().strip()
    cleaned = re.sub(r"[^\w\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def check_deterministic_identity(
    movie: Movie,
    tmdb_data: dict,
) -> Tuple[bool, str]:
    """
    Deterministic identity check:
    - TMDB status in ('Released', 'Post Production')
    - Title match: exact normalized title OR Levenshtein/ratio >= 0.85 with release year +/- 1.
    """
    tmdb_status = tmdb_data.get("status")
    if tmdb_status not in ("Released", "Post Production"):
        return False, f"TMDB status '{tmdb_status}' not in ('Released', 'Post Production')"

    local_title_norm = normalize_title(movie.title)
    tmdb_title_norm = normalize_title(tmdb_data.get("title"))
    tmdb_orig_title_norm = normalize_title(tmdb_data.get("original_title"))

    # Check exact normalized match against title or original_title
    if local_title_norm == tmdb_title_norm or (tmdb_orig_title_norm and local_title_norm == tmdb_orig_title_norm):
        return True, "Exact normalized title match"

    # Fuzzy similarity match with year check
    matcher1 = difflib.SequenceMatcher(None, local_title_norm, tmdb_title_norm)
    ratio1 = matcher1.ratio()
    ratio2 = (
        difflib.SequenceMatcher(None, local_title_norm, tmdb_orig_title_norm).ratio()
        if tmdb_orig_title_norm
        else 0.0
    )
    best_ratio = max(ratio1, ratio2)

    if best_ratio >= 0.85:
        # Check release year +/- 1 year
        local_year: Optional[int] = None
        if movie.release_date:
            local_year = movie.release_date.year

        tmdb_release_date_str = tmdb_data.get("release_date")
        tmdb_year: Optional[int] = None
        if tmdb_release_date_str and len(tmdb_release_date_str) >= 4:
            try:
                tmdb_year = int(tmdb_release_date_str[:4])
            except ValueError:
                pass

        if local_year is not None and tmdb_year is not None:
            if abs(local_year - tmdb_year) <= 1:
                return True, f"Fuzzy title match ({best_ratio:.2f}) and year match ({local_year} vs {tmdb_year})"
            else:
                return (
                    False,
                    f"Fuzzy title match ({best_ratio:.2f}) but year mismatch ({local_year} vs {tmdb_year})",
                )
        elif local_year is None or tmdb_year is None:
            # If year is missing on one side, allow fuzzy match if >= 0.90
            if best_ratio >= 0.90:
                return True, f"High-confidence fuzzy title match ({best_ratio:.2f}) with missing year"
            return False, f"Fuzzy title match ({best_ratio:.2f}) requires year verification but year was missing"

    return False, f"Title similarity {best_ratio:.2f} below 0.85 threshold"


def _tmdb_api_get(endpoint: str, params: Optional[dict] = None) -> requests.Response:
    """Helper to query TMDB API with api_key and standard headers via resilient pooled session."""
    api_key = getattr(settings, "TMDB_API_KEY", None)
    req_params = {"api_key": api_key}
    if params:
        req_params.update(params)

    session = get_tmdb_session()
    return session.get(
        f"{TMDB_BASE_URL}{endpoint}",
        params=req_params,
        timeout=TMDB_HTTP_TIMEOUT,
    )


def handle_catalogue_classification(
    job: CatalogueJob,
    worker_id: str,
    lease_token: uuid.UUID,
    generation: int,
    enqueue_downstream: bool = True,
) -> Dict[str, Any]:
    """
    Handle catalogue classification job:
    1. Load movie under row lock.
    2. Check synthetic patterns -> if synthetic, transition to 'synthetic_fixture'.
    3. For candidate genuine: acquire TMDB token ('background') and fetch TMDB `/3/movie/{tmdb_id}`.
    4. Deterministic identity check: normalized title matches (exact or Levenshtein >= 0.85 + year +/- 1),
       TMDB status in ('Released', 'Post Production').
    5. If verified:
       - Transition to 'tmdb_catalogue'.
       - Downstream enqueue: CatalogueQueueService.enqueue('catalogue_enrichment', ...)
         ONLY when enqueue_downstream=True (default). When enqueue_downstream=False (e.g. for
         controlled fixture execution), downstream enqueueing is suppressed.
    6. If 404 or mismatch: retain 'needs_review' and record classification audit.
    """
    movie_id = int(job.entity_id)

    with transaction.atomic():
        try:
            movie = Movie.objects.select_for_update().get(pk=movie_id)
        except Movie.DoesNotExist:
            return {"error": f"Movie {movie_id} does not exist", "status": "skipped"}

        # 1. Check synthetic patterns
        if is_synthetic_movie(movie):
            transition_movie_classification(
                movie_id=movie.id,
                new_provenance="synthetic_fixture",
                reason="Identified as synthetic test fixture or missing TMDB ID",
                worker_id=worker_id,
                metadata_evidence={"title": movie.title, "tmdb_id": movie.tmdb_id},
            )
            return {
                "classification": "synthetic_fixture",
                "movie_id": movie.id,
                "reason": "synthetic_fixture_identified",
            }

        tmdb_id = movie.tmdb_id

    # 2. Candidate genuine - fetch TMDB /3/movie/{tmdb_id}
    # Rate limiter token acquisition
    token_acquired = acquire_tmdb_token(traffic_type="background")
    if not token_acquired:
        raise RuntimeError("TMDB rate limit budget exhausted; failing closed for background classification.")

    response = _tmdb_api_get(f"/movie/{tmdb_id}")

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        record_tmdb_429(retry_after)
        raise RuntimeError(f"TMDB 429 Rate Limit encountered during classification of movie {movie_id}")

    if response.status_code == 404:
        # 404 Not Found in TMDB
        with transaction.atomic():
            movie = Movie.objects.select_for_update().get(pk=movie_id)
            raw_fp = getattr(movie, "field_provenance", None)
            if not isinstance(raw_fp, dict):
                movie.field_provenance = {}
            audit = movie.field_provenance.get("_classification_audit", [])
            if not isinstance(audit, list):
                audit = [{"malformed_prior_audit": audit}]
            audit.append({
                "from_provenance": movie.provenance,
                "to_provenance": movie.provenance,
                "reason": f"TMDB movie {tmdb_id} returned HTTP 404 Not Found; retaining needs_review",
                "timestamp": timezone.now().isoformat(),
                "actor": f"worker:{worker_id}",
                "actor_type": "worker",
            })
            movie.field_provenance["_classification_audit"] = audit
            movie.save(update_fields=["field_provenance"])
        return {
            "classification": "needs_review",
            "movie_id": movie_id,
            "reason": "tmdb_404_not_found",
        }

    if response.status_code != 200:
        response.raise_for_status()

    tmdb_data = response.json()

    # 3. Deterministic identity check
    is_match, match_reason = check_deterministic_identity(movie, tmdb_data)

    if is_match:
        with transaction.atomic():
            transition_movie_classification(
                movie_id=movie.id,
                new_provenance="tmdb_catalogue",
                reason=f"Verified TMDB identity: {match_reason}",
                worker_id=worker_id,
                metadata_evidence={
                    "tmdb_id": tmdb_id,
                    "tmdb_title": tmdb_data.get("title"),
                    "tmdb_status": tmdb_data.get("status"),
                    "match_reason": match_reason,
                },
            )

            # Downstream enqueue catalogue_enrichment (if enabled)
            downstream_job_id = None
            downstream_created = False
            if enqueue_downstream:
                downstream_job, created = CatalogueQueueService.enqueue(
                    job_type="catalogue_enrichment",
                    entity_type="movie",
                    entity_id=str(movie.id),
                    external_id=str(tmdb_id),
                    priority=100,
                )
                downstream_job_id = downstream_job.id
                downstream_created = created

        return {
            "classification": "tmdb_catalogue",
            "movie_id": movie.id,
            "match_reason": match_reason,
            "downstream_job_id": downstream_job_id,
            "downstream_job_created": downstream_created,
        }
    else:
        # Title/status mismatch - retain needs_review
        with transaction.atomic():
            movie = Movie.objects.select_for_update().get(pk=movie_id)
            raw_fp = getattr(movie, "field_provenance", None)
            if not isinstance(raw_fp, dict):
                movie.field_provenance = {}
            audit = movie.field_provenance.get("_classification_audit", [])
            if not isinstance(audit, list):
                audit = [{"malformed_prior_audit": audit}]
            audit.append({
                "from_provenance": movie.provenance,
                "to_provenance": movie.provenance,
                "reason": f"TMDB identity mismatch: {match_reason}; retaining needs_review",
                "timestamp": timezone.now().isoformat(),
                "actor": f"worker:{worker_id}",
                "actor_type": "worker",
                "metadata_evidence": {
                    "tmdb_id": tmdb_id,
                    "tmdb_title": tmdb_data.get("title"),
                    "tmdb_status": tmdb_data.get("status"),
                    "match_reason": match_reason,
                },
            })
            movie.field_provenance["_classification_audit"] = audit
            movie.save(update_fields=["field_provenance"])

        return {
            "classification": "needs_review",
            "movie_id": movie.id,
            "reason": f"mismatch: {match_reason}",
        }


def handle_catalogue_enrichment(
    job: CatalogueJob,
    worker_id: str,
    lease_token: uuid.UUID,
    generation: int,
) -> Dict[str, Any]:
    """
    Handle catalogue enrichment job:
    1. Fetch movie details, keywords, and credits from TMDB using acquire_tmdb_token('background').
    2. Update metadata using update_movie_metadata(movie.id, updates={...}, is_automated=True, actor=f"worker:{worker_id}").
    3. Update genres M2M and keywords M2M.
    4. Update credits_summary, last_enriched_at.
    5. Atomic eligibility recalculation under row lock.
    """
    movie_id = int(job.entity_id)

    try:
        movie = Movie.objects.get(pk=movie_id)
    except Movie.DoesNotExist:
        return {"error": f"Movie {movie_id} does not exist", "status": "skipped"}

    tmdb_id = movie.tmdb_id
    if not tmdb_id:
        return {"error": f"Movie {movie_id} has no tmdb_id", "status": "skipped"}

    # Acquire rate limit token
    token_acquired = acquire_tmdb_token(traffic_type="background")
    if not token_acquired:
        raise RuntimeError("TMDB rate limit budget exhausted; failing closed for background enrichment.")

    # Fetch TMDB movie details with append_to_response=keywords,credits
    response = _tmdb_api_get(
        f"/movie/{tmdb_id}",
        params={"append_to_response": "keywords,credits"},
    )

    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        record_tmdb_429(retry_after)
        raise RuntimeError(f"TMDB 429 Rate Limit encountered during enrichment of movie {movie_id}")

    if response.status_code == 404:
        logger.warning(f"TMDB ID {tmdb_id} for Movie {movie_id} not found during enrichment.")
        return {"status": "not_found", "movie_id": movie_id}

    if response.status_code != 200:
        response.raise_for_status()

    tmdb_data = response.json()

    # Parse details
    title = tmdb_data.get("title")
    overview = tmdb_data.get("overview")
    poster_path = tmdb_data.get("poster_path")
    backdrop_path = tmdb_data.get("backdrop_path")
    vote_count = tmdb_data.get("vote_count", 0)
    rating = tmdb_data.get("vote_average", 0.0)
    original_language = tmdb_data.get("original_language")

    release_date_str = tmdb_data.get("release_date")
    release_date = None
    if release_date_str:
        try:
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d").date()
        except ValueError:
            release_date = None

    # Parse credits summary
    credits_raw = tmdb_data.get("credits", {})
    cast_list = credits_raw.get("cast", [])
    crew_list = credits_raw.get("crew", [])

    top_cast = [
        {"id": c.get("id"), "name": c.get("name"), "character": c.get("character")}
        for c in cast_list[:10]
    ]
    directors = [
        {"id": c.get("id"), "name": c.get("name"), "job": c.get("job")}
        for c in crew_list
        if c.get("job") == "Director"
    ]

    existing_credits = movie.credits_summary if isinstance(movie.credits_summary, dict) else {}
    credits_summary = {
        **existing_credits,
        "cast": top_cast,
        "directors": directors,
    }
    raw_runtime = tmdb_data.get("runtime")
    parsed_runtime = None
    if isinstance(raw_runtime, (int, float)) and not isinstance(raw_runtime, bool) and int(raw_runtime) > 0:
        parsed_runtime = int(raw_runtime)
    if parsed_runtime is not None:
        credits_summary["runtime"] = parsed_runtime

    updates = {
        "title": title,
        "overview": overview,
        "poster_path": poster_path,
        "backdrop_path": backdrop_path,
        "release_date": release_date,
        "rating": rating,
        "vote_count": vote_count,
        "original_language": original_language,
        "credits_summary": credits_summary,
    }

    # Remove None values for fields that shouldn't be overwritten with None if existing is present
    filtered_updates = {k: v for k, v in updates.items() if v is not None}

    with transaction.atomic():
        # Update metadata with manual override protection and provenance recording
        updated_movie = update_movie_metadata(
            movie_id=movie_id,
            updates=filtered_updates,
            is_automated=True,
            actor=f"worker:{worker_id}",
        )

        # Update genres M2M
        raw_genres = tmdb_data.get("genres", [])
        genre_objs = []
        for g_data in raw_genres:
            g_tmdb_id = g_data.get("id")
            g_name = g_data.get("name")
            if g_tmdb_id and g_name:
                genre_obj, _ = Genre.objects.get_or_create(
                    tmdb_id=g_tmdb_id,
                    defaults={"name": g_name},
                )
                genre_objs.append(genre_obj)

        if genre_objs:
            updated_movie.genres.set(genre_objs)

        # Update keywords M2M
        keywords_container = tmdb_data.get("keywords", {})
        # Note: /movie/{id} returns keywords as a list under "keywords"
        raw_keywords = keywords_container.get("keywords", [])
        keyword_objs = []
        for kw in raw_keywords:
            kw_tmdb_id = kw.get("id")
            kw_name = kw.get("name")
            if kw_tmdb_id and kw_name:
                kw_obj, _ = MovieKeyword.objects.get_or_create(
                    tmdb_id=kw_tmdb_id,
                    defaults={"name": kw_name},
                )
                keyword_objs.append(kw_obj)

        if keyword_objs:
            updated_movie.keywords.set(keyword_objs)

        # Set last_enriched_at
        now = timezone.now()
        Movie.objects.filter(pk=movie_id).update(last_enriched_at=now)
        updated_movie.last_enriched_at = now

        # Atomic eligibility recalculation under row lock
        recalculate_movie_eligibility(updated_movie, commit=True)

    return {
        "status": "enriched",
        "movie_id": movie_id,
        "display_ready": updated_movie.display_ready,
        "recommendable": updated_movie.recommendable,
        "genres_count": len(genre_objs),
        "keywords_count": len(keyword_objs),
        "last_enriched_at": now.isoformat(),
    }
