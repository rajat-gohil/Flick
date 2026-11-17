import copy
import hashlib
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, QuerySet

from core.models import (
    CollaborativeAgreement,
    Genre,
    InteractionLog,
    Match,
    Movie,
    MovieKeyword,
    MovieTag,
    Session,
    SessionOccasionState,
    Swipe,
    UserTasteProfile,
    WatchlistItem,
)
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    ScoringConfig,
    ScoringResult,
    UserPreferenceData,
)

# Type alias for clarity
ParticipantProfileData = UserPreferenceData
from core.services.tmdb import _ingest_tmdb_results, discover_movies

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Constants & Thresholds (Frozen Phase 0 Architecture v1.2.2)
# -------------------------------------------------------------------

POOL_THRESHOLD_NORMAL = 40
POOL_THRESHOLD_BOUTIQUE = 16
MAX_TMDB_REPLENISHMENT_PAGES = 3
TMDB_PAGE_SIZE = 20

# Canonical Era Boundaries
ERA_DEFINITIONS = {
    "before_1990": {"max_year": 1989},
    "pre_1990": {"max_year": 1989},
    "classic": {"max_year": 1989},
    "90s": {"min_year": 1990, "max_year": 1999},
    "2000s": {"min_year": 2000, "max_year": 2009},
    "2010s": {"min_year": 2010, "max_year": 2019},
    "recent": {"min_year": 2020},
}

# Section 13: Approved Sovereign National Cinemas outside US/UK Domestic Studio Ecosystem
APPROVED_INTERNATIONAL_CODES: Set[str] = {
    "AU", "CA", "IE", "NZ", "NG", "ZA", "IN", "JM",
    "FR", "DE", "IT", "ES", "JP", "KR", "CN", "DK",
    "SE", "NO", "MX", "BR", "AR", "IR", "PL", "IS",
    "BE", "NL", "AT", "CH", "PT", "GR", "CZ", "HU",
    "RO", "TR", "EG", "TW", "HK", "TH", "ID", "PH",
}

# Section 13: Validated Noir Keywords
VALIDATED_NOIR_KEYWORDS: Set[str] = {
    "femme_fatale",
    "femme fatale",
    "hardboiled",
    "hard-boiled",
    "cynical_detective",
    "cynical detective",
    "corrupt_cop",
    "corrupt cop",
    "neonoir",
    "neo-noir",
    "neo_noir",
    "private_investigator",
    "private investigator",
    "private_eye",
    "private eye",
    "film_noir",
    "film noir",
}

VALIDATED_NOIR_TAGS: Set[str] = {
    "film_noir_canon",
    "neo_noir",
    "film_noir",
    "noir_archive",
}


# -------------------------------------------------------------------
# Hard Constraints Data Structure
# -------------------------------------------------------------------

@dataclass
class HardConstraints:
    """
    Enforceable hard constraints contract.
    Hard constraints must NEVER be silently relaxed.
    Missing metadata is NEVER treated as satisfying an active constraint.
    """
    min_rating: Optional[float] = None
    max_runtime: Optional[int] = None
    eras: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    excluded_genre_ids: List[int] = field(default_factory=list)
    excluded_movie_ids: List[int] = field(default_factory=list)
    required_genre_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_agreement(cls, agreement: CollaborativeAgreement) -> "HardConstraints":
        """
        Builds HardConstraints from a CollaborativeAgreement (Tier C).
        Falls back to session fields if agreement fields have not yet materialized.
        """
        min_r = None
        if agreement.shared_min_rating is not None:
            min_r = float(agreement.shared_min_rating)

        exclusions = dict(agreement.mutual_hard_exclusions or {})
        excluded_genres = list(exclusions.get("excluded_genre_ids", []))
        excluded_movies = list(exclusions.get("excluded_movie_ids", []))
        required_genres = list(exclusions.get("required_genre_ids", []))

        langs = list(agreement.shared_languages or [])
        eras = list(agreement.shared_eras or [])

        # Fallback to session fields if agreement not fully populated
        session = getattr(agreement, "session", None)
        if session is not None:
            if not langs and session.selected_languages:
                langs = list(session.selected_languages)
            if not required_genres:
                if hasattr(session, "genres") and session.genres.exists():
                    required_genres = list(session.genres.values_list("tmdb_id", flat=True))
                elif getattr(session, "genre", None) and session.genre and session.genre.tmdb_id:
                    required_genres = [session.genre.tmdb_id]
            if not eras:
                h_era = (session.host_preferences or {}).get("era", [])
                g_era = (session.guest_preferences or {}).get("era", [])
                h_list = h_era if isinstance(h_era, list) else ([h_era] if h_era else [])
                g_list = g_era if isinstance(g_era, list) else ([g_era] if g_era else [])
                if h_list and g_list:
                    eras = [e for e in h_list if e in g_list] or (h_list + g_list)
                else:
                    eras = h_list or g_list

        return cls(
            min_rating=min_r,
            max_runtime=agreement.shared_max_runtime,
            eras=eras,
            languages=langs,
            excluded_genre_ids=excluded_genres,
            excluded_movie_ids=excluded_movies,
            required_genre_ids=required_genres,
        )

    @classmethod
    def from_taste_profile(cls, profile: UserTasteProfile) -> "HardConstraints":
        """
        Builds HardConstraints from a UserTasteProfile (Tier A persistent).
        """
        min_r = None
        if profile.default_min_rating is not None:
            min_r = float(profile.default_min_rating)

        exclusions = profile.hard_exclusions or {}
        excluded_genres = list(exclusions.get("excluded_genre_ids", []))
        excluded_movies = list(exclusions.get("excluded_movie_ids", []))
        required_genres = list(exclusions.get("required_genre_ids", []))

        return cls(
            min_rating=min_r,
            max_runtime=profile.default_max_runtime,
            eras=list(profile.default_eras or []),
            languages=list(profile.preferred_languages or []),
            excluded_genre_ids=excluded_genres,
            excluded_movie_ids=excluded_movies,
            required_genre_ids=required_genres,
        )

    @classmethod
    def from_occasion_state(cls, occasion_state: SessionOccasionState) -> "HardConstraints":
        """
        Synthesizes collaborative hard constraints from SessionOccasionState (Tier B).
        Applies:
        - Collaborative min_rating: Arithmetic average of explicit thresholds.
        - Runtime: min(host, guest) when both explicit.
        - Eras: Intersection of explicit era envelopes.
        - Exclusions: Union of host and guest vetoes.
        """
        host_occ = occasion_state.host_occasion or {}
        guest_occ = occasion_state.guest_occasion or {}

        host_b = host_occ.get("boundaries", {})
        guest_b = guest_occ.get("boundaries", {})

        # 1. Rating: Arithmetic average of explicit selections
        h_r = host_b.get("min_rating")
        g_r = guest_b.get("min_rating")
        min_rating = None
        if h_r is not None and g_r is not None:
            min_rating = round((float(h_r) + float(g_r)) / 2.0, 2)
        elif h_r is not None:
            min_rating = float(h_r)
        elif g_r is not None:
            min_rating = float(g_r)

        # 2. Runtime: Lower of explicit limits
        h_rt = host_b.get("max_runtime")
        g_rt = guest_b.get("max_runtime")
        max_runtime = None
        if h_rt is not None and g_rt is not None:
            max_runtime = min(int(h_rt), int(g_rt))
        elif h_rt is not None:
            max_runtime = int(h_rt)
        elif g_rt is not None:
            max_runtime = int(g_rt)

        # 3. Eras: Intersection of explicit envelopes
        h_eras = set(e for e in host_b.get("eras", []) if e != "any")
        g_eras = set(e for e in guest_b.get("eras", []) if e != "any")
        if h_eras and g_eras:
            common = list(h_eras.intersection(g_eras))
            eras = common if common else ["__CONTRADICTORY_EMPTY_ERA__"]
        elif h_eras:
            eras = list(h_eras)
        elif g_eras:
            eras = list(g_eras)
        else:
            eras = []

        # 4. Languages: Intersection if both specified, else union/fallback
        h_lang = set(host_b.get("languages", []))
        g_lang = set(guest_b.get("languages", []))
        if h_lang and g_lang:
            languages = list(h_lang.intersection(g_lang))
        elif h_lang:
            languages = list(h_lang)
        elif g_lang:
            languages = list(g_lang)
        else:
            languages = []

        # 5. Excluded Genres: Union of explicit vetoes
        h_ex_genres = set(host_b.get("excluded_genre_ids", []))
        g_ex_genres = set(guest_b.get("excluded_genre_ids", []))
        excluded_genre_ids = list(h_ex_genres.union(g_ex_genres))

        # 6. Excluded Movies: Union of explicit vetoes
        h_ex_movies = set(host_b.get("excluded_movie_ids", []))
        g_ex_movies = set(guest_b.get("excluded_movie_ids", []))
        excluded_movie_ids = list(h_ex_movies.union(g_ex_movies))

        # 7. Required Genres (e.g. Session genre choice)
        req_genres = []
        if host_occ.get("genre_id"):
            req_genres.append(int(host_occ["genre_id"]))
        if guest_occ.get("genre_id") and int(guest_occ["genre_id"]) not in req_genres:
            req_genres.append(int(guest_occ["genre_id"]))

        return cls(
            min_rating=min_rating,
            max_runtime=max_runtime,
            eras=eras,
            languages=languages,
            excluded_genre_ids=excluded_genre_ids,
            excluded_movie_ids=excluded_movie_ids,
            required_genre_ids=req_genres,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardConstraints":
        """Builds HardConstraints from a raw dictionary."""
        min_r = data.get("shared_min_rating", data.get("min_rating"))
        if min_r is not None:
            min_r = float(min_r)

        max_rt = data.get("shared_max_runtime", data.get("max_runtime"))
        if max_rt is not None:
            max_rt = int(max_rt)

        eras = list(data.get("shared_eras", data.get("eras", [])))
        languages = list(data.get("shared_languages", data.get("languages", [])))
        ex_genres = list(data.get("excluded_genre_ids", []))
        ex_movies = list(data.get("excluded_movie_ids", []))
        req_genres = list(data.get("shared_genres", data.get("required_genre_ids", [])))

        return cls(
            min_rating=min_r,
            max_runtime=max_rt,
            eras=eras,
            languages=languages,
            excluded_genre_ids=ex_genres,
            excluded_movie_ids=ex_movies,
            required_genre_ids=req_genres,
        )


# -------------------------------------------------------------------
# Candidate Pool Container
# -------------------------------------------------------------------

@dataclass
class CandidatePool:
    """
    Candidate pool container with strict categorization.
    - >= 40: Normal Pool (compiles 40-card manifest)
    - 16-39: Boutique Pool (compiles N-card manifest, shows curated badge)
    - < 16: Constraint Exhaustion (triggers dual-approval proposal protocol)
    """
    pool_type: str  # "normal" | "boutique" | "exhausted"
    candidates: List[Movie]
    total_count: int
    local_count: int
    replenished_count: int
    hard_constraints: HardConstraints
    experience_type: str
    proposal_required: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# -------------------------------------------------------------------
# Eligibility Policy Engine (Section 8)
# -------------------------------------------------------------------

class EligibilityPolicyEngine:
    """
    Enforces experience-specific candidate eligibility policies.
    """
    EXPERIENCE_SCREENING = "screening"
    EXPERIENCE_DISCOVERY = "discovery"
    EXPERIENCE_ARCHIVE = "archive"

    @classmethod
    def get_excluded_movie_ids(
        cls,
        session: Optional[Session] = None,
        experience_type: str = EXPERIENCE_SCREENING,
        custom_exclusions: Optional[List[int]] = None,
    ) -> Set[int]:
        """
        Determines the set of movie IDs that must be strictly excluded.
        
        Policies (Architecture Section 8):
        - Screening Deck: Movies swiped in the active session are strictly excluded.
          Movies matched in the active session are strictly excluded.
        - Individual Discovery: Swiped movies are eligible (personal browsing is unconstrained).
          Watchlist movies are eligible. Matched movies are eligible.
        - Cinema Archives: Permanent editorial collections remain 100% browseable
          regardless of session swipe history.
        """
        excluded: Set[int] = set()

        if custom_exclusions:
            excluded.update(custom_exclusions)

        if experience_type == cls.EXPERIENCE_SCREENING and session:
            # All swipes within this session (host or guest) are excluded
            swiped_ids = Swipe.objects.filter(session=session).values_list("movie_id", flat=True)
            excluded.update(swiped_ids)

            # Matches formed in this session are excluded
            matched_ids = Match.objects.filter(session=session).values_list("movie_id", flat=True)
            excluded.update(matched_ids)

        return excluded


# -------------------------------------------------------------------
# Hard Constraint Filter (Zero Silent Relaxation)
# -------------------------------------------------------------------

class HardConstraintFilter:
    """
    Evaluates candidates against strict shared hard constraints.
    Rule: Missing metadata is NEVER treated as satisfying an active constraint.
    """

    @staticmethod
    def satisfies_min_rating(movie: Any, min_rating: Optional[float]) -> bool:
        if min_rating is None:
            return True
        rating = getattr(movie, "rating", None)
        if rating is None:
            # Missing rating never satisfies active rating threshold
            return False
        return float(rating) >= float(min_rating)

    @staticmethod
    def satisfies_max_runtime(movie: Any, max_runtime: Optional[int]) -> bool:
        if max_runtime is None:
            return True
        runtime = getattr(movie, "runtime", None)
        if runtime is None:
            runtime = getattr(movie, "runtime_minutes", None)
        if runtime is None and hasattr(movie, "credits_summary") and isinstance(movie.credits_summary, dict):
            runtime = movie.credits_summary.get("runtime")
        if runtime is None or int(runtime) <= 0:
            # Missing runtime never satisfies active runtime limit
            return False
        return int(runtime) <= int(max_runtime)

    @staticmethod
    def satisfies_eras(movie: Any, eras: List[str]) -> bool:
        if not eras or "any" in eras:
            return True
        if "__CONTRADICTORY_EMPTY_ERA__" in eras:
            return False
        rel_date = getattr(movie, "release_date", None)
        if rel_date is None:
            # Missing release date never satisfies active era constraint
            return False

        year = rel_date.year if isinstance(rel_date, (date, datetime)) else None
        if year is None:
            try:
                year = int(str(rel_date)[:4])
            except (ValueError, TypeError):
                return False

        for era in eras:
            era_key = era.lower()
            if era_key in ("before_1990", "pre_1990", "classic"):
                if isinstance(rel_date, (date, datetime)):
                    if rel_date <= date(1989, 12, 31):
                        return True
                elif str(rel_date)[:10] <= "1989-12-31":
                    return True
                elif year is not None and year <= 1989:
                    return True
                continue

            bounds = ERA_DEFINITIONS.get(era_key)
            if not bounds:
                continue
            min_y = bounds.get("min_year", -math.inf)
            max_y = bounds.get("max_year", math.inf)
            if min_y <= year <= max_y:
                return True
        return False

    @staticmethod
    def satisfies_languages(movie: Any, languages: List[str]) -> bool:
        if not languages or "all" in languages:
            return True
        lang = getattr(movie, "original_language", None)
        if not lang:
            # Missing language never satisfies active language constraint
            return False
        allowed = {l.strip().lower() for l in languages if l}
        return lang.strip().lower() in allowed

    @staticmethod
    def satisfies_excluded_genres(movie: Any, excluded_genre_ids: List[int]) -> bool:
        if not excluded_genre_ids:
            return True
        ex_set = set(excluded_genre_ids)

        # Check raw tmdb_genre_ids on movie
        raw_ids = getattr(movie, "tmdb_genre_ids", []) or []
        if any(gid in ex_set for gid in raw_ids):
            return False

        # Check relational genres if present
        if hasattr(movie, "genres"):
            try:
                rel_ids = set(movie.genres.values_list("tmdb_id", flat=True))
                if rel_ids.intersection(ex_set):
                    return False
            except Exception:
                pass

        return True

    @staticmethod
    def satisfies_required_genres(movie: Any, required_genre_ids: List[int]) -> bool:
        if not required_genre_ids:
            return True
        req_set = set(required_genre_ids)

        raw_ids = getattr(movie, "tmdb_genre_ids", []) or []
        if any(gid in req_set for gid in raw_ids):
            return True

        if hasattr(movie, "genres"):
            try:
                rel_ids = set(movie.genres.values_list("tmdb_id", flat=True))
                if rel_ids.intersection(req_set):
                    return True
            except Exception:
                pass

        return False

    @classmethod
    def matches_all(cls, movie: Any, constraints: HardConstraints) -> bool:
        """
        Evaluates whether a candidate strictly satisfies all active hard constraints.
        """
        if not cls.satisfies_min_rating(movie, constraints.min_rating):
            return False
        if not cls.satisfies_max_runtime(movie, constraints.max_runtime):
            return False
        if not cls.satisfies_eras(movie, constraints.eras):
            return False
        if not cls.satisfies_languages(movie, constraints.languages):
            return False
        if not cls.satisfies_excluded_genres(movie, constraints.excluded_genre_ids):
            return False
        if not cls.satisfies_required_genres(movie, constraints.required_genre_ids):
            return False
        return True


# -------------------------------------------------------------------
# Defensible Editorial Classifiers (Section 13)
# -------------------------------------------------------------------

class WorldCinemaClassifier:
    """
    Authoritative 7-Case World Cinema Decision Table (Architecture Section 13).
    Classifies whether a movie qualifies for the World Cinema Vault.
    """

    @classmethod
    def classify(
        cls,
        original_language: Optional[str],
        production_countries: Optional[List[str]] = None,
        is_festival_laureate: bool = False,
        curation_tags: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """
        Returns (is_world_cinema: bool, classification_reason: str).
        """
        lang = (original_language or "").strip().lower()
        countries = [c.strip().upper() for c in (production_countries or [])]
        tags = {t.strip().lower() for t in (curation_tags or [])}

        # Case 1 & Case 5: Standard Non-English film (original_language != 'en')
        if lang and lang != "en":
            return True, "Case 1/5: Automatic qualification via non-English dialogue"

        # If English dialogue:
        if lang == "en":
            has_us_gb = any(c in {"US", "GB"} for c in countries)

            # Domestic Hollywood Anglophone Cinema: US/UK production without international co-production partner
            # Festival awards CANNOT qualify a domestic US/GB movie for World Cinema (Case 3)
            if has_us_gb:
                coproduction_tags = {"international_coproduction", "auteur_lead", "european_coproduction"}
                if tags.intersection(coproduction_tags):
                    return True, "Case 4: Verified international co-production with auteur lead"
                return False, "Case 3: Domestic Anglophone studio production (Festival award alone does not qualify domestic cinema)"

            # Case 2: Anglophone Non-US/UK Cinema (e.g. AU, IE, NG, ZA, IN)
            if countries and not has_us_gb:
                primary_country = countries[0]
                if primary_country in APPROVED_INTERNATIONAL_CODES:
                    return True, f"Case 2: Anglophone sovereign cinema ({primary_country})"

            # Case 7: International Festival Laureate for incomplete/sparse metadata films
            # (Incomplete TMDB data, but verified Cannes, Venice, Berlin, or FIPRESCI award)
            festival_awards = {"cannes", "venice", "berlin", "fipresci", "golden_bear", "palme_d_or", "golden_lion"}
            if is_festival_laureate and tags.intersection(festival_awards):
                if not countries:
                    return True, "Case 7: International Festival Laureate (supersedes incomplete country metadata)"

            # Case 6: Sparse English metadata (production_countries is empty and no verified festival award)
            if not countries:
                # Safe curatorial fallback: Never assumed domestic; unclassified awaiting editorial
                return False, "Case 6: Sparse English metadata (unclassified / awaiting editorial)"

            return False, "Case 3: Domestic Anglophone studio production"

        # Unspecified/missing language
        return False, "Unclassified: Missing language metadata"


class FilmNoirClassifier:
    """
    Film Noir Classification Pipeline (Architecture Section 13).
    Strictly independent of TMDB Mystery genre ID 9648.
    Requires verified editorial tags OR >= 2 validated noir keywords.
    """

    @classmethod
    def classify(
        cls,
        curation_tags: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        tags = {t.strip().lower() for t in (curation_tags or [])}
        kws = [k.strip().lower() for k in (keywords or [])]

        # Tier 1: Explicit Editorial Noir Tag
        if tags.intersection(VALIDATED_NOIR_TAGS):
            return True, "Tier 1: Explicit editorial noir canon tag"

        # Tier 2: Validated Noir Keyword Cluster (>= 2 validated keywords)
        matched_kws = [kw for kw in kws if kw in VALIDATED_NOIR_KEYWORDS]
        if len(matched_kws) >= 2:
            return True, f"Tier 2: Validated noir keyword cluster ({', '.join(matched_kws)})"

        return False, "Excluded: Missing noir aesthetic markers (raw Mystery 9648 alone is insufficient)"


# -------------------------------------------------------------------
# Candidate Metadata Normalization
# -------------------------------------------------------------------

def normalize_candidate_metadata(movie: Any) -> MovieIntelligenceData:
    """
    Normalizes candidate movie data into MovieIntelligenceData structure
    for direct consumption by IndividualRelevanceScorer.
    """
    return MovieIntelligenceData.from_movie(movie)


# -------------------------------------------------------------------
# Candidate Retrieval Service
# -------------------------------------------------------------------

class CandidateRetrievalService:
    """
    Common Candidate Retrieval Service with experience-specific filtering,
    strict hard constraint enforcement, and asynchronous TMDB replenishment.
    """

    @staticmethod
    def classify_pool(count: int) -> str:
        """
        Categorizes candidate pool size per Section 8:
        - >= 40: "normal"
        - 16-39: "boutique"
        - < 16: "exhausted"
        """
        if count >= POOL_THRESHOLD_NORMAL:
            return "normal"
        elif count >= POOL_THRESHOLD_BOUTIQUE:
            return "boutique"
        return "exhausted"

    @classmethod
    def resolve_constraints(
        cls,
        constraints: Optional[Union[Dict[str, Any], HardConstraints, CollaborativeAgreement, SessionOccasionState, UserTasteProfile]] = None,
        session: Optional[Session] = None,
        user: Optional[Any] = None,
    ) -> HardConstraints:
        """
        Resolves input constraints from agreement, occasion state, taste profile, dict, session, or user.
        """
        if isinstance(constraints, HardConstraints):
            return constraints
        if isinstance(constraints, CollaborativeAgreement):
            return HardConstraints.from_agreement(constraints)
        if isinstance(constraints, SessionOccasionState):
            return HardConstraints.from_occasion_state(constraints)
        if isinstance(constraints, UserTasteProfile):
            return HardConstraints.from_taste_profile(constraints)
        if isinstance(constraints, dict):
            return HardConstraints.from_dict(constraints)

        if session is not None:
            # Check attached collaborative agreement
            if hasattr(session, "collaborative_agreement"):
                try:
                    return HardConstraints.from_agreement(session.collaborative_agreement)
                except Exception:
                    pass
            # Check attached occasion state
            if hasattr(session, "occasion_state"):
                try:
                    return HardConstraints.from_occasion_state(session.occasion_state)
                except Exception:
                    pass

            # Fall back to session fields
            req_genres = []
            if getattr(session, "genres", None):
                req_genres = list(session.genres.values_list("tmdb_id", flat=True))
            elif getattr(session, "genre", None) and session.genre.tmdb_id:
                req_genres = [session.genre.tmdb_id]

            langs = list(getattr(session, "selected_languages", []) or [])
            return HardConstraints(
                languages=langs,
                required_genre_ids=req_genres,
            )

        # Fall back to User Tier A taste profile if user provided
        if user is not None and hasattr(user, "taste_profile"):
            try:
                return HardConstraints.from_taste_profile(user.taste_profile)
            except Exception:
                pass

        return HardConstraints()

    @classmethod
    def _query_local_candidates(
        cls,
        excluded_ids: Set[int],
        constraints: HardConstraints,
        archive_slug: Optional[str] = None,
    ) -> List[Movie]:
        """
        Queries and filters local database movies against hard constraints.
        """
        qs = Movie.objects.all().prefetch_related("genres", "keywords", "tags")

        # Exclude swiped/matched/custom IDs
        if excluded_ids:
            qs = qs.exclude(id__in=excluded_ids)

        # Database-level filtering for rating
        if constraints.min_rating is not None:
            qs = qs.filter(rating__isnull=False, rating__gte=constraints.min_rating)

        # Database-level filtering for languages
        if constraints.languages and "all" not in constraints.languages:
            qs = qs.filter(original_language__in=constraints.languages)

        # Database-level filtering for required genres
        if constraints.required_genre_ids:
            qs = qs.filter(genres__tmdb_id__in=constraints.required_genre_ids)

        # Evaluate queryset with distinct to avoid duplicate rows from M2M joins
        candidates = list(qs.distinct())

        # In-memory evaluation for constraints requiring multi-field/missing-metadata checks
        filtered: List[Movie] = []
        for m in candidates:
            if not HardConstraintFilter.matches_all(m, constraints):
                continue

            # Archives specific defensible classifications (Section 13)
            if archive_slug == "world-cinema":
                is_world, _ = WorldCinemaClassifier.classify(
                    original_language=m.original_language,
                    curation_tags=list(m.tags.values_list("name", flat=True)) if hasattr(m, "tags") else [],
                )
                if not is_world:
                    continue

            elif archive_slug == "film-noir":
                is_noir, _ = FilmNoirClassifier.classify(
                    curation_tags=list(m.tags.values_list("name", flat=True)) if hasattr(m, "tags") else [],
                    keywords=list(m.keywords.values_list("name", flat=True)) if hasattr(m, "keywords") else [],
                )
                if not is_noir:
                    continue

            filtered.append(m)

        # Deduplicate candidates deterministically by tmdb_id
        seen_tmdb: Set[int] = set()
        deduped: List[Movie] = []
        for m in filtered:
            if m.tmdb_id not in seen_tmdb:
                seen_tmdb.add(m.tmdb_id)
                deduped.append(m)

        return deduped

    @classmethod
    def _replenish_from_tmdb(
        cls,
        constraints: HardConstraints,
        max_pages: int = MAX_TMDB_REPLENISHMENT_PAGES,
        error_collector: Optional[List[str]] = None,
    ) -> int:
        """
        Fetches candidates from TMDB discover endpoint and ingests them into the database.
        MANDATORY RULE: HTTP calls execute OUTSIDE database transactions.
        """
        if not getattr(settings, "TMDB_API_KEY", None):
            logger.info("TMDB replenishment skipped: No API key configured.")
            return 0

        target_pages = min(max_pages, MAX_TMDB_REPLENISHMENT_PAGES)
        ingested_count = 0

        languages = constraints.languages or ["en"]
        genre_id = constraints.required_genre_ids[0] if constraints.required_genre_ids else None
        eras_to_query = constraints.eras[:2] if constraints.eras else [None]
        min_rating = constraints.min_rating

        # Concurrency Gate: Prevent duplicate parallel replenishment for identical criteria
        key_raw = f"{languages}:{genre_id}:{eras_to_query}:{min_rating}"
        cache_lock_key = f"tmdb_replenish_lock:{hashlib.md5(key_raw.encode()).hexdigest()}"
        lock_token = uuid.uuid4().hex
        if not cache.add(cache_lock_key, lock_token, timeout=30):
            logger.info("Concurrent TMDB replenishment already in progress for criteria; waiting for lock release.")
            # Concurrency resolution: Wait up to 3 seconds for active replenishment to complete
            for _ in range(6):
                time.sleep(0.5)
                if not cache.get(cache_lock_key):
                    break
            if cache.get(cache_lock_key):
                if error_collector is not None:
                    error_collector.append("replenishment_in_progress")
            return 0

        pages_per_query = max(1, target_pages // len(eras_to_query)) if len(eras_to_query) > 1 else target_pages

        try:
            for era in eras_to_query:
                for lang in languages[:2]:  # Limit replenishment queries to top 2 languages
                    for page in range(1, pages_per_query + 1):
                        try:
                            # External HTTP call outside database transaction
                            res, _ = discover_movies(
                                page=page,
                                language=lang,
                                genre_id=genre_id,
                                era=era,
                                min_rating=min_rating,
                            )
                            results = res.get("results", []) if isinstance(res, dict) else []
                            if results:
                                count = _ingest_tmdb_results(results)
                                ingested_count += count
                        except Exception as e:
                            logger.warning(f"TMDB candidate replenishment error (page={page}, lang={lang}, era={era}): {e}")
                            if error_collector is not None:
                                error_collector.append(str(e))
        finally:
            # Safe token-verified lock release to prevent releasing another worker's lock after timeout
            try:
                if cache.get(cache_lock_key) == lock_token:
                    cache.delete(cache_lock_key)
            except Exception:
                pass

        return ingested_count

    @classmethod
    def retrieve_candidates(
        cls,
        session: Optional[Session] = None,
        experience_type: str = EligibilityPolicyEngine.EXPERIENCE_SCREENING,
        constraints: Optional[Union[Dict[str, Any], HardConstraints, CollaborativeAgreement, SessionOccasionState, UserTasteProfile]] = None,
        user: Optional[Any] = None,
        max_tmdb_pages: int = MAX_TMDB_REPLENISHMENT_PAGES,
        auto_replenish: bool = True,
        archive_slug: Optional[str] = None,
        custom_exclusions: Optional[List[int]] = None,
    ) -> CandidatePool:
        """
        Executes the candidate retrieval pipeline:
        1. Resolves active shared hard constraints.
        2. Applies experience-specific eligibility policy.
        3. Queries local catalog with strict hard constraints.
        4. If local pool < 40 candidates and auto_replenish is enabled,
           triggers TMDB replenishment (strictly outside DB transactions, max 3 pages).
        5. Re-evaluates pool size and classifies into Normal, Boutique, or Exhausted.
        """
        resolved_constraints = cls.resolve_constraints(constraints=constraints, session=session, user=user)

        # Merge custom exclusions into constraints
        if custom_exclusions:
            resolved_constraints.excluded_movie_ids.extend(custom_exclusions)

        # Get excluded movie IDs for experience
        excluded_ids = EligibilityPolicyEngine.get_excluded_movie_ids(
            session=session,
            experience_type=experience_type,
            custom_exclusions=resolved_constraints.excluded_movie_ids,
        )

        # Query local database
        candidates = cls._query_local_candidates(
            excluded_ids=excluded_ids,
            constraints=resolved_constraints,
            archive_slug=archive_slug,
        )
        local_count = len(candidates)
        replenished_count = 0
        network_errors: List[str] = []

        # Check replenishment requirement
        if local_count < POOL_THRESHOLD_NORMAL and auto_replenish:
            replenished_count = cls._replenish_from_tmdb(
                constraints=resolved_constraints,
                max_pages=max_tmdb_pages,
                error_collector=network_errors,
            )
            # Re-query local catalog after replenishment
            candidates = cls._query_local_candidates(
                excluded_ids=excluded_ids,
                constraints=resolved_constraints,
                archive_slug=archive_slug,
            )

        total_count = len(candidates)
        pool_type = cls.classify_pool(total_count)
        proposal_required = (pool_type == "exhausted")

        metadata: Dict[str, Any] = {
            "session_id": session.id if session else None,
            "archive_slug": archive_slug,
            "auto_replenish": auto_replenish,
        }
        if "replenishment_in_progress" in network_errors:
            metadata["replenishment_in_progress"] = True
        elif network_errors:
            metadata["transient_error"] = True
            metadata["transient_error_message"] = f"TMDB replenishment temporary failure: {network_errors[0]}"

        return CandidatePool(
            pool_type=pool_type,
            candidates=candidates,
            total_count=total_count,
            local_count=local_count,
            replenished_count=replenished_count,
            hard_constraints=resolved_constraints,
            experience_type=experience_type,
            proposal_required=proposal_required,
            metadata=metadata,
        )


# -------------------------------------------------------------------
# Integration with IndividualRelevanceScorer
# -------------------------------------------------------------------

def compute_learned_feedback_from_logs(
    interaction_logs: List[Any],
    half_life_days: float = 60.0,
) -> float:
    """
    Computes accumulated learned feedback score from interaction logs with:
    1. Standard event weights (superlike=3.0, match=2.5, watchlist=2.0, like=1.0, modal=0.3, undo=0.0, dislike=-1.2).
    2. Duplicate event protection: Deduplicates by (session_id, movie_id, event_type), keeping latest event.
    3. Undo semantics: An undo event neutralizes previous swipe events for that movie.
    4. Half-life decay: 2 ** (-delta_t / 60.0).
    5. Strict clamping to [-15.0, +15.0].
    """
    if not interaction_logs:
        return 0.0

    signal_weights = {
        "superlike": 3.0,
        "match": 2.5,
        "watchlist_add": 2.0,
        "swipe_like": 1.0,
        "modal_open": 0.3,
        "undo": 0.0,
        "swipe_dislike": -1.2,
    }

    # Sort logs by created_at ascending so latest events overwrite earlier duplicates
    now = datetime.now()

    # Deduplicate events: key = (session_id, movie_id, event_type)
    deduped_events: Dict[Tuple[Optional[int], int, str], Tuple[float, float]] = {}  # key -> (weight, delta_days)
    undone_session_movies: Set[Tuple[Optional[int], int]] = set()

    for log in interaction_logs:
        movie_id = getattr(log, "movie_id", None)
        session_id = getattr(log, "session_id", None)
        event_type = getattr(log, "event_type", "")
        created_at = getattr(log, "created_at", None)

        if not movie_id:
            continue

        if event_type == "undo":
            undone_session_movies.add((session_id, movie_id))
            continue

        weight = getattr(log, "weight", None)
        if weight is None or float(weight) == 0.0:
            weight = getattr(log, "event_weight", None)
        if weight is None or float(weight) == 0.0:
            weight = signal_weights.get(event_type, 0.0)

        delta_days = 0.0
        if created_at:
            if hasattr(created_at, "date"):
                dt = (now.date() - created_at.date()).days
                delta_days = max(0.0, float(dt))

        deduped_events[(session_id, movie_id, event_type)] = (float(weight), delta_days)

    # Filter out undone swipe events ONLY for the session where the undo occurred
    valid_events: List[Tuple[float, float]] = []
    for (sess_id, m_id, ev_type), (w, delta_t) in deduped_events.items():
        if (sess_id, m_id) in undone_session_movies and ev_type in {"swipe_like", "swipe_dislike", "superlike"}:
            continue
        valid_events.append((w, delta_t))

    total = 0.0
    for w, delta_t in valid_events:
        decay = 2.0 ** (-delta_t / half_life_days)
        total += w * decay

    return min(15.0, max(-15.0, total))


def rank_candidates_for_user(
    candidates: List[Movie],
    profile_data: ParticipantProfileData,
    scorer: Optional[IndividualRelevanceScorer] = None,
    interaction_logs: Optional[List[Any]] = None,
) -> List[Tuple[Movie, ScoringResult]]:
    """
    Ranks candidates for an individual participant using IndividualRelevanceScorer.
    Returns list of (Movie, ScoringResult) sorted by R_norm descending,
    with deterministic secondary tie-breaking on (vote_average, vote_count, tmdb_id).
    """
    if scorer is None:
        scorer = IndividualRelevanceScorer()

    # Copy preferences and apply learned feedback if computed
    user_prefs = profile_data
    if interaction_logs:
        feedback_score = compute_learned_feedback_from_logs(interaction_logs)
        user_prefs = UserPreferenceData(
            moods=list(profile_data.moods),
            narrative=list(profile_data.narrative),
            themes=list(profile_data.themes),
            experience=profile_data.experience,
            unswiped_impressions=list(profile_data.unswiped_impressions),
            learned_feedback_events=list(profile_data.learned_feedback_events),
            direct_learned_score=feedback_score,
        )

    scored_candidates: List[Tuple[Movie, ScoringResult]] = []

    for movie in candidates:
        m_intel = MovieIntelligenceData.from_movie(movie)
        result = scorer.score(
            movie=m_intel,
            preferences=user_prefs,
        )
        scored_candidates.append((movie, result))

    # Deterministic sort: normalized score desc, vote_average desc, vote_count desc, tmdb_id desc
    scored_candidates.sort(
        key=lambda item: (
            item[1].normalized_relevance,
            float(getattr(item[0], "rating", 0.0) or 0.0),
            int(getattr(item[0], "vote_count", 0) or 0),
            int(getattr(item[0], "tmdb_id", 0) or 0),
        ),
        reverse=True,
    )

    return scored_candidates
