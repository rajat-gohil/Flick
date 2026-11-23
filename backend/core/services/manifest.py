import copy
import logging
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

from django.conf import settings
from django.db import transaction

from core.models import (
    CollaborativeAgreement,
    InteractionLog,
    Movie,
    Session,
    SessionOccasionState,
    UserTasteProfile,
)
from core.services.retrieval import (
    CandidatePool,
    CandidateRetrievalService,
    compute_learned_feedback_from_logs,
)
from core.services.affinity import normalize_user_preferences
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    ScoringConfig,
    ScoringResult,
    UserPreferenceData,
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# Constants & Cadence (Phase 0 Architecture v1.2.2 Section 10)
# -------------------------------------------------------------------

NORMAL_MANIFEST_SIZE = 40
NORMAL_CONSENSUS_COUNT = 16
NORMAL_HOST_COUNT = 12
NORMAL_GUEST_COUNT = 12

MIN_BOUTIQUE_POOL_SIZE = 16
MAX_BOUTIQUE_POOL_SIZE = 39

# 10-Card Approved Cadence: [C, H, G, C, H, G, C, C, H, G]
CADENCE_10_CARD: List[str] = [
    "consensus",
    "host_priority",
    "guest_priority",
    "consensus",
    "host_priority",
    "guest_priority",
    "consensus",
    "consensus",
    "host_priority",
    "guest_priority",
]

# Relevance floor protection thresholds (Architecture Section 10 — Centrally Configurable Provisional Defaults)
DEFAULT_RELEVANCE_FLOOR_GUEST = getattr(settings, "GUEST_RELEVANCE_FLOOR", 0.30)
DEFAULT_RELEVANCE_FLOOR_HOST = getattr(settings, "HOST_RELEVANCE_FLOOR", 0.30)


# -------------------------------------------------------------------
# Custom Exceptions
# -------------------------------------------------------------------

class ManifestCompilationError(Exception):
    """Base exception for deck manifest compilation errors."""
    pass


class InsufficientCandidatesError(ManifestCompilationError):
    """Raised when eligible candidate pool is under 16 (Constraint Exhaustion)."""
    pass


class TransientReplenishmentError(ManifestCompilationError):
    """Raised when candidate replenishment fails due to temporary network or TMDB connection errors."""
    pass


class ReplenishmentInProgressError(ManifestCompilationError):
    """Raised when candidate replenishment is actively in progress for matching criteria."""
    pass


class ActiveManifestImmutableError(ManifestCompilationError):
    """Raised when attempting to overwrite an active, in-progress deck manifest."""
    pass


# -------------------------------------------------------------------
# Scored Candidate Container
# -------------------------------------------------------------------

@dataclass
class ScoredCandidate:
    """
    Represents a candidate movie with individual participant relevance
    scores and geometric mean consensus score.
    """
    movie: Movie
    movie_id: int
    tmdb_id: int
    title: str
    relevance_host: float
    relevance_guest: float
    consensus_score: float
    scoring_result_host: ScoringResult
    scoring_result_guest: ScoringResult


# -------------------------------------------------------------------
# Collaborative Deck Scorer
# -------------------------------------------------------------------

class CollaborativeDeckScorer:
    """
    Scores candidates for paired screening sessions:
    - Calculates IndividualRelevanceScorer scores for Host and Guest.
    - Computes consensus score via geometric mean: sqrt(Rel_Host * Rel_Guest).
    - Guaranteed real, non-negative, and bounded in [0.0, 1.0].
    """

    def __init__(self, scorer: Optional[IndividualRelevanceScorer] = None):
        self.scorer = scorer or IndividualRelevanceScorer()

    def score_candidate(
        self,
        movie: Movie,
        host_prefs: UserPreferenceData,
        guest_prefs: UserPreferenceData,
    ) -> ScoredCandidate:
        m_intel = MovieIntelligenceData.from_movie(movie)

        res_host = self.scorer.score(movie=m_intel, preferences=host_prefs)
        res_guest = self.scorer.score(movie=m_intel, preferences=guest_prefs)

        rel_host = max(0.0, min(1.0, float(res_host.normalized_relevance)))
        rel_guest = max(0.0, min(1.0, float(res_guest.normalized_relevance)))

        # Geometric Mean: Consensus(M) = sqrt(Rel_Host * Rel_Guest)
        consensus = math.sqrt(rel_host * rel_guest)
        consensus = max(0.0, min(1.0, consensus))

        return ScoredCandidate(
            movie=movie,
            movie_id=movie.id,
            tmdb_id=movie.tmdb_id,
            title=movie.title,
            relevance_host=rel_host,
            relevance_guest=rel_guest,
            consensus_score=consensus,
            scoring_result_host=res_host,
            scoring_result_guest=res_guest,
        )

    def score_candidate_pool(
        self,
        candidates: List[Movie],
        host_prefs: UserPreferenceData,
        guest_prefs: UserPreferenceData,
    ) -> List[ScoredCandidate]:
        return [
            self.score_candidate(movie=m, host_prefs=host_prefs, guest_prefs=guest_prefs)
            for m in candidates
        ]


# -------------------------------------------------------------------
# Hamilton Manifest Allocator (Architecture Section 10)
# -------------------------------------------------------------------

class HamiltonManifestAllocator:
    """
    Implements Hamilton's largest-remainder method for 40/30/30 seat allocation
    with deterministic tie-breaking (Consensus > Host Priority > Guest Priority)
    and category shortage redistribution.
    """

    @classmethod
    def calculate_allocation(cls, pool_size: int) -> Dict[str, int]:
        """
        Calculates exact category seat counts for a pool of N candidates (16 <= N <= 39).
        Exact seat quotas:
        - Q_C = 0.40 * N
        - Q_H = 0.30 * N
        - Q_G = 0.30 * N
        Floor seats: I_C = floor(Q_C), I_H = floor(Q_H), I_G = floor(Q_G).
        Remaining R seats distributed to highest fractional remainders.
        Tie-breaking: C > H > G.
        """
        if pool_size < MIN_BOUTIQUE_POOL_SIZE:
            raise InsufficientCandidatesError(
                f"Candidate pool size {pool_size} is under minimum threshold {MIN_BOUTIQUE_POOL_SIZE}."
            )

        n = float(pool_size)
        q_c = 0.40 * n
        q_h = 0.30 * n
        q_g = 0.30 * n

        i_c = int(math.floor(q_c))
        i_h = int(math.floor(q_h))
        i_g = int(math.floor(q_g))

        allocated = i_c + i_h + i_g
        remainder = pool_size - allocated

        # Fractional remainders with priority tie-breaker (lower tuple value wins)
        # Priority: Consensus (0) > Host (1) > Guest (2)
        fractions = [
            (q_c - i_c, 0, "consensus"),
            (q_h - i_h, 1, "host_priority"),
            (q_g - i_g, 2, "guest_priority"),
        ]

        # Sort by fraction descending; on tie, sort by tie-breaker ascending
        fractions.sort(key=lambda x: (-x[0], x[1]))

        counts = {
            "consensus": i_c,
            "host_priority": i_h,
            "guest_priority": i_g,
        }

        # Distribute remaining R seats
        for r in range(remainder):
            cat_name = fractions[r][2]
            counts[cat_name] += 1

        return counts


# -------------------------------------------------------------------
# Manifest Compiler Service
# -------------------------------------------------------------------

class ManifestCompilerService:
    """
    Compiles screening manifests for Normal and Boutique pools with
    strict zero-duplicate guarantees, deterministic tie-breaking, and persistence.
    """

    @staticmethod
    def _extract_user_preference_data(
        raw_prefs: Optional[Dict[str, Any]],
        fallback_profile: Optional[UserTasteProfile] = None,
        user: Optional[Any] = None,
        interaction_logs: Optional[List[Any]] = None,
    ) -> UserPreferenceData:
        """
        Converts raw occasion questionnaire responses or UserTasteProfile into UserPreferenceData.
        Extracts and applies accumulated learned feedback from InteractionLog if user or interaction_logs is provided.
        Incorporates persistent learned taste weights from UserTasteProfile via IdentityLinkingService.
        """
        learned_score: Optional[float] = None
        logs = interaction_logs
        if logs is None and user is not None:
            try:
                logs = list(InteractionLog.objects.filter(user=user).order_by("created_at"))
            except Exception:
                logs = None

        if logs:
            learned_score = compute_learned_feedback_from_logs(logs)

        # Resolve canonical user and taste profile via IdentityLinkingService
        canonical_user = user
        if user is not None and hasattr(user, "id"):
            try:
                from core.models import UserIdentityLink
                link = UserIdentityLink.objects.filter(linked_actor_id=user.id).first()
                if link:
                    canonical_user = link.canonical_user
            except Exception:
                pass

        profile = None
        if canonical_user is not None and hasattr(canonical_user, "id"):
            try:
                profile = UserTasteProfile.objects.filter(user=canonical_user).first()
            except Exception:
                profile = None
        if not profile:
            profile = fallback_profile

        # Extract learned taste weights from profile
        genre_weights: Dict[str, float] = {}
        tag_weights: Dict[str, float] = {}
        keyword_weights: Dict[str, float] = {}
        hard_exclusions: Dict[str, Any] = {}
        if profile:
            lw = profile.learned_weights or {}
            if isinstance(lw.get("genres"), dict):
                genre_weights = {str(k): float(v) for k, v in lw["genres"].items()}
            if isinstance(lw.get("tags"), dict):
                tag_weights = {str(k): float(v) for k, v in lw["tags"].items()}
            if isinstance(lw.get("keywords"), dict):
                keyword_weights = {str(k): float(v) for k, v in lw["keywords"].items()}
            if not genre_weights and not tag_weights and not keyword_weights and lw:
                for k, v in lw.items():
                    if isinstance(v, (int, float)):
                        keyword_weights[str(k)] = float(v)
            if isinstance(profile.hard_exclusions, dict):
                hard_exclusions = profile.hard_exclusions

        norm_prefs = normalize_user_preferences(raw_prefs)

        if not raw_prefs and profile:
            return UserPreferenceData(
                moods=list(profile.emotional_tonality or []),
                narrative=list(profile.narrative_structures or []),
                themes=list(profile.thematic_interests or []),
                experience=profile.viewing_rhythm or "balanced",
                direct_learned_score=learned_score,
                eras=list(profile.default_eras or []),
                min_rating=float(profile.default_min_rating) if profile.default_min_rating else None,
                genre_weights=genre_weights,
                tag_weights=tag_weights,
                keyword_weights=keyword_weights,
                hard_exclusions=hard_exclusions,
            )

        return UserPreferenceData(
            moods=norm_prefs["moods"],
            narrative=norm_prefs["narrative"],
            themes=norm_prefs["themes"],
            experience=norm_prefs["experience"],
            direct_learned_score=learned_score,
            theme_keywords=norm_prefs["theme_keywords"],
            setting=norm_prefs["setting"],
            setting_keywords=norm_prefs["setting_keywords"],
            eras=norm_prefs["era"],
            min_rating=norm_prefs["min_rating"],
            genre_weights=genre_weights,
            tag_weights=tag_weights,
            keyword_weights=keyword_weights,
            hard_exclusions=hard_exclusions,
        )

    @classmethod
    def compile_manifest(
        cls,
        candidates: List[Movie],
        host_prefs: UserPreferenceData,
        guest_prefs: UserPreferenceData,
        pool_type: Optional[str] = None,
        guest_floor: Optional[float] = None,
        host_floor: Optional[float] = None,
        host_user: Optional[Any] = None,
        guest_user: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Compiles candidate movies into a screening manifest.
        Guarantees:
        - Normal Mode (>= 40 candidates): Exactly 40 unique cards, 16C / 12H / 12G,
          cyclical 10-card cadence repeated 4 times.
        - Boutique Mode (16-39 candidates): Exactly N cards, Hamilton 40/30/30 allocation,
          fractional progression step interleaving, zero duplicates.
        - Exhausted Pool (< 16 candidates): Raises InsufficientCandidatesError.
        - Configurable relevance floors: Default 0.30, adjustable via settings or caller.
        """
        pool_size = len(candidates)
        if pool_size < MIN_BOUTIQUE_POOL_SIZE:
            raise InsufficientCandidatesError(
                f"Candidate pool size ({pool_size}) is under {MIN_BOUTIQUE_POOL_SIZE}. "
                "Constraint Exhaustion Protocol requires dual-approval proposal."
            )

        g_floor = guest_floor if guest_floor is not None else DEFAULT_RELEVANCE_FLOOR_GUEST
        h_floor = host_floor if host_floor is not None else DEFAULT_RELEVANCE_FLOOR_HOST

        # If user objects supplied and preferences don't have explicit learned score, compute from logs
        if host_user:
            if host_prefs.direct_learned_score is None:
                try:
                    h_logs = list(InteractionLog.objects.filter(user=host_user).order_by("created_at"))
                    if h_logs:
                        host_prefs.direct_learned_score = compute_learned_feedback_from_logs(h_logs)
                except Exception:
                    pass
            if not host_prefs.genre_weights and not host_prefs.keyword_weights:
                try:
                    hp = getattr(host_user, "taste_profile", None)
                    if hp and hp.learned_weights:
                        lw = hp.learned_weights
                        if isinstance(lw.get("genres"), dict):
                            host_prefs.genre_weights = {str(k): float(v) for k, v in lw["genres"].items()}
                        if isinstance(lw.get("tags"), dict):
                            host_prefs.tag_weights = {str(k): float(v) for k, v in lw["tags"].items()}
                        if isinstance(lw.get("keywords"), dict):
                            host_prefs.keyword_weights = {str(k): float(v) for k, v in lw["keywords"].items()}
                except Exception:
                    pass

        if guest_user:
            if guest_prefs.direct_learned_score is None:
                try:
                    g_logs = list(InteractionLog.objects.filter(user=guest_user).order_by("created_at"))
                    if g_logs:
                        guest_prefs.direct_learned_score = compute_learned_feedback_from_logs(g_logs)
                except Exception:
                    pass
            if not guest_prefs.genre_weights and not guest_prefs.keyword_weights:
                try:
                    gp = getattr(guest_user, "taste_profile", None)
                    if gp and gp.learned_weights:
                        lw = gp.learned_weights
                        if isinstance(lw.get("genres"), dict):
                            guest_prefs.genre_weights = {str(k): float(v) for k, v in lw["genres"].items()}
                        if isinstance(lw.get("tags"), dict):
                            guest_prefs.tag_weights = {str(k): float(v) for k, v in lw["tags"].items()}
                        if isinstance(lw.get("keywords"), dict):
                            guest_prefs.keyword_weights = {str(k): float(v) for k, v in lw["keywords"].items()}
                except Exception:
                    pass

        # Score all candidate movies
        scorer = CollaborativeDeckScorer()
        scored_candidates = scorer.score_candidate_pool(
            candidates=candidates,
            host_prefs=host_prefs,
            guest_prefs=guest_prefs,
        )

        if pool_size >= NORMAL_MANIFEST_SIZE:
            return cls._compile_normal_manifest(scored_candidates, guest_floor=g_floor, host_floor=h_floor)
        else:
            return cls._compile_boutique_manifest(scored_candidates, guest_floor=g_floor, host_floor=h_floor)

    @classmethod
    def _compile_normal_manifest(
        cls,
        scored: List[ScoredCandidate],
        guest_floor: float = DEFAULT_RELEVANCE_FLOOR_GUEST,
        host_floor: float = DEFAULT_RELEVANCE_FLOOR_HOST,
    ) -> List[Dict[str, Any]]:
        """
        Compiles Normal Mode manifest (40 unique cards, 16 Consensus, 12 Host, 12 Guest).
        Cadence: [C, H, G, C, H, G, C, C, H, G] repeated 4 times.
        """
        assigned_ids: Set[int] = set()

        # 1. Consensus selection (16 cards): Top consensus score descending
        consensus_sorted = sorted(
            scored,
            key=lambda c: (
                c.consensus_score,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                int(getattr(c.movie, "vote_count", 0) or 0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        consensus_selected: List[ScoredCandidate] = []
        for c in consensus_sorted:
            if len(consensus_selected) == NORMAL_CONSENSUS_COUNT:
                break
            if c.movie_id not in assigned_ids:
                consensus_selected.append(c)
                assigned_ids.add(c.movie_id)

        # 2. Host Priority selection (12 cards): Top Host relevance desc meeting partner floor
        host_sorted = sorted(
            scored,
            key=lambda c: (
                c.relevance_host,
                c.relevance_guest,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        host_selected: List[ScoredCandidate] = []
        # First pass: require partner floor
        for c in host_sorted:
            if len(host_selected) == NORMAL_HOST_COUNT:
                break
            if c.movie_id not in assigned_ids and c.relevance_guest >= guest_floor:
                host_selected.append(c)
                assigned_ids.add(c.movie_id)

        # Second pass (shortage fallback): relax floor if shortage exists
        if len(host_selected) < NORMAL_HOST_COUNT:
            for c in host_sorted:
                if len(host_selected) == NORMAL_HOST_COUNT:
                    break
                if c.movie_id not in assigned_ids:
                    host_selected.append(c)
                    assigned_ids.add(c.movie_id)

        # 3. Guest Priority selection (12 cards): Top Guest relevance desc meeting partner floor
        guest_sorted = sorted(
            scored,
            key=lambda c: (
                c.relevance_guest,
                c.relevance_host,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        guest_selected: List[ScoredCandidate] = []
        # First pass: require partner floor
        for c in guest_sorted:
            if len(guest_selected) == NORMAL_GUEST_COUNT:
                break
            if c.movie_id not in assigned_ids and c.relevance_host >= host_floor:
                guest_selected.append(c)
                assigned_ids.add(c.movie_id)

        # Second pass (shortage fallback): relax floor if shortage exists
        if len(guest_selected) < NORMAL_GUEST_COUNT:
            for c in guest_sorted:
                if len(guest_selected) == NORMAL_GUEST_COUNT:
                    break
                if c.movie_id not in assigned_ids:
                    guest_selected.append(c)
                    assigned_ids.add(c.movie_id)

        # Shortage redistribution if still lacking (redistribute to remaining candidates)
        # Any unfilled slots get top remaining unassigned candidates
        remaining_pool = [c for c in scored if c.movie_id not in assigned_ids]
        while len(consensus_selected) < NORMAL_CONSENSUS_COUNT and remaining_pool:
            c = remaining_pool.pop(0)
            consensus_selected.append(c)
            assigned_ids.add(c.movie_id)
        while len(host_selected) < NORMAL_HOST_COUNT and remaining_pool:
            c = remaining_pool.pop(0)
            host_selected.append(c)
            assigned_ids.add(c.movie_id)
        while len(guest_selected) < NORMAL_GUEST_COUNT and remaining_pool:
            c = remaining_pool.pop(0)
            guest_selected.append(c)
            assigned_ids.add(c.movie_id)

        # Interleave using 4 repetitions of the 10-card cadence
        # [C, H, G, C, H, G, C, C, H, G] * 4
        c_idx = 0
        h_idx = 0
        g_idx = 0

        manifest: List[Dict[str, Any]] = []

        for cycle in range(4):
            for slot_type in CADENCE_10_CARD:
                card_index = len(manifest)
                turn = "consensus"
                chosen: ScoredCandidate

                if slot_type == "consensus":
                    chosen = consensus_selected[c_idx]
                    c_idx += 1
                    turn = "consensus"
                elif slot_type == "host_priority":
                    chosen = host_selected[h_idx]
                    h_idx += 1
                    turn = "host"
                else:  # guest_priority
                    chosen = guest_selected[g_idx]
                    g_idx += 1
                    turn = "guest"

                manifest.append({
                    "card_index": card_index,
                    "movie_id": chosen.movie_id,
                    "tmdb_id": chosen.tmdb_id,
                    "title": chosen.title,
                    "slot_type": slot_type,
                    "turn": turn,
                    "scores": {
                        "relevance_host": round(chosen.relevance_host, 4),
                        "relevance_guest": round(chosen.relevance_guest, 4),
                        "consensus": round(chosen.consensus_score, 4),
                    },
                })

        return manifest

    @classmethod
    def _compile_boutique_manifest(
        cls,
        scored: List[ScoredCandidate],
        guest_floor: float = DEFAULT_RELEVANCE_FLOOR_GUEST,
        host_floor: float = DEFAULT_RELEVANCE_FLOOR_HOST,
    ) -> List[Dict[str, Any]]:
        """
        Compiles Boutique Mode manifest for 16 <= N <= 39 candidates.
        Uses Hamilton largest-remainder allocation, deterministic tie-breaking,
        and fractional progression step interleaving.
        Zero duplicate rule: Every candidate used exactly once.
        """
        n = len(scored)
        allocation = HamiltonManifestAllocator.calculate_allocation(n)
        n_c = allocation["consensus"]
        n_h = allocation["host_priority"]
        n_g = allocation["guest_priority"]

        assigned_ids: Set[int] = set()

        # 1. Consensus selection: Top n_c candidates
        consensus_sorted = sorted(
            scored,
            key=lambda c: (
                c.consensus_score,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                int(getattr(c.movie, "vote_count", 0) or 0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        consensus_selected: List[ScoredCandidate] = []
        for c in consensus_sorted:
            if len(consensus_selected) == n_c:
                break
            if c.movie_id not in assigned_ids:
                consensus_selected.append(c)
                assigned_ids.add(c.movie_id)

        # 2. Host Priority selection: Top n_h candidates meeting floor
        host_sorted = sorted(
            scored,
            key=lambda c: (
                c.relevance_host,
                c.relevance_guest,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        host_selected: List[ScoredCandidate] = []
        for c in host_sorted:
            if len(host_selected) == n_h:
                break
            if c.movie_id not in assigned_ids and c.relevance_guest >= guest_floor:
                host_selected.append(c)
                assigned_ids.add(c.movie_id)

        # Fallback for floor shortage
        if len(host_selected) < n_h:
            for c in host_sorted:
                if len(host_selected) == n_h:
                    break
                if c.movie_id not in assigned_ids:
                    host_selected.append(c)
                    assigned_ids.add(c.movie_id)

        # 3. Guest Priority selection: Top n_g candidates meeting floor
        guest_sorted = sorted(
            scored,
            key=lambda c: (
                c.relevance_guest,
                c.relevance_host,
                float(getattr(c.movie, "rating", 0.0) or 0.0),
                c.tmdb_id,
            ),
            reverse=True,
        )

        guest_selected: List[ScoredCandidate] = []
        for c in guest_sorted:
            if len(guest_selected) == n_g:
                break
            if c.movie_id not in assigned_ids and c.relevance_host >= host_floor:
                guest_selected.append(c)
                assigned_ids.add(c.movie_id)

        # Fallback for floor shortage
        if len(guest_selected) < n_g:
            for c in guest_sorted:
                if len(guest_selected) == n_g:
                    break
                if c.movie_id not in assigned_ids:
                    guest_selected.append(c)
                    assigned_ids.add(c.movie_id)

        # Category Shortage Redistribution (Architecture Section 10):
        # Unfillable slots redistributed first to Consensus, then to partner (C > H > G)
        remaining_unassigned = [c for c in scored if c.movie_id not in assigned_ids]
        while len(consensus_selected) < n_c and remaining_unassigned:
            c = remaining_unassigned.pop(0)
            consensus_selected.append(c)
            assigned_ids.add(c.movie_id)

        while len(host_selected) < n_h and remaining_unassigned:
            c = remaining_unassigned.pop(0)
            host_selected.append(c)
            assigned_ids.add(c.movie_id)

        while len(guest_selected) < n_g and remaining_unassigned:
            c = remaining_unassigned.pop(0)
            guest_selected.append(c)
            assigned_ids.add(c.movie_id)

        # If any remaining candidates still unassigned, distribute according to priority C > H > G
        while remaining_unassigned:
            c = remaining_unassigned.pop(0)
            if len(consensus_selected) <= len(host_selected) and len(consensus_selected) <= len(guest_selected):
                consensus_selected.append(c)
            elif len(host_selected) <= len(guest_selected):
                host_selected.append(c)
            else:
                guest_selected.append(c)
            assigned_ids.add(c.movie_id)

        # Deterministic Interleaving via Fractional Progression Step (Section 10)
        # Delta_C = N / N_C, Delta_H = N / N_H, Delta_G = N / N_G
        # Card position: (j + 0.5) * Delta_X. Tie-break: C (0) > H (1) > G (2)
        scheduled_slots: List[Tuple[float, int, str, ScoredCandidate]] = []

        actual_nc = len(consensus_selected)
        actual_nh = len(host_selected)
        actual_ng = len(guest_selected)

        if actual_nc > 0:
            delta_c = float(n) / float(actual_nc)
            for j, c in enumerate(consensus_selected):
                scheduled_slots.append(((j + 0.5) * delta_c, 0, "consensus", c))

        if actual_nh > 0:
            delta_h = float(n) / float(actual_nh)
            for j, c in enumerate(host_selected):
                scheduled_slots.append(((j + 0.5) * delta_h, 1, "host_priority", c))

        if actual_ng > 0:
            delta_g = float(n) / float(actual_ng)
            for j, c in enumerate(guest_selected):
                scheduled_slots.append(((j + 0.5) * delta_g, 2, "guest_priority", c))

        # Deterministic sort by step position; on tie, category priority C (0) > H (1) > G (2)
        scheduled_slots.sort(key=lambda s: (round(s[0], 6), s[1]))

        manifest: List[Dict[str, Any]] = []
        for card_idx, (_, _, slot_type, candidate) in enumerate(scheduled_slots):
            turn = "consensus"
            if slot_type == "host_priority":
                turn = "host"
            elif slot_type == "guest_priority":
                turn = "guest"

            manifest.append({
                "card_index": card_idx,
                "movie_id": candidate.movie_id,
                "tmdb_id": candidate.tmdb_id,
                "title": candidate.title,
                "slot_type": slot_type,
                "turn": turn,
                "scores": {
                    "relevance_host": round(candidate.relevance_host, 4),
                    "relevance_guest": round(candidate.relevance_guest, 4),
                    "consensus": round(candidate.consensus_score, 4),
                },
            })

        return manifest

    @classmethod
    def compile_and_persist_manifest(
        cls,
        session: Session,
        agreement: Optional[CollaborativeAgreement] = None,
        force_recompile: bool = False,
        candidate_pool: Optional[CandidatePool] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves candidates, compiles manifest, and persists snapshot
        into CollaborativeAgreement.deck_manifest.
        
        Guarantees:
        - Prevents accidental manifest regeneration if session is active and swiping has begun.
        - Persists snapshot atomically inside database transaction.
        - Idempotent and deterministic for identical candidate inputs.
        """
        # Resolve collaborative agreement
        if agreement is None:
            if hasattr(session, "collaborative_agreement"):
                agreement = session.collaborative_agreement
            else:
                agreement, _ = CollaborativeAgreement.objects.get_or_create(session=session)

        # Check existing active manifest protection
        existing_manifest = agreement.deck_manifest or []
        if existing_manifest:
            has_swiped = (
                agreement.host_card_index > 0
                or agreement.guest_card_index > 0
                or agreement.resolved_card_index > 0
            )
            if has_swiped:
                # Active manifests with recorded participant swipes are strictly immutable
                # Section 11: Served History Immutability
                raise ActiveManifestImmutableError(
                    f"Cannot recompile manifest for session {session.code}: "
                    "Participants have active swipe progress. Manifest is immutable."
                )
            if not force_recompile:
                return existing_manifest

        # Retrieve candidates if not pre-supplied
        if candidate_pool is None:
            candidate_pool = CandidateRetrievalService.retrieve_candidates(
                session=session,
                experience_type="screening",
                constraints=agreement,
                auto_replenish=True,
            )

        if candidate_pool.pool_type == "exhausted" or candidate_pool.total_count < MIN_BOUTIQUE_POOL_SIZE:
            if candidate_pool.metadata.get("transient_error"):
                raise TransientReplenishmentError(
                    candidate_pool.metadata.get("transient_error_message")
                    or "Unable to reach movie service during candidate replenishment. Please retry."
                )
            if candidate_pool.metadata.get("replenishment_in_progress"):
                raise ReplenishmentInProgressError(
                    "Screening deck is currently being curated. Please wait a moment..."
                )
            raise InsufficientCandidatesError(
                f"Candidate pool size ({candidate_pool.total_count}) is exhausted (< 16). "
                "Manifest cannot be compiled. Proposal pathway required."
            )

        # Extract preferences with learned feedback from InteractionLog
        host_prefs = cls._extract_user_preference_data(
            raw_prefs=agreement.host_soft_preferences,
            fallback_profile=getattr(session.host, "taste_profile", None) if session.host else None,
            user=session.host,
        )
        guest_prefs = cls._extract_user_preference_data(
            raw_prefs=agreement.guest_soft_preferences,
            fallback_profile=getattr(session.guest, "taste_profile", None) if session.guest else None,
            user=session.guest,
        )

        # Compile manifest
        manifest = cls.compile_manifest(
            candidates=candidate_pool.candidates,
            host_prefs=host_prefs,
            guest_prefs=guest_prefs,
            pool_type=candidate_pool.pool_type,
            host_user=session.host,
            guest_user=session.guest,
        )

        # Apply prioritized movies (e.g., from Curator's Double Feature) if eligible
        manifest = cls._apply_screening_prioritization(
            manifest=manifest,
            session=session,
            candidate_pool=candidate_pool,
        )

        # Persist manifest atomically
        with transaction.atomic():
            agreement.deck_manifest = manifest
            agreement.save(update_fields=["deck_manifest", "updated_at"])

        return manifest

    @classmethod
    def replenish_and_append_manifest(
        cls,
        session: Session,
        agreement: CollaborativeAgreement,
        candidate_pool: CandidatePool,
    ) -> List[Dict[str, Any]]:
        """
        Appends newly qualified candidates to an active deck manifest
        while guaranteeing strict immutability of already served cards.
        Section 11: Served History Immutability.
        """
        existing_manifest = agreement.deck_manifest or []
        served_count = max(agreement.host_card_index, agreement.guest_card_index)

        # If no cards have been served yet, compile fresh manifest
        if served_count == 0 or not existing_manifest:
            manifest = cls.compile_manifest(
                candidates=candidate_pool.candidates,
                host_prefs=cls._extract_user_preference_data(
                    raw_prefs=agreement.host_soft_preferences,
                    fallback_profile=getattr(session.host, "taste_profile", None) if session.host else None,
                    user=session.host,
                ),
                guest_prefs=cls._extract_user_preference_data(
                    raw_prefs=agreement.guest_soft_preferences,
                    fallback_profile=getattr(session.guest, "taste_profile", None) if session.guest else None,
                    user=session.guest,
                ),
                pool_type=candidate_pool.pool_type,
                host_user=session.host,
                guest_user=session.guest,
            )
            agreement.deck_manifest = manifest
            agreement.save(update_fields=["deck_manifest", "updated_at"])
            return manifest

        # Preserve already served cards strictly
        immutable_prefix = existing_manifest[:served_count]
        existing_movie_ids = {c["movie_id"] for c in existing_manifest}

        # Filter out movies already present in the manifest from candidates (Zero Duplicate Guarantee)
        available_candidates = [
            c for c in candidate_pool.candidates
            if c.id not in existing_movie_ids
        ]

        # Extract preferences with learned feedback
        host_prefs = cls._extract_user_preference_data(
            raw_prefs=agreement.host_soft_preferences,
            fallback_profile=getattr(session.host, "taste_profile", None) if session.host else None,
            user=session.host,
        )
        guest_prefs = cls._extract_user_preference_data(
            raw_prefs=agreement.guest_soft_preferences,
            fallback_profile=getattr(session.guest, "taste_profile", None) if session.guest else None,
            user=session.guest,
        )

        target_size = NORMAL_MANIFEST_SIZE if candidate_pool.pool_type == "normal" else min(NORMAL_MANIFEST_SIZE, len(existing_manifest) + len(available_candidates))
        needed_slots = max(0, target_size - len(existing_manifest))

        if needed_slots == 0:
            return existing_manifest

        # Score remaining candidates
        scorer = CollaborativeDeckScorer()
        scored_candidates = scorer.score_candidate_pool(
            candidates=available_candidates,
            host_prefs=host_prefs,
            guest_prefs=guest_prefs,
        )

        appended_cards = []
        cadence_cycle = ["consensus", "host_priority", "guest_priority"]
        assigned_ids = set(existing_movie_ids)

        for i in range(needed_slots):
            slot_idx = len(existing_manifest) + i
            desired_slot = cadence_cycle[i % 3]

            if desired_slot == "host_priority":
                sorted_pool = sorted(
                    [c for c in scored_candidates if c.movie_id not in assigned_ids],
                    key=lambda x: -x.relevance_host
                )
            elif desired_slot == "guest_priority":
                sorted_pool = sorted(
                    [c for c in scored_candidates if c.movie_id not in assigned_ids],
                    key=lambda x: -x.relevance_guest
                )
            else:
                sorted_pool = sorted(
                    [c for c in scored_candidates if c.movie_id not in assigned_ids],
                    key=lambda x: -x.consensus_score
                )

            if not sorted_pool:
                break

            chosen = sorted_pool[0]
            assigned_ids.add(chosen.movie_id)

            turn = "joint"
            if desired_slot == "host_priority":
                turn = "host"
            elif desired_slot == "guest_priority":
                turn = "guest"

            appended_cards.append({
                "card_index": slot_idx,
                "movie_id": chosen.movie_id,
                "tmdb_id": chosen.tmdb_id,
                "title": chosen.title,
                "slot_type": desired_slot,
                "turn": turn,
                "scores": {
                    "relevance_host": round(chosen.relevance_host, 4),
                    "relevance_guest": round(chosen.relevance_guest, 4),
                    "consensus": round(chosen.consensus_score, 4),
                },
            })

        new_manifest = existing_manifest + appended_cards
        agreement.deck_manifest = new_manifest
        agreement.save(update_fields=["deck_manifest", "updated_at"])
        return new_manifest

    @classmethod
    def _apply_screening_prioritization(
        cls,
        manifest: List[Dict[str, Any]],
        session: Session,
        candidate_pool: CandidatePool,
    ) -> List[Dict[str, Any]]:
        """
        Prioritizes eligible movies specified in session.host_preferences['prioritized_movie_ids']
        into the opening positions (0 and 1) of the screening deck manifest.

        Safety Guarantees:
        1. Confirms IDs exist in local Movie records.
        2. Strictly verifies candidate is eligible for this session (present in candidate_pool.candidates).
        3. Never bypasses filtering, language/industry constraints, or availability rules.
        4. Prevents duplicate cards in the manifest.
        5. Preserves existing 10-card cadence, slot_types, and turns.
        6. If prioritized film is unavailable or ineligible, falls back gracefully without corrupting manifest.
        """
        if not manifest or not session:
            return manifest

        prefs = getattr(session, "host_preferences", None) or {}
        prioritized_ids = prefs.get("prioritized_movie_ids")
        if not prioritized_ids or not isinstance(prioritized_ids, list):
            return manifest

        # 1. Candidate pool lookup: only candidates that successfully passed all constraints
        pool_candidate_map = {c.id: c for c in candidate_pool.candidates}

        # 2. Filter to eligible prioritized movies in order
        eligible_pids = [
            pid for pid in prioritized_ids[:2]
            if pid in pool_candidate_map
        ]

        if not eligible_pids:
            return manifest

        target_idx = 0
        for pid in eligible_pids:
            # Check if pid is already in the manifest
            existing_pos = next(
                (idx for idx, card in enumerate(manifest) if card.get("movie_id") == pid),
                None
            )

            if existing_pos is not None:
                # If it's already in the manifest, swap it into target_idx
                if existing_pos != target_idx and target_idx < len(manifest):
                    card_a = manifest[target_idx]
                    card_b = manifest[existing_pos]

                    card_a["movie_id"], card_b["movie_id"] = card_b["movie_id"], card_a["movie_id"]
                    card_a["tmdb_id"], card_b["tmdb_id"] = card_b["tmdb_id"], card_a["tmdb_id"]
                    card_a["title"], card_b["title"] = card_b["title"], card_a["title"]
                    card_a["scores"], card_b["scores"] = card_b["scores"], card_a["scores"]
                target_idx += 1
            else:
                # In candidate pool, but scored below manifest cutoff
                # Safely substitute the last card of the manifest and swap to target_idx
                if target_idx < len(manifest):
                    candidate_obj = pool_candidate_map[pid]
                    last_idx = len(manifest) - 1

                    manifest[last_idx]["movie_id"] = candidate_obj.id
                    manifest[last_idx]["tmdb_id"] = candidate_obj.tmdb_id
                    manifest[last_idx]["title"] = candidate_obj.title
                    manifest[last_idx]["scores"] = {
                        "relevance_host": 1.0,
                        "relevance_guest": 1.0,
                        "consensus": 1.0,
                    }

                    if last_idx != target_idx:
                        card_a = manifest[target_idx]
                        card_b = manifest[last_idx]

                        card_a["movie_id"], card_b["movie_id"] = card_b["movie_id"], card_a["movie_id"]
                        card_a["tmdb_id"], card_b["tmdb_id"] = card_b["tmdb_id"], card_a["tmdb_id"]
                        card_a["title"], card_b["title"] = card_b["title"], card_a["title"]
                        card_a["scores"], card_b["scores"] = card_b["scores"], card_a["scores"]

                    target_idx += 1

        return manifest
