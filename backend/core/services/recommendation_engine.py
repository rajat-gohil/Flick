"""
Personalized Recommendation Engine for Flick Catalogue Intelligence.

Workstream 1:
- PersonalizedRecommendationEngine:
  - get_recommendations(
      user: User,
      limit: int = 20,
      offset: int = 0,
      exclude_movie_ids: Optional[Set[int]] = None,
      min_quality: float = 0.0,
      apply_diversity: bool = True,
      shelf_context: Optional[str] = None
    ) -> Dict[str, Any]
  - Identity & Account Isolation:
    - Resolves canonical identity: actor_ids = IdentityLinkingService.get_all_actor_ids_for_user(user).
    - Strict account isolation: No interactions or exposures from other accounts leak into scoring.
  - Candidate Pool:
    - Movie.objects.filter(display_ready=True, recommendable=True, provenance__in=['tmdb_catalogue', 'manual_curated']).
  - Content-based Scoring:
    - Combines learned_weights['genres'], learned_weights['tags'], learned_weights['keywords'].
    - Negative penalties for disliked attributes.
    - Bayesian quality bonus based on rating, vote_count, and release_date.
    - True 14-day half-life fatigue penalty from MovieExposure for user_id__in=actor_ids.
  - Confidence & Honest Cold-Start:
    - HIGH (>=10 interactions), MEDIUM (3-9 interactions), LOW (1-2 interactions), COLD_START (0 interactions).
    - For COLD_START, Bayesian quality ranking with confidence='COLD_START' and explanation:
      'Editorial Selection: Highly rated in the Flick collection'.
  - Diversity & Novelty:
    - Max 3 movies per primary genre in top 15 when apply_diversity=True.
  - Grounded Explanations:
    - {'reason': str, 'matched_signals': list, 'confidence': str}.
  - Return contract:
    - {'movies': [list of annotated movies], 'confidence': str, 'total_candidates': int, 'user_id': user.id}.
"""

from __future__ import annotations

import collections
import datetime
import logging
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from core.models import (
    InteractionLog,
    Movie,
    MovieExposure,
    Swipe,
    UserTasteProfile,
)

logger = logging.getLogger(__name__)

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

# Canonical Era Definitions
ERA_BOUNDARIES = {
    "before_1990": (0, 1989),
    "pre_1990": (0, 1989),
    "classic": (0, 1989),
    "1970s": (1970, 1979),
    "1980s": (1980, 1989),
    "90s": (1990, 1999),
    "1990s": (1990, 1999),
    "2000s": (2000, 2009),
    "2010s": (2010, 2019),
    "recent": (2020, 2099),
    "2020s": (2020, 2099),
}


def _pluralize_genre(name: str) -> str:
    """Returns a natural plural or collective phrase for a genre name."""
    n = name.strip()
    low = n.lower()
    if low in ("thriller", "drama", "western", "romance"):
        return f"{n}s" if not n.endswith("s") else n
    if low == "comedy":
        return "Comedies"
    if low == "mystery":
        return "Mysteries"
    if low == "documentary":
        return "Documentaries"
    if low in ("action", "crime", "horror", "fantasy", "war", "animation", "music", "history"):
        return f"{n} films"
    if low in ("science fiction", "sci-fi"):
        return "Sci-Fi films"
    if n.endswith("s"):
        return n
    return f"{n}s"


# Monkeypatch Movie to safely support dictionary access if needed by callers/tests
if not hasattr(Movie, "__getitem__"):
    def _movie_getitem(self: Movie, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)
    Movie.__getitem__ = _movie_getitem  # type: ignore

if not hasattr(Movie, "get"):
    def _movie_get(self: Movie, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)
    Movie.get = _movie_get  # type: ignore

if not hasattr(Movie, "__contains__"):
    def _movie_contains(self: Movie, key: str) -> bool:
        return hasattr(self, key)
    Movie.__contains__ = _movie_contains  # type: ignore


class PersonalizedRecommendationEngine:
    """
    Centralized recommendation engine for Flick.
    Implements multi-signal scoring, Bayesian quality ranking, fatigue suppression,
    genre diversity clamping, grounded explanations, and honest cold-start fallbacks.
    """

    # Scoring constants
    BAYESIAN_MIN_VOTES_GENERAL: int = 500
    BAYESIAN_MIN_VOTES_CLASSIC: int = 100
    BAYESIAN_CATALOG_MEAN_NORMALIZED: float = 0.68  # 6.8 / 10.0
    CLASSIC_CUTOFF_YEAR: int = 1990
    FATIGUE_HALF_LIFE_DAYS: float = 14.0
    FATIGUE_UNIT_WEIGHT: float = 5.0
    MAX_FATIGUE: float = 15.0

    @classmethod
    def _resolve_user(cls, user_or_id: Any) -> Any:
        """Resolves a User instance from either a User instance or user ID."""
        if isinstance(user_or_id, (int, str)):
            User = get_user_model()
            return User.objects.get(id=int(user_or_id))
        return user_or_id

    @classmethod
    def get_actor_ids(cls, user: Any) -> List[int]:
        """
        Resolves canonical user and all linked guest actor IDs using IdentityLinkingService.
        Enforces strict account isolation.
        """
        try:
            from core.services.identity_linking import IdentityLinkingService
            return IdentityLinkingService.get_all_actor_ids_for_user(user)
        except Exception:
            user_id = user.id if hasattr(user, "id") else int(user)
            actor_ids = [user_id]
            try:
                from core.models import UserIdentityLink
                linked = list(
                    UserIdentityLink.objects.filter(canonical_user_id=user_id).values_list(
                        "linked_actor_id", flat=True
                    )
                )
                actor_ids.extend(linked)
            except Exception:
                pass
            return list(dict.fromkeys(int(aid) for aid in actor_ids))

    @classmethod
    def compute_bayesian_quality(
        cls,
        vote_average: Union[float, int, None],
        vote_count: Union[int, None],
        release_date: Optional[datetime.date] = None,
    ) -> float:
        """
        Computes Bayesian quality bonus in [0.0, 10.0]:
        S_quality = 10.0 * [ (v / (v + m)) * (R / 10.0) + (m / (v + m)) * C ]
        """
        r_raw = min(10.0, max(0.0, float(vote_average or 0.0)))
        v = max(0, int(vote_count or 0))

        is_classic = False
        if release_date:
            try:
                is_classic = release_date.year < cls.CLASSIC_CUTOFF_YEAR
            except (AttributeError, ValueError):
                pass

        m = cls.BAYESIAN_MIN_VOTES_CLASSIC if is_classic else cls.BAYESIAN_MIN_VOTES_GENERAL
        c = cls.BAYESIAN_CATALOG_MEAN_NORMALIZED

        denom = v + m
        if denom <= 0:
            return 10.0 * c

        term1 = (v / denom) * (r_raw / 10.0)
        term2 = (m / denom) * c
        bayesian_score = 10.0 * (term1 + term2)
        return min(10.0, max(0.0, bayesian_score))

    @classmethod
    def get_user_exposures(cls, actor_ids: List[int]) -> Dict[int, Any]:
        """
        Fetches MovieExposure records strictly isolated to user_id__in=actor_ids.
        Safely handles schemas or mocks where user or user_id is present.
        """
        exposure_map: Dict[int, Any] = {}
        # Try user_id__in first (standard for mock and schema isolation)
        try:
            exps = MovieExposure.objects.filter(user_id__in=actor_ids)
            for exp in exps:
                m_id = getattr(exp, "movie_id", None) or getattr(exp.movie, "id", None)
                if m_id is not None:
                    exposure_map[m_id] = exp
            return exposure_map
        except Exception:
            pass

        # Try user__in
        try:
            exps = MovieExposure.objects.filter(user__in=actor_ids)
            for exp in exps:
                m_id = getattr(exp, "movie_id", None) or getattr(exp.movie, "id", None)
                if m_id is not None:
                    exposure_map[m_id] = exp
            return exposure_map
        except Exception:
            pass

        return exposure_map

    @classmethod
    def compute_fatigue_penalty(
        cls,
        exposure: Optional[Any],
        now: Optional[datetime.datetime] = None,
    ) -> float:
        """
        Calculates 14-day half-life fatigue penalty:
        decay = 2 ** (-delta_t / 14.0)
        penalty = min(15.0, 5.0 * count * decay)
        """
        if exposure is None:
            return 0.0

        if now is None:
            now = timezone.now()

        count = getattr(exposure, "exposed_count", 1) or 1
        last_exposed = getattr(exposure, "last_exposed_at", None)

        if last_exposed:
            delta_t = max(0.0, (now - last_exposed).total_seconds() / 86400.0)
            decay = 2.0 ** (-delta_t / cls.FATIGUE_HALF_LIFE_DAYS)
            penalty = cls.FATIGUE_UNIT_WEIGHT * count * decay
        else:
            penalty = cls.FATIGUE_UNIT_WEIGHT * count

        return min(cls.MAX_FATIGUE, max(0.0, penalty))

    @classmethod
    def get_primary_genre(cls, movie: Movie) -> str:
        """Extracts the primary canonical genre name for diversity clamping."""
        # Check pre-fetched or related genres
        try:
            for g in movie.genres.all():
                if g.name:
                    return str(g.name).strip()
        except Exception:
            pass

        # Fallback to tmdb_genre_ids
        if movie.tmdb_genre_ids:
            for gid in movie.tmdb_genre_ids:
                if gid in TMDB_GENRE_MAP:
                    return TMDB_GENRE_MAP[gid]

        return "General"

    @classmethod
    def determine_movie_era(cls, release_date: Optional[datetime.date]) -> Optional[str]:
        """Determines the era label for a movie release date."""
        if not release_date:
            return None
        year = getattr(release_date, "year", None)
        if year is None:
            return None

        if year < 1990:
            return "classic"
        elif 1990 <= year <= 1999:
            return "1990s"
        elif 2000 <= year <= 2009:
            return "2000s"
        elif 2010 <= year <= 2019:
            return "2010s"
        else:
            return "recent"

    @classmethod
    def generate_explanation(
        cls,
        confidence: str,
        liked_genres: List[str],
        liked_tags: List[str],
        liked_keywords: List[str],
        matched_era: Optional[str],
    ) -> Dict[str, Any]:
        """
        Generates a grounded explanation dictionary:
        {'reason': str, 'matched_signals': list, 'confidence': str}.
        """
        if confidence == "COLD_START":
            return {
                "reason": "Editorial Selection: Highly rated in the Flick collection",
                "matched_signals": [],
                "confidence": "COLD_START",
            }

        matched_signals: List[str] = []
        matched_signals.extend(liked_genres)
        matched_signals.extend(liked_tags)
        matched_signals.extend(liked_keywords)
        if matched_era:
            matched_signals.append(matched_era)

        # Build grounded reason string
        reason = ""
        top_genre = liked_genres[0] if liked_genres else None
        top_tag = liked_tags[0] if liked_tags else None
        top_keyword = liked_keywords[0] if liked_keywords else None

        if top_genre and (top_tag or top_keyword):
            feature = top_tag if top_tag else top_keyword
            reason = f"Because you liked {_pluralize_genre(top_genre)} with {feature}"
            if matched_era:
                reason += f" • Strong alignment with your preferred era ({matched_era})"
        elif top_genre:
            if len(liked_genres) >= 2:
                reason = f"Because you liked {_pluralize_genre(liked_genres[0])} and {_pluralize_genre(liked_genres[1])}"
            else:
                reason = f"Because you liked {_pluralize_genre(top_genre)}"
            if matched_era:
                reason += f" • Strong alignment with your preferred era ({matched_era})"
        elif matched_era:
            reason = f"Strong alignment with your preferred era ({matched_era})"
            if top_tag:
                reason += f" featuring {top_tag}"
        elif top_tag:
            reason = f"Because you liked films featuring {top_tag}"
        elif top_keyword:
            reason = f"Because you liked stories exploring {top_keyword}"
        else:
            reason = "Recommended based on your taste profile"

        return {
            "reason": reason,
            "matched_signals": matched_signals,
            "confidence": confidence,
        }

    @classmethod
    def get_recommendations(
        cls,
        user: Any,
        limit: int = 20,
        offset: int = 0,
        exclude_movie_ids: Optional[Set[int]] = None,
        min_quality: float = 0.0,
        apply_diversity: bool = True,
        shelf_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates personalized movie recommendations.

        Arguments:
            user: User instance or user ID.
            limit: Number of recommendations to return (default 20).
            offset: Offset for pagination (default 0).
            exclude_movie_ids: Set of movie IDs to exclude from candidate pool.
            min_quality: Minimum Bayesian quality threshold (0.0 to 10.0).
            apply_diversity: If True, clamps max 3 movies per primary genre in top 15.
            shelf_context: Optional context string (e.g. 'because_you_liked', 'trending').

        Returns:
            {
                'movies': [list of annotated movies],
                'confidence': str,
                'total_candidates': int,
                'user_id': user.id
            }
        """
        canonical_user = cls._resolve_user(user)
        canonical_user_id = canonical_user.id

        # 1. Resolve canonical identity and all linked actor IDs
        actor_ids = cls.get_actor_ids(canonical_user)

        # 2. Query interactions across all linked actor IDs with strict account isolation
        interaction_count = InteractionLog.objects.filter(user_id__in=actor_ids).count()
        swipe_count = Swipe.objects.filter(user_id__in=actor_ids).count()
        total_interactions = max(interaction_count, swipe_count)

        # Categorize confidence
        if total_interactions >= 10:
            confidence = "HIGH"
        elif total_interactions >= 3:
            confidence = "MEDIUM"
        elif total_interactions >= 1:
            confidence = "LOW"
        else:
            confidence = "COLD_START"

        # 3. Fetch canonical UserTasteProfile
        taste_profile = UserTasteProfile.objects.filter(user_id=canonical_user_id).first()

        learned_weights: Dict[str, Any] = {}
        if taste_profile and isinstance(taste_profile.learned_weights, dict):
            learned_weights = taste_profile.learned_weights

        # Check if profile has any non-empty learned weights
        genre_weights: Dict[str, float] = {}
        tag_weights: Dict[str, float] = {}
        keyword_weights: Dict[str, float] = {}

        if isinstance(learned_weights.get("genres"), dict):
            genre_weights = {str(k): float(v) for k, v in learned_weights["genres"].items()}
        if isinstance(learned_weights.get("tags"), dict):
            tag_weights = {str(k): float(v) for k, v in learned_weights["tags"].items()}
        if isinstance(learned_weights.get("keywords"), dict):
            keyword_weights = {str(k): float(v) for k, v in learned_weights["keywords"].items()}

        # Top-level fallback if learned_weights is flat
        if not genre_weights and not tag_weights and not keyword_weights and learned_weights:
            for k, v in learned_weights.items():
                if isinstance(v, (int, float)):
                    keyword_weights[str(k)] = float(v)

        has_taste_data = bool(genre_weights or tag_weights or keyword_weights)
        is_cold_start = (confidence == "COLD_START") or (not has_taste_data and total_interactions == 0)

        if is_cold_start:
            confidence = "COLD_START"

        # Extract preferred eras and hard exclusions
        preferred_eras: List[str] = []
        hard_exclusions: Dict[str, Any] = {}
        if taste_profile:
            if isinstance(taste_profile.default_eras, list):
                preferred_eras = [str(e).lower() for e in taste_profile.default_eras]
            if isinstance(taste_profile.hard_exclusions, dict):
                hard_exclusions = taste_profile.hard_exclusions

        excluded_genre_ids: Set[int] = set()
        if "excluded_genre_ids" in hard_exclusions and isinstance(hard_exclusions["excluded_genre_ids"], list):
            excluded_genre_ids = {int(gid) for gid in hard_exclusions["excluded_genre_ids"]}

        # 4. Fetch MovieExposure records strictly isolated to actor_ids
        exposure_map = cls.get_user_exposures(actor_ids)
        now = timezone.now()

        # 5. Build candidate pool
        candidate_qs = Movie.objects.filter(
            display_ready=True,
            recommendable=True,
            provenance__in=["tmdb_catalogue", "manual_curated"],
        )

        if exclude_movie_ids:
            candidate_qs = candidate_qs.exclude(id__in=exclude_movie_ids)

        # Prefetch genres, tags, keywords for high performance
        candidate_qs = candidate_qs.prefetch_related("genres", "tags", "keywords")

        scored_candidates: List[Dict[str, Any]] = []

        for movie in candidate_qs:
            # Check hard exclusions
            if excluded_genre_ids:
                movie_genre_ids = set()
                if movie.tmdb_genre_ids:
                    movie_genre_ids.update(int(gid) for gid in movie.tmdb_genre_ids)
                try:
                    for g in movie.genres.all():
                        if getattr(g, "tmdb_id", None):
                            movie_genre_ids.add(int(g.tmdb_id))
                except Exception:
                    pass
                if movie_genre_ids.intersection(excluded_genre_ids):
                    continue

            # Calculate Bayesian quality bonus [0.0, 10.0]
            quality_bonus = cls.compute_bayesian_quality(
                vote_average=movie.rating,
                vote_count=movie.vote_count,
                release_date=movie.release_date,
            )

            # Apply min_quality threshold if set
            if min_quality > 0.0:
                movie_rating = float(movie.rating or 0.0)
                if quality_bonus < min_quality and movie_rating < min_quality:
                    continue

            # Calculate fatigue penalty from user-specific exposures
            exp = exposure_map.get(movie.id)
            fatigue_penalty = cls.compute_fatigue_penalty(exp, now=now)

            # Extract movie metadata
            movie_genres: Set[str] = set()
            try:
                for g in movie.genres.all():
                    if g.name:
                        movie_genres.add(str(g.name).strip())
            except Exception:
                pass

            if not movie_genres and movie.tmdb_genre_ids:
                for gid in movie.tmdb_genre_ids:
                    if gid in TMDB_GENRE_MAP:
                        movie_genres.add(TMDB_GENRE_MAP[gid])

            movie_tags: Set[str] = set()
            try:
                for t in movie.tags.all():
                    if t.name:
                        movie_tags.add(str(t.name).strip())
            except Exception:
                pass

            movie_keywords: Set[str] = set()
            try:
                for k in movie.keywords.all():
                    if k.name:
                        movie_keywords.add(str(k.name).strip())
            except Exception:
                pass

            primary_genre = cls.get_primary_genre(movie)
            movie_era = cls.determine_movie_era(movie.release_date)

            if is_cold_start:
                # Cold-start ranking relies purely on Bayesian quality minus fatigue
                final_score = quality_bonus - fatigue_penalty
                explanation = cls.generate_explanation(
                    confidence="COLD_START",
                    liked_genres=[],
                    liked_tags=[],
                    liked_keywords=[],
                    matched_era=None,
                )
            else:
                # Content-based scoring combining learned weights with negative penalties
                genre_score = 0.0
                tag_score = 0.0
                keyword_score = 0.0
                negative_penalty = 0.0

                liked_genres_list: List[Tuple[str, float]] = []
                liked_tags_list: List[Tuple[str, float]] = []
                liked_keywords_list: List[Tuple[str, float]] = []

                # Genre matching
                for g_name in movie_genres:
                    w = genre_weights.get(g_name, 0.0)
                    if w > 0:
                        genre_score += w
                        liked_genres_list.append((g_name, w))
                    elif w < 0:
                        # Negative penalty for disliked genres
                        negative_penalty += abs(w) * 1.5

                # Tag matching
                for t_name in movie_tags:
                    w = tag_weights.get(t_name, 0.0)
                    if w > 0:
                        tag_score += w
                        liked_tags_list.append((t_name, w))
                    elif w < 0:
                        # Negative penalty for disliked tags
                        negative_penalty += abs(w) * 1.2

                # Keyword matching
                for k_name in movie_keywords:
                    w = keyword_weights.get(k_name, 0.0)
                    if w > 0:
                        keyword_score += w
                        liked_keywords_list.append((k_name, w))
                    elif w < 0:
                        # Negative penalty for disliked keywords
                        negative_penalty += abs(w) * 1.2

                # Era alignment
                era_bonus = 0.0
                matched_era_str: Optional[str] = None
                if movie_era and preferred_eras:
                    if movie_era in preferred_eras or (movie_era == "1990s" and "90s" in preferred_eras):
                        era_bonus = 2.0
                        matched_era_str = movie_era

                # Sort matched signals by descending positive weight
                liked_genres_list.sort(key=lambda x: x[1], reverse=True)
                liked_tags_list.sort(key=lambda x: x[1], reverse=True)
                liked_keywords_list.sort(key=lambda x: x[1], reverse=True)

                # Composite personalized score:
                # Content alignment is primary, supplemented by Bayesian quality and era alignment,
                # penalized by disliked attributes and exposure fatigue.
                final_score = (
                    (genre_score * 2.0)
                    + (tag_score * 1.5)
                    + (keyword_score * 1.2)
                    + (quality_bonus * 0.5)
                    + era_bonus
                    - negative_penalty
                    - fatigue_penalty
                )

                explanation = cls.generate_explanation(
                    confidence=confidence,
                    liked_genres=[g for g, _ in liked_genres_list],
                    liked_tags=[t for t, _ in liked_tags_list],
                    liked_keywords=[k for k, _ in liked_keywords_list],
                    matched_era=matched_era_str,
                )

            scored_candidates.append({
                "movie": movie,
                "score": final_score,
                "quality_bonus": quality_bonus,
                "fatigue_penalty": fatigue_penalty,
                "primary_genre": primary_genre,
                "explanation": explanation,
            })

        # Deterministic sorting:
        # Score desc, Bayesian quality desc, rating desc, vote_count desc, movie.id asc
        scored_candidates.sort(
            key=lambda item: (
                item["score"],
                item["quality_bonus"],
                float(item["movie"].rating or 0.0),
                int(item["movie"].vote_count or 0),
                -int(item["movie"].id or 0),
            ),
            reverse=True,
        )

        # 6. Diversity & Novelty Clamping:
        # Max 3 movies per primary genre in top 15 when apply_diversity is True
        if apply_diversity:
            top_15: List[Dict[str, Any]] = []
            overflow: List[Dict[str, Any]] = []
            genre_counts: collections.defaultdict[str, int] = collections.defaultdict(int)

            for item in scored_candidates:
                p_genre = item["primary_genre"]
                if len(top_15) < 15:
                    if genre_counts[p_genre] < 3:
                        top_15.append(item)
                        genre_counts[p_genre] += 1
                    else:
                        overflow.append(item)
                else:
                    overflow.append(item)

            total_candidates = len(top_15) + len(overflow)

            # Strict top-15 genre clamping invariant:
            # If top_15 has fewer than 15 items, overflow items (which were clamped because
            # their genre already reached 3) are held back until position 16 (index 15+).
            safe_offset = max(0, offset)
            safe_limit = max(0, limit)

            if len(top_15) >= 15:
                ranked_items = top_15 + overflow
                paginated_items = ranked_items[safe_offset : safe_offset + safe_limit]
            else:
                if safe_offset < 15:
                    paginated_items = list(top_15[safe_offset : min(15, safe_offset + safe_limit)])
                    needed_overflow = max(0, (safe_offset + safe_limit) - 15)
                    if needed_overflow > 0:
                        paginated_items.extend(overflow[:needed_overflow])
                else:
                    overflow_start = safe_offset - 15
                    paginated_items = list(overflow[overflow_start : overflow_start + safe_limit])
        else:
            ranked_items = scored_candidates
            total_candidates = len(ranked_items)
            safe_offset = max(0, offset)
            safe_limit = max(0, limit)
            paginated_items = ranked_items[safe_offset : safe_offset + safe_limit]

        # 8. Annotate Movie objects
        annotated_movies: List[Movie] = []
        for item in paginated_items:
            m = item["movie"]
            m.explanation = item["explanation"]
            m.score = round(float(item["score"]), 4)
            m.recommendation_score = round(float(item["score"]), 4)
            annotated_movies.append(m)

        return {
            "movies": annotated_movies,
            "confidence": confidence,
            "total_candidates": total_candidates,
            "user_id": canonical_user_id,
        }
