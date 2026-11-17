"""
Durable Taste Engine for Flick Catalogue Intelligence.

Workstream D:
- TasteEngineService:
  - recompute_user_taste_profile(user_or_id, batch_size: int = 100, force: bool = False) -> Dict[str, Any]:
    - Resolves canonical user and all linked actor IDs:
      actor_ids = IdentityLinkingService.get_all_actor_ids_for_user(user).
    - Executes in an atomic database transaction with select_for_update(skip_locked=True)
      on pending InteractionLog records for actor_ids.
    - If no pending events (and not force), returns early without DB mutations.
    - Deterministically aggregates interaction events:
      likes (+1.0), dislikes (-1.2), superlikes (+3.0), matches (+2.5), undos (-1.0, +1.2, -3.0).
    - Updates UserTasteProfile.learned_weights deterministically using movie keywords, tags, genres,
      and event weights.
    - Incorporates inverse undo events properly to restore baseline signal state.
    - Atomically updates claimed event rows to processing_status='processed' and processed_at=now.
    - Single source of truth: ledger-based determinism and idempotency.
- handle_recompute_taste_profile(job, worker_id, lease_token, generation) -> Dict[str, Any]:
  - Dedicated background intelligence worker handler registered in run_intelligence_worker.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Union

from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.db import models, transaction
from django.utils import timezone

from core.models import (
    CatalogueJob,
    Genre,
    InteractionLog,
    Movie,
    MovieKeyword,
    MovieTag,
    Swipe,
    UserTasteProfile,
)

logger = logging.getLogger(__name__)

# Standard interaction signal weights
SIGNAL_WEIGHTS: Dict[str, float] = {
    "superlike": 3.0,
    "match": 2.5,
    "watchlist_add": 2.0,
    "swipe_like": 1.0,
    "like": 1.0,
    "modal_open": 0.3,
    "swipe_dislike": -1.2,
    "dislike": -1.2,
    "undo": 0.0,
}

# Standard TMDB genre ID to canonical name mapping
TMDB_GENRE_MAP: Dict[int, str] = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Science Fiction",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western",
}


class TasteEngineService:
    """
    Durable service managing the recomputation of UserTasteProfile learned weights
    from an append-only ledger of InteractionLog records.
    """

    @classmethod
    def _resolve_user(cls, user_or_id: Any) -> Any:
        """Resolves a User instance from either a User instance or user ID."""
        if isinstance(user_or_id, (int, str)):
            User = get_user_model()
            try:
                return User.objects.get(id=int(user_or_id))
            except ObjectDoesNotExist as exc:
                raise ValueError(f"User with ID {user_or_id} does not exist.") from exc
        return user_or_id

    @classmethod
    def get_actor_ids(cls, user: Any) -> List[int]:
        """
        Resolves canonical user and all linked guest actor IDs using IdentityLinkingService.
        Falls back to local query if IdentityLinkingService is unavailable.
        """
        try:
            from core.services.identity_linking import IdentityLinkingService
            return IdentityLinkingService.get_all_actor_ids_for_user(user)
        except Exception:
            actor_ids = [user.id]
            try:
                from core.models import UserIdentityLink
                linked = list(
                    UserIdentityLink.objects.filter(canonical_user=user).values_list(
                        "linked_actor_id", flat=True
                    )
                )
                actor_ids.extend(linked)
            except Exception:
                pass
            return list(dict.fromkeys(int(aid) for aid in actor_ids))

    @classmethod
    def resolve_event_weight(cls, event: InteractionLog) -> float:
        """
        Resolves the effective numerical signal weight for an InteractionLog record.
        - Respects explicit non-zero event.weight.
        - For 'undo' events with 0.0 weight, inspects metadata for undone_reaction.
        - For standard events with 0.0 weight, falls back to SIGNAL_WEIGHTS.
        """
        w = event.weight
        if event.event_type == "undo":
            if w != 0.0 and w is not None:
                return float(w)
            meta = event.metadata if isinstance(event.metadata, dict) else {}
            reaction = str(meta.get("undone_reaction", "")).lower()
            if reaction in ("like", Swipe.LIKE):
                return -1.0
            elif reaction in ("dislike", Swipe.DISLIKE):
                return 1.2
            elif reaction in ("superlike", Swipe.SUPERLIKE):
                return -3.0
            return 0.0

        if w != 0.0 and w is not None:
            return float(w)

        return SIGNAL_WEIGHTS.get(event.event_type, 0.0)

    @classmethod
    def recompute_user_taste_profile(
        cls,
        user_or_id: Any,
        batch_size: int = 100,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Recomputes UserTasteProfile.learned_weights deterministically from the InteractionLog ledger.

        Algorithm:
        1. Resolves canonical user and all linked actor IDs:
           actor_ids = IdentityLinkingService.get_all_actor_ids_for_user(user).
        2. In an atomic transaction with select_for_update(skip_locked=True):
           - Queries pending InteractionLogs for actor_ids up to batch_size.
           - If no pending events and not force, returns early without mutation.
           - Claims the pending event rows.
           - Aggregates the full event ledger for actor_ids (processed events + newly claimed events)
             to guarantee determinism and idempotency.
           - Computes genre, tag, and keyword weights based on movie metadata and event weights.
           - Incorporates inverse undo events properly (e.g. LIKE +1.0 then UNDO -1.0 -> 0.0 net).
           - Updates UserTasteProfile.learned_weights and increments version counter.
           - Updates claimed events to processing_status='processed' and processed_at=now.
        3. Returns execution metrics dictionary.
        """
        user = cls._resolve_user(user_or_id)
        actor_ids = cls.get_actor_ids(user)

        with transaction.atomic():
            # Ensure taste profile exists under lock
            profile, _ = UserTasteProfile.objects.select_for_update().get_or_create(
                user=user,
                defaults={
                    "emotional_tonality": [],
                    "narrative_structures": [],
                    "thematic_interests": [],
                    "preferred_languages": [],
                    "default_eras": [],
                    "hard_exclusions": {},
                    "learned_weights": {},
                },
            )

            # Claim pending events with SKIP LOCKED
            pending_qs = (
                InteractionLog.objects.select_for_update(skip_locked=True)
                .filter(user_id__in=actor_ids, processing_status="pending")
                .order_by("created_at", "id")
            )

            if batch_size is not None and batch_size > 0:
                claimed_events = list(pending_qs[:batch_size])
            else:
                claimed_events = list(pending_qs)

            # If no pending events to process and no force flag, return early
            if not claimed_events and not force:
                return {
                    "user_id": user.id,
                    "events_claimed": 0,
                    "events_processed": 0,
                    "remaining_pending": 0,
                    "profile_version": profile.version,
                    "learned_weights": profile.learned_weights or {},
                    "status": "noop",
                }

            claimed_ids = [e.id for e in claimed_events]

            # The complete event ledger is the single source of truth:
            # Query all processed events plus the newly claimed events for all actor_ids
            ledger_events = list(
                InteractionLog.objects.filter(user_id__in=actor_ids)
                .filter(
                    models.Q(processing_status="processed")
                    | models.Q(id__in=claimed_ids)
                )
                .select_related("movie")
                .prefetch_related("movie__genres", "movie__tags", "movie__keywords")
                .order_by("created_at", "id")
            )

            # Deterministic weight aggregation across genres, tags, and keywords
            genre_weights: Dict[str, float] = {}
            tag_weights: Dict[str, float] = {}
            keyword_weights: Dict[str, float] = {}

            for event in ledger_events:
                weight = cls.resolve_event_weight(event)
                if weight == 0.0:
                    continue

                movie = event.movie
                if not movie:
                    continue

                # 1. Genres
                movie_genres: Set[str] = set()
                for g in movie.genres.all():
                    if g.name:
                        movie_genres.add(g.name)

                # Fallback to tmdb_genre_ids if M2M relation is empty
                if not movie_genres and movie.tmdb_genre_ids:
                    for gid in movie.tmdb_genre_ids:
                        name = TMDB_GENRE_MAP.get(gid)
                        if name:
                            movie_genres.add(name)

                # 2. Tags
                movie_tags: Set[str] = {t.name for t in movie.tags.all() if t.name}

                # 3. Keywords
                movie_keywords: Set[str] = {k.name for k in movie.keywords.all() if k.name}

                # Contextual tags or genres from metadata if present
                meta = event.metadata if isinstance(event.metadata, dict) else {}
                if isinstance(meta.get("genres"), list):
                    movie_genres.update(str(x) for x in meta["genres"] if x)
                if isinstance(meta.get("tags"), list):
                    movie_tags.update(str(x) for x in meta["tags"] if x)
                if isinstance(meta.get("keywords"), list):
                    movie_keywords.update(str(x) for x in meta["keywords"] if x)

                # Accumulate weights
                for g_name in movie_genres:
                    genre_weights[g_name] = genre_weights.get(g_name, 0.0) + weight

                for t_name in movie_tags:
                    tag_weights[t_name] = tag_weights.get(t_name, 0.0) + weight

                for k_name in movie_keywords:
                    keyword_weights[k_name] = keyword_weights.get(k_name, 0.0) + weight

            # Build cleaned, rounded weight mappings
            clean_genres = {k: round(v, 4) for k, v in genre_weights.items()}
            clean_tags = {k: round(v, 4) for k, v in tag_weights.items()}
            clean_keywords = {k: round(v, 4) for k, v in keyword_weights.items()}

            # Structure learned_weights:
            # Contains both category-nested mappings ('genres', 'tags', 'keywords')
            # and flattened token keys for direct lookup compatibility.
            learned_weights: Dict[str, Any] = {
                "genres": clean_genres,
                "tags": clean_tags,
                "keywords": clean_keywords,
            }

            for k, v in clean_genres.items():
                if k not in learned_weights:
                    learned_weights[k] = v

            for k, v in clean_tags.items():
                if k not in learned_weights:
                    learned_weights[k] = v
                elif k in clean_genres:
                    learned_weights[k] = round(clean_genres[k] + clean_tags[k], 4)

            for k, v in clean_keywords.items():
                if k not in learned_weights:
                    learned_weights[k] = v
                else:
                    learned_weights[k] = round(learned_weights[k] + clean_keywords[k], 4)

            # Atomically update taste profile
            profile.learned_weights = learned_weights
            profile.version = models.F("version") + 1
            profile.save(update_fields=["learned_weights", "version", "updated_at"])
            profile.refresh_from_db(fields=["version", "updated_at", "learned_weights"])

            # Atomically transition claimed events to processed
            if claimed_ids:
                now = timezone.now()
                InteractionLog.objects.filter(id__in=claimed_ids).update(
                    processing_status="processed",
                    processed_at=now,
                )

            # Query remaining pending logs
            remaining_pending = InteractionLog.objects.filter(
                user_id__in=actor_ids,
                processing_status="pending",
            ).count()

            logger.info(
                "Taste profile recomputed for User %s (actor_ids=%s): "
                "%d events processed, %d remaining pending, profile v%d",
                user.id,
                actor_ids,
                len(claimed_ids),
                remaining_pending,
                profile.version,
            )

            return {
                "user_id": user.id,
                "events_claimed": len(claimed_ids),
                "events_processed": len(claimed_ids),
                "remaining_pending": remaining_pending,
                "profile_version": profile.version,
                "learned_weights": profile.learned_weights,
                "status": "success",
            }


def recompute_user_taste_profile(
    user_or_id: Any,
    batch_size: int = 100,
    force: bool = False,
) -> Dict[str, Any]:
    """Module-level convenience wrapper for TasteEngineService.recompute_user_taste_profile."""
    return TasteEngineService.recompute_user_taste_profile(
        user_or_id=user_or_id,
        batch_size=batch_size,
        force=force,
    )


def handle_recompute_taste_profile(
    job: CatalogueJob,
    worker_id: str,
    lease_token: uuid.UUID,
    generation: int,
) -> Dict[str, Any]:
    """
    Background worker handler for 'recompute_taste_profile' jobs.
    - Extracts user_id from job.entity_id or job.payload.
    - Extracts batch_size and force parameters from job.payload.
    - Iteratively drains pending interaction logs in batches for the target user.
    - Returns summary dictionary of events processed and updated profile metadata.
    """
    payload = job.payload if isinstance(job.payload, dict) else {}
    raw_user_id = payload.get("user_id") or job.entity_id
    if not raw_user_id:
        raise ValueError(
            f"Job {job.id} (type='{job.job_type}') missing user_id in entity_id or payload."
        )

    try:
        user_id = int(raw_user_id)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Job {job.id} invalid user_id '{raw_user_id}': must be integer.") from exc

    batch_size = payload.get("batch_size", 100)
    force = payload.get("force", False)

    logger.info(
        "[%s] Executing recompute_taste_profile for User %s (Job %s, gen=%d, batch_size=%s)",
        worker_id,
        user_id,
        job.id,
        generation,
        batch_size,
    )

    total_processed = 0
    final_result: Dict[str, Any] = {}
    max_iterations = 100  # Guard against unbounded loops

    for _ in range(max_iterations):
        step_result = TasteEngineService.recompute_user_taste_profile(
            user_or_id=user_id,
            batch_size=batch_size,
            force=force,
        )
        final_result = step_result
        processed = step_result.get("events_processed", 0)
        total_processed += processed
        force = False  # Only apply force flag on initial batch

        if processed == 0 or step_result.get("remaining_pending", 0) == 0:
            break

    return {
        "status": final_result.get("status", "success"),
        "user_id": user_id,
        "events_processed": total_processed,
        "remaining_pending": final_result.get("remaining_pending", 0),
        "profile_version": final_result.get("profile_version"),
        "learned_weights": final_result.get("learned_weights", {}),
    }
