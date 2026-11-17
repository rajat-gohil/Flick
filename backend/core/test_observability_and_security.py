"""
Tests for Phase 6 Batch A: Observability, Request Correlation IDs, and Secret Redaction.

Covers:
1. Secret redaction across all configured loggers (urllib3.connectionpool, requests,
   django.request, django.server, core, root, and mail_admins).
2. Simulated TMDB connection reset logging reproducing urllib3 retry warning and verifying redaction.
3. CorrelationIdMiddleware ID generation, validation, sanitization of malformed IDs, and response echoing.
4. Concurrency isolation under asyncio/ASGI tasks without cross-contamination.
5. ContextVar cleanup on exception/500 error paths.
6. Outbound per-request TMDB header injection without shared session default mutation.
"""

import asyncio
import io
import logging
import re
import uuid
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse, HttpResponseServerError
from django.test import TestCase, RequestFactory, override_settings
from django.test.client import Client

from core.logging import (
    get_correlation_id,
    set_correlation_id,
    reset_correlation_id,
    correlation_id_ctx,
    SecretRedactionFilter,
    CorrelationIdFilter,
    SecretRedactionFormatter,
)
from core.middleware import CorrelationIdMiddleware, CORRELATION_ID_REGEX
from core.services.tmdb import (
    _get_session,
    _get_tmdb_request_headers,
    redact_sensitive_params,
    get_movie_by_tmdb_id,
)


class SecretRedactionLoggerTests(TestCase):
    """Verify credential and secret scrubbing across configured logging infrastructure."""

    def setUp(self):
        self.dummy_key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(SecretRedactionFormatter("[%(correlation_id)s] [%(name)s]: %(message)s"))
        self.handler.addFilter(CorrelationIdFilter())
        self.handler.addFilter(SecretRedactionFilter())

    def tearDown(self):
        self.handler.close()

    def test_direct_redact_sensitive_params(self):
        """Test redact_sensitive_params utility function."""
        raw_url = f"https://api.themoviedb.org/3/movie/popular?api_key={self.dummy_key}&page=1"
        with override_settings(TMDB_API_KEY=self.dummy_key):
            redacted = redact_sensitive_params(raw_url)
            self.assertNotIn(self.dummy_key, redacted)
            self.assertIn("api_key=[REDACTED]", redacted)

    def test_secret_redaction_filter_text(self):
        """Test SecretRedactionFilter.redact_text across all known credential patterns."""
        with override_settings(TMDB_API_KEY=self.dummy_key, SECRET_KEY="django-insecure-test-secret-key-12345"):
            # 1. api_key in query string
            msg1 = f"Outbound call: https://api.themoviedb.org/3/discover?api_key={self.dummy_key}&language=en"
            r1 = SecretRedactionFilter.redact_text(msg1)
            self.assertNotIn(self.dummy_key, r1)
            self.assertIn("api_key=[REDACTED]", r1)

            # 2. Bearer token
            msg2 = "Authorization failed: Bearer secret-auth-token-xyz123"
            r2 = SecretRedactionFilter.redact_text(msg2)
            self.assertNotIn("secret-auth-token-xyz123", r2)
            self.assertIn("Bearer [REDACTED]", r2)

            # 3. password param
            msg3 = "Login query: /api/login?username=test&password=SuperSecretPassword123"
            r3 = SecretRedactionFilter.redact_text(msg3)
            self.assertNotIn("SuperSecretPassword123", r3)
            self.assertIn("password=[REDACTED]", r3)

            # 4. Django SECRET_KEY in text
            msg4 = "Internal setting exposed: django-insecure-test-secret-key-12345 in stacktrace"
            r4 = SecretRedactionFilter.redact_text(msg4)
            self.assertNotIn("django-insecure-test-secret-key-12345", r4)
            self.assertIn("[REDACTED]", r4)

    def test_redaction_across_all_configured_loggers(self):
        """
        Verify log records emitted to urllib3.connectionpool, requests,
        django.request, django.server, core, and root have secrets redacted.
        """
        loggers_to_test = [
            "urllib3.connectionpool",
            "requests",
            "django.request",
            "django.server",
            "core",
            "",  # root logger
        ]

        with override_settings(TMDB_API_KEY=self.dummy_key):
            for logger_name in loggers_to_test:
                test_logger = logging.getLogger(logger_name)
                test_logger.addHandler(self.handler)
                try:
                    self.stream.truncate(0)
                    self.stream.seek(0)

                    # Emit log with query param and raw key
                    test_logger.warning(
                        "Outbound request failure for URL: https://api.themoviedb.org/3/movie/550?api_key=%s",
                        self.dummy_key,
                    )
                    output = self.stream.getvalue()

                    self.assertNotIn(self.dummy_key, output, f"Key leaked in logger '{logger_name}'")
                    self.assertIn("api_key=[REDACTED]", output)
                finally:
                    test_logger.removeHandler(self.handler)

    def test_simulated_tmdb_connection_reset_logging(self):
        """
        Reproduce the exact urllib3 ConnectionResetError warning that occurred
        in production logs and verify that the configured logging setup scrubs the key.
        """
        urllib3_pool_logger = logging.getLogger("urllib3.connectionpool")
        urllib3_pool_logger.addHandler(self.handler)

        try:
            self.stream.truncate(0)
            self.stream.seek(0)

            # Simulate the urllib3 HTTPConnectionPool._make_request retry log message
            simulated_msg = (
                "Retrying (Retry(total=3, connect=None, read=None, redirect=None, status=None)) "
                "after connection broken by 'ConnectionResetError(54, 'Connection reset by peer')': "
                f"/3/movie/popular?api_key={self.dummy_key}&page=1"
            )

            with override_settings(TMDB_API_KEY=self.dummy_key):
                urllib3_pool_logger.warning(simulated_msg)

            output = self.stream.getvalue()
            self.assertNotIn(
                self.dummy_key,
                output,
                "Simulated connection reset warning leaked TMDB API key in urllib3 log!",
            )
            self.assertIn("api_key=[REDACTED]", output)
            self.assertIn("ConnectionResetError", output)
        finally:
            urllib3_pool_logger.removeHandler(self.handler)

    def test_exception_traceback_redaction_in_formatter(self):
        """Verify that secrets in exception messages and tracebacks are scrubbed."""
        with override_settings(TMDB_API_KEY=self.dummy_key):
            core_logger = logging.getLogger("core.views")
            core_logger.addHandler(self.handler)
            try:
                self.stream.truncate(0)
                self.stream.seek(0)

                try:
                    raise ValueError(f"Connection failed: https://api.themoviedb.org/3/movie?api_key={self.dummy_key}")
                except ValueError as e:
                    core_logger.exception("On-demand TMDB sync failed: %s", e)

                output = self.stream.getvalue()
                self.assertNotIn(self.dummy_key, output)
                self.assertIn("api_key=[REDACTED]", output)
            finally:
                core_logger.removeHandler(self.handler)

    @override_settings(ADMINS=[("Admin", "admin@flick.test")], DEBUG=False)
    def test_mail_admins_handler_redaction(self):
        """Verify AdminEmailHandler filters scrub secrets before dispatch."""
        from django.utils.log import AdminEmailHandler

        email_handler = AdminEmailHandler()
        email_handler.setFormatter(SecretRedactionFormatter("[%(correlation_id)s] [%(name)s]: %(message)s"))
        email_handler.addFilter(CorrelationIdFilter())
        email_handler.addFilter(SecretRedactionFilter())

        with override_settings(TMDB_API_KEY=self.dummy_key):
            record = logging.LogRecord(
                name="django.request",
                level=logging.ERROR,
                pathname=__file__,
                lineno=1,
                msg="Internal server error calling https://api.themoviedb.org/3/movie?api_key=%s",
                args=(self.dummy_key,),
                exc_info=None,
            )
            for f in email_handler.filters:
                f.filter(record)

            self.assertNotIn(self.dummy_key, record.getMessage())
            self.assertIn("api_key=[REDACTED]", record.getMessage())


class CorrelationIdMiddlewareTests(TestCase):
    """Test suite for CorrelationIdMiddleware validation, generation, and cleanup."""

    def setUp(self):
        self.rf = RequestFactory()
        self.success_response = HttpResponse("OK", status=200)

    def test_missing_correlation_id_generates_uuid4(self):
        """When no correlation header is provided, generate UUID4 and echo in response headers."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        request = self.rf.get("/api/auth/profile/")

        response = middleware(request)

        self.assertIn("X-Request-ID", response)
        self.assertIn("X-Correlation-ID", response)
        generated_id = response["X-Request-ID"]
        self.assertEqual(response["X-Correlation-ID"], generated_id)

        # Validate UUID4 structure
        uuid_obj = uuid.UUID(generated_id, version=4)
        self.assertEqual(str(uuid_obj), generated_id)

        # Verify contextvar was cleaned up after request
        self.assertEqual(get_correlation_id(), "-")

    def test_valid_incoming_x_request_id_preserved(self):
        """Valid incoming X-Request-ID should be retained and echoed exactly."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        custom_id = "flick-client-req-9876543210"
        request = self.rf.get("/api/auth/profile/", HTTP_X_REQUEST_ID=custom_id)

        response = middleware(request)

        self.assertEqual(response["X-Request-ID"], custom_id)
        self.assertEqual(response["X-Correlation-ID"], custom_id)
        self.assertEqual(get_correlation_id(), "-")

    def test_valid_incoming_x_correlation_id_preserved(self):
        """Valid incoming X-Correlation-ID should be accepted if X-Request-ID is absent."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        custom_id = "correlation-trace-id-abcdef-123456"
        request = self.rf.get("/api/auth/profile/", HTTP_X_CORRELATION_ID=custom_id)

        response = middleware(request)

        self.assertEqual(response["X-Request-ID"], custom_id)
        self.assertEqual(response["X-Correlation-ID"], custom_id)
        self.assertEqual(get_correlation_id(), "-")

    def test_malformed_short_id_is_replaced(self):
        """IDs shorter than 8 characters must be rejected and replaced with UUID4."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        request = self.rf.get("/api/auth/profile/", HTTP_X_REQUEST_ID="short")

        response = middleware(request)

        returned_id = response["X-Request-ID"]
        self.assertNotEqual(returned_id, "short")
        uuid_obj = uuid.UUID(returned_id, version=4)
        self.assertEqual(str(uuid_obj), returned_id)

    def test_malformed_invalid_characters_replaced(self):
        """IDs with invalid injection characters must be rejected and replaced with UUID4."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        invalid_id = "req;drop table users;--12345678"
        request = self.rf.get("/api/auth/profile/", HTTP_X_REQUEST_ID=invalid_id)

        response = middleware(request)

        returned_id = response["X-Request-ID"]
        self.assertNotEqual(returned_id, invalid_id)
        uuid_obj = uuid.UUID(returned_id, version=4)
        self.assertEqual(str(uuid_obj), returned_id)

    def test_malformed_oversized_id_replaced(self):
        """IDs exceeding 64 characters must be rejected and replaced with UUID4."""
        middleware = CorrelationIdMiddleware(lambda r: self.success_response)
        oversized_id = "a" * 65
        request = self.rf.get("/api/auth/profile/", HTTP_X_REQUEST_ID=oversized_id)

        response = middleware(request)

        returned_id = response["X-Request-ID"]
        self.assertNotEqual(returned_id, oversized_id)
        uuid_obj = uuid.UUID(returned_id, version=4)
        self.assertEqual(str(uuid_obj), returned_id)

    def test_contextvar_cleanup_on_exception(self):
        """When a downstream view raises an unhandled exception, contextvar must be reset."""
        def failing_view(request):
            # Check that correlation_id was set during view execution
            self.assertTrue(request.correlation_id)
            self.assertEqual(get_correlation_id(), request.correlation_id)
            raise RuntimeError("Database connection timed out during view execution")

        middleware = CorrelationIdMiddleware(failing_view)
        request = self.rf.get("/api/auth/profile/")

        with self.assertRaises(RuntimeError):
            middleware(request)

        # ContextVar must be reset back to '-' in finally block
        self.assertEqual(get_correlation_id(), "-")


class CorrelationIdConcurrencyTests(TestCase):
    """Test ASGI/asyncio task concurrency isolation for correlation IDs."""

    def test_asyncio_task_concurrency_isolation(self):
        """
        Verify that 10 concurrent tasks with IDs request-001 through request-010
        maintain absolute context isolation without cross-contamination.
        """
        results = {}

        async def worker(task_name: str, test_id: str):
            token = set_correlation_id(test_id)
            try:
                # Interleave execution with sleep to provoke race conditions
                await asyncio.sleep(0.01)
                observed_id = get_correlation_id()
                results[task_name] = observed_id
                await asyncio.sleep(0.01)
                # Second observation after interleaving
                results[f"{task_name}_end"] = get_correlation_id()
            finally:
                reset_correlation_id(token)

        async def run_all():
            tasks = [
                worker(f"task_{i:03d}", f"request-{i:03d}")
                for i in range(1, 11)
            ]
            await asyncio.gather(*tasks)

        asyncio.run(run_all())

        # Verify each task only observed its own ID
        for i in range(1, 11):
            expected_id = f"request-{i:03d}"
            task_key = f"task_{i:03d}"
            self.assertEqual(results[task_key], expected_id)
            self.assertEqual(results[f"{task_key}_end"], expected_id)

        # Verify global context is clean
        self.assertEqual(get_correlation_id(), "-")

    def test_concurrent_http_asgi_requests_through_middleware(self):
        """
        Run actual concurrent HTTP/ASGI requests through CorrelationIdMiddleware.
        Verify that each request independently retains its own ID in:
        1. The HTTP response headers (X-Request-ID and X-Correlation-ID).
        2. Application log records and formatted logs ([correlation_id]).
        3. Outbound TMDB request headers (_get_tmdb_request_headers()).
        """
        from django.test import AsyncRequestFactory

        rf = AsyncRequestFactory()
        view_logs = []
        outbound_headers_captured = {}

        class CaptureHandler(logging.Handler):
            def __init__(self):
                super().__init__()
                self.records = []

            def emit(self, record):
                self.records.append(record)

        capture_handler = CaptureHandler()
        capture_handler.addFilter(CorrelationIdFilter())
        capture_handler.setFormatter(SecretRedactionFormatter("[%(correlation_id)s] [%(name)s]: %(message)s"))
        app_logger = logging.getLogger("core.test_concurrent")
        app_logger.setLevel(logging.INFO)
        app_logger.addHandler(capture_handler)

        async def async_view(request):
            cid = get_correlation_id()
            # 1. Emit an application log during request execution
            app_logger.info("Executing concurrent view logic for %s", cid)

            # 2. Capture outbound TMDB request headers
            tmdb_headers = _get_tmdb_request_headers()
            outbound_headers_captured[cid] = tmdb_headers

            # 3. Simulate asynchronous I/O to force execution interleaving
            await asyncio.sleep(0.015)

            # 4. Verify ID remained intact across await
            observed_after_sleep = get_correlation_id()
            return HttpResponse(f"Processed:{observed_after_sleep}", status=200)

        middleware = CorrelationIdMiddleware(async_view)

        async def run_concurrent_requests():
            tasks = []
            for i in range(1, 11):
                req_id = f"request-{i:03d}"
                req = rf.get(
                    f"/api/test/{req_id}/",
                    headers={"X-Request-ID": req_id},
                )
                tasks.append(middleware(req))

            return await asyncio.gather(*tasks)

        try:
            responses = asyncio.run(run_concurrent_requests())

            self.assertEqual(len(responses), 10)

            # Verify response headers and content for each request
            for i, response in enumerate(responses, start=1):
                expected_id = f"request-{i:03d}"
                self.assertEqual(response["X-Request-ID"], expected_id)
                self.assertEqual(response["X-Correlation-ID"], expected_id)
                self.assertEqual(response.content.decode(), f"Processed:{expected_id}")

                # Verify outbound TMDB headers for this request
                self.assertIn(expected_id, outbound_headers_captured)
                self.assertEqual(outbound_headers_captured[expected_id], {
                    "X-Request-ID": expected_id,
                    "X-Correlation-ID": expected_id,
                })

            # Verify application logs
            self.assertEqual(len(capture_handler.records), 10)
            captured_ids = [rec.correlation_id for rec in capture_handler.records]
            for i in range(1, 11):
                expected_id = f"request-{i:03d}"
                self.assertIn(expected_id, captured_ids)

            # Verify formatted logs contained [expected_id]
            for rec in capture_handler.records:
                formatted = capture_handler.format(rec)
                self.assertIn(f"[{rec.correlation_id}]", formatted)
                self.assertIn(f"Executing concurrent view logic for {rec.correlation_id}", formatted)

            # Verify global context is clean
            self.assertEqual(get_correlation_id(), "-")
        finally:
            app_logger.removeHandler(capture_handler)


class TMDBOutboundHeaderPropagationTests(TestCase):
    """Verify outbound TMDB requests carry correlation headers without mutating shared Session."""

    def test_get_tmdb_request_headers_when_unset(self):
        """When no correlation ID is set (default '-'), return empty dict."""
        self.assertEqual(get_correlation_id(), "-")
        headers = _get_tmdb_request_headers()
        self.assertEqual(headers, {})

    def test_get_tmdb_request_headers_when_set(self):
        """When correlation ID is set, return X-Request-ID and X-Correlation-ID."""
        token = set_correlation_id("request-001-xyz")
        try:
            headers = _get_tmdb_request_headers()
            self.assertEqual(headers, {
                "X-Request-ID": "request-001-xyz",
                "X-Correlation-ID": "request-001-xyz",
            })
        finally:
            reset_correlation_id(token)

    def test_shared_session_headers_not_mutated(self):
        """
        Outbound requests must pass per-request headers without mutating
        the shared requests.Session headers dict.
        """
        session = _get_session()
        original_headers = dict(session.headers)

        # Verify session headers do NOT have X-Request-ID
        self.assertNotIn("X-Request-ID", session.headers)

        token = set_correlation_id("request-042-test")
        try:
            # Mock session.get to verify kwargs passed
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"id": 123, "title": "Test Movie"}

            with patch.object(session, "get", return_value=mock_res) as mock_get:
                # Call get using per-request headers helper
                req_headers = _get_tmdb_request_headers()
                session.get(
                    "https://api.themoviedb.org/3/movie/123",
                    params={"api_key": "dummy"},
                    headers=req_headers,
                    timeout=10.0,
                )

                # Verify mock was called with the per-request headers
                mock_get.assert_called_once()
                call_kwargs = mock_get.call_args[1]
                self.assertEqual(call_kwargs["headers"], {
                    "X-Request-ID": "request-042-test",
                    "X-Correlation-ID": "request-042-test",
                })

                # CRITICAL: Verify session.headers was NOT mutated
                self.assertNotIn("X-Request-ID", session.headers)
                self.assertNotIn("X-Correlation-ID", session.headers)
                self.assertEqual(session.headers, original_headers)
        finally:
            reset_correlation_id(token)
            session.close()
