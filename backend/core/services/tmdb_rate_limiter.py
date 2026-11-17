"""
TMDB Rate Limiter for Flick Batch 2.

Implements a dual-bucket token bucket model with priority borrowing,
HTTP 429 global cooldown management, atomic Lua scripts for Redis,
and fail-closed semantics in production.
"""

import datetime
import email.utils
import logging
import math
import os
import random
import threading
import time
from typing import Any, Optional, Tuple

from django.conf import settings
import redis

logger = logging.getLogger(__name__)

# Redis Keys
INTERACTIVE_BUCKET_KEY = "flick:tmdb:tokens:interactive"
BACKGROUND_BUCKET_KEY = "flick:tmdb:tokens:background"
GLOBAL_COOLDOWN_KEY = "flick:tmdb:global_cooldown"

# Rate Limit & Burst Specifications
TARGET_BUDGET_RPS = 4.0
INTERACTIVE_FILL_RATE = 1.2  # tokens / sec
INTERACTIVE_BURST_CAPACITY = 2.0  # max tokens
BACKGROUND_FILL_RATE = 2.8  # tokens / sec
BACKGROUND_BURST_CAPACITY = 2.0  # max tokens
COMBINED_BURST_CAPACITY = 4.0  # max combined tokens

# Cooldown Specifications
DEFAULT_COOLDOWN_SECONDS = 12.0
JITTER_MIN = 0.5
JITTER_MAX = 2.0
BUCKET_KEY_TTL = 86400  # 24 hours Redis key expiration for idle buckets


class RedisRateLimiterUnavailableError(Exception):
    """Raised when Redis is unavailable in production (fail-closed contract)."""
    pass


# ─────────────────────────────────────────────────────────────────────────────
# REDIS LUA SCRIPTS
# ─────────────────────────────────────────────────────────────────────────────

LUA_ACQUIRE_TOKEN = """
local it_key = KEYS[1]
local bg_key = KEYS[2]
local cd_key = KEYS[3]

local traffic_type = ARGV[1]
local cost = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local it_fill_rate = tonumber(ARGV[4])
local it_capacity = tonumber(ARGV[5])
local bg_fill_rate = tonumber(ARGV[6])
local bg_capacity = tonumber(ARGV[7])
local key_ttl = tonumber(ARGV[8])

-- 1. Check global cooldown atomically
local cd_val = redis.call('GET', cd_key)
if cd_val then
    local cd_until = tonumber(cd_val)
    if cd_until and cd_until > now then
        local rem_ms = math.ceil((cd_until - now) * 1000)
        return {0, 1, rem_ms, "0", "0"}
    end
end

-- 2. Fetch and replenish interactive bucket
local it_tokens_raw = redis.call('HGET', it_key, 'tokens')
local it_last_raw = redis.call('HGET', it_key, 'last_updated')
local it_tokens = it_capacity
local it_last = now

if it_tokens_raw and it_last_raw then
    local t = tonumber(it_tokens_raw)
    local l = tonumber(it_last_raw)
    if t and l then
        local elapsed = math.max(0, now - l)
        it_tokens = math.min(it_capacity, t + elapsed * it_fill_rate)
    end
end

-- 3. Fetch and replenish background bucket
local bg_tokens_raw = redis.call('HGET', bg_key, 'tokens')
local bg_last_raw = redis.call('HGET', bg_key, 'last_updated')
local bg_tokens = bg_capacity
local bg_last = now

if bg_tokens_raw and bg_last_raw then
    local t = tonumber(bg_tokens_raw)
    local l = tonumber(bg_last_raw)
    if t and l then
        local elapsed = math.max(0, now - l)
        bg_tokens = math.min(bg_capacity, t + elapsed * bg_fill_rate)
    end
end

-- 4. Consume tokens based on traffic_type
local acquired = 0

if traffic_type == 'background' then
    if bg_tokens >= cost then
        bg_tokens = bg_tokens - cost
        acquired = 1
    end
elseif traffic_type == 'interactive' then
    if it_tokens >= cost then
        it_tokens = it_tokens - cost
        acquired = 1
    else
        local deficit = cost - it_tokens
        if bg_tokens >= deficit then
            it_tokens = 0.0
            bg_tokens = bg_tokens - deficit
            acquired = 1
        end
    end
end

-- 5. Save updated states and return
redis.call('HSET', it_key, 'tokens', tostring(it_tokens), 'last_updated', tostring(now))
redis.call('EXPIRE', it_key, key_ttl)

redis.call('HSET', bg_key, 'tokens', tostring(bg_tokens), 'last_updated', tostring(now))
redis.call('EXPIRE', bg_key, key_ttl)

return {acquired, 0, 0, tostring(it_tokens), tostring(bg_tokens)}
"""

LUA_RECORD_429 = """
local cd_key = KEYS[1]
local new_until = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

local cur_val = redis.call('GET', cd_key)
if cur_val then
    local cur_until = tonumber(cur_val)
    if cur_until and cur_until > new_until then
        local rem_ms = math.max(1, math.ceil((cur_until - now) * 1000))
        redis.call('PEXPIRE', cd_key, rem_ms)
        return tostring(cur_until)
    end
end

local ttl_ms = math.max(1, math.ceil((new_until - now) * 1000))
redis.call('SET', cd_key, tostring(new_until), 'PX', ttl_ms)
return tostring(new_until)
"""

LUA_GET_STATUS = """
local it_key = KEYS[1]
local bg_key = KEYS[2]
local cd_key = KEYS[3]

local now = tonumber(ARGV[1])
local it_fill_rate = tonumber(ARGV[2])
local it_capacity = tonumber(ARGV[3])
local bg_fill_rate = tonumber(ARGV[4])
local bg_capacity = tonumber(ARGV[5])

local cd_active = 0
local cd_rem_ms = 0
local cd_until_str = ""

local cd_val = redis.call('GET', cd_key)
if cd_val then
    local cd_until = tonumber(cd_val)
    if cd_until and cd_until > now then
        cd_active = 1
        cd_rem_ms = math.ceil((cd_until - now) * 1000)
        cd_until_str = tostring(cd_until)
    end
end

local it_tokens = it_capacity
local it_last = now
local it_tokens_raw = redis.call('HGET', it_key, 'tokens')
local it_last_raw = redis.call('HGET', it_key, 'last_updated')
if it_tokens_raw and it_last_raw then
    local t = tonumber(it_tokens_raw)
    local l = tonumber(it_last_raw)
    if t and l then
        local elapsed = math.max(0, now - l)
        it_tokens = math.min(it_capacity, t + elapsed * it_fill_rate)
        it_last = l
    end
end

local bg_tokens = bg_capacity
local bg_last = now
local bg_tokens_raw = redis.call('HGET', bg_key, 'tokens')
local bg_last_raw = redis.call('HGET', bg_key, 'last_updated')
if bg_tokens_raw and bg_last_raw then
    local t = tonumber(bg_tokens_raw)
    local l = tonumber(bg_last_raw)
    if t and l then
        local elapsed = math.max(0, now - l)
        bg_tokens = math.min(bg_capacity, t + elapsed * bg_fill_rate)
        bg_last = l
    end
end

return {
    cd_active,
    cd_rem_ms,
    cd_until_str,
    tostring(it_tokens),
    tostring(it_last),
    tostring(bg_tokens),
    tostring(bg_last)
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# IN-MEMORY FALLBACK (DEBUG=True single-process safe)
# ─────────────────────────────────────────────────────────────────────────────

class InMemoryTokenBucket:
    """Thread-safe in-memory dual token bucket fallback for local development."""

    def __init__(self):
        self._lock = threading.Lock()
        now = time.time()
        self.it_tokens = INTERACTIVE_BURST_CAPACITY
        self.it_last = now
        self.bg_tokens = BACKGROUND_BURST_CAPACITY
        self.bg_last = now
        self.cooldown_until: Optional[float] = None

    def reset(self):
        with self._lock:
            now = time.time()
            self.it_tokens = INTERACTIVE_BURST_CAPACITY
            self.it_last = now
            self.bg_tokens = BACKGROUND_BURST_CAPACITY
            self.bg_last = now
            self.cooldown_until = None

    def acquire(self, traffic_type: str, cost: float, now: float) -> Tuple[bool, bool, float, float, float]:
        """
        Returns: (acquired, cooldown_active, remaining_wait_ms, it_tokens, bg_tokens)
        """
        with self._lock:
            # 1. Cooldown check
            if self.cooldown_until is not None:
                if self.cooldown_until > now:
                    remaining_ms = math.ceil((self.cooldown_until - now) * 1000)
                    return False, True, float(remaining_ms), self.it_tokens, self.bg_tokens
                else:
                    self.cooldown_until = None

            # 2. Replenish interactive
            elapsed_it = max(0.0, now - self.it_last)
            self.it_tokens = min(INTERACTIVE_BURST_CAPACITY, self.it_tokens + elapsed_it * INTERACTIVE_FILL_RATE)
            self.it_last = now

            # 3. Replenish background
            elapsed_bg = max(0.0, now - self.bg_last)
            self.bg_tokens = min(BACKGROUND_BURST_CAPACITY, self.bg_tokens + elapsed_bg * BACKGROUND_FILL_RATE)
            self.bg_last = now

            # 4. Attempt consumption
            acquired = False
            if traffic_type == "background":
                if self.bg_tokens >= cost:
                    self.bg_tokens -= cost
                    acquired = True
            elif traffic_type == "interactive":
                if self.it_tokens >= cost:
                    self.it_tokens -= cost
                    acquired = True
                else:
                    deficit = cost - self.it_tokens
                    if self.bg_tokens >= deficit:
                        self.it_tokens = 0.0
                        self.bg_tokens -= deficit
                        acquired = True

            return acquired, False, 0.0, self.it_tokens, self.bg_tokens

    def record_429(self, cooldown_seconds: float, now: float) -> float:
        with self._lock:
            new_until = now + cooldown_seconds
            if self.cooldown_until is None or new_until > self.cooldown_until:
                self.cooldown_until = new_until
            return cooldown_seconds

    def get_status(self, now: float) -> dict:
        with self._lock:
            # Replenish on read
            elapsed_it = max(0.0, now - self.it_last)
            it_tokens = min(INTERACTIVE_BURST_CAPACITY, self.it_tokens + elapsed_it * INTERACTIVE_FILL_RATE)
            elapsed_bg = max(0.0, now - self.bg_last)
            bg_tokens = min(BACKGROUND_BURST_CAPACITY, self.bg_tokens + elapsed_bg * BACKGROUND_FILL_RATE)

            cd_active = False
            cd_remaining = 0.0
            if self.cooldown_until is not None and self.cooldown_until > now:
                cd_active = True
                cd_remaining = max(0.0, self.cooldown_until - now)

            return {
                "interactive": {
                    "tokens": round(it_tokens, 4),
                    "capacity": INTERACTIVE_BURST_CAPACITY,
                    "fill_rate": INTERACTIVE_FILL_RATE,
                    "last_updated": self.it_last,
                },
                "background": {
                    "tokens": round(bg_tokens, 4),
                    "capacity": BACKGROUND_BURST_CAPACITY,
                    "fill_rate": BACKGROUND_FILL_RATE,
                    "last_updated": self.bg_last,
                },
                "global_cooldown": {
                    "active": cd_active,
                    "remaining_seconds": round(cd_remaining, 3),
                    "cooldown_until": self.cooldown_until,
                },
                "operating_budget_rps": TARGET_BUDGET_RPS,
                "combined_burst_capacity": COMBINED_BURST_CAPACITY,
                "backend": "memory",
                "cooldown_active": cd_active,
                "cooldown_remaining_seconds": round(cd_remaining, 3),
                "interactive_tokens": round(it_tokens, 4),
                "background_tokens": round(bg_tokens, 4),
                "total_tokens": round(it_tokens + bg_tokens, 4),
            }


_in_memory_bucket = InMemoryTokenBucket()
_redis_client_override: Optional[Any] = None
_cached_redis_client: Optional[redis.Redis] = None


# ─────────────────────────────────────────────────────────────────────────────
# REDIS CLIENT ACCESS & ENVIRONMENT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def is_production() -> bool:
    """Checks whether running in production (DEBUG=False) and Redis fail-closed is required."""
    if getattr(settings, "DEBUG", True) is True:
        return False
    if getattr(settings, "TMDB_RATELIMIT_ALLOW_IN_MEMORY", False) is True:
        return False
    return True


def get_redis_client() -> Optional[redis.Redis]:
    """
    Returns active Redis client if configured and available.
    Supports dependency injection via set_redis_client.
    """
    global _cached_redis_client, _redis_client_override
    if _redis_client_override is not None:
        return _redis_client_override

    url = (
        getattr(settings, "TMDB_RATELIMIT_REDIS_URL", None)
        or getattr(settings, "REDIS_URL", None)
        or os.environ.get("REDIS_URL")
    )
    if not url:
        caches = getattr(settings, "CACHES", {})
        default_cache = caches.get("default", {})
        backend_cls = default_cache.get("BACKEND", "")
        if "redis" in backend_cls.lower():
            url = default_cache.get("LOCATION")

    if not url:
        return None

    if _cached_redis_client is None:
        _cached_redis_client = redis.Redis.from_url(
            url,
            socket_connect_timeout=1.0,
            socket_timeout=2.0,
            decode_responses=True,
        )
    return _cached_redis_client


def set_redis_client(client: Any) -> None:
    """Inject a Redis client or mock for testing."""
    global _redis_client_override
    _redis_client_override = client


def reset_rate_limiter() -> None:
    """Resets rate limiter state across memory and Redis if available."""
    global _in_memory_bucket, _cached_redis_client, _redis_client_override
    _in_memory_bucket.reset()
    client = get_redis_client()
    if client is not None:
        try:
            client.delete(INTERACTIVE_BUCKET_KEY, BACKGROUND_BUCKET_KEY, GLOBAL_COOLDOWN_KEY)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# RETRY-AFTER PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_retry_after(header: Optional[str], now: Optional[datetime.datetime] = None) -> float:
    """
    Parses Retry-After header safely.
    Handles:
      - Integer or float seconds (e.g. "12", "5.5")
      - HTTP-date strings (RFC 7231 / RFC 9110, IMF-fixdate)
      - Missing, empty, or malformed strings -> defaults to 12.0s
    Returns base duration in seconds (non-negative).
    """
    if header is None or not isinstance(header, str):
        return DEFAULT_COOLDOWN_SECONDS

    cleaned = header.strip()
    if not cleaned:
        return DEFAULT_COOLDOWN_SECONDS

    # 1. Try integer/float seconds
    try:
        seconds = float(cleaned)
        if seconds < 0:
            return DEFAULT_COOLDOWN_SECONDS
        return seconds
    except ValueError:
        pass

    # 2. Try HTTP-date formats (RFC 7231 / RFC 9110)
    try:
        dt = email.utils.parsedate_to_datetime(cleaned)
        if dt is None:
            return DEFAULT_COOLDOWN_SECONDS
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        if now is None:
            now_dt = datetime.datetime.now(datetime.timezone.utc)
        else:
            now_dt = now if now.tzinfo is not None else now.replace(tzinfo=datetime.timezone.utc)
        diff = (dt - now_dt).total_seconds()
        if diff < 0:
            return DEFAULT_COOLDOWN_SECONDS
        return diff
    except Exception:
        return DEFAULT_COOLDOWN_SECONDS


def calculate_cooldown_with_jitter(retry_after_header: Optional[str] = None) -> float:
    """
    Parses Retry-After and adds random jitter (+0.5s to 2.0s).
    """
    base = parse_retry_after(retry_after_header)
    jitter = random.uniform(JITTER_MIN, JITTER_MAX)
    return base + jitter


# ─────────────────────────────────────────────────────────────────────────────
# REDIS EXECUTION HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _redis_eval_acquire(client: redis.Redis, traffic_type: str, cost: float, now: float) -> Tuple[bool, bool, float]:
    """
    Executes LUA_ACQUIRE_TOKEN in Redis.
    Returns: (acquired, cooldown_active, remaining_wait_ms)
    """
    keys = [INTERACTIVE_BUCKET_KEY, BACKGROUND_BUCKET_KEY, GLOBAL_COOLDOWN_KEY]
    args = [
        traffic_type,
        str(cost),
        str(now),
        str(INTERACTIVE_FILL_RATE),
        str(INTERACTIVE_BURST_CAPACITY),
        str(BACKGROUND_FILL_RATE),
        str(BACKGROUND_BURST_CAPACITY),
        str(BUCKET_KEY_TTL),
    ]
    res = client.eval(LUA_ACQUIRE_TOKEN, len(keys), *keys, *args)
    acquired = bool(res[0])
    cooldown_active = bool(res[1])
    remaining_wait_ms = float(res[2])
    return acquired, cooldown_active, remaining_wait_ms


def _redis_eval_record_429(client: redis.Redis, cooldown_until: float, now: float) -> float:
    keys = [GLOBAL_COOLDOWN_KEY]
    args = [str(cooldown_until), str(now)]
    client.eval(LUA_RECORD_429, len(keys), *keys, *args)
    return cooldown_until


def _redis_eval_status(client: redis.Redis, now: float) -> dict:
    keys = [INTERACTIVE_BUCKET_KEY, BACKGROUND_BUCKET_KEY, GLOBAL_COOLDOWN_KEY]
    args = [
        str(now),
        str(INTERACTIVE_FILL_RATE),
        str(INTERACTIVE_BURST_CAPACITY),
        str(BACKGROUND_FILL_RATE),
        str(BACKGROUND_BURST_CAPACITY),
    ]
    res = client.eval(LUA_GET_STATUS, len(keys), *keys, *args)
    cd_active = bool(res[0])
    cd_remaining_ms = float(res[1])
    cd_until = float(res[2]) if res[2] else None
    it_tokens = float(res[3])
    it_last = float(res[4])
    bg_tokens = float(res[5])
    bg_last = float(res[6])
    cd_remaining_sec = max(0.0, round(cd_remaining_ms / 1000.0, 3))

    return {
        "interactive": {
            "tokens": round(it_tokens, 4),
            "capacity": INTERACTIVE_BURST_CAPACITY,
            "fill_rate": INTERACTIVE_FILL_RATE,
            "last_updated": it_last,
        },
        "background": {
            "tokens": round(bg_tokens, 4),
            "capacity": BACKGROUND_BURST_CAPACITY,
            "fill_rate": BACKGROUND_FILL_RATE,
            "last_updated": bg_last,
        },
        "global_cooldown": {
            "active": cd_active,
            "remaining_seconds": cd_remaining_sec,
            "cooldown_until": cd_until,
        },
        "operating_budget_rps": TARGET_BUDGET_RPS,
        "combined_burst_capacity": COMBINED_BURST_CAPACITY,
        "backend": "redis",
        "cooldown_active": cd_active,
        "cooldown_remaining_seconds": cd_remaining_sec,
        "interactive_tokens": round(it_tokens, 4),
        "background_tokens": round(bg_tokens, 4),
        "total_tokens": round(it_tokens + bg_tokens, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PRIMARY INTERFACE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def acquire_tmdb_token(
    traffic_type: str = "background",
    cost: float = 1.0,
    timeout: float = 5.0,
) -> bool:
    """
    Acquires a TMDB rate limit token.

    Parameters:
      traffic_type: 'interactive' or 'background'.
      cost: Number of tokens requested (default: 1.0).
      timeout: Max seconds to wait for tokens to become available (default: 5.0).

    Behavior:
      - Validates traffic_type and parameters.
      - In production (DEBUG=False): Fails closed and raises
        RedisRateLimiterUnavailableError if Redis is unavailable.
      - Checks global cooldown atomically in Lua. If active, fails immediately.
      - If tokens are not currently available, sleeps in bounded intervals
        until timeout expires.
      - Returns True if acquired, False on timeout or active cooldown.
    """
    if traffic_type not in ("interactive", "background"):
        raise ValueError(f"Invalid traffic_type: {traffic_type!r}. Must be 'interactive' or 'background'.")
    if cost <= 0:
        raise ValueError(f"Cost must be positive, got {cost}.")
    if timeout < 0:
        raise ValueError(f"Timeout must be non-negative, got {timeout}.")

    prod = is_production()
    client = get_redis_client()

    if client is None and prod:
        raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production")

    start_time = time.monotonic()

    while True:
        now = time.time()
        try:
            if client is not None:
                acquired, cd_active, remaining_ms = _redis_eval_acquire(client, traffic_type, cost, now)
            else:
                acquired, cd_active, remaining_ms, _, _ = _in_memory_bucket.acquire(traffic_type, cost, now)
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            if prod:
                raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production") from e
            logger.warning("Redis error in dev mode; falling back to in-memory rate limiter: %s", e)
            acquired, cd_active, remaining_ms, _, _ = _in_memory_bucket.acquire(traffic_type, cost, now)

        if acquired:
            return True

        if cd_active:
            # Atomic global cooldown active: fail immediately without waiting
            logger.info("TMDB rate limit global cooldown active; remaining_ms=%.1f", remaining_ms)
            return False

        elapsed = time.monotonic() - start_time
        remaining_timeout = timeout - elapsed
        if remaining_timeout <= 0:
            return False

        sleep_time = min(0.05, remaining_timeout)
        time.sleep(sleep_time)


def record_tmdb_429(retry_after_header: Optional[str] = None) -> float:
    """
    Records an upstream TMDB HTTP 429 response.

    Parses Retry-After header (integer seconds or HTTP-date RFC 7231 / RFC 9110),
    defaults to 12.0s if missing or unparseable, adds random jitter (+0.5s to 2.0s),
    and atomically updates flick:tmdb:global_cooldown.

    Atomic cooldown extension rule: A shorter Retry-After must NEVER shorten
    an existing longer cooldown.

    Returns the calculated cooldown duration in seconds.
    """
    cooldown_seconds = calculate_cooldown_with_jitter(retry_after_header)
    now = time.time()
    cooldown_until = now + cooldown_seconds

    prod = is_production()
    client = get_redis_client()

    if client is None and prod:
        raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production")

    try:
        if client is not None:
            _redis_eval_record_429(client, cooldown_until, now)
        else:
            _in_memory_bucket.record_429(cooldown_seconds, now)
    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        if prod:
            raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production") from e
        logger.warning("Redis error in dev mode; falling back to in-memory rate limiter: %s", e)
        _in_memory_bucket.record_429(cooldown_seconds, now)

    return cooldown_seconds


def get_rate_limiter_status() -> dict:
    """
    Returns current rate limiter metrics and state.
    """
    now = time.time()
    prod = is_production()
    client = get_redis_client()

    if client is None and prod:
        raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production")

    try:
        if client is not None:
            return _redis_eval_status(client, now)
        else:
            return _in_memory_bucket.get_status(now)
    except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
        if prod:
            raise RedisRateLimiterUnavailableError("Redis unavailable; failing closed in production") from e
        logger.warning("Redis error in dev mode; falling back to in-memory rate limiter: %s", e)
        return _in_memory_bucket.get_status(now)
