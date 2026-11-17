"""
Recommendation Quality Evaluation Service for Flick Catalogue Personalization.

Provides standardized metric calculation functions for evaluating recommendation quality,
cohort divergence, preference alignment, negative response rates, discovery novelties,
and shelf differentiation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from django.contrib.auth import get_user_model
from django.db import models

from core.models import InteractionLog, Movie, MovieExposure, Swipe, UserTasteProfile
from core.services.identity_linking import IdentityLinkingService

logger = logging.getLogger(__name__)


def _extract_movie_id(movie: Any) -> Optional[int]:
    """Extracts integer ID from a Movie instance, dictionary, or integer."""
    if isinstance(movie, int):
        return movie
    if isinstance(movie, str):
        try:
            return int(movie)
        except ValueError:
            return None
    if isinstance(movie, dict):
        val = movie.get("id") or movie.get("movie_id")
        if val is not None:
            try:
                return int(val)
            except ValueError:
                return None
    if hasattr(movie, "id"):
        return movie.id
    return None


def _extract_movie_tokens(movie: Any) -> Set[str]:
    """
    Extracts lowercase genre names, tag names, keyword names, and era/director
    from a Movie model instance or dictionary representation.
    """
    tokens: Set[str] = set()

    if isinstance(movie, dict):
        # Extract from dict
        for g in movie.get("genres", []) or []:
            if isinstance(g, str):
                tokens.add(g.strip().lower())
            elif isinstance(g, dict) and g.get("name"):
                tokens.add(str(g["name"]).strip().lower())

        for t in movie.get("tags", []) or []:
            if isinstance(t, str):
                tokens.add(t.strip().lower())
            elif isinstance(t, dict) and t.get("name"):
                tokens.add(str(t["name"]).strip().lower())

        for k in movie.get("keywords", []) or []:
            if isinstance(k, str):
                tokens.add(k.strip().lower())
            elif isinstance(k, dict) and k.get("name"):
                tokens.add(str(k["name"]).strip().lower())

        for gid in movie.get("tmdb_genre_ids", []) or []:
            tokens.add(f"genre_id:{gid}")

        if movie.get("director"):
            tokens.add(str(movie["director"]).strip().lower())

        if movie.get("era"):
            tokens.add(str(movie["era"]).strip().lower())

        return tokens

    # Movie model instance
    if isinstance(movie, Movie) or hasattr(movie, "genres"):
        try:
            for g in movie.genres.all():
                if g.name:
                    tokens.add(g.name.strip().lower())
        except Exception:
            pass

        try:
            for t in movie.tags.all():
                if t.name:
                    tokens.add(t.name.strip().lower())
        except Exception:
            pass

        try:
            for k in movie.keywords.all():
                if k.name:
                    tokens.add(k.name.strip().lower())
        except Exception:
            pass

        if getattr(movie, "tmdb_genre_ids", None):
            for gid in movie.tmdb_genre_ids:
                tokens.add(f"genre_id:{gid}")

        if getattr(movie, "director", None):
            tokens.add(str(movie.director).strip().lower())

        if getattr(movie, "release_date", None):
            year = movie.release_date.year
            if year < 1980:
                tokens.add("classic")
            elif 1980 <= year < 1990:
                tokens.add("80s")
            elif 1990 <= year < 2000:
                tokens.add("90s")
            elif 2000 <= year < 2010:
                tokens.add("2000s")
            elif 2010 <= year < 2020:
                tokens.add("2010s")
            else:
                tokens.add("2020s")

    return tokens


def _resolve_user_actor_ids(user: Any) -> List[int]:
    """Resolves all actor IDs for a user including linked guest accounts."""
    try:
        return IdentityLinkingService.get_all_actor_ids_for_user(user)
    except Exception:
        uid = getattr(user, "id", None)
        return [uid] if uid is not None else []


def compute_cohort_divergence(
    user_a_ids: Sequence[int],
    user_b_ids: Sequence[int],
) -> float:
    """
    Computes the Jaccard similarity between two recommendation cohorts.

    Jaccard Similarity = |A ∩ B| / |A ∪ B|.
    - Returns 1.0 if cohorts are identical.
    - Returns 0.0 if cohorts have no items in common or if both cohorts are empty.
    - Used to verify cohort divergence target: Jaccard similarity < 0.30 between
      accounts with different taste profiles.
    """
    set_a = set(user_a_ids)
    set_b = set(user_b_ids)

    if not set_a and not set_b:
        return 0.0

    union = set_a | set_b
    if not union:
        return 0.0

    intersection = set_a & set_b
    return round(len(intersection) / len(union), 4)


def compute_preference_alignment(
    user: Any,
    recommended_movies: Sequence[Any],
) -> float:
    """
    Computes the ratio of recommended items that contain the user's top affinity
    tags, genres, or keywords.

    Ratio = (items containing user's top affinity attributes) / (total recommended items).
    Returns 0.0 if recommended_movies is empty or if user has no affinity signals.
    """
    if isinstance(recommended_movies, dict) and "movies" in recommended_movies:
        recommended_movies = recommended_movies["movies"]

    if not recommended_movies:
        return 0.0

    actor_ids = _resolve_user_actor_ids(user)
    profile = UserTasteProfile.objects.filter(user=user).first()

    # Collect user's positive affinity attributes
    affinity_tokens: Set[str] = set()

    if profile and profile.learned_weights:
        weights = profile.learned_weights
        # Genres with positive weight
        genres_dict = weights.get("genres", {})
        if isinstance(genres_dict, dict):
            for g, w in genres_dict.items():
                if isinstance(w, (int, float)) and w > 0:
                    affinity_tokens.add(str(g).strip().lower())

        # Tags with positive weight
        tags_dict = weights.get("tags", {})
        if isinstance(tags_dict, dict):
            for t, w in tags_dict.items():
                if isinstance(w, (int, float)) and w > 0:
                    affinity_tokens.add(str(t).strip().lower())

        # Keywords with positive weight
        keywords_dict = weights.get("keywords", {})
        if isinstance(keywords_dict, dict):
            for k, w in keywords_dict.items():
                if isinstance(w, (int, float)) and w > 0:
                    affinity_tokens.add(str(k).strip().lower())

        # Flattened tokens
        for k, v in weights.items():
            if k not in ("genres", "tags", "keywords") and isinstance(v, (int, float)) and v > 0:
                affinity_tokens.add(str(k).strip().lower())

        # Thematic interests
        if profile.thematic_interests:
            for item in profile.thematic_interests:
                affinity_tokens.add(str(item).strip().lower())

    # Fallback to positive interaction logs if profile has no learned weights
    if not affinity_tokens and actor_ids:
        positive_logs = (
            InteractionLog.objects.filter(
                user_id__in=actor_ids,
                event_type__in=["like", "swipe_like", "superlike", "match"],
            )
            .select_related("movie")
            .prefetch_related("movie__genres", "movie__tags", "movie__keywords")
        )
        for log in positive_logs:
            if log.movie:
                affinity_tokens.update(_extract_movie_tokens(log.movie))

    if not affinity_tokens:
        return 0.0

    aligned_count = 0
    total = len(recommended_movies)

    for item in recommended_movies:
        # Check if item has movie object or dict
        movie_obj = item.get("movie") if isinstance(item, dict) and "movie" in item else item
        tokens = _extract_movie_tokens(movie_obj)

        # Check matched signals if present in explanation
        if isinstance(item, dict):
            exp = item.get("explanation")
            if isinstance(exp, dict) and exp.get("matched_signals"):
                for sig in exp["matched_signals"]:
                    tokens.add(str(sig).strip().lower())

        if tokens & affinity_tokens:
            aligned_count += 1

    return round(aligned_count / total, 4)


def compute_negative_response_rate(
    user: Any,
    recommended_movies: Sequence[Any],
) -> float:
    """
    Computes the ratio of top recommended items featuring the user's disliked attributes.

    In a compliant personalization engine, this should be 0.0.
    Identifies attributes with negative weights in learned_weights, hard exclusions,
    or movies explicitly swiped dislike.
    """
    if isinstance(recommended_movies, dict) and "movies" in recommended_movies:
        recommended_movies = recommended_movies["movies"]

    if not recommended_movies:
        return 0.0

    actor_ids = _resolve_user_actor_ids(user)
    profile = UserTasteProfile.objects.filter(user=user).first()

    disliked_tokens: Set[str] = set()
    disliked_movie_ids: Set[int] = set()

    if profile:
        # Hard exclusions
        if profile.hard_exclusions:
            exclusions = profile.hard_exclusions
            if isinstance(exclusions, dict):
                for k, v in exclusions.items():
                    if isinstance(v, list):
                        for item in v:
                            disliked_tokens.add(str(item).strip().lower())
                    elif isinstance(v, str):
                        disliked_tokens.add(v.strip().lower())
            elif isinstance(exclusions, list):
                for item in exclusions:
                    disliked_tokens.add(str(item).strip().lower())

        # Negative learned weights
        if profile.learned_weights:
            weights = profile.learned_weights
            genres_dict = weights.get("genres", {})
            if isinstance(genres_dict, dict):
                for g, w in genres_dict.items():
                    if isinstance(w, (int, float)) and w < 0:
                        disliked_tokens.add(str(g).strip().lower())

            tags_dict = weights.get("tags", {})
            if isinstance(tags_dict, dict):
                for t, w in tags_dict.items():
                    if isinstance(w, (int, float)) and w < 0:
                        disliked_tokens.add(str(t).strip().lower())

            keywords_dict = weights.get("keywords", {})
            if isinstance(keywords_dict, dict):
                for k, w in keywords_dict.items():
                    if isinstance(w, (int, float)) and w < 0:
                        disliked_tokens.add(str(k).strip().lower())

            for k, v in weights.items():
                if k not in ("genres", "tags", "keywords") and isinstance(v, (int, float)) and v < 0:
                    disliked_tokens.add(str(k).strip().lower())

    if actor_ids:
        dislike_logs = (
            InteractionLog.objects.filter(
                user_id__in=actor_ids,
                event_type__in=["dislike", "swipe_dislike"],
            )
            .select_related("movie")
            .prefetch_related("movie__genres")
        )
        for log in dislike_logs:
            if log.movie_id:
                disliked_movie_ids.add(log.movie_id)
            if log.movie:
                for g in log.movie.genres.all():
                    if g.name:
                        disliked_tokens.add(g.name.strip().lower())

    if not disliked_tokens and not disliked_movie_ids:
        return 0.0

    violation_count = 0
    total = len(recommended_movies)

    for item in recommended_movies:
        movie_obj = item.get("movie") if isinstance(item, dict) and "movie" in item else item
        mid = _extract_movie_id(movie_obj)

        if mid is not None and mid in disliked_movie_ids:
            violation_count += 1
            continue

        tokens = _extract_movie_tokens(movie_obj)
        if tokens & disliked_tokens:
            violation_count += 1

    return round(violation_count / total, 4)


def compute_unexposed_discovery_ratio(
    user: Any,
    recommended_movies: Sequence[Any],
) -> float:
    """
    Computes the ratio of unexposed films in the recommended list.

    Unexposed films are films that neither the user nor any of their linked guest actors
    have interacted with or previously seen.
    """
    if isinstance(recommended_movies, dict) and "movies" in recommended_movies:
        recommended_movies = recommended_movies["movies"]

    if not recommended_movies:
        return 0.0

    actor_ids = _resolve_user_actor_ids(user)
    exposed_movie_ids: Set[int] = set()

    if actor_ids:
        # 1. InteractionLog
        int_ids = InteractionLog.objects.filter(
            user_id__in=actor_ids
        ).values_list("movie_id", flat=True)
        exposed_movie_ids.update(int_ids)

        # 2. Swipe
        swipe_ids = Swipe.objects.filter(
            user_id__in=actor_ids
        ).values_list("movie_id", flat=True)
        exposed_movie_ids.update(swipe_ids)

        # 3. MovieExposure (if user field exists)
        if any(f.name == "user" for f in MovieExposure._meta.get_fields()):
            exp_ids = MovieExposure.objects.filter(
                models.Q(user_id__in=actor_ids)
            ).values_list("movie_id", flat=True)
            exposed_movie_ids.update(exp_ids)

    unexposed_count = 0
    total = len(recommended_movies)

    for item in recommended_movies:
        movie_obj = item.get("movie") if isinstance(item, dict) and "movie" in item else item
        mid = _extract_movie_id(movie_obj)
        if mid is None or mid not in exposed_movie_ids:
            unexposed_count += 1

    return round(unexposed_count / total, 4)


def compute_shelf_diversity(
    shelves: Dict[str, Sequence[Any]],
) -> float:
    """
    Computes the inter-shelf differentiation score.

    Evaluates the average pairwise Jaccard distance (1.0 - Jaccard similarity)
    between all non-empty shelf pairs.
    - Returns 1.0 if all shelves have completely disjoint movie sets.
    - Returns 0.0 if all shelves contain identical movie sets.
    - Returns 1.0 if there is 1 or 0 shelves.
    """
    shelf_movie_ids: Dict[str, Set[int]] = {}

    for shelf_name, items in shelves.items():
        if not items:
            continue
        ids: Set[int] = set()
        for item in items:
            movie_obj = item.get("movie") if isinstance(item, dict) and "movie" in item else item
            mid = _extract_movie_id(movie_obj)
            if mid is not None:
                ids.add(mid)
        if ids:
            shelf_movie_ids[shelf_name] = ids

    shelf_names = list(shelf_movie_ids.keys())
    if len(shelf_names) <= 1:
        return 1.0 if shelf_names else 0.0

    pairwise_distances: List[float] = []

    for i in range(len(shelf_names)):
        for j in range(i + 1, len(shelf_names)):
            ids_a = shelf_movie_ids[shelf_names[i]]
            ids_b = shelf_movie_ids[shelf_names[j]]
            similarity = compute_cohort_divergence(list(ids_a), list(ids_b))
            pairwise_distances.append(1.0 - similarity)

    if not pairwise_distances:
        return 1.0

    return round(sum(pairwise_distances) / len(pairwise_distances), 4)


class RecommendationEvaluationService:
    """
    Comprehensive evaluation service aggregating metrics across users and shelves.
    """

    @classmethod
    def evaluate_user_recommendations(
        cls,
        user: Any,
        recommended_movies: Sequence[Any],
    ) -> Dict[str, float]:
        """Evaluates alignment, negative response rate, and unexposed ratio for a user's recommendations."""
        return {
            "preference_alignment": compute_preference_alignment(user, recommended_movies),
            "negative_response_rate": compute_negative_response_rate(user, recommended_movies),
            "unexposed_discovery_ratio": compute_unexposed_discovery_ratio(user, recommended_movies),
        }

    @classmethod
    def evaluate_cohort_divergence(
        cls,
        user_a_ids: Sequence[int],
        user_b_ids: Sequence[int],
    ) -> float:
        """Evaluates Jaccard similarity between two recommendation cohorts."""
        return compute_cohort_divergence(user_a_ids, user_b_ids)

    @classmethod
    def evaluate_shelf_diversity(
        cls,
        shelves: Dict[str, Sequence[Any]],
    ) -> float:
        """Evaluates inter-shelf differentiation score."""
        return compute_shelf_diversity(shelves)
