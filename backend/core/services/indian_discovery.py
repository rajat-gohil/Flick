"""
Indian-First Catalogue Discovery & Ingestion Strategy Service for Flick.

Product Principle:
Flick is an Indian movie discovery app. Its catalogue must meaningfully represent
Indian cinema across languages, regions, genres, and eras, rather than treating
Indian cinema as an addendum to international cinema.

Supported Language Priorities:
Primary Indian Languages:
  1. Hindi (hi)
  2. Gujarati (gu)
  3. Marathi (mr)
  4. Tamil (ta)
  5. Telugu (te)
  6. Malayalam (ml)
  7. Kannada (kn)
  8. Bengali (bn)

Secondary Indian Languages:
  9. Punjabi (pa)
  10. Assamese (as)
  11. Odia (or)
  12. Urdu (ur)

Coverage Targets:
- Total eligible Indian movies: >= 500
- Each primary Indian language: >= 40 eligible movies (Normal pool threshold)
- Major language x genre combinations: >= 16 where verified source data exists (Boutique pool threshold)
- Historical / era depth: Pre-1970 through 2020s
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from django.db.models import Count, Q

from core.constants.languages import ISO_639_1_CODES, validate_movie_language
from core.models import Genre, Movie
from core.services.tmdb import INDIAN_LANGUAGES, _ingest_tmdb_results, discover_movies

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL INDIAN CINEMA TAXONOMY & PRIORITIES
# ─────────────────────────────────────────────────────────────────────────────

PRIMARY_INDIAN_LANGUAGES: Dict[str, str] = {
    "hi": "Hindi",
    "gu": "Gujarati",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "ml": "Malayalam",
    "kn": "Kannada",
    "bn": "Bengali",
}

SECONDARY_INDIAN_LANGUAGES: Dict[str, str] = {
    "pa": "Punjabi",
    "as": "Assamese",
    "or": "Odia",
    "ur": "Urdu",
}

ALL_INDIAN_LANGUAGES: Dict[str, str] = {
    **PRIMARY_INDIAN_LANGUAGES,
    **SECONDARY_INDIAN_LANGUAGES,
}

# Coverage Targets (Architecture Section 2)
TARGET_ELIGIBLE_INDIAN_TOTAL = 500
TARGET_ELIGIBLE_PER_PRIMARY_LANG = 40
TARGET_ELIGIBLE_PER_LANG_GENRE = 16

# Canonical Era Definitions for Historical Depth
INDIAN_ERA_DEFINITIONS: Dict[str, Dict[str, Optional[str]]] = {
    "pre_1970": {"name": "Golden Age / Pre-1970", "max_date": "1969-12-31"},
    "1970s": {"name": "1970s Cinema", "min_date": "1970-01-01", "max_date": "1979-12-31"},
    "1980s": {"name": "1980s Cinema", "min_date": "1980-01-01", "max_date": "1989-12-31"},
    "1990s": {"name": "1990s Cinema", "min_date": "1990-01-01", "max_date": "1999-12-31"},
    "2000s": {"name": "2000s Millennium", "min_date": "2000-01-01", "max_date": "2009-12-31"},
    "2010s": {"name": "2010s Modern Era", "min_date": "2010-01-01", "max_date": "2019-12-31"},
    "2020s": {"name": "2020s Contemporary", "min_date": "2020-01-01"},
}

# Key Regional Genre Affinities (Ensures key cultural genres are not overlooked)
KEY_REGIONAL_GENRES: Dict[str, List[str]] = {
    "gu": ["Horror", "Thriller", "Comedy", "Drama", "Family"],
    "mr": ["Drama", "Comedy", "Family", "History"],
    "ml": ["Thriller", "Mystery", "Crime", "Drama"],
    "ta": ["Action", "Thriller", "Drama", "Science Fiction"],
    "te": ["Action", "Fantasy", "Drama", "Comedy"],
    "kn": ["Action", "Thriller", "Drama"],
    "bn": ["Drama", "Mystery", "Romance"],
    "hi": ["Drama", "Comedy", "Romance", "Action", "Thriller"],
}


@dataclass
class DiscoveryQuerySpec:
    """Specification for a targeted TMDB Indian cinema discovery query."""
    language: str
    language_name: str
    genre_id: Optional[int] = None
    genre_name: Optional[str] = None
    era: Optional[str] = None
    era_name: Optional[str] = None
    sort_by: str = "popularity.desc"
    vote_count_gte: int = 1
    page: int = 1
    priority: int = 50


@dataclass
class IndianCatalogueCoverageReport:
    """Evidence-backed coverage status of Indian cinema in local catalogue."""
    total_indian_movies: int
    eligible_indian_movies: int
    target_total: int
    is_total_satisfied: bool
    language_breakdown: Dict[str, Dict[str, Any]]
    shortfalls: List[str]


class IndianCatalogueDiscoveryService:
    """
    Reusable Indian-first catalogue discovery and ingestion strategy service.
    
    Adheres strictly to Flick's unified intelligence architecture:
    - Verifies actual original_language code (ISO 639-1).
    - Never uses production country as a substitute for original language.
    - Never promotes discovered items directly to tmdb_catalogue.
    - Routes candidates through durable CatalogueJob classification queue.
    - Protects manual_curated records and manual field overrides.
    """

    @classmethod
    def is_indian_language(cls, lang_code: Optional[str]) -> bool:
        """Check whether a language code belongs to supported Indian languages."""
        if not lang_code:
            return False
        return lang_code.strip().lower() in ALL_INDIAN_LANGUAGES

    @classmethod
    def get_language_name(cls, lang_code: Optional[str]) -> str:
        """Resolve human-readable name for an Indian language code."""
        if not lang_code:
            return "Unknown"
        return ALL_INDIAN_LANGUAGES.get(lang_code.strip().lower(), lang_code)

    @classmethod
    def get_adaptive_vote_count_threshold(
        cls,
        language: str,
        era: Optional[str] = None,
        sort_by: str = "popularity.desc",
    ) -> int:
        """
        Calculates an adaptive vote count threshold to prevent excluding valuable
        regional or classic Indian films that have low international vote density on TMDB.
        """
        lang = (language or "").strip().lower()
        era_str = str(era).lower() if era else ""

        # Pre-2000 classics: Vote count threshold = 1
        if era_str in ("pre_1970", "1970s", "1980s", "1990s", "before_1990", "classic"):
            return 1

        # Regional languages with lower TMDB coverage: Vote count threshold = 1 or 2
        if lang in ("gu", "mr", "as", "or", "pa", "kn", "bn", "ml", "ur"):
            return 1 if sort_by.startswith("primary_release_date") else 2

        # High-volume Indian commercial languages (Hindi, Tamil, Telugu):
        if lang in ("hi", "ta", "te"):
            return 5 if era_str == "2000s" else 10

        return 5

    @classmethod
    def execute_targeted_discovery(
        cls,
        language: str,
        genre_id: Optional[int] = None,
        era: Optional[str] = None,
        sort_by: str = "popularity.desc",
        vote_count_gte: Optional[int] = None,
        min_rating: Optional[float] = None,
        page: int = 1,
        auto_ingest: bool = True,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Executes a targeted TMDB discovery query for Indian cinema with regional safeguards.
        
        Safeguards:
        - Enforces valid ISO 639-1 language code.
        - Applies adaptive vote count threshold if not explicitly supplied.
        - Verifies that discovered candidates match target original language.
        - If auto_ingest=True, routes candidates through _ingest_tmdb_results,
          putting them in 'needs_review' and enqueuing durable classification jobs.
        
        Returns:
            Tuple[List[Dict[str, Any]], int]: (raw_results, ingested_count)
        """
        norm_lang = (language or "").strip().lower()
        if not cls.is_indian_language(norm_lang):
            valid, _ = validate_movie_language(norm_lang)
            if not valid:
                raise ValueError(f"Invalid language code: '{language}'")

        effective_vote_count = (
            vote_count_gte
            if vote_count_gte is not None
            else cls.get_adaptive_vote_count_threshold(norm_lang, era=era, sort_by=sort_by)
        )

        # Call TMDB discover endpoint via shared rate-limited client
        res, source = discover_movies(
            page=page,
            language=norm_lang,
            genre_id=genre_id,
            sort_by=sort_by,
            era=era,
            min_rating=min_rating,
            vote_count_gte=effective_vote_count,
        )

        results = res.get("results", []) if isinstance(res, dict) else []
        ingested_count = 0

        if results and auto_ingest:
            # Regional safeguard: Filter results to verify original_language matches target
            # Do NOT treat dubbed versions or country-of-origin mislabels as genuine regional films
            verified_results = []
            for item in results:
                item_lang = item.get("original_language")
                if item_lang == norm_lang:
                    verified_results.append(item)
                else:
                    logger.info(
                        f"Discovery language mismatch: target={norm_lang}, actual={item_lang} "
                        f"for '{item.get('title')}' (TMDB {item.get('id')}). Ingesting with actual language."
                    )
                    # Still ingest with its ACTUAL language, never re-tagging it falsely
                    verified_results.append(item)

            ingested_count = _ingest_tmdb_results(verified_results)

        return results, ingested_count

    @classmethod
    def get_indian_catalogue_coverage(cls) -> IndianCatalogueCoverageReport:
        """
        Generates an evidence-backed coverage analysis of Indian cinema in the local catalogue.
        Measures progress toward:
        - 500 total eligible Indian movies
        - 40 eligible movies per primary Indian language
        - 16 candidates per major language x genre combination
        """
        all_indian_movies = Movie.objects.filter(original_language__in=ALL_INDIAN_LANGUAGES.keys())
        total_indian_count = all_indian_movies.count()

        eligible_indian_movies = all_indian_movies.filter(display_ready=True, recommendable=True)
        eligible_indian_count = eligible_indian_movies.count()

        language_breakdown: Dict[str, Dict[str, Any]] = {}
        shortfalls: List[str] = []

        # Analyze each primary Indian language
        for lang_code, lang_name in PRIMARY_INDIAN_LANGUAGES.items():
            lang_qs = Movie.objects.filter(original_language=lang_code)
            all_c = lang_qs.count()
            rec_c = lang_qs.filter(display_ready=True, recommendable=True).count()

            # Genre breakdown for eligible movies
            genre_counts: Dict[str, int] = {}
            for g in Genre.objects.all():
                c = lang_qs.filter(display_ready=True, recommendable=True, genres=g).count()
                if c > 0:
                    genre_counts[g.name] = c

            status = "Normal Pool" if rec_c >= 40 else ("Boutique Pool" if rec_c >= 16 else "Exhausted")
            if rec_c < 40:
                shortfalls.append(
                    f"{lang_name} ({lang_code}): {rec_c} eligible / target 40 ({status})"
                )

            language_breakdown[lang_code] = {
                "name": lang_name,
                "tier": "Primary",
                "all_movies": all_c,
                "eligible_movies": rec_c,
                "target_eligible": TARGET_ELIGIBLE_PER_PRIMARY_LANG,
                "pool_status": status,
                "genre_breakdown": genre_counts,
            }

        # Analyze secondary Indian languages
        for lang_code, lang_name in SECONDARY_INDIAN_LANGUAGES.items():
            lang_qs = Movie.objects.filter(original_language=lang_code)
            all_c = lang_qs.count()
            rec_c = lang_qs.filter(display_ready=True, recommendable=True).count()

            language_breakdown[lang_code] = {
                "name": lang_name,
                "tier": "Secondary",
                "all_movies": all_c,
                "eligible_movies": rec_c,
                "target_eligible": 16,
                "pool_status": "Boutique Pool" if rec_c >= 16 else "Exhausted",
            }
            if rec_c == 0:
                shortfalls.append(f"{lang_name} ({lang_code}): 0 eligible records")

        if eligible_indian_count < TARGET_ELIGIBLE_INDIAN_TOTAL:
            shortfalls.insert(
                0,
                f"Total Eligible Indian Movies: {eligible_indian_count} / {TARGET_ELIGIBLE_INDIAN_TOTAL} target",
            )

        return IndianCatalogueCoverageReport(
            total_indian_movies=total_indian_count,
            eligible_indian_movies=eligible_indian_count,
            target_total=TARGET_ELIGIBLE_INDIAN_TOTAL,
            is_total_satisfied=(eligible_indian_count >= TARGET_ELIGIBLE_INDIAN_TOTAL),
            language_breakdown=language_breakdown,
            shortfalls=shortfalls,
        )

    @classmethod
    def generate_targeted_discovery_plan(
        cls,
        target_languages: Optional[List[str]] = None,
        max_pages_per_combo: int = 2,
    ) -> List[DiscoveryQuerySpec]:
        """
        Generates a deterministic, prioritized list of targeted discovery queries
        designed to systematically eliminate catalogue gaps across languages, genres, and eras.
        
        Does NOT execute queries; produces the specification plan for controlled execution.
        """
        languages_to_plan = target_languages or list(PRIMARY_INDIAN_LANGUAGES.keys())
        plan: List[DiscoveryQuerySpec] = []

        genres_map = {g.name: g.tmdb_id for g in Genre.objects.all() if g.tmdb_id}

        for lang in languages_to_plan:
            lang_name = cls.get_language_name(lang)
            key_genres = KEY_REGIONAL_GENRES.get(lang, ["Drama", "Comedy", "Thriller", "Action"])

            # 1. High-Priority Mainstream Discovery (Recent & Popular)
            for page in range(1, max_pages_per_combo + 1):
                plan.append(
                    DiscoveryQuerySpec(
                        language=lang,
                        language_name=lang_name,
                        sort_by="popularity.desc",
                        vote_count_gte=cls.get_adaptive_vote_count_threshold(lang, sort_by="popularity.desc"),
                        page=page,
                        priority=40,
                    )
                )

            # 2. Targeted Key Regional Genre Discovery
            for genre_name in key_genres:
                gid = genres_map.get(genre_name)
                if gid:
                    plan.append(
                        DiscoveryQuerySpec(
                            language=lang,
                            language_name=lang_name,
                            genre_id=gid,
                            genre_name=genre_name,
                            sort_by="vote_average.desc",
                            vote_count_gte=cls.get_adaptive_vote_count_threshold(lang, sort_by="vote_average.desc"),
                            page=1,
                            priority=50,
                        )
                    )

            # 3. Targeted Era Depth Discovery (Golden Age / 1970s / 1980s / 1990s)
            for era_code in ["pre_1970", "1970s", "1980s", "1990s", "2000s"]:
                era_name = INDIAN_ERA_DEFINITIONS[era_code]["name"]
                plan.append(
                    DiscoveryQuerySpec(
                        language=lang,
                        language_name=lang_name,
                        era=era_code,
                        era_name=era_name,
                        sort_by="vote_average.desc",
                        vote_count_gte=1,  # Adaptive vote threshold for classic eras
                        page=1,
                        priority=60,
                    )
                )

        return plan
