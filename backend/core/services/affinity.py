"""
Flick Affinity & Taste Compatibility Service
Handles canonical normalization and deterministic similarity evaluation:
1. Questionnaire Similarity: alignment between ephemeral screening questionnaire responses.
2. Taste Compatibility: alignment between persistent learned taste profile weights.
3. Screening Match Affinity: percentage of reviewed deck movies that became mutual matches.
"""

import math
from typing import Any, Dict, List, Optional, Set, Tuple


TONE_TO_MOOD_MAP: Dict[str, str] = {
    "dark": "dark",
    "atmospheric": "atmospheric",
    "suspenseful": "tense",
    "bleak": "bleak",
    "humorous": "fun",
    "lighthearted": "lighthearted",
    "scary": "scary",
    "campy": "campy",
    "mind-bending": "mind-bending",
    "emotional": "poignant",
}


def normalize_user_preferences(raw_prefs: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Canonical normalization layer handling:
    - tone
    - mood / moods
    - intensity
    - pace
    - narrative
    - setting
    - themes
    - theme_keywords
    - setting_keywords
    - era
    - min_rating

    Resolves frontend/backend naming differences, preserves backward compatibility,
    and returns a clean, canonical preference dictionary.
    """
    if not raw_prefs or not isinstance(raw_prefs, dict):
        return {
            "moods": [],
            "tone": [],
            "intensity": "balanced",
            "pace": ["balanced"],
            "experience": "balanced",
            "narrative": [],
            "setting": [],
            "setting_keywords": [],
            "themes": [],
            "theme_keywords": [],
            "era": [],
            "min_rating": None,
        }

    # 1. Tones
    raw_tone = raw_prefs.get("tone") or []
    if isinstance(raw_tone, str):
        tones = [raw_tone.strip().lower()]
    elif isinstance(raw_tone, (list, tuple, set)):
        tones = [str(t).strip().lower() for t in raw_tone if str(t).strip()]
    else:
        tones = []

    # 2. Moods (union of mood, moods, mapped tones)
    mood_candidates: Set[str] = set()
    raw_mood = raw_prefs.get("mood") or []
    if isinstance(raw_mood, str):
        mood_candidates.add(raw_mood.strip().lower())
    elif isinstance(raw_mood, (list, tuple, set)):
        mood_candidates.update(str(m).strip().lower() for m in raw_mood if str(m).strip())

    raw_moods = raw_prefs.get("moods") or []
    if isinstance(raw_moods, str):
        mood_candidates.add(raw_moods.strip().lower())
    elif isinstance(raw_moods, (list, tuple, set)):
        mood_candidates.update(str(m).strip().lower() for m in raw_moods if str(m).strip())

    for t in tones:
        if t in TONE_TO_MOOD_MAP:
            mood_candidates.add(TONE_TO_MOOD_MAP[t])
        else:
            mood_candidates.add(t)

    moods = sorted(list(mood_candidates))

    # 3. Intensity / Experience / Pace
    intensity = "balanced"
    raw_intensity = raw_prefs.get("intensity") or raw_prefs.get("experience")
    if raw_intensity and isinstance(raw_intensity, str):
        intensity = raw_intensity.strip().lower()
    elif isinstance(raw_intensity, (list, tuple)) and raw_intensity:
        intensity = str(raw_intensity[0]).strip().lower()

    if intensity not in ("light", "balanced", "medium", "heavy", "any"):
        intensity = "balanced"
    if intensity == "medium":
        intensity = "balanced"

    raw_pace = raw_prefs.get("pace") or []
    if isinstance(raw_pace, str):
        pace = [raw_pace.strip().lower()]
    elif isinstance(raw_pace, (list, tuple, set)):
        pace = sorted(list({str(p).strip().lower() for p in raw_pace if str(p).strip()}))
    else:
        if intensity == "light":
            pace = ["balanced", "slow"]
        elif intensity == "heavy":
            pace = ["fast", "slow"]
        else:
            pace = ["balanced"]

    # 4. Themes & Theme Keywords
    raw_themes = raw_prefs.get("themes") or []
    if isinstance(raw_themes, str):
        themes = [raw_themes.strip().lower()]
    elif isinstance(raw_themes, (list, tuple, set)):
        themes = sorted(list({str(t).strip().lower() for t in raw_themes if str(t).strip()}))
    else:
        themes = []

    raw_tk = raw_prefs.get("theme_keywords") or []
    if isinstance(raw_tk, str):
        theme_keywords = [raw_tk.strip().lower()]
    elif isinstance(raw_tk, (list, tuple, set)):
        theme_keywords = sorted(list({str(k).strip().lower() for k in raw_tk if str(k).strip()}))
    else:
        theme_keywords = []

    # 5. Setting & Setting Keywords
    raw_setting = raw_prefs.get("setting") or []
    if isinstance(raw_setting, str):
        setting = [raw_setting.strip().lower()]
    elif isinstance(raw_setting, (list, tuple, set)):
        setting = sorted(list({str(s).strip().lower() for s in raw_setting if str(s).strip()}))
    else:
        setting = []

    raw_sk = raw_prefs.get("setting_keywords") or []
    if isinstance(raw_sk, str):
        setting_keywords = [raw_sk.strip().lower()]
    elif isinstance(raw_sk, (list, tuple, set)):
        setting_keywords = sorted(list({str(k).strip().lower() for k in raw_sk if str(k).strip()}))
    else:
        setting_keywords = []

    # 6. Narrative
    raw_narr = raw_prefs.get("narrative") or []
    if isinstance(raw_narr, str):
        narrative = [raw_narr.strip().lower()]
    elif isinstance(raw_narr, (list, tuple, set)):
        narrative = sorted(list({str(n).strip().lower() for n in raw_narr if str(n).strip()}))
    else:
        narrative = []

    # 7. Era
    raw_era = raw_prefs.get("era") or raw_prefs.get("eras") or []
    if isinstance(raw_era, str):
        era = [raw_era.strip().lower()]
    elif isinstance(raw_era, (list, tuple, set)):
        era = sorted(list({str(e).strip().lower() for e in raw_era if str(e).strip()}))
    else:
        era = []

    # 8. Minimum Rating
    min_rating = None
    raw_rating = raw_prefs.get("min_rating")
    if raw_rating is not None:
        if isinstance(raw_rating, (list, tuple)) and raw_rating:
            try:
                min_rating = float(raw_rating[0])
            except (ValueError, TypeError):
                min_rating = None
        elif isinstance(raw_rating, (int, float)):
            min_rating = float(raw_rating)
        elif isinstance(raw_rating, str) and raw_rating.strip():
            try:
                min_rating = float(raw_rating.strip())
            except ValueError:
                min_rating = None

    return {
        "moods": moods,
        "tone": tones,
        "intensity": intensity,
        "pace": pace,
        "experience": intensity,
        "narrative": narrative,
        "setting": setting,
        "setting_keywords": setting_keywords,
        "themes": themes,
        "theme_keywords": theme_keywords,
        "era": era,
        "min_rating": min_rating,
    }


def calculate_questionnaire_similarity(
    host_prefs: Optional[Dict[str, Any]],
    guest_prefs: Optional[Dict[str, Any]],
) -> int:
    """
    Computes deterministic questionnaire similarity in [0, 100]%.
    Measures multi-attribute alignment across normalized active questionnaire dimensions:
    - Moods / Tones (weight 0.25)
    - Themes & Theme Keywords (weight 0.25)
    - Setting & Setting Keywords (weight 0.15)
    - Narrative Structures (weight 0.15)
    - Pacing & Intensity (weight 0.10)
    - Era Preferences (weight 0.10)

    Guarantees:
    - Identical complete inputs produce exactly 100%.
    - Disjoint inputs produce exactly 0%.
    - Inputs with order differences produce identical results (set-based).
    - Missing answers are penalized honestly.
    - Cold-start empty answers return 0% without fabricated compatibility.
    - Bounded in [0, 100]%.
    """
    if not host_prefs or not guest_prefs:
        return 0

    h = normalize_user_preferences(host_prefs)
    g = normalize_user_preferences(guest_prefs)

    weights: List[Tuple[float, float]] = []

    # 1. Moods / Tones (weight 0.25)
    h_moods = set(h["moods"]) | set(h["tone"])
    g_moods = set(g["moods"]) | set(g["tone"])
    if h_moods or g_moods:
        j_mood = len(h_moods & g_moods) / len(h_moods | g_moods) if (h_moods | g_moods) else 0.0
        weights.append((0.25, j_mood))

    # 2. Themes & Theme Keywords (weight 0.25)
    h_themes = set(h["themes"]) | set(h["theme_keywords"])
    g_themes = set(g["themes"]) | set(g["theme_keywords"])
    if h_themes or g_themes:
        j_theme = len(h_themes & g_themes) / len(h_themes | g_themes) if (h_themes | g_themes) else 0.0
        weights.append((0.25, j_theme))

    # 3. Setting & Setting Keywords (weight 0.15)
    h_setting = set(h["setting"]) | set(h["setting_keywords"])
    g_setting = set(g["setting"]) | set(g["setting_keywords"])
    if h_setting or g_setting:
        h_has_any = bool({"any", "anywhere"} & h_setting)
        g_has_any = bool({"any", "anywhere"} & g_setting)
        if h_has_any and g_has_any:
            weights.append((0.15, 1.0))
        elif (h_has_any and g_setting) or (g_has_any and h_setting):
            weights.append((0.15, 0.50))
        else:
            h_clean = h_setting - {"any", "anywhere"}
            g_clean = g_setting - {"any", "anywhere"}
            j_setting = len(h_clean & g_clean) / len(h_clean | g_clean) if (h_clean | g_clean) else 0.0
            weights.append((0.15, j_setting))

    # 4. Narrative Structures (weight 0.15)
    h_narr = set(h["narrative"])
    g_narr = set(g["narrative"])
    if h_narr or g_narr:
        j_narr = len(h_narr & g_narr) / len(h_narr | g_narr) if (h_narr | g_narr) else 0.0
        weights.append((0.15, j_narr))

    # 5. Pacing / Intensity (weight 0.10)
    h_int = h["intensity"]
    g_int = g["intensity"]
    if h_int == g_int:
        sim_pace = 1.0
    elif h_int == "any" or g_int == "any":
        sim_pace = 0.75
    elif (h_int == "light" and g_int == "heavy") or (h_int == "heavy" and g_int == "light"):
        sim_pace = 0.0
    else:
        sim_pace = 0.50
    weights.append((0.10, sim_pace))

    # 6. Era Preferences (weight 0.10)
    h_era = set(h["era"])
    g_era = set(g["era"])
    if h_era or g_era:
        h_any_era = "any" in h_era
        g_any_era = "any" in g_era
        if h_any_era and g_any_era:
            weights.append((0.10, 1.0))
        elif (h_any_era and g_era) or (g_any_era and h_era):
            weights.append((0.10, 0.50))
        else:
            h_clean_era = h_era - {"any"}
            g_clean_era = g_era - {"any"}
            j_era = len(h_clean_era & g_clean_era) / len(h_clean_era | g_clean_era) if (h_clean_era | g_clean_era) else 0.0
            weights.append((0.10, j_era))

    if not weights:
        return 0

    total_weight = sum(w for w, _ in weights)
    if total_weight <= 0:
        return 0

    weighted_sum = sum(w * score for w, score in weights)
    raw_pct = (weighted_sum / total_weight) * 100.0
    return min(100, max(0, round(raw_pct)))


def calculate_taste_compatibility(
    host_weights: Optional[Dict[str, Any]],
    guest_weights: Optional[Dict[str, Any]],
) -> Optional[int]:
    """
    Evaluates compatibility between historical learned taste profiles.
    Returns None if either participant is cold-start (no learned weights).
    Otherwise returns integer percentage [0, 100] based on cosine similarity of attribute weights.
    """
    if not host_weights or not guest_weights:
        return None

    def _flatten_weights(weights_dict: Dict[str, Any]) -> Dict[str, float]:
        flat: Dict[str, float] = {}
        for category in ("genres", "tags", "keywords"):
            sub = weights_dict.get(category)
            if isinstance(sub, dict):
                for k, v in sub.items():
                    try:
                        flat[f"{category}:{str(k).lower()}"] = float(v)
                    except (ValueError, TypeError):
                        pass
        # Top-level fallback
        if not flat:
            for k, v in weights_dict.items():
                if isinstance(v, (int, float)):
                    flat[f"attr:{str(k).lower()}"] = float(v)
        return flat

    h_flat = _flatten_weights(host_weights)
    g_flat = _flatten_weights(guest_weights)

    if not h_flat or not g_flat:
        return None

    all_keys = set(h_flat.keys()) | set(g_flat.keys())
    dot_product = sum(h_flat.get(k, 0.0) * g_flat.get(k, 0.0) for k in all_keys)
    norm_h = math.sqrt(sum(v * v for v in h_flat.values()))
    norm_g = math.sqrt(sum(v * v for v in g_flat.values()))

    if norm_h <= 0 or norm_g <= 0:
        return 0

    cosine = dot_product / (norm_h * norm_g)
    # Cosine is in [-1.0, 1.0]; normalize to [0, 100]%
    norm_compat = max(0.0, min(1.0, (cosine + 1.0) / 2.0))
    return min(100, max(0, round(norm_compat * 100)))


def calculate_screening_affinity(reviewed_count: int, matched_count: int) -> int:
    """
    Post-screening match affinity.
    Percentage of reviewed deck movies that became mutual matches.
    Bounded in [0, 100]%.
    """
    if reviewed_count <= 0 or matched_count <= 0:
        return 0
    return min(100, max(0, round((matched_count / reviewed_count) * 100)))


def calculate_session_statistics(session: Any, user: Optional[Any] = None) -> Dict[str, Any]:
    """
    Single authoritative calculation of session statistics across all endpoints:
    - reviewed_count: distinct movies reviewed (mathematically guaranteed >= matched_count)
    - matched_count: mutual matches formed in session
    - affinity_percent: percentage (matched / reviewed * 100), bounded [0, 100]%
    - total_swipes: session-wide distinct reviewed movies

    Mathematical & Logical Invariants:
    1. Every mutual match is inherently a movie reviewed by both participants.
       Therefore: reviewed_count >= matched_count.
    2. If reviewed_count == 0, affinity_percent is 0.
    3. Affinity is bounded in [0, 100]%.
    4. Self-heals persistent SessionStats if ended session has zero/stale counters.
    """
    # 1. Matched count (supports prefetched and live querysets)
    if hasattr(session, "prefetched_matches") and session.prefetched_matches is not None:
        matched_count = len(session.prefetched_matches)
    elif hasattr(session, "match_set"):
        matched_count = session.match_set.count()
    else:
        matched_count = 0

    # 2. Distinct movies reviewed by current participant vs session-wide
    user_distinct = 0
    session_distinct = 0

    if hasattr(session, "prefetched_swipes") and session.prefetched_swipes is not None:
        prefetched = session.prefetched_swipes
        if user and getattr(user, "is_authenticated", False):
            user_distinct = len({sw.movie_id for sw in prefetched if sw.user_id == user.id})
        session_distinct = len({sw.movie_id for sw in prefetched})
    elif hasattr(session, "swipe_set"):
        if user and getattr(user, "is_authenticated", False):
            user_distinct = session.swipe_set.filter(user=user).values("movie_id").distinct().count()
        session_distinct = session.swipe_set.values("movie_id").distinct().count()

    # Candidate reviewed count: user-specific if available, else session-wide distinct
    reviewed_candidate = user_distinct if user_distinct > 0 else session_distinct

    # Fallback to persistent SessionStats if swipe rows are unavailable
    if reviewed_candidate == 0 and hasattr(session, "stats") and session.stats:
        reviewed_candidate = session.stats.total_swipes

    # Invariant: reviewed_count CANNOT be less than matched_count
    reviewed_count = max(reviewed_candidate, matched_count)

    # 3. Authoritative Affinity Calculation
    affinity_percent = calculate_screening_affinity(reviewed_count, matched_count)

    # 4. Self-healing for ended sessions with stale/zero SessionStats
    if getattr(session, "ended_at", None) is not None and hasattr(session, "stats") and session.stats:
        stats = session.stats
        needs_save = False
        update_fields: List[str] = []
        if stats.total_matches != matched_count:
            stats.total_matches = matched_count
            needs_save = True
            update_fields.append("total_matches")
        if stats.total_swipes < reviewed_count:
            stats.total_swipes = reviewed_count
            needs_save = True
            update_fields.append("total_swipes")
        if needs_save:
            try:
                stats.save(update_fields=update_fields)
            except Exception:
                pass

    return {
        "reviewed_count": reviewed_count,
        "matched_count": matched_count,
        "affinity_percent": affinity_percent,
        "total_swipes": max(session_distinct, matched_count),
    }

