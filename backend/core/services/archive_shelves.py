"""
Archive Shelves Service for Flick Catalogue Intelligence.

Generates 5 distinct, meaningful, and cross-shelf deduplicated shelves for
personalized archive browsing:
1. 'recommended_for_you': General personalized matches via PersonalizedRecommendationEngine.
2. 'because_you_liked': Finds user's top-weighted positive interaction/superlike ('anchor_movie'),
   returns nearest content matches by shared keywords/tags/director.
3. 'explore_your_genres': Focuses on user's top 2 affinity genres from learned_weights['genres'].
4. 'explore_by_era': Focuses on user's preferred era (classic, 90s, 2000s, 2010s) based on positive interaction history.
5. 'outside_your_comfort_zone': Serendipity shelf: high quality (rating >= 7.0), zero previous user exposure,
   genres with neutral/limited exposure (not disliked).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

from core.models import (
    Genre,
    InteractionLog,
    Movie,
    MovieExposure,
    MovieKeyword,
    MovieTag,
    Swipe,
    UserTasteProfile,
)
from core.serializers import MovieSerializer

logger = logging.getLogger(__name__)

# Standard TMDB genre ID mapping for fallback
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
ERA_BOUNDS = {
    "classic": {"max_year": 1989, "label": "Classic (pre-1990)"},
    "90s": {"min_year": 1990, "max_year": 1999, "label": "1990s"},
    "2000s": {"min_year": 2000, "max_year": 2009, "label": "2000s"},
    "2010s": {"min_year": 2010, "max_year": 2019, "label": "2010s"},
    "recent": {"min_year": 2020, "label": "2020s & Recent"},
}


class ArchiveShelvesService:
    """
    Coordinates and builds personalized discovery shelves with strict cross-shelf
    deduplication and distinct shelf identities.
    """

    @classmethod
    def _resolve_user(cls, user_or_id: Any) -> Optional[Any]:
        if user_or_id is None:
            return None
        if isinstance(user_or_id, (int, str)):
            User = get_user_model()
            try:
                return User.objects.get(id=int(user_or_id))
            except (User.DoesNotExist, ValueError):
                return None
        return user_or_id

    @classmethod
    def _get_actor_ids(cls, user: Any) -> List[int]:
        if not user or not getattr(user, "is_authenticated", True):
            return []
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
    def _get_candidate_pool(cls, exclude_movie_ids: Optional[Set[int]] = None) -> models.QuerySet:
        qs = Movie.objects.all()
        # If any movie in the database has display_ready=True, filter by display_ready & recommendable
        if qs.filter(display_ready=True).exists():
            qs = qs.filter(display_ready=True)
            if qs.filter(recommendable=True).exists():
                qs = qs.filter(recommendable=True)

        if exclude_movie_ids:
            qs = qs.exclude(id__in=exclude_movie_ids)
        return qs

    @classmethod
    def _format_movie(
        cls,
        movie: Any,
        explanation: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Serializes a Movie instance or dict into the standard contract."""
        if isinstance(movie, dict):
            formatted = dict(movie)
            if explanation and "explanation" not in formatted:
                formatted["explanation"] = explanation
            return formatted

        data = MovieSerializer(movie).data
        genres = [g.name for g in movie.genres.all() if g.name]
        if not genres and movie.tmdb_genre_ids:
            genres = [TMDB_GENRE_MAP[gid] for gid in movie.tmdb_genre_ids if gid in TMDB_GENRE_MAP]
        data["genres"] = genres
        data["recommendable"] = getattr(movie, "recommendable", True)
        data["display_ready"] = getattr(movie, "display_ready", True)
        data["explanation"] = explanation or getattr(movie, "explanation", None) or {
            "reason": "Editorial Selection: Highly rated in the Flick collection",
            "matched_signals": [],
            "confidence": "COLD_START",
        }
        return data

    @classmethod
    def _get_movie_year(cls, movie: Any) -> Optional[int]:
        rel = getattr(movie, "release_date", None)
        if isinstance(rel, (date, datetime)):
            return rel.year
        if rel:
            try:
                return int(str(rel)[:4])
            except (ValueError, TypeError):
                pass
        return None

    @classmethod
    def _get_movie_genres(cls, movie: Any) -> Set[str]:
        if isinstance(movie, dict):
            g_list = movie.get("genres", [])
            return set(g_list)
        genres = {g.name for g in movie.genres.all() if g.name}
        if not genres and getattr(movie, "tmdb_genre_ids", None):
            genres = {TMDB_GENRE_MAP[gid] for gid in movie.tmdb_genre_ids if gid in TMDB_GENRE_MAP}
        return genres

    @classmethod
    def _get_movie_keywords(cls, movie: Any) -> Set[str]:
        if isinstance(movie, dict):
            return set(movie.get("keywords", []))
        return {k.name for k in movie.keywords.all() if k.name}

    @classmethod
    def _get_movie_tags(cls, movie: Any) -> Set[str]:
        if isinstance(movie, dict):
            return set(movie.get("tags", []))
        return {t.name for t in movie.tags.all() if t.name}

    @classmethod
    def _get_movie_directors(cls, movie: Any) -> Set[str]:
        credits = getattr(movie, "credits_summary", None)
        if isinstance(credits, dict):
            dirs = credits.get("directors", [])
            if isinstance(dirs, list):
                return {d.get("name", "").strip() for d in dirs if isinstance(d, dict) and d.get("name")}
        return set()

    # -------------------------------------------------------------------------
    # Shelf 1: Recommended For You
    # -------------------------------------------------------------------------
    @classmethod
    def _build_recommended_for_you(
        cls,
        user: Optional[Any],
        max_per_shelf: int,
        seen_movie_ids: Set[int],
    ) -> List[Dict[str, Any]]:
        """
        General personalized matches via PersonalizedRecommendationEngine.
        """
        movies_out: List[Dict[str, Any]] = []

        if user and getattr(user, "is_authenticated", True):
            try:
                from core.services.recommendation_engine import PersonalizedRecommendationEngine
                rec_res = PersonalizedRecommendationEngine.get_recommendations(
                    user=user,
                    limit=max_per_shelf,
                    offset=0,
                    exclude_movie_ids=seen_movie_ids,
                    min_quality=0.0,
                    apply_diversity=True,
                    shelf_context="recommended_for_you",
                )
                rec_movies = rec_res.get("movies", [])
                for m in rec_movies:
                    m_id = m.get("id") if isinstance(m, dict) else getattr(m, "id", None)
                    if m_id and m_id not in seen_movie_ids:
                        seen_movie_ids.add(m_id)
                        m_expl = getattr(m, "explanation", None) if not isinstance(m, dict) else m.get("explanation")
                        movies_out.append(cls._format_movie(m, explanation=m_expl))
                        if len(movies_out) >= max_per_shelf:
                            break
            except Exception as e:
                logger.warning(f"[ArchiveShelvesService] RecommendationEngine fallback: {e}")

        # Fallback if engine unavailable or returned insufficient items
        if len(movies_out) < max_per_shelf:
            remaining = max_per_shelf - len(movies_out)
            candidates = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids)
            fallback_items = candidates.order_by("-rating", "-vote_count", "-id")[:remaining]
            for m in fallback_items:
                seen_movie_ids.add(m.id)
                expl = {
                    "reason": "Editorial Selection: Highly rated in the Flick collection",
                    "matched_signals": ["high_rating"],
                    "confidence": "COLD_START",
                }
                movies_out.append(cls._format_movie(m, explanation=expl))

        return movies_out

    # -------------------------------------------------------------------------
    # Shelf 2: Because You Liked
    # -------------------------------------------------------------------------
    @classmethod
    def _build_because_you_liked(
        cls,
        user: Optional[Any],
        actor_ids: List[int],
        max_per_shelf: int,
        seen_movie_ids: Set[int],
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Finds user's top-weighted positive interaction/superlike ('anchor_movie'),
        returns nearest content matches by shared keywords/tags/director.
        """
        anchor_movie: Optional[Movie] = None
        anchor_info: Optional[Dict[str, Any]] = None

        if actor_ids:
            # Query top positive interactions (superlikes weighted 3.0 take precedence)
            top_log = (
                InteractionLog.objects.filter(
                    user_id__in=actor_ids,
                    weight__gt=0,
                    movie__isnull=False,
                )
                .select_related("movie")
                .order_by("-weight", "-created_at")
                .first()
            )
            if top_log and top_log.movie:
                anchor_movie = top_log.movie
            else:
                top_swipe = (
                    Swipe.objects.filter(
                        user_id__in=actor_ids,
                        reaction__in=[Swipe.SUPERLIKE, Swipe.LIKE],
                        movie__isnull=False,
                    )
                    .select_related("movie")
                    .order_by(
                        models.Case(
                            models.When(reaction=Swipe.SUPERLIKE, then=0),
                            default=1,
                        ),
                        "-created_at",
                    )
                    .first()
                )
                if top_swipe and top_swipe.movie:
                    anchor_movie = top_swipe.movie

        movies_out: List[Dict[str, Any]] = []

        if anchor_movie:
            anchor_info = {
                "id": anchor_movie.id,
                "title": anchor_movie.title,
                "release_year": cls._get_movie_year(anchor_movie),
                "poster_url": MovieSerializer(anchor_movie).data.get("poster_url"),
            }
            anchor_directors = cls._get_movie_directors(anchor_movie)
            anchor_keywords = cls._get_movie_keywords(anchor_movie)
            anchor_tags = cls._get_movie_tags(anchor_movie)
            anchor_genres = cls._get_movie_genres(anchor_movie)

            candidates = cls._get_candidate_pool(
                exclude_movie_ids=seen_movie_ids | {anchor_movie.id}
            )

            # Prefetch m2m relations for fast Python scoring
            candidates_list = list(
                candidates.prefetch_related("keywords", "tags", "genres")[:150]
            )

            scored: List[Tuple[float, List[str], Movie]] = []
            for cand in candidates_list:
                score = 0.0
                signals: List[str] = []

                c_dirs = cls._get_movie_directors(cand)
                c_kw = cls._get_movie_keywords(cand)
                c_tags = cls._get_movie_tags(cand)
                c_gen = cls._get_movie_genres(cand)

                # Director match: +5.0 pts
                shared_dirs = anchor_directors.intersection(c_dirs)
                if shared_dirs:
                    score += 5.0 * len(shared_dirs)
                    signals.extend([f"Director: {d}" for d in shared_dirs])

                # Keywords match: +2.0 pts
                shared_kw = anchor_keywords.intersection(c_kw)
                if shared_kw:
                    score += 2.0 * len(shared_kw)
                    signals.extend([f"Keyword: {k}" for k in list(shared_kw)[:2]])

                # Tags match: +1.5 pts
                shared_tags = anchor_tags.intersection(c_tags)
                if shared_tags:
                    score += 1.5 * len(shared_tags)
                    signals.extend([f"Tag: {t}" for t in list(shared_tags)[:2]])

                # Genres match: +1.0 pts
                shared_gen = anchor_genres.intersection(c_gen)
                if shared_gen:
                    score += 1.0 * len(shared_gen)
                    signals.extend([f"Genre: {g}" for g in list(shared_gen)[:2]])

                # Small Bayesian quality tie-breaker
                score += (cand.rating or 0.0) * 0.1

                if score > 0:
                    scored.append((score, signals, cand))

            scored.sort(
                key=lambda x: (x[0], x[2].rating or 0.0, x[2].vote_count or 0),
                reverse=True,
            )

            for score, signals, cand in scored[:max_per_shelf]:
                seen_movie_ids.add(cand.id)
                confidence = "HIGH" if score >= 3.0 else ("MEDIUM" if score >= 1.0 else "LOW")
                expl = {
                    "reason": f"Because you liked {anchor_movie.title}",
                    "matched_signals": signals[:4],
                    "confidence": confidence,
                    "anchor_movie": anchor_info,
                }
                movies_out.append(cls._format_movie(cand, explanation=expl))

        # Fallback if no anchor movie or candidates
        if len(movies_out) < max_per_shelf:
            remaining = max_per_shelf - len(movies_out)
            candidates = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids)
            fallback_items = candidates.order_by("-rating", "-vote_count", "-id")[:remaining]
            for m in fallback_items:
                seen_movie_ids.add(m.id)
                expl = {
                    "reason": "Editorial Selection: Critically acclaimed cinema",
                    "matched_signals": ["high_rating"],
                    "confidence": "COLD_START",
                }
                movies_out.append(cls._format_movie(m, explanation=expl))

        return movies_out, anchor_info

    # -------------------------------------------------------------------------
    # Shelf 3: Explore Your Genres
    # -------------------------------------------------------------------------
    @classmethod
    def _build_explore_your_genres(
        cls,
        user: Optional[Any],
        max_per_shelf: int,
        seen_movie_ids: Set[int],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Focuses on user's top 2 affinity genres from learned_weights['genres'].
        """
        top_2_genres: List[str] = []
        genre_weights: Dict[str, float] = {}

        if user and getattr(user, "is_authenticated", True):
            profile = UserTasteProfile.objects.filter(user=user).first()
            if profile and profile.learned_weights:
                raw_gw = profile.learned_weights.get("genres", {})
                if isinstance(raw_gw, dict):
                    genre_weights = {str(k): float(v) for k, v in raw_gw.items()}

        positive_genres = [(g, w) for g, w in genre_weights.items() if w > 0]
        positive_genres.sort(key=lambda x: x[1], reverse=True)
        top_2_genres = [g for g, _ in positive_genres[:2]]

        # Fallback to top catalogue genres if user has < 2 positive genres
        if len(top_2_genres) < 2:
            default_candidates = ["Drama", "Science Fiction", "Thriller", "Action", "Comedy"]
            for dg in default_candidates:
                if dg not in top_2_genres:
                    top_2_genres.append(dg)
                if len(top_2_genres) == 2:
                    break

        candidates = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids)

        # Match either by Genre M2M or TMDB genre IDs
        target_tmdb_ids = [
            tid for tid, name in TMDB_GENRE_MAP.items() if name in top_2_genres
        ]

        genre_q = Q(genres__name__in=top_2_genres)
        if target_tmdb_ids:
            genre_q |= Q(genres__tmdb_id__in=target_tmdb_ids)

        filtered_qs = candidates.filter(genre_q).distinct()
        candidates_list = list(filtered_qs.prefetch_related("genres")[:100])
        # If relational query yielded fewer than max_per_shelf (e.g. movies only have tmdb_genre_ids JSON list)
        if len(candidates_list) < max_per_shelf:
            existing_ids = {c.id for c in candidates_list}
            all_pool = list(candidates.exclude(id__in=existing_ids).prefetch_related("genres")[:200])
            for c in all_pool:
                c_genres = cls._get_movie_genres(c)
                if any(g in c_genres for g in top_2_genres):
                    candidates_list.append(c)

        scored: List[Tuple[float, List[str], Movie]] = []
        for cand in candidates_list:
            c_genres = cls._get_movie_genres(cand)
            matching = [g for g in top_2_genres if g in c_genres]
            affinity = sum(genre_weights.get(g, 1.0) for g in matching)
            quality = (cand.rating or 0.0) * 1.0 + (cand.vote_count or 0) * 0.0001
            score = affinity + quality
            scored.append((score, matching, cand))

        scored.sort(key=lambda x: x[0], reverse=True)

        movies_out: List[Dict[str, Any]] = []
        for score, matching, cand in scored[:max_per_shelf]:
            seen_movie_ids.add(cand.id)
            expl = {
                "reason": f"From your favorite genres: {', '.join(top_2_genres)}",
                "matched_signals": matching or top_2_genres,
                "confidence": "HIGH" if positive_genres else "COLD_START",
            }
            movies_out.append(cls._format_movie(cand, explanation=expl))

        # Fallback padding if needed
        if len(movies_out) < max_per_shelf:
            remaining = max_per_shelf - len(movies_out)
            fallback_items = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids).order_by(
                "-rating", "-vote_count", "-id"
            )[:remaining]
            for m in fallback_items:
                seen_movie_ids.add(m.id)
                expl = {
                    "reason": f"Popular selections in {', '.join(top_2_genres)}",
                    "matched_signals": top_2_genres,
                    "confidence": "COLD_START",
                }
                movies_out.append(cls._format_movie(m, explanation=expl))

        return movies_out, top_2_genres

    # -------------------------------------------------------------------------
    # Shelf 4: Explore By Era
    # -------------------------------------------------------------------------
    @classmethod
    def _build_explore_by_era(
        cls,
        user: Optional[Any],
        actor_ids: List[int],
        max_per_shelf: int,
        seen_movie_ids: Set[int],
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Focuses on user's preferred era (classic, 90s, 2000s, 2010s) based on
        positive interaction history.
        """
        era_scores: Dict[str, float] = {
            "classic": 0.0,
            "90s": 0.0,
            "2000s": 0.0,
            "2010s": 0.0,
        }

        if actor_ids:
            positive_logs = InteractionLog.objects.filter(
                user_id__in=actor_ids,
                weight__gt=0,
                movie__isnull=False,
            ).select_related("movie")

            for log in positive_logs:
                year = cls._get_movie_year(log.movie)
                if year is not None:
                    w = float(log.weight or 1.0)
                    if year <= 1989:
                        era_scores["classic"] += w
                    elif 1990 <= year <= 1999:
                        era_scores["90s"] += w
                    elif 2000 <= year <= 2009:
                        era_scores["2000s"] += w
                    elif 2010 <= year <= 2019:
                        era_scores["2010s"] += w
                    elif year >= 2020:
                        era_scores["2010s"] += w * 0.8  # blend recent into modern era

            positive_swipes = Swipe.objects.filter(
                user_id__in=actor_ids,
                reaction__in=[Swipe.SUPERLIKE, Swipe.LIKE],
                movie__isnull=False,
            ).select_related("movie")

            for swipe in positive_swipes:
                year = cls._get_movie_year(swipe.movie)
                if year is not None:
                    w = 3.0 if swipe.reaction == Swipe.SUPERLIKE else 1.0
                    if year <= 1989:
                        era_scores["classic"] += w
                    elif 1990 <= year <= 1999:
                        era_scores["90s"] += w
                    elif 2000 <= year <= 2009:
                        era_scores["2000s"] += w
                    elif 2010 <= year <= 2019:
                        era_scores["2010s"] += w
                    elif year >= 2020:
                        era_scores["2010s"] += w * 0.8

        # Determine preferred era
        sorted_eras = sorted(era_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_eras and sorted_eras[0][1] > 0.0:
            preferred_era = sorted_eras[0][0]
            confidence = "HIGH"
        else:
            # Check profile default_eras if set
            preferred_era = "90s"
            confidence = "COLD_START"
            if user and getattr(user, "is_authenticated", True):
                profile = UserTasteProfile.objects.filter(user=user).first()
                if profile and profile.default_eras:
                    for e in profile.default_eras:
                        if e in era_scores:
                            preferred_era = e
                            break

        era_info = ERA_BOUNDS.get(preferred_era, ERA_BOUNDS["90s"])
        candidates = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids)

        if "min_year" in era_info and "max_year" in era_info:
            candidates = candidates.filter(
                release_date__range=(
                    date(era_info["min_year"], 1, 1),
                    date(era_info["max_year"], 12, 31),
                )
            )
        elif "max_year" in era_info:
            candidates = candidates.filter(
                release_date__lte=date(era_info["max_year"], 12, 31)
            )
        elif "min_year" in era_info:
            candidates = candidates.filter(
                release_date__gte=date(era_info["min_year"], 1, 1)
            )

        selected = list(
            candidates.order_by("-rating", "-vote_count", "-id")[:max_per_shelf]
        )

        movies_out: List[Dict[str, Any]] = []
        for cand in selected:
            seen_movie_ids.add(cand.id)
            expl = {
                "reason": f"From your preferred era: {era_info['label']}",
                "matched_signals": [preferred_era],
                "confidence": confidence,
            }
            movies_out.append(cls._format_movie(cand, explanation=expl))

        # Fallback padding if candidate count was lower than max_per_shelf
        if len(movies_out) < max_per_shelf:
            remaining = max_per_shelf - len(movies_out)
            fallback_items = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids).order_by(
                "-rating", "-vote_count", "-id"
            )[:remaining]
            for m in fallback_items:
                seen_movie_ids.add(m.id)
                expl = {
                    "reason": f"Selection from {era_info['label']}",
                    "matched_signals": [preferred_era],
                    "confidence": "COLD_START",
                }
                movies_out.append(cls._format_movie(m, explanation=expl))

        return movies_out, preferred_era

    # -------------------------------------------------------------------------
    # Shelf 5: Outside Your Comfort Zone
    # -------------------------------------------------------------------------
    @classmethod
    def _build_outside_your_comfort_zone(
        cls,
        user: Optional[Any],
        actor_ids: List[int],
        max_per_shelf: int,
        seen_movie_ids: Set[int],
    ) -> List[Dict[str, Any]]:
        """
        Serendipity shelf: high quality (rating >= 7.0), zero previous user exposure,
        genres with neutral/limited exposure (not disliked).
        """
        disliked_genres: Set[str] = set()
        affinity_genres: Set[str] = set()

        if user and getattr(user, "is_authenticated", True):
            profile = UserTasteProfile.objects.filter(user=user).first()
            if profile and profile.learned_weights:
                gw = profile.learned_weights.get("genres", {})
                if isinstance(gw, dict):
                    for g, w in gw.items():
                        try:
                            fw = float(w)
                            if fw < 0:
                                disliked_genres.add(str(g))
                            elif fw >= 2.0:
                                affinity_genres.add(str(g))
                        except (ValueError, TypeError):
                            pass

        # Zero previous user exposure
        exposed_ids: Set[int] = set()
        if actor_ids:
            try:
                exp_qs = MovieExposure.objects.filter(user_id__in=actor_ids).values_list(
                    "movie_id", flat=True
                )
                exposed_ids.update(exp_qs)
            except Exception:
                try:
                    exp_qs = MovieExposure.objects.filter(user__in=actor_ids).values_list(
                        "movie_id", flat=True
                    )
                    exposed_ids.update(exp_qs)
                except Exception:
                    pass
            log_qs = InteractionLog.objects.filter(user_id__in=actor_ids).values_list(
                "movie_id", flat=True
            )
            exposed_ids.update(log_qs)
            swipe_qs = Swipe.objects.filter(user_id__in=actor_ids).values_list(
                "movie_id", flat=True
            )
            exposed_ids.update(swipe_qs)

        all_excluded = seen_movie_ids | exposed_ids
        candidates = cls._get_candidate_pool(exclude_movie_ids=all_excluded)

        # High quality constraint: rating >= 7.0 (fallback to >= 6.0 if limited catalogue)
        high_quality = candidates.filter(rating__gte=7.0)
        if high_quality.count() < max_per_shelf:
            high_quality = candidates.filter(rating__gte=6.0)

        # Filter out movies with disliked genres and prioritize fresh, unexposed genres
        candidates_list = list(high_quality.prefetch_related("genres")[:150])

        serendipity_scored: List[Tuple[float, List[str], Movie]] = []
        for cand in candidates_list:
            c_genres = cls._get_movie_genres(cand)
            # Exclude if it touches any disliked genre
            if c_genres.intersection(disliked_genres):
                continue

            # Serendipity score: bonus for genres outside top affinity
            serendipity_score = (cand.rating or 0.0) * 2.0 + (cand.vote_count or 0) * 0.001
            fresh_genres = [g for g in c_genres if g not in affinity_genres]
            if fresh_genres:
                serendipity_score += 3.0  # Fresh genre discovery bonus

            serendipity_scored.append((serendipity_score, fresh_genres or list(c_genres), cand))

        serendipity_scored.sort(key=lambda x: x[0], reverse=True)

        movies_out: List[Dict[str, Any]] = []
        for score, fresh_g, cand in serendipity_scored[:max_per_shelf]:
            seen_movie_ids.add(cand.id)
            expl = {
                "reason": "Outside your comfort zone: acclaimed cinema exploring fresh genres",
                "matched_signals": ["serendipity", "high_rating"] + fresh_g[:2],
                "confidence": "HIGH" if user and getattr(user, "is_authenticated", True) else "COLD_START",
            }
            movies_out.append(cls._format_movie(cand, explanation=expl))

        # Fallback padding if needed
        if len(movies_out) < max_per_shelf:
            remaining = max_per_shelf - len(movies_out)
            fallback_items = cls._get_candidate_pool(exclude_movie_ids=seen_movie_ids).order_by(
                "-rating", "-vote_count", "-id"
            )[:remaining]
            for m in fallback_items:
                seen_movie_ids.add(m.id)
                expl = {
                    "reason": "Acclaimed discovery outside familiar pathways",
                    "matched_signals": ["serendipity", "high_rating"],
                    "confidence": "COLD_START",
                }
                movies_out.append(cls._format_movie(m, explanation=expl))

        return movies_out

    # -------------------------------------------------------------------------
    # Master Entrypoint: get_archive_shelves
    # -------------------------------------------------------------------------
    @classmethod
    def get_archive_shelves(
        cls,
        user: Optional[Any],
        max_per_shelf: int = 8,
    ) -> Dict[str, Any]:
        """
        Generates 5 distinct, meaningful shelves:
        1. 'recommended_for_you'
        2. 'because_you_liked'
        3. 'explore_your_genres'
        4. 'explore_by_era'
        5. 'outside_your_comfort_zone'

        Ensures cross-shelf deduplication: each movie is unique across all shelves.
        """
        user = cls._resolve_user(user)
        actor_ids = cls._get_actor_ids(user)
        seen_movie_ids: Set[int] = set()

        # 1. Recommended For You
        rec_for_you = cls._build_recommended_for_you(
            user=user,
            max_per_shelf=max_per_shelf,
            seen_movie_ids=seen_movie_ids,
        )

        # 2. Because You Liked
        because_you_liked, anchor_info = cls._build_because_you_liked(
            user=user,
            actor_ids=actor_ids,
            max_per_shelf=max_per_shelf,
            seen_movie_ids=seen_movie_ids,
        )

        # 3. Explore Your Genres
        explore_genres, top_genres = cls._build_explore_your_genres(
            user=user,
            max_per_shelf=max_per_shelf,
            seen_movie_ids=seen_movie_ids,
        )

        # 4. Explore By Era
        explore_era, preferred_era = cls._build_explore_by_era(
            user=user,
            actor_ids=actor_ids,
            max_per_shelf=max_per_shelf,
            seen_movie_ids=seen_movie_ids,
        )

        # 5. Outside Your Comfort Zone
        comfort_zone = cls._build_outside_your_comfort_zone(
            user=user,
            actor_ids=actor_ids,
            max_per_shelf=max_per_shelf,
            seen_movie_ids=seen_movie_ids,
        )

        era_label = ERA_BOUNDS.get(preferred_era, {}).get("label", preferred_era)

        shelves_map: Dict[str, List[Dict[str, Any]]] = {
            "recommended_for_you": rec_for_you,
            "because_you_liked": because_you_liked,
            "explore_your_genres": explore_genres,
            "explore_by_era": explore_era,
            "outside_your_comfort_zone": comfort_zone,
        }

        shelves_details = {
            "recommended_for_you": {
                "title": "Recommended For You",
                "slug": "recommended_for_you",
                "description": "Personalized selections based on your taste profile",
                "movies": rec_for_you,
                "count": len(rec_for_you),
            },
            "because_you_liked": {
                "title": f"Because You Liked {anchor_info['title']}" if anchor_info else "Because You Liked",
                "slug": "because_you_liked",
                "description": (
                    f"Films sharing thematic and directorial resonance with {anchor_info['title']}"
                    if anchor_info
                    else "Films connected to your top reactions"
                ),
                "anchor_movie": anchor_info,
                "movies": because_you_liked,
                "count": len(because_you_liked),
            },
            "explore_your_genres": {
                "title": f"Explore {', '.join(top_genres)}" if top_genres else "Explore Your Genres",
                "slug": "explore_your_genres",
                "description": "Deeper cuts from your most affinity genres",
                "genres": top_genres,
                "movies": explore_genres,
                "count": len(explore_genres),
            },
            "explore_by_era": {
                "title": f"Explore {era_label}",
                "slug": "explore_by_era",
                "description": f"Curated cinema from the {era_label} era",
                "era": preferred_era,
                "movies": explore_era,
                "count": len(explore_era),
            },
            "outside_your_comfort_zone": {
                "title": "Outside Your Comfort Zone",
                "slug": "outside_your_comfort_zone",
                "description": "High-acclaim cinema from genres you haven't explored yet",
                "movies": comfort_zone,
                "count": len(comfort_zone),
            },
        }

        return {
            "user_id": user.id if user and getattr(user, "is_authenticated", True) else None,
            "shelves": shelves_map,
            "shelves_details": shelves_details,
            "recommended_for_you": rec_for_you,
            "because_you_liked": because_you_liked,
            "explore_your_genres": explore_genres,
            "explore_by_era": explore_era,
            "outside_your_comfort_zone": comfort_zone,
            "meta": {
                "anchor_movie": anchor_info,
                "top_genres": top_genres,
                "preferred_era": preferred_era,
                "total_shelves": 5,
                "total_unique_movies": len(seen_movie_ids),
            },
        }
