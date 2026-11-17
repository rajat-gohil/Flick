import logging
import re
import threading
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, IntegrityError
from core.logging import get_correlation_id

logger = logging.getLogger(__name__)

BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
# Bounded split timeout: (connect_timeout, read_timeout)
TIMEOUT = (3.05, 12.0)

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURABLE REDIS CACHE TTLs (in seconds)
# ─────────────────────────────────────────────────────────────────────────────
CACHE_TTL_TRENDING = getattr(settings, "TMDB_CACHE_TTL_TRENDING", 3600)         # 1 hour
CACHE_TTL_POPULAR = getattr(settings, "TMDB_CACHE_TTL_POPULAR", 3600)           # 1 hour
CACHE_TTL_NOW_PLAYING = getattr(settings, "TMDB_CACHE_TTL_NOW_PLAYING", 3600)   # 1 hour
CACHE_TTL_TOP_RATED = getattr(settings, "TMDB_CACHE_TTL_TOP_RATED", 21600)     # 6 hours
CACHE_TTL_UPCOMING = getattr(settings, "TMDB_CACHE_TTL_UPCOMING", 21600)       # 6 hours
CACHE_TTL_SEARCH = getattr(settings, "TMDB_CACHE_TTL_SEARCH", 1800)             # 30 minutes
CACHE_TTL_DISCOVER = getattr(settings, "TMDB_CACHE_TTL_DISCOVER", 1800)         # 30 minutes
CACHE_TTL_DETAILS = getattr(settings, "TMDB_CACHE_TTL_DETAILS", 86400)         # 24 hours
CACHE_TTL_GENRES = getattr(settings, "TMDB_CACHE_TTL_GENRES", 86400 * 7)        # 7 days
CACHE_TTL_STALE = getattr(settings, "TMDB_CACHE_TTL_STALE", 86400 * 7)          # 7 days backup

INDIAN_LANGUAGES = [
    "hi", "gu", "mr", "ta", "te", "ml", "kn", "bn",
    "pa", "as", "or", "ur"
]


class TMDBServiceError(Exception):
    """Base exception for TMDB API service errors."""
    pass


class TMDBTimeoutError(TMDBServiceError):
    """Raised when TMDB API requests timeout."""
    pass


class TMDBAPIError(TMDBServiceError):
    """Raised when TMDB returns an HTTP error status."""
    pass


def redact_sensitive_params(msg: object) -> str:
    """
    Redacts sensitive credentials (such as TMDB API keys or auth tokens)
    from log messages, exception strings, or URLs.
    """
    if not msg:
        return ""
    text = str(msg)
    # Redact query params: api_key=...
    text = re.sub(r'([?&]api_key=)[^&\s"\']+', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    # Redact Authorization header token if present
    text = re.sub(r'(Bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    # Redact configured API key if present
    api_key = getattr(settings, "TMDB_API_KEY", None)
    if api_key and len(str(api_key)) > 5 and str(api_key) in text:
        text = text.replace(str(api_key), "[REDACTED]")
    return text


# ─────────────────────────────────────────────────────────────────────────────
# THREAD-LOCAL CONNECTION POOLING & RESILIENT RETRIES
# ─────────────────────────────────────────────────────────────────────────────

_thread_local = threading.local()


def _create_tmdb_session() -> requests.Session:
    """
    Creates an HTTP session with pooled connections, exponential backoff,
    full random jitter, Retry-After header handling, and connection reset resilience.
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        backoff_jitter=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(
        max_retries=retry,
        pool_connections=10,
        pool_maxsize=20,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    })
    return session


def get_tmdb_session() -> requests.Session:
    """
    Thread-local pooled session accessor.
    Guarantees thread-safety across concurrent ASGI/WSGI worker threads
    while maintaining socket/connection pooling per thread.
    """
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = _create_tmdb_session()
        _thread_local.session = session
    return session


def reset_tmdb_session() -> None:
    """
    Safely closes and resets the thread-local session for testing or cleanup.
    """
    session = getattr(_thread_local, "session", None)
    if session is not None:
        try:
            session.close()
        except Exception:
            pass
        _thread_local.session = None


# Alias for backwards compatibility
_get_session = get_tmdb_session


def _get_tmdb_request_headers() -> dict:
    """
    Build per-request headers including correlation ID if set.
    Passed per-request to avoid mutating shared Session defaults.
    """
    cid = get_correlation_id()
    if cid and cid != "-":
        return {"X-Request-ID": cid, "X-Correlation-ID": cid}
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# REDIS CACHING HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _make_cache_key(*parts) -> str:
    """
    Deterministic Redis cache key generator.
    Normalizes strings, strips invalid characters, and joins with colons.
    """
    sanitized = []
    for p in parts:
        if p is None or p == "":
            continue
        cleaned = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", str(p).strip().lower())
        sanitized.append(cleaned)
    return "tmdb:" + ":".join(sanitized)


def fetch_cached_tmdb(cache_key: str, fetch_fn, ttl: int):
    """
    Hybrid caching workflow:
    1. Check Redis for active cached response.
    2. If found, return cached data and source="cache".
    3. If miss, invoke fetch_fn().
    4. On success, store in cache and stale cache, return data and source="tmdb".
    5. On error/timeout, check stale cache fallback; if found return source="stale_cache".
    6. If all fails, raise exception for caller to handle local database fallback.
    """
    try:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result, "cache"
    except Exception as e:
        logger.warning(f"Redis cache lookup error for key {cache_key}: {e}")

    try:
        # Acquire interactive token from shared rate limiter
        try:
            from core.services.tmdb_rate_limiter import acquire_tmdb_token, RedisRateLimiterUnavailableError
            token_acquired = acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=1.5)
            if not token_acquired:
                logger.warning(f"Interactive TMDB token acquisition rejected for key {cache_key}")
                try:
                    stale = cache.get(f"{cache_key}:stale")
                    if stale is not None:
                        logger.info(f"Serving stale cache for key {cache_key} following rate limit rejection")
                        return stale, "stale_cache"
                except Exception:
                    pass
                raise TMDBServiceError(f"TMDB rate limit budget exhausted for key {cache_key}")
        except RedisRateLimiterUnavailableError as e:
            logger.error(f"Redis rate limiter unavailable in production for {cache_key}: {e}")
            try:
                stale = cache.get(f"{cache_key}:stale")
                if stale is not None:
                    logger.info(f"Serving stale cache for key {cache_key} following Redis rate limiter failure")
                    return stale, "stale_cache"
            except Exception:
                pass
            raise TMDBServiceError(f"TMDB rate limiter unavailable; failing closed in production for {cache_key}") from e
        except ImportError:
            pass

        fresh_data = fetch_fn()
        try:
            cache.set(cache_key, fresh_data, timeout=ttl)
            cache.set(f"{cache_key}:stale", fresh_data, timeout=CACHE_TTL_STALE)
        except Exception as e:
            logger.warning(f"Redis cache write error for key {cache_key}: {e}")
        return fresh_data, "tmdb"
    except (requests.exceptions.Timeout, TMDBTimeoutError) as e:
        logger.warning(redact_sensitive_params(f"TMDB request timed out for key {cache_key}: {e}"))
        try:
            stale = cache.get(f"{cache_key}:stale")
            if stale is not None:
                logger.info(f"Serving stale cache for key {cache_key} following TMDB timeout")
                return stale, "stale_cache"
        except Exception:
            pass
        raise TMDBTimeoutError(redact_sensitive_params(f"TMDB request timed out: {e}")) from None
    except requests.exceptions.HTTPError as e:
        status_code = getattr(getattr(e, "response", None), "status_code", None)
        if status_code == 429:
            resp_headers = getattr(e.response, "headers", {}) if (getattr(e, "response", None) is not None) else {}
            retry_after = None
            if hasattr(resp_headers, "get"):
                retry_after = resp_headers.get("Retry-After") or resp_headers.get("retry-after")
            logger.warning(redact_sensitive_params(f"TMDB HTTP 429 Rate Limit encountered for key {cache_key}. Retry-After: {retry_after}"))
            try:
                from core.services.tmdb_rate_limiter import record_tmdb_429
                record_tmdb_429(retry_after)
            except Exception as r_err:
                logger.error(f"Failed to record TMDB 429 cooldown: {r_err}")
            try:
                stale = cache.get(f"{cache_key}:stale")
                if stale is not None:
                    logger.info(f"Serving stale cache for key {cache_key} following TMDB HTTP 429")
                    return stale, "stale_cache"
            except Exception:
                pass
            raise TMDBServiceError(f"TMDB HTTP 429 Too Many Requests: {e}") from e

        logger.warning(redact_sensitive_params(f"TMDB HTTP error for key {cache_key} (status={status_code}): {e}"))
        try:
            stale = cache.get(f"{cache_key}:stale")
            if stale is not None:
                logger.info(f"Serving stale cache for key {cache_key} following TMDB HTTP error")
                return stale, "stale_cache"
        except Exception:
            pass
        raise TMDBServiceError(redact_sensitive_params(f"TMDB HTTP error: {e}")) from None
    except Exception as e:
        # Check if underlying response was a 429
        resp = getattr(e, "response", None)
        if resp is not None and getattr(resp, "status_code", None) == 429:
            retry_after = resp.headers.get("Retry-After")
            logger.warning(redact_sensitive_params(f"TMDB 429 encountered in general exception for key {cache_key}. Retry-After: {retry_after}"))
            try:
                from core.services.tmdb_rate_limiter import record_tmdb_429
                record_tmdb_429(retry_after)
            except Exception as r_err:
                logger.error(f"Failed to record TMDB 429 cooldown: {r_err}")

        logger.warning(redact_sensitive_params(f"TMDB request error for key {cache_key}: {e}"))
        try:
            stale = cache.get(f"{cache_key}:stale")
            if stale is not None:
                logger.info(f"Serving stale cache for key {cache_key} following TMDB error")
                return stale, "stale_cache"
        except Exception:
            pass
        raise TMDBServiceError(redact_sensitive_params(f"TMDB request error: {e}")) from None


# ─────────────────────────────────────────────────────────────────────────────
# CORE TMDB API CLIENT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_trending_movies(time_window: str = "day", page: int = 1):
    """
    Fetch trending movies from TMDB (/trending/movie/{time_window}).
    time_window: 'day' or 'week'
    """
    valid_window = "week" if time_window == "week" else "day"
    cache_key = _make_cache_key("trending", valid_window, "page", page)

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/trending/movie/{valid_window}",
            params={"api_key": settings.TMDB_API_KEY, "page": page},
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_TRENDING)


def get_popular_movies(page: int = 1):
    """
    Fetch popular movies from TMDB (/movie/popular).
    Uses data directly from TMDB response to avoid N+1 sequential requests.
    """
    cache_key = _make_cache_key("popular", "page", page)

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/movie/popular",
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": "en-US",
                "page": page,
            },
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_POPULAR)


def get_top_rated_movies(page: int = 1):
    """
    Fetch top-rated movies from TMDB (/movie/top_rated).
    """
    cache_key = _make_cache_key("top_rated", "page", page)

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/movie/top_rated",
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": "en-US",
                "page": page,
            },
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_TOP_RATED)


def get_now_playing_movies(page: int = 1):
    """
    Fetch now-playing movies from TMDB (/movie/now_playing).
    """
    cache_key = _make_cache_key("now_playing", "page", page)

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/movie/now_playing",
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": "en-US",
                "page": page,
            },
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_NOW_PLAYING)


def get_upcoming_movies(page: int = 1):
    """
    Fetch upcoming movies from TMDB (/movie/upcoming).
    """
    cache_key = _make_cache_key("upcoming", "page", page)

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/movie/upcoming",
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": "en-US",
                "page": page,
            },
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_UPCOMING)


def search_movies(query: str, page: int = 1, year=None):
    """
    Search TMDB movie catalogue by keyword or title (/search/movie).
    """
    q_clean = query.strip()
    cache_key = _make_cache_key("search", q_clean, "year", year or "any", "page", page)

    def _fetch():
        session = _get_session()
        params = {
            "api_key": settings.TMDB_API_KEY,
            "query": q_clean,
            "page": page,
            "include_adult": False,
            "language": "en-US",
        }
        if year:
            params["primary_release_year"] = year
        res = session.get(
            f"{BASE_URL}/search/movie",
            params=params,
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_SEARCH)


def discover_movies(
    page: int = 1,
    language: str = None,
    genre_id=None,
    sort_by: str = "popularity.desc",
    year=None,
    era: str = None,
    min_rating=None,
    region: str = None,
    vote_count_gte: Optional[int] = None,
    watch_provider_id: Optional[str] = None,
    watch_region: Optional[str] = None,
):
    """
    Discover movies using TMDB's /discover/movie endpoint with comprehensive filtering.
    Supports genre, original language, year, era ranges, minimum rating, region,
    and adaptive vote count thresholds for regional and classic Indian cinema.
    """
    if vote_count_gte is not None:
        effective_vote_count = max(0, int(vote_count_gte))
    elif era and str(era).lower() in ("before_1990", "pre_1990", "classic", "1970s", "1980s"):
        effective_vote_count = 1  # Classic eras have fewer TMDB ratings
    elif language and language in INDIAN_LANGUAGES and language not in ("hi", "ta", "te"):
        effective_vote_count = 2  # Regional Indian languages have lower TMDB vote density
    else:
        effective_vote_count = 10

    params = {
        "api_key": settings.TMDB_API_KEY,
        "sort_by": sort_by or "popularity.desc",
        "page": page,
        "vote_count.gte": effective_vote_count,
        "include_adult": False,
    }
    if language and language != "all":
        params["with_original_language"] = language
    if genre_id:
        params["with_genres"] = str(genre_id)
    if min_rating and str(min_rating) != "any":
        try:
            params["vote_average.gte"] = float(min_rating)
        except (ValueError, TypeError):
            pass

    if year:
        params["primary_release_year"] = int(year)
    elif era and era != "any":
        era_lower = str(era).lower()
        if era_lower in ("before_1990", "pre_1990", "classic"):
            params["primary_release_date.lte"] = "1989-12-31"
        elif era_lower == "recent":
            params["primary_release_date.gte"] = "2020-01-01"
        elif era_lower == "2010s":
            params["primary_release_date.gte"] = "2010-01-01"
            params["primary_release_date.lte"] = "2019-12-31"
        elif era_lower == "2000s":
            params["primary_release_date.gte"] = "2000-01-01"
            params["primary_release_date.lte"] = "2009-12-31"
        elif era_lower == "90s":
            params["primary_release_date.gte"] = "1990-01-01"
            params["primary_release_date.lte"] = "1999-12-31"

    if region:
        params["region"] = region.strip().upper()

    if watch_provider_id:
        params["with_watch_providers"] = str(watch_provider_id)
        effective_watch_region = (watch_region or region or getattr(settings, "DEFAULT_STREAMING_REGION", "IN") or "IN").strip().upper()
        params["watch_region"] = effective_watch_region

    cache_key = _make_cache_key(
        "discover",
        "lang", language or "all",
        "genre", genre_id or "all",
        "sort", sort_by,
        "year", year or "any",
        "era", era or "any",
        "min_rating", min_rating or "any",
        "region", region or "all",
        "wp", watch_provider_id or "all",
        "wr", watch_region or "all",
        "vc", effective_vote_count,
        "page", page,
    )

    def _fetch():
        session = _get_session()
        response = session.get(
            f"{BASE_URL}/discover/movie",
            params=params,
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_DISCOVER)


def get_movie_by_tmdb_id(tmdb_id: int):
    """
    Fetch single movie details from TMDB with videos and credits appended.
    Cached for 24 hours.
    """
    cache_key = _make_cache_key("movie", tmdb_id, "details")

    def _fetch():
        session = _get_session()
        res = session.get(
            f"{BASE_URL}/movie/{tmdb_id}",
            params={
                "api_key": settings.TMDB_API_KEY,
                "language": "en-US",
                "append_to_response": "videos,credits",
            },
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        return res.json()

    return fetch_cached_tmdb(cache_key, _fetch, CACHE_TTL_DETAILS)


def get_genres_map() -> dict:
    """
    Return dictionary of {genre_id: genre_name} cached for 7 days.
    """
    cache_key = "tmdb:genres:map"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    session = _get_session()
    try:
        response = session.get(
            f"{BASE_URL}/genre/movie/list",
            params={"api_key": settings.TMDB_API_KEY, "language": "en-US"},
            headers=_get_tmdb_request_headers(),
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        mapping = {g["id"]: g["name"] for g in response.json().get("genres", [])}
        cache.set(cache_key, mapping, timeout=CACHE_TTL_GENRES)
        return mapping
    except Exception as e:
        logger.warning(f"Failed to fetch genres map from TMDB: {redact_sensitive_params(str(e))}")
        # Fallback to local Genre model
        from core.models import Genre
        return {g.tmdb_id: g.name for g in Genre.objects.filter(tmdb_id__isnull=False)}


def get_movie_genres(tmdb_id):
    """Get list of genre IDs for a movie."""
    try:
        movie_data, _ = get_movie_by_tmdb_id(tmdb_id)
        return [g["id"] for g in movie_data.get("genres", []) if "id" in g]
    except Exception:
        return []


def get_tmdb_genres():
    """Return raw list of genre dictionaries."""
    session = _get_session()
    url = f"{BASE_URL}/genre/movie/list"
    params = {"api_key": settings.TMDB_API_KEY, "language": "en-US"}
    res = session.get(url, params=params, headers=_get_tmdb_request_headers(), timeout=TIMEOUT)
    res.raise_for_status()
    return res.json().get("genres", [])


def get_movie_trailer_key(tmdb_id):
    """Get the YouTube trailer key for a movie from TMDB videos."""
    try:
        movie_data, _ = get_movie_by_tmdb_id(tmdb_id)
        for v in movie_data.get("videos", {}).get("results", []):
            if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
                return v.get("key")
    except Exception:
        pass
    return None


def get_enhanced_movie_details(tmdb_id):
    """Get enhanced movie details including trailers and ratings."""
    try:
        movie_data, _ = get_movie_by_tmdb_id(tmdb_id)
        trailer_url = None
        if movie_data.get("videos", {}).get("results"):
            trailers = [
                v for v in movie_data["videos"]["results"]
                if v.get("type") == "Trailer" and v.get("site") == "YouTube"
            ]
            if trailers:
                trailer_url = f"https://www.youtube.com/watch?v={trailers[0]['key']}"

        return {
            "description": movie_data.get("overview", ""),
            "trailer_url": trailer_url,
            "imdb_id": movie_data.get("imdb_id"),
            "runtime": movie_data.get("runtime"),
            "release_date": movie_data.get("release_date"),
            "vote_average": movie_data.get("vote_average"),
            "vote_count": movie_data.get("vote_count"),
        }
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# DATA NORMALIZATION & ON-DEMAND PERSISTENCE
# ─────────────────────────────────────────────────────────────────────────────

def format_tmdb_movie(item: dict, local_movie_id: int = None, genres_map: dict = None) -> dict:
    """
    Normalize TMDB movie object to match MovieSerializer fields consumed by frontend.
    """
    poster_path = item.get("poster_path")
    backdrop_path = item.get("backdrop_path")
    release_date_str = item.get("release_date") or None
    release_year = None
    if release_date_str:
        try:
            release_year = int(release_date_str[:4])
        except (ValueError, TypeError):
            pass

    genre_ids = item.get("genre_ids") or []
    genre_names = []
    if genres_map:
        genre_names = [genres_map[gid] for gid in genre_ids if gid in genres_map]
    elif item.get("genres"):
        genre_names = [g.get("name") for g in item.get("genres", []) if isinstance(g, dict) and g.get("name")]

    rating_raw = item.get("vote_average")
    rating_rounded = round(float(rating_raw), 1) if rating_raw is not None else None

    return {
        "id": local_movie_id,
        "tmdb_id": item.get("id"),
        "title": item.get("title") or item.get("name") or "",
        "overview": item.get("overview") or "",
        "release_date": release_date_str,
        "release_year": release_year,
        "rating": rating_rounded,
        "vote_count": item.get("vote_count") or 0,
        "original_language": item.get("original_language"),
        "poster_path": poster_path,
        "poster_url": f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else None,
        "backdrop_path": backdrop_path,
        "backdrop_url": f"https://image.tmdb.org/t/p/w780{backdrop_path}" if backdrop_path else None,
        "trailer_url": None,
        "genres": genre_names,
        "tmdb_genre_ids": genre_ids,
    }


def get_or_create_movie_from_tmdb(tmdb_id: int):
    """
    Atomically get or create a local PostgreSQL Movie record from TMDB.
    Persists only when required (e.g. Watchlist, Swipe, Session Match).
    Handles concurrency safely using transaction.atomic.
    """
    from core.models import Movie, Genre

    if not tmdb_id:
        return None, False

    # 1. Quick check if already stored locally
    existing = Movie.objects.filter(tmdb_id=tmdb_id).first()
    if existing:
        return existing, False

    # 2. Fetch movie data from TMDB / Redis
    try:
        movie_data, _ = get_movie_by_tmdb_id(tmdb_id)
    except Exception as e:
        logger.error(redact_sensitive_params(f"Failed to fetch details for tmdb_id={tmdb_id}: {e}"))
        return None, False

    title = movie_data.get("title") or movie_data.get("name")
    if not title:
        return None, False

    release_date_str = movie_data.get("release_date") or None
    raw_genre_ids = [g["id"] for g in movie_data.get("genres", []) if isinstance(g, dict) and "id" in g]

    # Find YouTube trailer key if available
    trailer_key = None
    for v in movie_data.get("videos", {}).get("results", []):
        if v.get("site") == "YouTube" and v.get("type") in ["Trailer", "Teaser"]:
            trailer_key = v.get("key")
            break

    # 3. Create atomically
    try:
        with transaction.atomic():
            movie, created = Movie.objects.get_or_create(
                tmdb_id=tmdb_id,
                defaults={
                    "title": title,
                    "overview": movie_data.get("overview") or "",
                    "poster_path": movie_data.get("poster_path") or "",
                    "backdrop_path": movie_data.get("backdrop_path") or "",
                    "release_date": release_date_str,
                    "rating": movie_data.get("vote_average"),
                    "vote_count": movie_data.get("vote_count"),
                    "original_language": movie_data.get("original_language"),
                    "tmdb_genre_ids": raw_genre_ids,
                    "trailer_key": trailer_key,
                    "provenance": "tmdb_catalogue",
                }
            )
            if created and raw_genre_ids:
                matching_genres = Genre.objects.filter(tmdb_id__in=raw_genre_ids)
                if matching_genres.exists():
                    movie.genres.add(*matching_genres)

            if created:
                from core.services.catalogue_eligibility import recalculate_movie_eligibility
                recalculate_movie_eligibility(movie, commit=True)

            return movie, created
    except IntegrityError:
        # Concurrent insert resolved
        movie = Movie.objects.filter(tmdb_id=tmdb_id).first()
        return movie, False


# ─────────────────────────────────────────────────────────────────────────────
# EXISTING BATCH SYNC & STREAMING UTILITIES (PRESERVED)
# ─────────────────────────────────────────────────────────────────────────────

def sync_tmdb_movies_for_criteria(genres=None, industry=None, languages=None, max_pages=2, era=None, min_rating=None):
    """
    Sync real movies from TMDB for the given criteria directly into the database.
    Safe and idempotent. Supports era and min_rating filtering.
    """
    if not getattr(settings, "TMDB_API_KEY", None):
        return 0

    target_languages = []
    if languages:
        target_languages = list(languages)
    elif industry == "bollywood":
        target_languages = ["hi"]
    elif industry == "hollywood":
        target_languages = ["en"]
    else:
        target_languages = ["en", "hi"]

    genre_tmdb_ids = []
    if genres:
        for g in genres:
            if hasattr(g, "tmdb_id") and g.tmdb_id:
                genre_tmdb_ids.append(g.tmdb_id)
            elif isinstance(g, int):
                genre_tmdb_ids.append(g)

    created_count = 0

    for lang in target_languages:
        for page in range(1, max_pages + 1):
            try:
                if genre_tmdb_ids:
                    for g_id in genre_tmdb_ids:
                        res, _ = discover_movies(page=page, language=lang, genre_id=g_id, era=era, min_rating=min_rating)
                        created_count += _ingest_tmdb_results(res.get("results", []))
                else:
                    res, _ = discover_movies(page=page, language=lang, era=era, min_rating=min_rating)
                    created_count += _ingest_tmdb_results(res.get("results", []))
            except Exception as e:
                logger.warning(redact_sensitive_params(f"Error discovering TMDB movies (lang={lang}, page={page}): {e}"))

    return created_count


def _ingest_tmdb_results(results):
    """
    Safely ingest TMDB discovery results with provenance guardrails and durable queue handoff:
    1. Newly discovered movies enter 'needs_review' with display_ready=False and recommendable=False.
    2. Enqueues a 'catalogue_classification' job into CatalogueJob for identity verification.
    3. Existing 'manual_curated' records are strictly protected (no downgrade or overwrites).
    4. Existing 'synthetic_fixture' records are strictly protected (no promotion).
    5. Existing 'tmdb_catalogue' records update non-manual fields and recalculate eligibility.
    6. Existing 'needs_review' records ensure a classification job is queued.
    """
    from core.models import Movie, Genre
    from core.services.catalogue_queue import CatalogueQueueService
    from core.services.catalogue_eligibility import recalculate_movie_eligibility
    from django.utils import timezone

    created_count = 0
    now_iso = timezone.now().isoformat()

    for item in results:
        tmdb_id = item.get("id")
        if not tmdb_id or not item.get("title"):
            continue

        raw_genre_ids = item.get("genre_ids", [])
        existing_movie = Movie.objects.filter(tmdb_id=tmdb_id).first()

        if existing_movie:
            movie = existing_movie
            # Safeguard 1: Manual curated records are strictly protected
            if movie.provenance == "manual_curated":
                logger.info(f"Skipping unverified discovery overwrite for manual_curated movie {movie.id} ({movie.title})")
                continue

            # Safeguard 2: Synthetic fixtures remain synthetic fixtures
            if movie.provenance == "synthetic_fixture":
                logger.info(f"Skipping discovery overwrite for synthetic_fixture movie {movie.id} ({movie.title})")
                continue

            fp = movie.field_provenance if isinstance(movie.field_provenance, dict) else {}

            # Update non-manual fields safely
            updated_fields = []
            if fp.get("title", {}).get("source") != "manual" and item.get("title"):
                movie.title = item["title"]
                updated_fields.append("title")
            if fp.get("overview", {}).get("source") != "manual" and item.get("overview") is not None:
                movie.overview = item.get("overview", "") or ""
                updated_fields.append("overview")
            if fp.get("poster_path", {}).get("source") != "manual" and item.get("poster_path") is not None:
                movie.poster_path = item.get("poster_path") or ""
                updated_fields.append("poster_path")
            if fp.get("backdrop_path", {}).get("source") != "manual" and item.get("backdrop_path") is not None:
                movie.backdrop_path = item.get("backdrop_path") or ""
                updated_fields.append("backdrop_path")
            if fp.get("release_date", {}).get("source") != "manual" and item.get("release_date") is not None:
                movie.release_date = item.get("release_date") or None
                updated_fields.append("release_date")
            if fp.get("rating", {}).get("source") != "manual" and item.get("vote_average") is not None:
                movie.rating = item.get("vote_average")
                updated_fields.append("rating")
            if fp.get("vote_count", {}).get("source") != "manual" and item.get("vote_count") is not None:
                movie.vote_count = item.get("vote_count")
                updated_fields.append("vote_count")
            if fp.get("original_language", {}).get("source") != "manual" and item.get("original_language"):
                movie.original_language = item.get("original_language")
                updated_fields.append("original_language")

            if raw_genre_ids:
                movie.tmdb_genre_ids = raw_genre_ids
                updated_fields.append("tmdb_genre_ids")

            if updated_fields:
                movie.save(update_fields=updated_fields)

            if raw_genre_ids:
                matching_genres = Genre.objects.filter(tmdb_id__in=raw_genre_ids)
                if matching_genres.exists():
                    movie.genres.add(*matching_genres)

            if movie.provenance == "tmdb_catalogue":
                # Recalculate eligibility in case metadata or genres improved
                recalculate_movie_eligibility(movie, commit=True)
            elif movie.provenance == "needs_review":
                recalculate_movie_eligibility(movie, commit=True)
                try:
                    CatalogueQueueService.enqueue(
                        job_type="catalogue_classification",
                        entity_type="movie",
                        entity_id=str(movie.id),
                        external_id=str(movie.tmdb_id),
                        priority=50,
                        payload={"source": "tmdb_replenishment", "original_language": movie.original_language},
                    )
                except Exception as e:
                    logger.warning(f"Failed to enqueue classification job for existing movie {movie.id}: {e}")

        else:
            # Newly discovered movie: starts in 'needs_review' with display_ready=False, recommendable=False
            initial_fp = {
                field: {"source": "tmdb", "updated_at": now_iso, "actor": "discovery"}
                for field in ["title", "overview", "poster_path", "backdrop_path", "release_date", "rating", "vote_count", "original_language"]
                if item.get(field)
            }
            movie = Movie.objects.create(
                tmdb_id=tmdb_id,
                title=item["title"],
                overview=item.get("overview", "") or "",
                poster_path=item.get("poster_path") or "",
                backdrop_path=item.get("backdrop_path") or "",
                release_date=item.get("release_date") or None,
                rating=item.get("vote_average"),
                vote_count=item.get("vote_count"),
                original_language=item.get("original_language"),
                tmdb_genre_ids=raw_genre_ids,
                provenance="needs_review",
                display_ready=False,
                recommendable=False,
                field_provenance=initial_fp,
            )
            created_count += 1

            if raw_genre_ids:
                matching_genres = Genre.objects.filter(tmdb_id__in=raw_genre_ids)
                if matching_genres.exists():
                    movie.genres.add(*matching_genres)

            # Enqueue durable classification job for upstream identity verification
            try:
                CatalogueQueueService.enqueue(
                    job_type="catalogue_classification",
                    entity_type="movie",
                    entity_id=str(movie.id),
                    external_id=str(movie.tmdb_id),
                    priority=50,
                    payload={"source": "tmdb_discovery", "original_language": movie.original_language},
                )
            except Exception as e:
                logger.warning(f"Failed to enqueue classification job for new movie {movie.id}: {e}")

    return created_count


def get_movie_watch_providers(tmdb_id, region="IN"):
    """
    Fetch watch provider availability for a movie from TMDB's official endpoint:
    GET /3/movie/{movie_id}/watch/providers
    
    Attribution: Data provided by JustWatch via TMDB.
    """
    if not getattr(settings, "TMDB_API_KEY", None):
        raise TMDBServiceError("TMDB_API_KEY is not configured")

    target_region = (region or "IN").strip().upper()
    url = f"{BASE_URL}/movie/{tmdb_id}/watch/providers"
    params = {"api_key": settings.TMDB_API_KEY}

    try:
        from core.services.tmdb_rate_limiter import acquire_tmdb_token, RedisRateLimiterUnavailableError
        token_acquired = acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=1.5)
        if not token_acquired:
            raise TMDBServiceError(f"TMDB rate limit budget exhausted for watch providers of movie {tmdb_id}")
    except RedisRateLimiterUnavailableError as e:
        logger.error(f"Redis rate limiter unavailable in production for watch providers {tmdb_id}: {e}")
        raise TMDBServiceError(f"TMDB rate limiter unavailable; failing closed in production for watch providers {tmdb_id}") from e
    except ImportError:
        pass

    session = _get_session()
    try:
        response = session.get(url, params=params, headers=_get_tmdb_request_headers(), timeout=TIMEOUT)
    except requests.exceptions.Timeout as e:
        logger.warning(redact_sensitive_params(f"TMDB watch provider request timed out for tmdb_id={tmdb_id}: {e}"))
        raise TMDBTimeoutError(f"TMDB watch provider request timed out for tmdb_id={tmdb_id}") from None
    except requests.exceptions.RequestException as e:
        logger.warning(redact_sensitive_params(f"TMDB watch provider connection error for tmdb_id={tmdb_id}: {e}"))
        raise TMDBServiceError(redact_sensitive_params(f"TMDB connection error: {str(e)}")) from None

    if response.status_code == 429:
        try:
            from core.services.tmdb_rate_limiter import record_tmdb_429
            record_tmdb_429(response.headers.get("Retry-After"))
        except Exception:
            pass

    if response.status_code == 404:
        logger.info(f"TMDB watch provider returned 404 for tmdb_id={tmdb_id}; returning empty provider set.")
        return {
            "link": None,
            "region": target_region,
            "flatrate": [],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

    if response.status_code != 200:
        logger.warning(f"TMDB watch provider returned HTTP {response.status_code} for tmdb_id={tmdb_id}")
        raise TMDBAPIError(f"TMDB returned HTTP {response.status_code}")

    try:
        data = response.json()
    except Exception as e:
        logger.error(f"Failed to parse TMDB watch provider response as JSON: {e}")
        raise TMDBServiceError("Malformed TMDB watch provider response") from e

    results = data.get("results", {}) if isinstance(data, dict) else {}
    country_data = results.get(target_region, {}) if isinstance(results, dict) else {}

    if not country_data or not isinstance(country_data, dict):
        return {
            "link": None,
            "region": target_region,
            "flatrate": [],
            "rent": [],
            "buy": [],
            "free": [],
            "ads": [],
        }

    return {
        "link": country_data.get("link"),
        "region": target_region,
        "flatrate": country_data.get("flatrate", []) or [],
        "rent": country_data.get("rent", []) or [],
        "buy": country_data.get("buy", []) or [],
        "free": country_data.get("free", []) or [],
        "ads": country_data.get("ads", []) or [],
    }
