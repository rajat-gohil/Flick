import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple, Union


# -------------------------------------------------------------------
# Configurable Provisional Defaults
# -------------------------------------------------------------------

@dataclass(frozen=True)
class ScoringConfig:
    """
    Central scoring parameters and provisional defaults.
    All parameters are configurable for empirical calibration.
    """
    # Component maximums (sum = 115.0)
    MAX_TONE: float = 30.0
    MAX_NARRATIVE: float = 20.0
    MAX_THEME: float = 25.0
    MAX_PACE: float = 15.0
    MAX_QUALITY: float = 10.0
    MAX_LEARNED_POSITIVE: float = 15.0
    MAX_LEARNED_NEGATIVE: float = -15.0
    MAX_FATIGUE: float = 15.0

    # Normalization divisor (exact positive maximum)
    NORMALIZATION_DIVISOR: float = 115.0

    # Neutral 50% baselines
    NEUTRAL_TONE: float = 15.0
    NEUTRAL_NARRATIVE: float = 10.0
    NEUTRAL_THEME: float = 12.5
    NEUTRAL_PACE: float = 7.5

    # Confidence cutoff threshold
    CONFIDENCE_CUTOFF: float = 0.35

    # Bayesian quality bonus parameters
    BAYESIAN_MIN_VOTES_GENERAL: int = 500
    BAYESIAN_MIN_VOTES_CLASSIC: int = 100
    BAYESIAN_CATALOG_MEAN_NORMALIZED: float = 0.68  # 6.8 / 10.0
    CLASSIC_CUTOFF_YEAR: int = 1990

    # 14-day fatigue half-life parameters
    FATIGUE_IMPRESSION_WEIGHT: float = 5.0
    FATIGUE_HALF_LIFE_DAYS: float = 14.0

    # 60-day learned feedback half-life parameters
    FEEDBACK_HALF_LIFE_DAYS: float = 60.0

    # Q4 Viewing Rhythm Target Vectors: (Pacing, Gravity)
    Q4_TARGETS: Dict[str, Tuple[float, float]] = field(
        default_factory=lambda: {
            "light": (0.60, 0.20),
            "balanced": (0.50, 0.50),
            "heavy": (0.40, 0.85),
        }
    )

    # Standard interaction signal weights
    SIGNAL_WEIGHTS: Dict[str, float] = field(
        default_factory=lambda: {
            "superlike": 3.0,
            "match": 2.5,
            "watchlist_add": 2.0,
            "swipe_like": 1.0,
            "modal_open": 0.3,
            "undo": 0.0,
            "swipe_dislike": -1.2,
        }
    )


# -------------------------------------------------------------------
# Data Structures
# -------------------------------------------------------------------

@dataclass
class MovieIntelligenceData:
    """
    Candidate movie data container for scoring.
    Accepts explicit machine inference scores and confidence metrics,
    falling back safely to neutral baselines when metadata is missing.
    """
    movie_id: Optional[int] = None
    title: str = ""
    vote_average: float = 0.0
    vote_count: int = 0
    release_date: Optional[date] = None

    # Inferred dimension vectors (probabilities over canonical taxonomies)
    tonality_distribution: Dict[str, float] = field(default_factory=dict)
    narrative_distribution: Dict[str, float] = field(default_factory=dict)
    thematic_distribution: Dict[str, float] = field(default_factory=dict)

    # Inferred continuous scalars in [0.0, 1.0]
    pacing_score: float = 0.50
    emotional_gravity: float = 0.50
    cerebral_depth: float = 0.50

    # Dimension-specific confidence metrics in [0.0, 1.0]
    confidence_tone: float = 0.0
    confidence_narrative: float = 0.0
    confidence_theme: float = 0.0
    confidence_pacing: float = 0.0
    confidence_gravity: float = 0.0
    confidence_cerebral: float = 0.0  # Tracked for metadata, kept out of additive score

    # Fallback tags/keywords for content matching
    keywords: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    overview: str = ""
    runtime: Optional[int] = None

    @classmethod
    def from_movie(cls, movie: Any) -> "MovieIntelligenceData":
        """
        Factory helper to build MovieIntelligenceData from a Django Movie model instance.
        """
        rel_date = getattr(movie, "release_date", None)
        rating = getattr(movie, "rating", None) or 0.0
        vote_count = getattr(movie, "vote_count", None) or 0

        # Extract keyword strings if available (safe prefetch handling)
        keyword_names: List[str] = []
        if hasattr(movie, "keywords"):
            try:
                keyword_names = [k.name.strip() for k in movie.keywords.all() if getattr(k, "name", None)]
            except Exception:
                pass

        tag_names: List[str] = []
        if hasattr(movie, "tags"):
            try:
                tag_names = [t.name.strip() for t in movie.tags.all() if getattr(t, "name", None)]
            except Exception:
                pass

        genre_names: List[str] = []
        if hasattr(movie, "genres"):
            try:
                genre_names = [g.name.strip() for g in movie.genres.all() if getattr(g, "name", None)]
            except Exception:
                pass
        if not genre_names and getattr(movie, "tmdb_genre_ids", None):
            try:
                from core.services.recommendation_engine import TMDB_GENRE_MAP
                for gid in movie.tmdb_genre_ids:
                    if gid in TMDB_GENRE_MAP:
                        genre_names.append(TMDB_GENRE_MAP[gid])
            except ImportError:
                pass

        return cls(
            movie_id=getattr(movie, "id", None),
            title=getattr(movie, "title", ""),
            vote_average=float(rating),
            vote_count=int(vote_count),
            release_date=rel_date,
            genres=genre_names,
            tags=tag_names,
            keywords=keyword_names,
            overview=getattr(movie, "overview", "") or "",
            runtime=getattr(movie, "runtime", None),
            # Continuous dimensions default to 0.50 median if not stored
            pacing_score=0.50,
            emotional_gravity=0.50,
            cerebral_depth=0.50,
            confidence_tone=0.0,
            confidence_narrative=0.0,
            confidence_theme=0.0,
            confidence_pacing=0.0,
            confidence_gravity=0.0,
            confidence_cerebral=0.0,
        )


@dataclass
class UserPreferenceData:
    """
    User preference container for scoring.
    """
    moods: List[str] = field(default_factory=list)          # Q1: 1-3 moods
    narrative: List[str] = field(default_factory=list)      # Q2: 0-2 structures (optional)
    themes: List[str] = field(default_factory=list)         # Q3: 0-3 themes (optional)
    experience: str = "balanced"                            # Q4: light, balanced, heavy, any
    unswiped_impressions: List[float] = field(default_factory=list) # Elapsed days for unswiped views
    learned_feedback_events: List[Tuple[float, float]] = field(default_factory=list) # (weight, elapsed_days)
    direct_learned_score: Optional[float] = None            # Direct pre-computed feedback score
    # Normalized questionnaire fields
    theme_keywords: List[str] = field(default_factory=list)
    setting: List[str] = field(default_factory=list)
    setting_keywords: List[str] = field(default_factory=list)
    eras: List[str] = field(default_factory=list)
    min_rating: Optional[float] = None
    # Learned taste weights from UserTasteProfile
    genre_weights: Dict[str, float] = field(default_factory=dict)
    tag_weights: Dict[str, float] = field(default_factory=dict)
    keyword_weights: Dict[str, float] = field(default_factory=dict)
    hard_exclusions: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoringResult:
    """
    Comprehensive, transparent scoring output.
    """
    relevance: float                 # Normalized score in [0.0, 1.0]
    raw_score: float                 # Raw score in [-30.0, 115.0]
    s_tone: float                    # [0.0, 30.0]
    s_narrative: float               # [0.0, 20.0]
    s_theme: float                   # [0.0, 25.0]
    s_pace: float                    # [0.0, 15.0]
    s_quality: float                 # [0.0, 10.0]
    s_learned: float                 # [-15.0, 15.0]
    p_fatigue: float                 # [0.0, 15.0]
    kappa_tone: float                # Attenuation [0.0, 1.0]
    kappa_narrative: float           # Attenuation [0.0, 1.0]
    kappa_theme: float               # Attenuation [0.0, 1.0]
    kappa_pace: float                # Attenuation [0.0, 1.0]
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_relevance(self) -> float:
        """Alias for relevance in [0.0, 1.0]."""
        return self.relevance


# -------------------------------------------------------------------
# Individual Relevance Scorer Implementation
# -------------------------------------------------------------------

class IndividualRelevanceScorer:
    """
    Deterministic 115-point scoring and normalization engine.
    Computes individual relevance Rel(M, U) in [0.0, 1.0] with dimension-specific
    confidence attenuation, Bayesian quality bonus, 14-day fatigue half-life,
    and 60-day learned feedback half-life.
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self.config = config or ScoringConfig()

    # ---------------------------------------------------------------
    # Confidence Attenuation Helper
    # ---------------------------------------------------------------
    def compute_attenuation(self, confidence: float) -> float:
        """
        Calculates attenuation factor kappa in [0.0, 1.0].
        If confidence <= CONFIDENCE_CUTOFF (0.35), returns 0.0.
        Otherwise scales linearly from 0.0 to 1.0.
        """
        if confidence <= self.config.CONFIDENCE_CUTOFF:
            return 0.0
        denom = 1.0 - self.config.CONFIDENCE_CUTOFF
        if denom <= 0:
            return 1.0
        return min(1.0, max(0.0, (confidence - self.config.CONFIDENCE_CUTOFF) / denom))

    # ---------------------------------------------------------------
    # 1. Emotional Tonality Score (0 to 30)
    # ---------------------------------------------------------------
    def calculate_tonality_score(
        self,
        user_moods: List[str],
        movie_distribution: Dict[str, float],
        confidence: float,
        movie_keywords: Optional[List[str]] = None,
        movie_tags: Optional[List[str]] = None,
    ) -> Tuple[float, float]:
        """
        Computes tone score.
        If user selected moods and movie has distribution, computes cosine match.
        Attenuates toward neutral baseline (15.0 pts) when confidence <= 0.35.
        When distribution is absent or attenuated, falls back to direct matching against
        movie keywords and tags if available, or neutral baseline.
        Returns: (final_score, kappa_tone)
        """
        kappa = self.compute_attenuation(confidence)
        neutral = self.config.NEUTRAL_TONE

        if not user_moods:
            return neutral, kappa

        # Check explicit machine vector distribution if available and confident
        if movie_distribution and kappa > 0.0:
            user_vector = {m.lower(): 1.0 for m in user_moods}
            dot_product = sum(user_vector.get(k.lower(), 0.0) * v for k, v in movie_distribution.items())
            user_norm = math.sqrt(len(user_moods))
            movie_norm = math.sqrt(sum(v * v for v in movie_distribution.values()))
            if user_norm > 0 and movie_norm > 0:
                cosine_sim = min(1.0, max(0.0, dot_product / (user_norm * movie_norm)))
                evidence_score = cosine_sim * self.config.MAX_TONE
                final_score = neutral + kappa * (evidence_score - neutral)
                return min(self.config.MAX_TONE, max(0.0, final_score)), kappa

        # Content-based fallback: match user moods against movie keywords and tags
        candidate_terms = [k.lower().strip() for k in (movie_keywords or []) + (movie_tags or []) if k]
        if not candidate_terms:
            return neutral, kappa

        target_moods = [m.lower().strip() for m in user_moods if m]
        if not target_moods:
            return neutral, kappa

        matches = 0
        for m in target_moods:
            if any(m == term or m in term or term in m for term in candidate_terms):
                matches += 1

        if matches > 0:
            match_ratio = min(1.0, matches / min(2, len(target_moods)))
            evidence_score = neutral + (self.config.MAX_TONE - neutral) * match_ratio
            return min(self.config.MAX_TONE, max(0.0, evidence_score)), kappa

        return neutral, kappa

    # ---------------------------------------------------------------
    # 2. Narrative Structure Score (0 to 20)
    # ---------------------------------------------------------------
    def calculate_narrative_score(
        self,
        user_narrative: List[str],
        movie_distribution: Dict[str, float],
        confidence: float,
        movie_keywords: Optional[List[str]] = None,
        movie_tags: Optional[List[str]] = None,
        movie_overview: Optional[str] = None,
    ) -> Tuple[float, float]:
        """
        Computes narrative score.
        If user skipped Q2 (user_narrative is empty), returns neutral 10.0 pts.
        Otherwise computes overlap and attenuates toward neutral baseline (10.0 pts).
        Falls back to keyword/tag/overview matching when vector distribution is unpopulated.
        Returns: (final_score, kappa_narrative)
        """
        kappa = self.compute_attenuation(confidence)
        neutral = self.config.NEUTRAL_NARRATIVE

        if not user_narrative:
            # Deliberately skipped Q2 -> Neutral 50% baseline
            return neutral, kappa

        if movie_distribution and kappa > 0.0:
            user_vector = {n.lower(): 1.0 for n in user_narrative}
            dot_product = sum(user_vector.get(k.lower(), 0.0) * v for k, v in movie_distribution.items())
            user_norm = math.sqrt(len(user_narrative))
            movie_norm = math.sqrt(sum(v * v for v in movie_distribution.values()))
            if user_norm > 0 and movie_norm > 0:
                cosine_sim = min(1.0, max(0.0, dot_product / (user_norm * movie_norm)))
                evidence_score = cosine_sim * self.config.MAX_NARRATIVE
                final_score = neutral + kappa * (evidence_score - neutral)
                return min(self.config.MAX_NARRATIVE, max(0.0, final_score)), kappa

        # Content-based fallback
        candidate_terms = [k.lower().strip() for k in (movie_keywords or []) + (movie_tags or []) if k]
        overview_text = (movie_overview or "").lower()
        if not candidate_terms and not overview_text:
            return neutral, kappa

        target_narratives = [n.lower().strip() for n in user_narrative if n]
        matches = 0
        for n in target_narratives:
            if any(n == term or n in term or term in n for term in candidate_terms) or (n in overview_text):
                matches += 1

        if matches > 0:
            match_ratio = min(1.0, matches / min(2, len(target_narratives)))
            evidence_score = neutral + (self.config.MAX_NARRATIVE - neutral) * match_ratio
            return min(self.config.MAX_NARRATIVE, max(0.0, evidence_score)), kappa

        return neutral, kappa

    # ---------------------------------------------------------------
    # 3. Thematic Focus Score (0 to 25)
    # ---------------------------------------------------------------
    def calculate_thematic_score(
        self,
        user_themes: List[str],
        movie_distribution: Dict[str, float],
        confidence: float,
        theme_keywords: Optional[List[str]] = None,
        setting_keywords: Optional[List[str]] = None,
        movie_keywords: Optional[List[str]] = None,
        movie_tags: Optional[List[str]] = None,
    ) -> Tuple[float, float]:
        """
        Computes theme score.
        If user skipped Q3 (user_themes is empty), returns neutral 12.5 pts.
        Otherwise computes overlap and attenuates toward neutral baseline (12.5 pts).
        Falls back to matching questionnaire themes, theme_keywords, and setting_keywords
        against candidate movie keywords and tags.
        Returns: (final_score, kappa_theme)
        """
        kappa = self.compute_attenuation(confidence)
        neutral = self.config.NEUTRAL_THEME

        # If explicit machine vector distribution is present and confident
        if movie_distribution and kappa > 0.0 and user_themes:
            user_vector = {t.lower(): 1.0 for t in user_themes}
            dot_product = sum(user_vector.get(k.lower(), 0.0) * v for k, v in movie_distribution.items())
            user_norm = math.sqrt(len(user_themes))
            movie_norm = math.sqrt(sum(v * v for v in movie_distribution.values()))
            if user_norm > 0 and movie_norm > 0:
                cosine_sim = min(1.0, max(0.0, dot_product / (user_norm * movie_norm)))
                evidence_score = cosine_sim * self.config.MAX_THEME
                final_score = neutral + kappa * (evidence_score - neutral)
                return min(self.config.MAX_THEME, max(0.0, final_score)), kappa

        # Collect questionnaire query terms
        query_terms: Set[str] = set()
        for t in (user_themes or []):
            if t and t.lower() not in ("any", "anywhere"):
                query_terms.add(t.lower().strip())
        for tk in (theme_keywords or []):
            if tk and tk.lower() not in ("any", "anywhere"):
                query_terms.add(tk.lower().strip())
        for sk in (setting_keywords or []):
            if sk and sk.lower() not in ("any", "anywhere"):
                query_terms.add(sk.lower().strip())

        if not query_terms:
            return neutral, kappa

        candidate_terms = [k.lower().strip() for k in (movie_keywords or []) + (movie_tags or []) if k]
        if not candidate_terms:
            return neutral, kappa

        # Count term matches
        matched_terms: Set[str] = set()
        for q in query_terms:
            for term in candidate_terms:
                if q == term or q in term or term in q:
                    matched_terms.add(q)
                    break

        if matched_terms:
            match_ratio = min(1.0, len(matched_terms) / min(3, max(1, len(query_terms))))
            evidence_score = neutral + (self.config.MAX_THEME - neutral) * match_ratio
            return min(self.config.MAX_THEME, max(0.0, evidence_score)), kappa

        return neutral, kappa

    # ---------------------------------------------------------------
    # 4. Pacing & Emotional Intensity Score (0 to 15)
    # ---------------------------------------------------------------
    def calculate_pacing_score(
        self,
        user_experience: str,
        pacing_score: float,
        emotional_gravity: float,
        confidence_pacing: float,
        confidence_gravity: float,
        movie_keywords: Optional[List[str]] = None,
        movie_tags: Optional[List[str]] = None,
        runtime: Optional[int] = None,
    ) -> Tuple[float, float]:
        """
        Deterministic mapping from pacing-vector distance to 0-15 score.
        Uses both confidence_pacing and confidence_gravity.
        If user selects 'any', returns neutral 7.5 pts directly.
        Falls back to runtime/keyword matching when continuous confidence is <= 0.35.
        Returns: (final_score, kappa_pace)
        """
        neutral = self.config.NEUTRAL_PACE
        composite_confidence = min(confidence_pacing, confidence_gravity)
        kappa = self.compute_attenuation(composite_confidence)

        exp_key = (user_experience or "balanced").strip().lower()
        if exp_key == "any":
            return neutral, kappa

        # If confident continuous metrics are available
        if kappa > 0.0:
            target = self.config.Q4_TARGETS.get(exp_key, self.config.Q4_TARGETS["balanced"])
            target_p, target_g = target
            p_m = min(1.0, max(0.0, pacing_score))
            g_m = min(1.0, max(0.0, emotional_gravity))
            dist = math.sqrt((target_p - p_m) ** 2 + (target_g - g_m) ** 2)
            max_dist = math.sqrt(2.0)
            normalized_closeness = max(0.0, 1.0 - (dist / max_dist))
            evidence_score = normalized_closeness * self.config.MAX_PACE
            final_score = neutral + kappa * (evidence_score - neutral)
            return min(self.config.MAX_PACE, max(0.0, final_score)), kappa

        # Content-based fallback
        candidate_terms = {k.lower().strip() for k in (movie_keywords or []) + (movie_tags or []) if k}
        if exp_key == "light":
            if (runtime and runtime < 100) or bool(candidate_terms & {"lighthearted", "comedy", "gentle", "fun", "slow burn"}):
                return min(self.config.MAX_PACE, neutral + 4.5), kappa
            if bool(candidate_terms & {"gore", "brutal", "gruesome", "torture", "relentless"}):
                return max(0.0, neutral - 4.5), kappa
            return neutral, kappa
        elif exp_key == "heavy":
            if bool(candidate_terms & {"fast-paced", "relentless", "intense", "brutal", "action", "gore", "slasher", "survival"}):
                return min(self.config.MAX_PACE, neutral + 4.5), kappa
            if bool(candidate_terms & {"lighthearted", "gentle", "family"}):
                return max(0.0, neutral - 4.5), kappa
            return neutral, kappa

        return neutral, kappa

        exp_key = (user_experience or "balanced").strip().lower()
        if exp_key == "any":
            return neutral, kappa

        target = self.config.Q4_TARGETS.get(exp_key, self.config.Q4_TARGETS["balanced"])
        target_p, target_g = target

        # Clamp movie coordinates to [0.0, 1.0]
        p_m = min(1.0, max(0.0, pacing_score))
        g_m = min(1.0, max(0.0, emotional_gravity))

        # Euclidean distance in unit square [0, 1]^2
        dist = math.sqrt((target_p - p_m) ** 2 + (target_g - g_m) ** 2)
        max_dist = math.sqrt(2.0)  # ~1.41421356

        # Deterministic linear distance mapping: distance 0 -> 15.0; distance sqrt(2) -> 0.0
        normalized_closeness = max(0.0, 1.0 - (dist / max_dist))
        evidence_score = normalized_closeness * self.config.MAX_PACE

        final_score = neutral + kappa * (evidence_score - neutral)
        return min(self.config.MAX_PACE, max(0.0, final_score)), kappa

    # ---------------------------------------------------------------
    # 5. Bayesian Quality Bonus (0 to 10)
    # ---------------------------------------------------------------
    def calculate_quality_bonus(
        self,
        vote_average: float,
        vote_count: int,
        release_date: Optional[date] = None
    ) -> float:
        """
        Computes Bayesian quality bonus using:
        S_quality = 10.0 * [ (v / (v + m)) * (R / 10.0) + (m / (v + m)) * C ]
        """
        r_raw = min(10.0, max(0.0, float(vote_average or 0.0)))
        v = max(0, int(vote_count or 0))

        # Check if film is classic (pre-1990)
        is_classic = False
        if release_date:
            try:
                is_classic = release_date.year < self.config.CLASSIC_CUTOFF_YEAR
            except AttributeError:
                pass

        m = self.config.BAYESIAN_MIN_VOTES_CLASSIC if is_classic else self.config.BAYESIAN_MIN_VOTES_GENERAL
        c = self.config.BAYESIAN_CATALOG_MEAN_NORMALIZED

        denom = v + m
        if denom <= 0:
            return 10.0 * c

        term1 = (v / denom) * (r_raw / 10.0)
        term2 = (m / denom) * c
        bayesian_score = 10.0 * (term1 + term2)
        return min(self.config.MAX_QUALITY, max(0.0, bayesian_score))

    # ---------------------------------------------------------------
    # 6. Fatigue Penalty (0 to 15) with True 14-Day Half-Life
    # ---------------------------------------------------------------
    def calculate_fatigue_penalty(
        self,
        unswiped_impression_days: List[float]
    ) -> float:
        """
        True 14-day half-life fatigue penalty:
        decay = 2 ** (-delta_t / 14.0)
        P_fatigue = min(15.0, sum(5.0 * 2 ** (-delta_t / 14.0)))
        """
        if not unswiped_impression_days:
            return 0.0

        half_life = self.config.FATIGUE_HALF_LIFE_DAYS
        weight = self.config.FATIGUE_IMPRESSION_WEIGHT
        total_penalty = 0.0

        for delta_t in unswiped_impression_days:
            t = max(0.0, float(delta_t))
            # True half-life formulation: 2 ** (-t / half_life)
            decay = 2.0 ** (-t / half_life)
            total_penalty += weight * decay

        return min(self.config.MAX_FATIGUE, max(0.0, total_penalty))

    # ---------------------------------------------------------------
    # 7. Learned Feedback (-15 to +15) with 60-Day Half-Life
    # ---------------------------------------------------------------
    def calculate_learned_feedback(
        self,
        feedback_events: List[Tuple[float, float]],
        direct_score: Optional[float] = None,
        movie_genres: Optional[List[str]] = None,
        movie_tags: Optional[List[str]] = None,
        movie_keywords: Optional[List[str]] = None,
        genre_weights: Optional[Dict[str, float]] = None,
        tag_weights: Optional[Dict[str, float]] = None,
        keyword_weights: Optional[Dict[str, float]] = None,
        hard_exclusions: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Computes learned feedback clamped to [-15.0, +15.0].
        Incorporate persistent taste profile weights (positive affinity bonuses and negative penalties)
        matched against candidate movie attributes.
        Aggregates interaction log events (weight, elapsed_days) with a 60-day half-life:
        decay = 2 ** (-delta_t / 60.0)
        """
        total = 0.0

        # Incorporate learned taste weights from UserTasteProfile
        if genre_weights and movie_genres:
            for g in movie_genres:
                w = genre_weights.get(g) or genre_weights.get(g.lower())
                if w is not None:
                    try:
                        w_val = float(w)
                        if w_val > 0:
                            total += min(4.0, w_val * 2.0)
                        elif w_val < 0:
                            total -= min(6.0, abs(w_val) * 2.5)
                    except (ValueError, TypeError):
                        pass

        if tag_weights and movie_tags:
            for t in movie_tags:
                w = tag_weights.get(t) or tag_weights.get(t.lower())
                if w is not None:
                    try:
                        w_val = float(w)
                        if w_val > 0:
                            total += min(3.0, w_val * 1.5)
                        elif w_val < 0:
                            total -= min(5.0, abs(w_val) * 2.0)
                    except (ValueError, TypeError):
                        pass

        if keyword_weights and movie_keywords:
            for k in movie_keywords:
                w = keyword_weights.get(k) or keyword_weights.get(k.lower())
                if w is not None:
                    try:
                        w_val = float(w)
                        if w_val > 0:
                            total += min(3.0, w_val * 1.2)
                        elif w_val < 0:
                            total -= min(5.0, abs(w_val) * 2.0)
                    except (ValueError, TypeError):
                        pass

        # Also support top-level fallback keyword_weights if dictionary is flat
        if not total and keyword_weights and not tag_weights and not genre_weights and (movie_keywords or movie_tags or movie_genres):
            all_terms = set(movie_keywords or []) | set(movie_tags or []) | set(movie_genres or [])
            for term in all_terms:
                w = keyword_weights.get(term) or keyword_weights.get(term.lower())
                if w is not None:
                    try:
                        w_val = float(w)
                        if w_val > 0:
                            total += min(3.0, w_val * 1.2)
                        elif w_val < 0:
                            total -= min(5.0, abs(w_val) * 2.0)
                    except (ValueError, TypeError):
                        pass

        if direct_score is not None:
            total += float(direct_score)

        if feedback_events:
            half_life = self.config.FEEDBACK_HALF_LIFE_DAYS
            for w, delta_t in feedback_events:
                t = max(0.0, float(delta_t))
                decay = 2.0 ** (-t / half_life)
                total += float(w) * decay

        return min(self.config.MAX_LEARNED_POSITIVE, max(self.config.MAX_LEARNED_NEGATIVE, total))

    # ---------------------------------------------------------------
    # Normalization to [0, 1]
    # ---------------------------------------------------------------
    def normalize_score(self, raw_score: float) -> float:
        """
        Normalizes raw score to [0.0, 1.0] by dividing by 115.0 and clamping.
        Rel(M, U) = clamp(R_raw / 115.0, 0.0, 1.0)
        """
        return min(1.0, max(0.0, raw_score / self.config.NORMALIZATION_DIVISOR))

    # ---------------------------------------------------------------
    # Master Score Evaluation
    # ---------------------------------------------------------------
    def score(
        self,
        movie: Union[MovieIntelligenceData, Any],
        preferences: UserPreferenceData
    ) -> ScoringResult:
        """
        Computes complete 115-point score and normalized relevance in [0.0, 1.0].
        Accepts MovieIntelligenceData or a Django Movie model instance.
        """
        if not isinstance(movie, MovieIntelligenceData):
            m_data = MovieIntelligenceData.from_movie(movie)
        else:
            m_data = movie

        # 1. Emotional Tonality
        s_tone, k_tone = self.calculate_tonality_score(
            preferences.moods,
            m_data.tonality_distribution,
            m_data.confidence_tone,
            movie_keywords=m_data.keywords,
            movie_tags=m_data.tags,
        )

        # 2. Narrative Structure
        s_narr, k_narr = self.calculate_narrative_score(
            preferences.narrative,
            m_data.narrative_distribution,
            m_data.confidence_narrative,
            movie_keywords=m_data.keywords,
            movie_tags=m_data.tags,
            movie_overview=m_data.overview,
        )

        # 3. Thematic Focus
        s_theme, k_theme = self.calculate_thematic_score(
            preferences.themes,
            m_data.thematic_distribution,
            m_data.confidence_theme,
            theme_keywords=preferences.theme_keywords,
            setting_keywords=preferences.setting_keywords,
            movie_keywords=m_data.keywords,
            movie_tags=m_data.tags,
        )

        # 4. Pacing & Intensity
        s_pace, k_pace = self.calculate_pacing_score(
            preferences.experience,
            m_data.pacing_score,
            m_data.emotional_gravity,
            m_data.confidence_pacing,
            m_data.confidence_gravity,
            movie_keywords=m_data.keywords,
            movie_tags=m_data.tags,
            runtime=m_data.runtime,
        )

        # 5. Bayesian Quality
        s_quality = self.calculate_quality_bonus(
            m_data.vote_average,
            m_data.vote_count,
            m_data.release_date
        )

        # 6. Learned Feedback
        s_learned = self.calculate_learned_feedback(
            feedback_events=preferences.learned_feedback_events,
            direct_score=preferences.direct_learned_score,
            movie_genres=m_data.genres,
            movie_tags=m_data.tags,
            movie_keywords=m_data.keywords,
            genre_weights=preferences.genre_weights,
            tag_weights=preferences.tag_weights,
            keyword_weights=preferences.keyword_weights,
            hard_exclusions=preferences.hard_exclusions,
        )

        # 7. Fatigue Penalty
        p_fatigue = self.calculate_fatigue_penalty(
            preferences.unswiped_impressions
        )

        # Linear additive raw score in [-30.0, 115.0]
        r_raw = s_tone + s_narr + s_theme + s_pace + s_quality + s_learned - p_fatigue

        # Bounded normalization in [0.0, 1.0]
        relevance = self.normalize_score(r_raw)

        # Collect transparent details breakdown
        matched_liked: List[str] = []
        matched_disliked: List[str] = []
        if preferences.genre_weights:
            for g in m_data.genres:
                w = preferences.genre_weights.get(g) or preferences.genre_weights.get(g.lower())
                if w is not None and float(w) > 0:
                    matched_liked.append(f"genre:{g}")
                elif w is not None and float(w) < 0:
                    matched_disliked.append(f"genre:{g}")
        if preferences.tag_weights:
            for t in m_data.tags:
                w = preferences.tag_weights.get(t) or preferences.tag_weights.get(t.lower())
                if w is not None and float(w) > 0:
                    matched_liked.append(f"tag:{t}")
                elif w is not None and float(w) < 0:
                    matched_disliked.append(f"tag:{t}")
        if preferences.keyword_weights:
            for k in m_data.keywords:
                w = preferences.keyword_weights.get(k) or preferences.keyword_weights.get(k.lower())
                if w is not None and float(w) > 0:
                    matched_liked.append(f"keyword:{k}")
                elif w is not None and float(w) < 0:
                    matched_disliked.append(f"keyword:{k}")

        questionnaire_contrib = round(
            (s_tone - self.config.NEUTRAL_TONE)
            + (s_narr - self.config.NEUTRAL_NARRATIVE)
            + (s_theme - self.config.NEUTRAL_THEME)
            + (s_pace - self.config.NEUTRAL_PACE),
            4
        )

        return ScoringResult(
            relevance=relevance,
            raw_score=r_raw,
            s_tone=s_tone,
            s_narrative=s_narr,
            s_theme=s_theme,
            s_pace=s_pace,
            s_quality=s_quality,
            s_learned=s_learned,
            p_fatigue=p_fatigue,
            kappa_tone=k_tone,
            kappa_narrative=k_narr,
            kappa_theme=k_theme,
            kappa_pace=k_pace,
            details={
                "movie_id": m_data.movie_id,
                "title": m_data.title,
                "confidence_cerebral": m_data.confidence_cerebral,
                "questionnaire_contribution": questionnaire_contrib,
                "taste_contribution": round(s_learned, 4),
                "quality_contribution": round(s_quality, 4),
                "fatigue_penalty": round(p_fatigue, 4),
                "matched_positive_attributes": matched_liked,
                "matched_negative_attributes": matched_disliked,
            }
        )
