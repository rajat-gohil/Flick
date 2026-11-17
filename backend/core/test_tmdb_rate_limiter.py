"""
Unit and integration tests for TMDB Rate Limiter (Flick Batch 2).
"""

import datetime
import email.utils
import time
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings
import redis

from core.services.tmdb_rate_limiter import (
    acquire_tmdb_token,
    record_tmdb_429,
    get_rate_limiter_status,
    reset_rate_limiter,
    set_redis_client,
    parse_retry_after,
    calculate_cooldown_with_jitter,
    InMemoryTokenBucket,
    RedisRateLimiterUnavailableError,
    INTERACTIVE_BUCKET_KEY,
    BACKGROUND_BUCKET_KEY,
    GLOBAL_COOLDOWN_KEY,
    INTERACTIVE_FILL_RATE,
    BACKGROUND_FILL_RATE,
    INTERACTIVE_BURST_CAPACITY,
    BACKGROUND_BURST_CAPACITY,
    COMBINED_BURST_CAPACITY,
    DEFAULT_COOLDOWN_SECONDS,
    LUA_ACQUIRE_TOKEN,
    LUA_RECORD_429,
    LUA_GET_STATUS,
)


@override_settings(DEBUG=True)
class TMDBRateLimiterInMemoryTests(SimpleTestCase):
    """
    Tests for token bucket logic, burst capacities, borrowing rules,
    and HTTP 429 cooldowns using the thread-safe in-memory engine.
    """

    def setUp(self):
        super().setUp()
        set_redis_client(None)
        reset_rate_limiter()

    def tearDown(self):
        set_redis_client(None)
        reset_rate_limiter()
        super().tearDown()

    def test_initial_status(self):
        """Verify initial bucket capacities and operating targets."""
        status = get_rate_limiter_status()
        self.assertEqual(status["operating_budget_rps"], 4.0)
        self.assertEqual(status["combined_burst_capacity"], 4.0)
        self.assertEqual(status["interactive"]["capacity"], 2.0)
        self.assertEqual(status["interactive"]["fill_rate"], 1.2)
        self.assertEqual(status["interactive"]["tokens"], 2.0)
        self.assertEqual(status["background"]["capacity"], 2.0)
        self.assertEqual(status["background"]["fill_rate"], 2.8)
        self.assertEqual(status["background"]["tokens"], 2.0)
        self.assertFalse(status["global_cooldown"]["active"])
        self.assertEqual(status["global_cooldown"]["remaining_seconds"], 0.0)

    def test_interactive_token_consumption(self):
        """Interactive traffic consumes from interactive bucket first."""
        # 1st interactive token
        acquired = acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 1.0, delta=0.1)
        self.assertAlmostEqual(status["background_tokens"], 2.0, delta=0.1)

        # 2nd interactive token
        acquired = acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["background_tokens"], 2.0, delta=0.1)

    def test_background_token_consumption(self):
        """Background traffic consumes from background bucket."""
        # 1st background token
        acquired = acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["background_tokens"], 1.0, delta=0.1)
        self.assertAlmostEqual(status["interactive_tokens"], 2.0, delta=0.1)

        # 2nd background token
        acquired = acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["background_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["interactive_tokens"], 2.0, delta=0.1)

    def test_interactive_borrowing_from_background(self):
        """
        Interactive traffic CAN borrow from the background bucket
        when interactive bucket is exhausted.
        """
        # Drain interactive bucket completely (2.0 tokens)
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["background_tokens"], 2.0, delta=0.1)

        # 3rd interactive request: must borrow 1.0 from background
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["background_tokens"], 1.0, delta=0.1)

        # 4th interactive request: borrow remaining 1.0 from background
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["background_tokens"], 0.0, delta=0.1)

        # 5th interactive request: both empty -> fails
        self.assertFalse(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))

    def test_background_cannot_borrow_from_interactive(self):
        """
        Background traffic CANNOT borrow from the interactive bucket
        under any circumstances.
        """
        # Drain background bucket (2.0 tokens)
        self.assertTrue(acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0))
        self.assertTrue(acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0))

        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["background_tokens"], 0.0, delta=0.1)
        self.assertAlmostEqual(status["interactive_tokens"], 2.0, delta=0.1)

        # Background attempts to acquire token: MUST FAIL even though interactive is full
        acquired = acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0)
        self.assertFalse(acquired)

        # Interactive bucket must still be intact
        status = get_rate_limiter_status()
        self.assertAlmostEqual(status["interactive_tokens"], 2.0, delta=0.1)

    def test_burst_capacity_limits(self):
        """
        Burst capacity limits: max 2.0 per bucket, max 4.0 aggregate.
        """
        # Consume full aggregate burst capacity (2 interactive + 2 background)
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        self.assertTrue(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        self.assertTrue(acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0))
        self.assertTrue(acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0))

        # 5th request must fail immediately
        self.assertFalse(acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0))
        self.assertFalse(acquire_tmdb_token(traffic_type="background", cost=1.0, timeout=0.0))

    def test_replenishment_capped_at_burst_capacity(self):
        """Buckets replenish over time but never exceed 2.0 each / 4.0 aggregate."""
        bucket = InMemoryTokenBucket()
        now = time.time()
        # Simulate 100 seconds elapsed without consumption
        bucket.acquire("background", 1.0, now)
        _, _, _, it, bg = bucket.acquire("background", 1.0, now + 100.0)
        self.assertLessEqual(it, 2.0)
        self.assertLessEqual(bg, 2.0)
        self.assertLessEqual(it + bg, 4.0)

    def test_retry_after_parsing_integer_seconds(self):
        """Integer seconds in Retry-After are parsed cleanly."""
        self.assertEqual(parse_retry_after("12"), 12.0)
        self.assertEqual(parse_retry_after("  5  "), 5.0)
        self.assertEqual(parse_retry_after("120"), 120.0)

    def test_retry_after_parsing_http_date(self):
        """HTTP-date (RFC 7231 IMF-fixdate) in Retry-After is parsed correctly."""
        now = datetime.datetime.now(datetime.timezone.utc)
        future_dt = now + datetime.timedelta(seconds=25)
        http_date_str = email.utils.format_datetime(future_dt, usegmt=True)

        parsed = parse_retry_after(http_date_str, now=now)
        self.assertAlmostEqual(parsed, 25.0, delta=1.0)

    def test_retry_after_parsing_malformed_and_missing(self):
        """Malformed or missing Retry-After defaults to 12.0s."""
        self.assertEqual(parse_retry_after(None), 12.0)
        self.assertEqual(parse_retry_after(""), 12.0)
        self.assertEqual(parse_retry_after("   "), 12.0)
        self.assertEqual(parse_retry_after("not-a-number-or-date"), 12.0)
        self.assertEqual(parse_retry_after("-5"), 12.0)

    def test_calculate_cooldown_with_jitter(self):
        """Cooldown adds random jitter between +0.5s and 2.0s."""
        cd = calculate_cooldown_with_jitter("10")
        self.assertGreaterEqual(cd, 10.5)
        self.assertLessEqual(cd, 12.0)

        # Default header (None)
        cd_default = calculate_cooldown_with_jitter(None)
        self.assertGreaterEqual(cd_default, 12.5)
        self.assertLessEqual(cd_default, 14.0)

    def test_record_tmdb_429_sets_cooldown(self):
        """record_tmdb_429 activates global cooldown and blocks acquisitions."""
        cd_duration = record_tmdb_429("10")
        self.assertGreaterEqual(cd_duration, 10.5)

        status = get_rate_limiter_status()
        self.assertTrue(status["cooldown_active"])
        self.assertGreater(status["cooldown_remaining_seconds"], 9.0)

        # Acquisition fails immediately during cooldown
        start = time.monotonic()
        acquired = acquire_tmdb_token(traffic_type="interactive", timeout=2.0)
        elapsed = time.monotonic() - start

        self.assertFalse(acquired)
        # Verify it failed immediately without waiting for the 2.0s timeout
        self.assertLess(elapsed, 0.2)

    def test_non_shortening_atomic_cooldown_extension(self):
        """
        A shorter Retry-After must NEVER shorten an existing longer cooldown.
        A longer Retry-After DOES extend an existing cooldown.
        """
        # 1. Set a 30s cooldown
        cd1 = record_tmdb_429("30")
        status1 = get_rate_limiter_status()
        rem1 = status1["cooldown_remaining_seconds"]
        self.assertGreater(rem1, 28.0)

        # 2. Receive a subsequent 429 with Retry-After: 5s
        cd2 = record_tmdb_429("5")
        status2 = get_rate_limiter_status()
        rem2 = status2["cooldown_remaining_seconds"]

        # MUST NOT be shortened to ~5s! Must remain ~28-30s!
        self.assertGreater(rem2, 25.0)

        # 3. Receive a subsequent 429 with Retry-After: 60s
        cd3 = record_tmdb_429("60")
        status3 = get_rate_limiter_status()
        rem3 = status3["cooldown_remaining_seconds"]

        # Longer cooldown DOES extend it to ~60s
        self.assertGreater(rem3, 58.0)

    def test_invalid_traffic_type_raises(self):
        """Invalid traffic type raises ValueError."""
        with self.assertRaises(ValueError):
            acquire_tmdb_token(traffic_type="invalid_type")

    def test_invalid_cost_or_timeout_raises(self):
        """Negative cost or timeout raises ValueError."""
        with self.assertRaises(ValueError):
            acquire_tmdb_token(cost=0)
        with self.assertRaises(ValueError):
            acquire_tmdb_token(cost=-1.0)
        with self.assertRaises(ValueError):
            acquire_tmdb_token(timeout=-0.5)


class TMDBRateLimiterProductionFailClosedTests(SimpleTestCase):
    """
    Tests for universal fail-closed behavior in production (DEBUG=False).
    """

    def setUp(self):
        super().setUp()
        reset_rate_limiter()

    def tearDown(self):
        set_redis_client(None)
        reset_rate_limiter()
        super().tearDown()

    @override_settings(DEBUG=False)
    def test_fail_closed_when_redis_none_in_production(self):
        """In production, missing/unconfigured Redis raises RedisRateLimiterUnavailableError."""
        set_redis_client(None)
        with self.assertRaises(RedisRateLimiterUnavailableError) as ctx:
            acquire_tmdb_token("interactive")
        self.assertIn("failing closed in production", str(ctx.exception))

        with self.assertRaises(RedisRateLimiterUnavailableError):
            acquire_tmdb_token("background")

        with self.assertRaises(RedisRateLimiterUnavailableError):
            record_tmdb_429()

        with self.assertRaises(RedisRateLimiterUnavailableError):
            get_rate_limiter_status()

    @override_settings(DEBUG=False)
    def test_fail_closed_on_redis_connection_error_in_production(self):
        """In production, Redis ConnectionError raises RedisRateLimiterUnavailableError."""
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = redis.ConnectionError("Connection refused by Redis")
        set_redis_client(mock_redis)

        with self.assertRaises(RedisRateLimiterUnavailableError):
            acquire_tmdb_token("interactive")

        with self.assertRaises(RedisRateLimiterUnavailableError):
            acquire_tmdb_token("background")

        with self.assertRaises(RedisRateLimiterUnavailableError):
            record_tmdb_429("10")

        with self.assertRaises(RedisRateLimiterUnavailableError):
            get_rate_limiter_status()

    @override_settings(DEBUG=False)
    def test_fail_closed_on_redis_timeout_error_in_production(self):
        """In production, Redis TimeoutError raises RedisRateLimiterUnavailableError."""
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = redis.TimeoutError("Redis socket timed out")
        set_redis_client(mock_redis)

        with self.assertRaises(RedisRateLimiterUnavailableError):
            acquire_tmdb_token("interactive")

        with self.assertRaises(RedisRateLimiterUnavailableError):
            acquire_tmdb_token("background")

    @override_settings(DEBUG=True)
    def test_fallback_to_in_memory_on_redis_error_in_dev(self):
        """In local development (DEBUG=True), Redis failure falls back to in-memory gracefully."""
        mock_redis = MagicMock()
        mock_redis.eval.side_effect = redis.ConnectionError("Connection refused")
        set_redis_client(mock_redis)

        # Should NOT raise RedisRateLimiterUnavailableError; must fallback to in-memory!
        acquired = acquire_tmdb_token("background", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)

        status = get_rate_limiter_status()
        self.assertEqual(status["backend"], "memory")


class TMDBRateLimiterRedisLuaMockTests(SimpleTestCase):
    """
    Tests verifying Redis Lua execution and parsing contract with mock Redis client.
    """

    def setUp(self):
        super().setUp()
        reset_rate_limiter()

    def tearDown(self):
        set_redis_client(None)
        reset_rate_limiter()
        super().tearDown()

    @override_settings(DEBUG=False)
    def test_redis_acquire_success(self):
        """Verify successful acquisition dispatch to Redis Lua script."""
        mock_redis = MagicMock()
        # Return format from LUA_ACQUIRE_TOKEN: {acquired, cd_active, cd_wait_ms, it_tokens, bg_tokens}
        mock_redis.eval.return_value = [1, 0, 0, "1.0", "2.0"]
        set_redis_client(mock_redis)

        acquired = acquire_tmdb_token(traffic_type="interactive", cost=1.0, timeout=0.0)
        self.assertTrue(acquired)

        # Verify eval call args
        mock_redis.eval.assert_called_once()
        args = mock_redis.eval.call_args[0]
        lua_script = args[0]
        num_keys = args[1]
        keys = args[2:2 + num_keys]

        self.assertEqual(lua_script, LUA_ACQUIRE_TOKEN)
        self.assertEqual(keys, (INTERACTIVE_BUCKET_KEY, BACKGROUND_BUCKET_KEY, GLOBAL_COOLDOWN_KEY))

    @override_settings(DEBUG=False)
    def test_redis_acquire_cooldown_active(self):
        """Verify immediate failure when Redis Lua reports cooldown_active=1."""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = [0, 1, 15000, "0", "0"]
        set_redis_client(mock_redis)

        start = time.monotonic()
        acquired = acquire_tmdb_token(traffic_type="interactive", timeout=5.0)
        elapsed = time.monotonic() - start

        self.assertFalse(acquired)
        # Fails immediately without sleeping
        self.assertLess(elapsed, 0.2)

    @override_settings(DEBUG=False)
    def test_redis_record_429(self):
        """Verify record_tmdb_429 dispatches to Redis LUA_RECORD_429."""
        mock_redis = MagicMock()
        mock_redis.eval.return_value = "1700000020.5"
        set_redis_client(mock_redis)

        cd = record_tmdb_429("10")
        self.assertGreaterEqual(cd, 10.5)

        mock_redis.eval.assert_called_once()
        args = mock_redis.eval.call_args[0]
        self.assertEqual(args[0], LUA_RECORD_429)
        self.assertEqual(args[2], GLOBAL_COOLDOWN_KEY)

    @override_settings(DEBUG=False)
    def test_redis_get_status(self):
        """Verify get_rate_limiter_status parsing from LUA_GET_STATUS."""
        mock_redis = MagicMock()
        # {cd_active, cd_rem_ms, cd_until_str, it_tokens, it_last, bg_tokens, bg_last}
        mock_redis.eval.return_value = [1, 12500, "1700000012.5", "1.5", "1700000000.0", "0.8", "1700000000.0"]
        set_redis_client(mock_redis)

        status = get_rate_limiter_status()
        self.assertEqual(status["backend"], "redis")
        self.assertTrue(status["cooldown_active"])
        self.assertEqual(status["cooldown_remaining_seconds"], 12.5)
        self.assertEqual(status["interactive_tokens"], 1.5)
        self.assertEqual(status["background_tokens"], 0.8)
        self.assertAlmostEqual(status["total_tokens"], 2.3, delta=0.01)
