"""
Movie mutation services enforcing field whitelisting, provenance auditing,
manual override protection, and atomic eligibility recalculation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from core.models import Movie
from core.services.catalogue_eligibility import recalculate_movie_eligibility

if TYPE_CHECKING:
    from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# Permitted provenance values across Flick
PERMITTED_PROVENANCE_VALUES: frozenset[str] = frozenset({
    "needs_review",
    "tmdb_catalogue",
    "synthetic_fixture",
    "manual_curated",
})

# Permitted metadata fields for general updates
# CRITICAL: 'provenance' is strictly excluded from generic metadata updates!
PERMITTED_METADATA_FIELDS: frozenset[str] = frozenset({
    "title",
    "overview",
    "poster_path",
    "backdrop_path",
    "release_date",
    "rating",
    "vote_count",
    "trailer_key",
    "original_language",
    "credits_summary",
    "metadata_content_hash",
})

# Permitted per-field provenance keys
PERMITTED_PROVENANCE_KEYS: frozenset[str] = frozenset({
    "source",
    "updated_at",
    "updated_by",
    "fetched_empty",
    "divergent_tmdb_value",
    "diverged_at",
})

# Allowed manual state transitions for movie classification
MANUAL_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "needs_review": frozenset({"tmdb_catalogue", "synthetic_fixture", "manual_curated"}),
    "tmdb_catalogue": frozenset({"manual_curated", "needs_review"}),
    "synthetic_fixture": frozenset({"manual_curated", "needs_review"}),
    "manual_curated": frozenset({"needs_review", "tmdb_catalogue"}),
}


def _validate_field_provenance_updates(field_provenance_updates: dict) -> None:
    """Validate structure and allowed keys for field_provenance_updates."""
    if not isinstance(field_provenance_updates, dict):
        raise ValueError("field_provenance_updates must be a dictionary")

    for field_name, p_meta in field_provenance_updates.items():
        if str(field_name).startswith("_"):
            raise ValueError(f"Cannot overwrite reserved audit key '{field_name}'")
        if not isinstance(p_meta, dict):
            raise ValueError(f"Field provenance update for '{field_name}' must be a dictionary")
        for k in p_meta.keys():
            if str(k).startswith("_"):
                raise ValueError(f"Cannot overwrite reserved audit key '{k}'")
            if k not in PERMITTED_PROVENANCE_KEYS:
                raise ValueError(
                    f"Unpermitted provenance key '{k}' for field '{field_name}'. "
                    f"Permitted keys: {sorted(PERMITTED_PROVENANCE_KEYS)}"
                )


@transaction.atomic
def update_movie_metadata(
    movie_id: int,
    updates: dict,
    field_provenance_updates: Optional[dict] = None,
    is_automated: bool = True,
    actor: str = "system",
) -> Movie:
    """
    Safely update movie metadata with whitelist enforcement, manual override protection,
    and atomic eligibility recalculation.

    - Locks row via Movie.objects.select_for_update().get(pk=movie_id).
    - Whitelist validation on updates.keys(). Rejects unpermitted fields with ValueError.
    - Manual override protection: if field_meta.get('source') == 'manual', automated updates
      CANNOT overwrite the column. If new_value differs, records divergent_tmdb_value = new_value
      and diverged_at = now_iso.
    - Deep merges field_provenance_updates into movie.field_provenance. Disallows overwriting
      reserved audit keys starting with '_'.
    - Recalculates eligibility atomically via recalculate_movie_eligibility(movie, commit=False)
      before movie.save().
    """
    if not isinstance(updates, dict):
        raise ValueError("updates must be a dictionary")

    unpermitted = set(updates.keys()) - PERMITTED_METADATA_FIELDS
    if unpermitted:
        raise ValueError(
            f"Unpermitted metadata fields: {sorted(unpermitted)}. "
            f"Allowed fields: {sorted(PERMITTED_METADATA_FIELDS)}"
        )

    if field_provenance_updates is not None:
        _validate_field_provenance_updates(field_provenance_updates)

    movie = Movie.objects.select_for_update().get(pk=movie_id)

    # Safely initialize field_provenance if malformed
    raw_fp = getattr(movie, "field_provenance", None)
    if not isinstance(raw_fp, dict):
        movie.field_provenance = {"_raw_malformed_provenance": raw_fp} if raw_fp is not None else {}
    else:
        movie.field_provenance = dict(raw_fp)

    now_iso = timezone.now().isoformat()

    # Apply updates with manual override protection
    for field_name, new_val in updates.items():
        existing_meta = movie.field_provenance.get(field_name)
        if isinstance(existing_meta, dict):
            field_meta = dict(existing_meta)
        else:
            field_meta = {}

        if field_meta.get("source") == "manual":
            if is_automated:
                # Automated updates CANNOT overwrite a manual override column
                current_val = getattr(movie, field_name)
                if new_val != current_val:
                    field_meta["divergent_tmdb_value"] = new_val
                    field_meta["diverged_at"] = now_iso
            else:
                # Manual update overwriting manual field
                setattr(movie, field_name, new_val)
                field_meta["source"] = "manual"
                field_meta["updated_at"] = now_iso
                field_meta["updated_by"] = actor
                field_meta.pop("divergent_tmdb_value", None)
                field_meta.pop("diverged_at", None)
        else:
            setattr(movie, field_name, new_val)
            field_meta["source"] = "tmdb" if is_automated else "manual"
            field_meta["updated_at"] = now_iso
            field_meta["updated_by"] = actor
            field_meta.pop("divergent_tmdb_value", None)
            field_meta.pop("diverged_at", None)

        movie.field_provenance[field_name] = field_meta

    # Deep merge caller-supplied field_provenance_updates
    if field_provenance_updates:
        for field_name, p_updates in field_provenance_updates.items():
            existing = movie.field_provenance.get(field_name)
            if not isinstance(existing, dict):
                existing = {}
            else:
                existing = dict(existing)
            existing.update(p_updates)
            movie.field_provenance[field_name] = existing

    # Recalculate eligibility atomically in-memory before save
    recalculate_movie_eligibility(movie, commit=False)
    movie.save()
    return movie


@transaction.atomic
def transition_movie_classification(
    movie_id: int,
    new_provenance: str,
    reason: str,
    user: Optional[User] = None,
    worker_id: Optional[str] = None,
    metadata_evidence: Optional[dict] = None,
) -> Movie:
    """
    Transition a movie's provenance classification with state-machine validation,
    strict role enforcement, and hardened audit history recording.

    - Destination MUST be in PERMITTED_PROVENANCE_VALUES.
    - If user is not None: Manual classification. Enforce user.is_authenticated and
      (user.is_staff or user.has_perm('core.change_movie')). Raise PermissionDenied if unauthorized.
      Allowed manual transitions:
        needs_review -> {'tmdb_catalogue', 'synthetic_fixture', 'manual_curated'}
        tmdb_catalogue -> {'manual_curated', 'needs_review'}
        synthetic_fixture -> {'manual_curated', 'needs_review'}
        manual_curated -> {'needs_review', 'tmdb_catalogue'}
    - If user is None: Automated classification. Requires non-empty worker_id.
      Cannot touch existing manual_curated.
      Transition must be from needs_review to {'tmdb_catalogue', 'synthetic_fixture'}.
    - Hardened audit initialization: safely handle movie.field_provenance (wrap if malformed);
      safely handle _classification_audit (if not list, preserve existing as
      {'malformed_prior_audit': raw_audit}, never discard history!).
    - Atomically updates movie.provenance, audit history, recalculates eligibility
      via recalculate_movie_eligibility(movie, commit=True), and saves.
    """
    if new_provenance not in PERMITTED_PROVENANCE_VALUES:
        raise ValueError(
            f"Invalid provenance '{new_provenance}'. Permitted values: {sorted(PERMITTED_PROVENANCE_VALUES)}"
        )

    if not reason or not isinstance(reason, str) or not reason.strip():
        raise ValueError("A non-empty reason is required for classification transition.")

    if user is not None:
        # Manual classification: authorization check
        if not (user.is_authenticated and (user.is_staff or user.has_perm("core.change_movie"))):
            raise PermissionDenied("User is not authorized to transition movie classification.")
    else:
        # Automated classification: worker_id check
        if not worker_id or not str(worker_id).strip():
            raise ValueError("Automated classification requires a non-empty worker_id.")

    movie = Movie.objects.select_for_update().get(pk=movie_id)
    current_provenance = getattr(movie, "provenance", None)

    # Reject corrupt or unknown existing provenance values
    if current_provenance not in PERMITTED_PROVENANCE_VALUES:
        raise ValueError(
            f"Corrupt or unknown existing provenance '{current_provenance}' on Movie {movie_id}; "
            "cannot transition. Surfaced for administrative review."
        )

    if user is not None:
        allowed = MANUAL_ALLOWED_TRANSITIONS.get(current_provenance, frozenset())
        if new_provenance not in allowed:
            raise ValueError(
                f"Invalid manual classification transition from '{current_provenance}' to '{new_provenance}'. "
                f"Allowed destinations: {sorted(allowed)}"
            )
    else:
        if current_provenance == "manual_curated":
            raise ValueError("Automated classification cannot modify movie with 'manual_curated' provenance.")
        if current_provenance != "needs_review" or new_provenance not in {"tmdb_catalogue", "synthetic_fixture"}:
            raise ValueError(
                f"Invalid automated classification transition from '{current_provenance}' to '{new_provenance}'. "
                f"Automated transitions must be from 'needs_review' to 'tmdb_catalogue' or 'synthetic_fixture'."
            )

    # Hardened audit initialization
    raw_fp = getattr(movie, "field_provenance", None)
    if not isinstance(raw_fp, dict):
        movie.field_provenance = {"_raw_malformed_provenance": raw_fp} if raw_fp is not None else {}
    else:
        movie.field_provenance = dict(raw_fp)

    raw_audit = movie.field_provenance.get("_classification_audit")
    if raw_audit is None:
        audit_history: list[dict[str, Any]] = []
    elif isinstance(raw_audit, list):
        audit_history = list(raw_audit)
    else:
        # Preserve malformed prior audit, never discard history
        audit_history = [{"malformed_prior_audit": raw_audit}]

    now_iso = timezone.now().isoformat()
    audit_entry: dict[str, Any] = {
        "from_provenance": current_provenance,
        "to_provenance": new_provenance,
        "reason": reason,
        "timestamp": now_iso,
        "actor": user.get_username() if user is not None else f"worker:{worker_id}",
        "actor_type": "user" if user is not None else "worker",
    }
    if metadata_evidence is not None:
        audit_entry["metadata_evidence"] = metadata_evidence

    audit_history.append(audit_entry)
    movie.field_provenance["_classification_audit"] = audit_history
    movie.provenance = new_provenance

    # Atomic recalculation and commit
    recalculate_movie_eligibility(movie, commit=True)
    movie.save()
    return movie
