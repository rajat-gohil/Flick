"""
Curator's Double Feature Service.

Orchestrates daily editorial art-house cinema pairings and personalized double features
grounded in authentic user taste signals and catalog metadata.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db import models
from django.contrib.auth.models import User

from core.models import (
    GuestProfile,
    InteractionLog,
    Movie,
    MovieStreamingAvailability,
    StreamingProvider,
    Swipe,
    UserTasteProfile,
    WatchlistItem,
)
from core.serializers import MovieSerializer
from core.services.archive_shelves import TMDB_GENRE_MAP
from core.services.guest_cleanup import is_taste_profile_customized
from core.services.recommendation_engine import PersonalizedRecommendationEngine

logger = logging.getLogger(__name__)

# 7 Verified Local Catalog Pairings (all 14 movie IDs confirmed present in local database)
EDITORIAL_CATALOGUE: List[Dict[str, Any]] = [
    {
        "day_index": 0,
        "theme": "Neo-Noir & Investigation",
        "curator_note": (
            "Two procedural masterclasses from David Fincher exploring the psychological toll, "
            "obsessive pursuit, and harrowing moral dread of hunting an elusive killer."
        ),
        "film_1_id": 799,  # Zodiac (2007)
        "film_2_id": 366,  # Se7en (1995)
    },
    {
        "day_index": 1,
        "theme": "Cosmic Odysseys & Speculative Worlds",
        "curator_note": (
            "Two visionary science-fiction epics that explore survival against hostile environments, "
            "the burden of destiny, and humanity's reach beyond known horizons."
        ),
        "film_1_id": 42,   # Interstellar (2014)
        "film_2_id": 47,   # Dune: Part Two (2024)
    },
    {
        "day_index": 2,
        "theme": "Unspoken Longing & Enduring Devotion",
        "curator_note": (
            "Two landmark Indian romances capturing the bittersweet resonance of school-day memories "
            "and the enduring devotion of a love that transcends boundaries."
        ),
        "film_1_id": 156,  # 96 (2018)
        "film_2_id": 66,   # Dilwale Dulhania Le Jayenge (1995)
    },
    {
        "day_index": 3,
        "theme": "Auteur Rebellion & Stylized Transgression",
        "curator_note": (
            "Two subversive cinema milestones by singular directors who fractured narrative convention, "
            "stylized moral ambiguity, and challenged censorship norms."
        ),
        "film_1_id": 270,  # Pulp Fiction (1994)
        "film_2_id": 812,  # A Clockwork Orange (1971)
    },
    {
        "day_index": 4,
        "theme": "Courtroom & Neo-Noir Suspense",
        "curator_note": (
            "Two precision-crafted mystery thrillers where sharp intellects navigate deceptive testimonies, "
            "hidden motives, and cynical corruption."
        ),
        "film_1_id": 824,  # Witness for the Prosecution (1957)
        "film_2_id": 823,  # Chinatown (1974)
    },
    {
        "day_index": 5,
        "theme": "Deception & Fractured Identity",
        "curator_note": (
            "Two high-velocity thrillers driven by double lives, psychological espionage, "
            "and the perilous unraveling of reality under intense pressure."
        ),
        "film_1_id": 881,  # Inception (2010)
        "film_2_id": 791,  # The Departed (2006)
    },
    {
        "day_index": 6,
        "theme": "Human Resilience & Fortitude",
        "curator_note": (
            "Two timeless 1994 classics that examine the endurance of the human spirit—one through patience "
            "in adversity, the other through unwavering earnestness."
        ),
        "film_1_id": 60,   # The Shawshank Redemption (1994)
        "film_2_id": 268,  # Forrest Gump (1994)
    },
]


class DoubleFeatureService:
    """
    Provides the Curator's Double Feature according to the 5-tier eligibility model.
    """

    @classmethod
    def get_current_day_index(cls, current_dt: Optional[datetime] = None) -> int:
        """
        Calculates the continuous ordinal day index in UTC.
        Formula: datetime.now(timezone.utc).date().toordinal() % 7
        """
        dt = current_dt or datetime.now(timezone.utc)
        return dt.date().toordinal() % len(EDITORIAL_CATALOGUE)

    @classmethod
    def is_user_established(cls, user: Optional[User]) -> Tuple[bool, str]:
        """
        Evaluates user eligibility for personalized double features.
        Returns (is_established: bool, reason: str).

        Tiers:
        - None or AnonymousUser: False ('unauthenticated')
        - Active unclaimed guest: False ('unclaimed_guest')
        - User with < 3 distinct movie interactions and default profile: False ('no_signals')
        - Established user with customized profile or >= 3 distinct interactions: True ('established')
        """
        if not user or not getattr(user, "is_authenticated", False):
            return False, "unauthenticated"

        # Check for active unclaimed guest account
        # Distinguish claimed/converted accounts (is_claimed=True) from active guests (is_claimed=False)
        is_unclaimed_guest = GuestProfile.objects.filter(user=user, is_claimed=False).exists()
        if is_unclaimed_guest:
            return False, "unclaimed_guest"

        # Check explicit customized taste profile
        taste_profile = UserTasteProfile.objects.filter(user=user).first()
        has_custom_profile = is_taste_profile_customized(taste_profile)

        # Count distinct interacted movie IDs across InteractionLog, Swipe, and Watchlist
        # to prevent double-counting activities for the same movie
        interacted_movie_ids: Set[int] = set()

        try:
            log_ids = InteractionLog.objects.filter(user=user).exclude(movie_id__isnull=True).values_list("movie_id", flat=True)
            interacted_movie_ids.update(log_ids)
        except Exception as e:
            logger.debug("Error fetching interaction logs for user %s: %s", user.id, e)

        try:
            swipe_ids = Swipe.objects.filter(user=user).exclude(movie_id__isnull=True).values_list("movie_id", flat=True)
            interacted_movie_ids.update(swipe_ids)
        except Exception as e:
            logger.debug("Error fetching swipes for user %s: %s", user.id, e)

        try:
            watchlist_ids = WatchlistItem.objects.filter(user=user).exclude(movie_id__isnull=True).values_list("movie_id", flat=True)
            interacted_movie_ids.update(watchlist_ids)
        except Exception as e:
            logger.debug("Error fetching watchlist for user %s: %s", user.id, e)

        distinct_interactions_count = len(interacted_movie_ids)

        if distinct_interactions_count >= 3 or has_custom_profile:
            return True, "established"

        return False, "no_signals"

    @classmethod
    def get_double_feature(
        cls,
        user: Optional[User] = None,
        region: str = "IN",
        current_dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrates retrieval of the double feature.
        Attempts personalized selection if user qualifies; falls back gracefully
        to the deterministic daily editorial pairing.
        """
        norm_region = cls._normalize_region(region)

        # 1. Evaluate user eligibility
        is_established, reason = cls.is_user_established(user)

        # 2. If established, attempt personalized pairing
        if is_established and user:
            try:
                personalized_data = cls._get_personalized_pair(user, norm_region)
                if personalized_data:
                    return personalized_data
                logger.info("Personalized candidate shortage for user %s; falling back to daily editorial.", user.id)
            except Exception as e:
                logger.warning("Personalized pair generation failed for user %s: %s; falling back to daily editorial.", user.id, e)

        # 3. Serve deterministic daily editorial fallback
        return cls._get_daily_editorial_pair(norm_region, current_dt=current_dt)

    @classmethod
    def _normalize_region(cls, region: Optional[str]) -> str:
        """Validates and normalizes 2-letter uppercase ISO country code."""
        if not region or not isinstance(region, str):
            return "IN"
        cleaned = region.strip().upper()
        if len(cleaned) == 2 and cleaned.isalpha():
            return cleaned
        return "IN"

    @classmethod
    def _get_daily_editorial_pair(
        cls,
        region: str,
        current_dt: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves the deterministic daily editorial pairing for the given UTC date.
        """
        day_index = cls.get_current_day_index(current_dt)
        entry = EDITORIAL_CATALOGUE[day_index]

        movie_1 = Movie.objects.filter(id=entry["film_1_id"]).first()
        movie_2 = Movie.objects.filter(id=entry["film_2_id"]).first()

        # Resilient fallback if any catalog record was deleted or unavailable
        if not movie_1 or not movie_2:
            logger.error("Editorial catalogue missing movie records for day %s", day_index)
            # Find any two top-rated movies in local DB
            candidates = list(Movie.objects.filter(poster_path__isnull=False, rating__gte=7.0).order_by("-rating")[:2])
            if len(candidates) == 2:
                movie_1, movie_2 = candidates[0], candidates[1]
            else:
                return {
                    "success": False,
                    "error": "Insufficient movies available in database",
                }

        film_1_data = cls._serialize_movie(movie_1, region)
        film_2_data = cls._serialize_movie(movie_2, region)

        return {
            "success": True,
            "source": "daily_editorial",
            "is_personalized": False,
            "theme": entry["theme"],
            "curator_note": entry["curator_note"],
            "total_runtime_minutes": None,  # Movie model has no runtime field; do not fabricate
            "film_1": film_1_data,
            "film_2": film_2_data,
        }

    @classmethod
    def _get_personalized_pair(cls, user: User, region: str) -> Optional[Dict[str, Any]]:
        """
        Selects two complementary high-scoring films from PersonalizedRecommendationEngine.
        """
        rec_result = PersonalizedRecommendationEngine.get_recommendations(
            user=user,
            limit=30,
            min_quality=6.8,
            apply_diversity=False,
        )

        candidates = rec_result.get("movies", [])
        if len(candidates) < 2:
            return None

        # Filter candidates: must have valid ID, poster, and rating >= 7.0
        valid_candidates = []
        for c in candidates:
            # Handle dict or Movie instance
            m_id = c.get("id") if isinstance(c, dict) else getattr(c, "id", None)
            if not m_id:
                continue
            movie_obj = Movie.objects.filter(id=m_id).first()
            if not movie_obj or not movie_obj.poster_path:
                continue
            rating = float(getattr(movie_obj, "rating", 0.0) or 0.0)
            if rating < 7.0:
                continue
            valid_candidates.append(movie_obj)

        if len(valid_candidates) < 2:
            return None

        # Find best complementary pair sharing a genre or theme
        best_pair: Optional[Tuple[Movie, Movie, str, str]] = None
        best_score = -1.0

        for i in range(len(valid_candidates)):
            for j in range(i + 1, len(valid_candidates)):
                m1 = valid_candidates[i]
                m2 = valid_candidates[j]
                if m1.id == m2.id:
                    continue

                # Compute genre overlap
                g1 = set(m1.genres.values_list("name", flat=True))
                g2 = set(m2.genres.values_list("name", flat=True))
                overlap = g1 & g2

                if not overlap:
                    # Check TMDB genre IDs if local genres empty
                    tg1 = set(m1.tmdb_genre_ids or [])
                    tg2 = set(m2.tmdb_genre_ids or [])
                    tmdb_overlap = tg1 & tg2
                    if tmdb_overlap:
                        overlap = {TMDB_GENRE_MAP[gid] for gid in tmdb_overlap if gid in TMDB_GENRE_MAP}

                if not overlap:
                    continue

                shared_genre = sorted(list(overlap))[0]
                r1 = float(m1.rating or 7.0)
                r2 = float(m2.rating or 7.0)
                pair_score = r1 + r2

                if pair_score > best_score:
                    best_score = pair_score
                    theme = f"Explorations in {shared_genre}"
                    note = (
                        f"Screened together as complementary studies in {shared_genre.lower()}, "
                        f"connected by atmospheric storytelling and compelling character focus."
                    )
                    best_pair = (m1, m2, theme, note)

        if not best_pair:
            return None

        m1, m2, theme, note = best_pair

        confidence = rec_result.get("confidence", "HIGH")
        if confidence not in ("HIGH", "MEDIUM"):
            confidence = "MEDIUM"

        return {
            "success": True,
            "source": "personalized",
            "is_personalized": True,
            "confidence": confidence,
            "theme": theme,
            "curator_note": note,
            "total_runtime_minutes": None,
            "film_1": cls._serialize_movie(m1, region),
            "film_2": cls._serialize_movie(m2, region),
        }

    @classmethod
    def _serialize_movie(cls, movie: Movie, region: str) -> Dict[str, Any]:
        """
        Serializes a movie using MovieSerializer and appends verified genres
        and local/regional streaming providers.
        """
        data = MovieSerializer(movie).data

        # Populate genres list
        genres = [g.name for g in movie.genres.all() if g.name]
        if not genres and movie.tmdb_genre_ids:
            genres = [TMDB_GENRE_MAP[gid] for gid in movie.tmdb_genre_ids if gid in TMDB_GENRE_MAP]
        data["genres"] = genres

        # Resolve regional streaming availability
        streaming_providers = []
        try:
            availabilities = MovieStreamingAvailability.objects.filter(
                movie=movie,
                provider__country_code=region,
                provider__is_active=True,
            ).select_related("provider")

            for avail in availabilities:
                streaming_providers.append({
                    "id": avail.provider.id,
                    "name": avail.provider.name,
                    "logo_url": avail.provider.logo_url,
                    "type": avail.monetization_type or "flatrate",
                    "url": avail.url or avail.provider.website_url,
                })
        except Exception as e:
            logger.debug("Error serializing streaming availability for movie %s: %s", movie.id, e)

        data["streaming_providers"] = streaming_providers
        return data
