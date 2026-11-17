# Flick — HTTP Status Codes, Server Logs & Error-Handling Reference

> A comprehensive, beginner-friendly guide to understanding the numbers, status codes, server logs, queue metrics, and error responses encountered while developing, debugging, and running Flick.

---

## Table of Contents

1. [Quick-Reference Cheat Sheet](#1-quick-reference-cheat-sheet)
2. [What Are HTTP Status Codes?](#2-what-are-http-status-codes)
3. [Complete HTTP Status Code Guide](#3-complete-http-status-code-guide)
   - [2xx — Success](#2xx--successful-responses)
   - [3xx — Redirection & Caching](#3xx--redirection--caching)
   - [4xx — Client Errors](#4xx--client-side-errors)
   - [5xx — Server & Upstream Errors](#5xx--server-side--upstream-errors)
4. [Deciphering Server Logs & Trailing Numbers](#4-deciphering-server-logs--trailing-numbers)
   - [Anatomy of a Django/Daphne Access Log](#anatomy-of-a-djangodaphne-access-log)
   - [What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery)](#what-do-the-trailing-numbers-mean-the-55-vs-1989-mystery)
   - [WSGI vs ASGI Logging Differences](#wsgi-vs-asgi-logging-differences)
5. [Deep Dive: HTTP 304 Not Modified & Caching](#5-deep-dive-http-304-not-modified--caching)
   - [How Browser Caching Works](#how-browser-caching-works)
   - [Conditional Requests (ETag & Last-Modified)](#conditional-requests-etag--last-modified)
   - [How Caching Is Implemented in Flick](#how-caching-is-implemented-in-flick)
   - [When 304 Is Healthy vs When It Is a Problem](#when-304-is-healthy-vs-when-it-is-a-problem)
6. [Flick-Specific Error Handling Architecture](#6-flick-specific-error-handling-architecture)
   - [Frontend Error Handling (`api.ts` & React)](#frontend-error-handling-apits--react)
   - [Backend Error Handling (DRF, Exceptions & Middleware)](#backend-error-handling-drf-exceptions--middleware)
   - [External Service Failure Modes (TMDB, Redis, Postgres)](#external-service-failure-modes-tmdb-redis-postgres)
7. [Background Queue & Worker Numbers](#7-background-queue--worker-numbers)
   - [Queue Priorities & Fair Scheduling Quotas](#queue-priorities--fair-scheduling-quotas)
   - [Worker Leases, Fencing Tokens & Heartbeats](#worker-leases-fencing-tokens--heartbeats)
   - [Retry Limits, Exponential Backoff & Quarantine](#retry-limits-exponential-backoff--quarantine)
   - [TMDB Dual-Bucket Rate Limiter Constants](#tmdb-dual-bucket-rate-limiter-constants)
8. [Frontend & Build-Related Numbers](#8-frontend--build-related-numbers)
   - [Port Numbers](#port-numbers)
   - [Vite Build Counts & Vitest Test Stats](#vite-build-counts--vitest-test-stats)
9. [Practical Troubleshooting Playbook](#9-practical-troubleshooting-playbook)
10. [Glossary of Key Technical Terms](#10-glossary-of-key-technical-terms)

---

## 1. Quick-Reference Cheat Sheet

### At a Glance: What Do These Numbers Mean?

| Log / Status | Meaning | Category | Normal in Flick? | What Action to Take |
| :--- | :--- | :--- | :--- | :--- |
| **`200 55`** | OK: Sent 55-byte payload | Status + Body Size | ✅ Healthy | None. Profile or small JSON loaded. |
| **`200 1989`** | OK: Sent 1,989-byte payload | Status + Body Size | ✅ Healthy | None. Movie collection loaded. |
| **`201`** | Resource Created | Success | ✅ Healthy | None. User or session created. |
| **`204`** | No Content (Success) | Success | ✅ Healthy | None. Logout or delete succeeded. |
| **`304`** | Not Modified (Cache Hit) | Caching | ✅ Healthy | None. Browser used local copy. |
| **`400`** | Bad Request (Validation) | Client Error | ⚠️ Expected | Check invalid form fields / payload. |
| **`401`** | Unauthorized (No/Bad Token)| Client Auth Error| ⚠️ Expected | Client token expired; re-login. |
| **`403`** | Forbidden (No Permission) | Client Perm Error| ⚠️ Expected | Authenticated user lacks permission. |
| **`404`** | Not Found | Client Error | ⚠️ Expected | URL or record ID does not exist. |
| **`409`** | Conflict | Client Error | ⚠️ Expected | Duplicate username or email. |
| **`429`** | Too Many Requests | Rate Limiting | ⚠️ Throttled | Client sent too many requests; wait. |
| **`500`** | Internal Server Error | Server Crash | ❌ Problem | Check backend logs / traceback. |
| **`502`** | Bad Gateway | Upstream Failure | ❌ Problem | TMDB API failed or returned error. |
| **`503`** | Service Unavailable | Infra Offline | ❌ Problem | Redis or database is unreachable. |
| **`504`** | Gateway Timeout | Upstream Timeout | ❌ Problem | TMDB took > 5s to respond. |
| **`5173`** | Vite Dev Server Port | Port Number | ✅ Normal | Access frontend UI in browser. |
| **`8000`** | Django/Daphne Port | Port Number | ✅ Normal | Backend API & WebSocket server. |

---

## 2. What Are HTTP Status Codes?

Whenever a web browser, mobile device, or frontend application (like Flick's React frontend) talks to a backend server (like Flick's Django API), it sends an **HTTP Request**. 

The server answers with an **HTTP Response**. The very first piece of information in that response is a three-digit numerical code called the **HTTP Status Code**.

```text
+-----------------------+                         +----------------------+
|                       |  GET /api/movies/       |                      |
|  Flick Frontend (UI)  | ----------------------> |  Flick Backend (API) |
|  (Browser / Vite)     |                         |  (Django / Daphne)   |
|                       | <---------------------- |                      |
+-----------------------+   HTTP 200 OK + JSON    +----------------------+
```

Status codes are grouped by their first digit:

* **1xx (Informational):** "Hold on, I'm processing your request." (Rarely seen directly in web development).
* **2xx (Success):** "Everything worked! Here is what you asked for."
* **3xx (Redirection & Caching):** "Go look over there, or use the copy you already saved."
* **4xx (Client Error):** "You made a mistake in your request (wrong password, missing parameter, bad URL)."
* **5xx (Server Error):** "I (the server or a third party like TMDB) crashed or failed to complete your request."

---

## 3. Complete HTTP Status Code Guide

### 2xx — Successful Responses

#### HTTP 200 OK
* **Plain English:** "Everything went smoothly. Here is your data."
* **Flick Example:** `GET /api/curators-selection/` returning movie cards, or `GET /api/users/profile/` returning the active user's details.
* **Status in Flick:** *Verified in code & Observed in logs.*

#### HTTP 201 Created
* **Plain English:** "Your request was successful, and a new record was permanently created in the database."
* **Flick Example:** `POST /api/auth/register/` creates a new user; `POST /api/auth/guest-provision/` creates an anonymous guest user profile and returns a session token and recovery code.
* **Status in Flick:** *Verified in code.*

#### HTTP 202 Accepted
* **Plain English:** "I received your request and started working on it, but it will take some time to finish in the background."
* **Flick Example:** Asynchronous background intelligence tasks (e.g., enqueuing a full catalogue reconciliation sweep or large-scale taste profile recomputation).
* **Status in Flick:** *General HTTP Reference / Background Queue Design.*

#### HTTP 204 No Content
* **Plain English:** "The action succeeded, but there is no data to send back in the response body."
* **Flick Example:** Deleting a swipe reaction or logging out of an authenticated session (`POST /api/auth/logout/`).
* **Status in Flick:** *Verified in code.*

---

### 3xx — Redirection & Caching

#### HTTP 301 Moved Permanently
* **Plain English:** "The resource you are looking for has permanently moved to a new URL. Update your bookmarks."
* **Flick Example:** Django redirects requests without a trailing slash (e.g., `/api/movies` → `/api/movies/`) when `APPEND_SLASH=True`.
* **Status in Flick:** *Standard Django behavior.*

#### HTTP 302 Found / Temporary Redirect
* **Plain English:** "The resource is temporarily somewhere else. Go to this other URL for now, but check back here in the future."
* **Flick Example:** OAuth / Google Login redirection flow sending the user to Google's consent screen.
* **Status in Flick:** *Verified in authentication integrations.*

#### HTTP 304 Not Modified
* **Plain English:** "Nothing has changed since you last downloaded this file. Please use your local saved copy to save bandwidth and load faster."
* **Flick Example:** Browsers repeatedly requesting static JavaScript/CSS files or catalog endpoints when caching headers match.
* **Status in Flick:** *Observed in logs & Verified in WhiteNoise/middleware.* (See Section 5 for a dedicated deep dive).

---

### 4xx — Client-Side Errors

#### HTTP 400 Bad Request
* **Plain English:** "The server could not understand what you sent because some information is missing, badly formatted, or invalid."
* **Flick Example:** Submitting a registration form with passwords that do not match, or submitting an invalid `--limit 0` to a management command.
* **Response Format in Flick:**
  ```json
  {
    "success": false,
    "errors": {
      "email": ["Enter a valid email address."]
    }
  }
  ```
* **Status in Flick:** *Verified in code & Observed in logs.*

#### HTTP 401 Unauthorized
* **Plain English:** "You need to log in first. Either no authentication token was provided, or your token has expired or is invalid."
* **Flick Example:** Calling `GET /api/users/profile/` without an `Authorization: Token <token>` header, or using a token after deleting your account.
* **Frontend Reaction:** In Flick's frontend (`backend/flick-frontend/src/lib/api.ts`), receiving a 401 automatically clears `localStorage` and routes the user to the `/login` page.
* **Status in Flick:** *Verified in code.*

#### HTTP 403 Forbidden
* **Plain English:** "I know who you are, but you do not have permission to do this."
* **Flick Example:** A normal member attempting to run administrative actions (like `transition_movie_classification` without `is_staff=True`), or a user trying to access another user's private watchlist.
* **Status in Flick:** *Verified in code.*

#### HTTP 404 Not Found
* **Plain English:** "The item or URL you requested does not exist."
* **Flick Example:** `GET /api/movies/999999/` where movie ID 999999 does not exist, or requesting a deleted screening session.
* **Status in Flick:** *Verified in code.*

#### HTTP 405 Method Not Allowed
* **Plain English:** "This endpoint exists, but it doesn't support the HTTP method you used (for example, trying to `POST` to a view that only supports `GET`)."
* **Flick Example:** Attempting to `POST` JSON data to `GET /api/curators-selection/`.
* **Status in Flick:** *Standard DRF behavior.*

#### HTTP 408 Request Timeout
* **Plain English:** "The server waited for your browser to finish sending the request, but you took too long."
* **Flick Example:** Client network stalls halfway through uploading large images or payloads.
* **Status in Flick:** *General HTTP Reference.*

#### HTTP 409 Conflict
* **Plain English:** "Your request cannot be completed because it conflicts with existing data in the database."
* **Flick Example:** Trying to register an account with a username or email that is already registered by another member.
* **Status in Flick:** *Verified in code.*

#### HTTP 413 Content Too Large
* **Plain English:** "The file or payload you tried to upload exceeds the server's allowed file size limit."
* **Flick Example:** Uploading a custom profile avatar larger than 5 MB.
* **Status in Flick:** *General HTTP Reference.*

#### HTTP 415 Unsupported Media Type
* **Plain English:** "The server refuses to accept the format of the data you sent."
* **Flick Example:** Sending raw HTML or plain text when the endpoint expects `Content-Type: application/json`.
* **Status in Flick:** *Standard DRF behavior.*

#### HTTP 422 Unprocessable Content
* **Plain English:** "The JSON syntax was valid, but the business logic rejected the instructions."
* **Flick Example:** Used by modern REST and GraphQL APIs when validation succeeds syntactically but violates semantic rules.
* **Status in Flick:** *General HTTP Reference.*

#### HTTP 429 Too Many Requests
* **Plain English:** "Slow down! You are sending requests too quickly. Wait a while before trying again."
* **Flick Example:** Flick's `AuthRateThrottle` restricts unauthenticated login attempts to 10 per minute to prevent brute-force attacks. When tripped, DRF returns HTTP 429 with a `Retry-After: 60` header.
* **Status in Flick:** *Verified in code (`core/throttling.py`).*

---

### 5xx — Server-Side & Upstream Errors

#### HTTP 500 Internal Server Error
* **Plain English:** "Something broke inside the backend code. The developers need to check the server logs."
* **Flick Example:** A database connection drops unexpectedly, an uncaught Python `KeyError` or `ValueError` occurs, or code attempts an operation on `None`.
* **Status in Flick:** *Observed during test suites and debugging.*

#### HTTP 502 Bad Gateway
* **Plain English:** "Flick's backend was acting as a bridge to an external service (like The Movie Database / TMDB), and that external service returned an error or sent garbage data."
* **Flick Example:** If TMDB returns an HTTP 500 or HTTP 503 while Flick is fetching movie watch providers, Flick catches the upstream error and returns HTTP 502 to the frontend with `{ "error_code": "UPSTREAM_ERROR" }`.
* **Status in Flick:** *Verified in code (`core/views.py`).*

#### HTTP 503 Service Unavailable
* **Plain English:** "The server is temporarily unable to handle the request because a critical infrastructure service (like Redis or PostgreSQL) is offline or undergoing maintenance."
* **Flick Example:** In production (`DEBUG=False`), Flick enforces a strict **fail-closed contract**: if the Redis cache is unreachable, rate-limited operations immediately return HTTP 503 rather than proceeding unthrottled.
* **Status in Flick:** *Verified in code (`core/services/tmdb_rate_limiter.py`).*

#### HTTP 504 Gateway Timeout
* **Plain English:** "Flick's backend asked an external service (like TMDB) for data, but the external service took too long to reply and Flick gave up waiting."
* **Flick Example:** TMDB API taking longer than the 5.0-second HTTP timeout during watch provider lookups. Flick returns HTTP 504 with `{ "error_code": "UPSTREAM_TIMEOUT" }`.
* **Status in Flick:** *Verified in code (`core/services/tmdb.py`).*

---

## 4. Deciphering Server Logs & Trailing Numbers

### Anatomy of a Django/Daphne Access Log

When running Flick locally, you will see lines like this scrolling in your terminal:

```text
[2026-11-13 18:00:02] [INFO] [d0133b9c-3c47] "GET /api/users/profile/ HTTP/1.1" 200 55
[2026-11-13 18:00:05] [INFO] [a78b41e2-9f12] "GET /api/curators-selection/ HTTP/1.1" 200 1989
[2026-11-13 18:00:08] [INFO] [c1289df4-67aa] "GET /api/movies/ HTTP/1.1" 304 -
```

Let's dissect each component:

```text
 [2026-11-13 18:00:02] [INFO] [d0133b9c-3c47] "GET /api/users/profile/ HTTP/1.1" 200 55
 |___________________| |____| |______________|  |__  |__________________| |______|  |_| |_|
           |              |           |           |            |              |       |   |
      Timestamp         Level   Correlation ID  Method      Endpoint       Protocol Status Response
                                                                                   Code   Size (Bytes)
```

1. **`[2026-11-13 18:00:02]`**: The exact wall-clock date and time the request was completed.
2. **`[INFO]`**: The log severity level. `INFO` is normal operation. `WARNING` is a minor issue (e.g. 404). `ERROR` is a server crash (500).
3. **`[d0133b9c-3c47]` (Correlation ID)**: A unique identifier injected into every request by Flick's `CorrelationIdMiddleware` (`core/logging.py`). It lets developers trace a single user's request across database queries, external API calls, and background workers.
4. **`"GET /api/users/profile/ HTTP/1.1"`**:
   * **`GET`**: The HTTP method (reading data).
   * **`/api/users/profile/`**: The exact URL path requested.
   * **`HTTP/1.1`**: The version of the HTTP protocol used by the browser.
5. **`200`**: The HTTP Status Code (OK).
6. **`55`**: **The Trailing Number**.

---

### What Do the Trailing Numbers Mean? (The 55 vs 1989 Mystery)

> [!IMPORTANT]
> **Verified in Code:** In Django's development server (`WSGIRequestHandler` in `django.core.servers.basehttp` and `ServerHandler.close()` in Python's standard `wsgiref.simple_server`), the trailing number is **`self.bytes_sent`** — the exact size of the HTTP response body in **bytes**.

It is **NOT** milliseconds, response duration, or an error code.

#### Why does `/api/users/profile/` show `200 55`?
The profile endpoint returns a small JSON object with your account details:
```json
{"id": 1, "username": "rajat", "email": "rgohil27@gmail.com"}
```
If you count every character, bracket, and quote in that string, it equals **exactly 55 bytes**. Hence, `200 55`.

#### Why does `/api/curators-selection/` show `200 1989`?
Curator's Selection returns an array of rich movie recommendation cards, complete with titles, poster paths, release years, and taste match reasons:
```json
[
  {"id": 1, "title": "Spider-Man: Brand New Day", "rating": 8.5, ...},
  {"id": 4, "title": "The Odyssey", "rating": 8.4, ...}
]
```
That JSON payload measures **1,989 bytes** (approximately 1.94 Kilobytes). Hence, `200 1989`.

#### Why does `GET /api/movies/` show `304 -` or `304 0`?
Because HTTP 304 means **Not Modified**. The server tells the browser: "You already have the newest version of this catalogue. Use your local copy!" 

Since no movie data needed to travel over the wire, the response body contains **0 bytes**. In server logs, this is shown as `304 0` or `304 -`.

---

### WSGI vs ASGI Logging Differences

Flick supports both traditional WSGI and modern ASGI (via Daphne for WebSockets):

* **WSGI `manage.py runserver --noasgi`:**
  ```text
  "GET /api/users/profile/ HTTP/1.1" 200 55
  ```
  Format: `"<method> <path> <protocol>" <status_code> <response_bytes>`

* **Daphne ASGI `manage.py runserver`:**
  ```text
  HTTP GET /api/users/profile/ 200 [0.03, 127.0.0.1:5173]
  ```
  Format: `HTTP <method> <path> <status_code> [<duration_seconds>, <client_ip:port>]`
  In Daphne's direct console format, the bracketed number `[0.03]` represents the **execution time in seconds** (30 milliseconds).

---

## 5. Deep Dive: HTTP 304 Not Modified & Caching

### How Browser Caching Works

When a user opens Flick, their browser downloads many resources: HTML, JavaScript bundles, CSS styles, poster images, and movie lists.

If the browser had to re-download all of this every single time the user clicked a page, Flick would be slow and waste cellular data.

To solve this, browsers save copies of previously downloaded files on the user's hard drive or phone memory. This is called **browser caching**.

```text
Browser                                                          Server
   |                                                                |
   | 1. Initial Request: GET /api/movies/                           |
   | -------------------------------------------------------------> |
   |                                                                |
   | 2. Full Response: 200 OK (50 KB JSON payload)                  |
   |    Headers: ETag: "v3-abc12345"                                |
   | <------------------------------------------------------------- |
   | (Browser saves 50 KB data and remembers ETag: "v3-abc12345")   |
   |                                                                |
   | 3. Subsequent Request: GET /api/movies/                        |
   |    Headers: If-None-Match: "v3-abc12345"                       |
   | -------------------------------------------------------------> |
   |                                                                |
   | 4. Conditional Check: Server calculates hash -> still abc12345 |
   |    Response: 304 Not Modified (0 bytes payload!)               |
   | <------------------------------------------------------------- |
   | (Browser immediately loads saved copy from disk in 2ms)        |
```

### Conditional Requests (ETag & Last-Modified)

How does the server know the browser's copy is still good? Through two HTTP headers:

1. **`ETag` (Entity Tag):** A unique fingerprint (like an MD5 or SHA hash) of the content. If the movie catalog changes, the ETag fingerprint changes.
2. **`If-None-Match`:** On the next visit, the browser sends this header back: "Here is the ETag fingerprint I saved. Does it still match?" If yes, the server replies `304 Not Modified`.
3. **`Last-Modified` / `If-Modified-Since`:** Same concept, but uses a timestamp instead of a content hash.

### How Caching Is Implemented in Flick

* **Static Assets (JavaScript, CSS, Images):** Flick uses `WhiteNoiseMiddleware` (`backend/settings.py`). WhiteNoise automatically computes content hashes for every compiled `.js` and `.css` file, serving them with permanent caching headers and instant `304 Not Modified` validations.
* **REST API Endpoints:** Flick's API views return fresh JSON responses without forced server-side page caches. When testing in local development with Chrome or Safari, the browser itself may send conditional `If-None-Match` headers on repeated GET requests.
* **Frontend Safe GET Deduplication:** In `backend/flick-frontend/src/lib/api.ts`, Flick maintains a client-side in-memory map of in-flight `GET` requests (`inFlightGetRequests`). If two React components ask for `/api/curators-selection/` at the exact same millisecond, Flick makes **only one** network call and shares the result with both components, preventing redundant requests.

### When 304 Is Healthy vs When It Is a Problem

* **Healthy (99% of the time):** You refresh a page, and the browser loads your profile and movie posters in 15 milliseconds because nothing changed.
* **Problematic (Stale Cache Bug):** If you edited your profile name, refreshed the page, and the server returned `304` showing your *old* name, that means cache invalidation failed. In Flick, mutation endpoints (`POST`, `PUT`, `PATCH`, `DELETE`) do not return 304 and force fresh data fetches.

---

## 6. Flick-Specific Error Handling Architecture

### Frontend Error Handling (`api.ts` & React)

Flick's frontend uses a centralized wrapper called `apiRequest()` around the browser's native `fetch()` API (`backend/flick-frontend/src/lib/api.ts`).

#### 1. The `ApiError` Class
When an API request fails (any status code outside 200–299), `apiRequest()` parses the error response and throws a custom `ApiError`:

```typescript
export class ApiError extends Error {
  status: number;  // e.g. 400, 401, 404, 500
  data: any;       // The parsed JSON payload from the backend
}
```

#### 2. Automatic Error Message Extraction
Backends format errors in different ways (`data.error`, `data.detail`, `data.non_field_errors`, or field-specific objects like `data.errors.password`). 

`ApiError.extractErrorMessage()` automatically traverses the response and picks the best human-readable message:

```typescript
// If backend returns: { "errors": { "password": ["Password too short"] } }
// ApiError.message resolves to: "Password too short"
```

#### 3. Automatic Session Expiration Handling (401 Interceptor)
If any authenticated API call fails with HTTP 401:
1. `apiRequest()` instantly clears all credentials from `localStorage`:
   - `auth_token`
   - `username`, `email`, `user_id`
   - `is_guest`, `guest_uuid`
2. If the user is currently on an authenticated page (like `/profile` or `/curators-selection`), they are automatically redirected to `/login`.
3. If they are on a public page (like `/login`, `/register`, or `/recover`), no redirect loop occurs.

#### 4. Empty States vs. Actual Errors
Flick strictly distinguishes between an empty state and a system error:
* **Empty State (Not an error):** A user with no watch history visits Curator's Selection. The backend returns `HTTP 200 OK` with an empty array `[]`. The UI displays a friendly illustration: *"Your Curator's Selection is empty. Start swiping on movies to train your taste profile!"*
* **System Error:** The backend returns `HTTP 500` or the network is offline. The UI displays an alert banner with a retry button: *"Unable to connect to Flick. Please check your internet connection."*

---

### Backend Error Handling (DRF, Exceptions & Middleware)

#### 1. Custom Exception Handler (`backend/backend/exceptions.py`)
Flick configures Django REST Framework with a custom exception wrapper:

```python
def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "success": False,
            "errors": response.data
        }
    return response
```
Every standard DRF error (validation failures, auth errors, 404s) is normalized into a standard `{ "success": false, "errors": ... }` contract.

#### 2. Secret Redaction Filter (`core/logging.py`)
To prevent developers from accidentally leaking credentials into log files, Flick installs a `SecretRedactionFilter` across all logging handlers. 

It automatically redacts:
* TMDB API keys: `?api_key=[REDACTED]`
* Authorization tokens: `Bearer [REDACTED]`
* Passwords: `?password=[REDACTED]`
* Django's `SECRET_KEY`

#### 3. Request Correlation ID Middleware (`core/middleware.py`)
Every incoming HTTP request is assigned a unique UUID in `X-Correlation-ID`. This ID is attached to every log statement, making it easy to isolate one user's request among thousands of log lines.

---

### External Service Failure Modes (TMDB, Redis, Postgres)

Flick communicates with three external systems. Each has dedicated fail-safe rules:

#### 1. The Movie Database (TMDB)
* **Watch Provider 404:** TMDB does not have streaming providers for every indie film. Previously, a TMDB 404 crashed the view with HTTP 502. **Remediated behavior:** Flick catches the TMDB 404 and safely returns an empty streaming list `providers: []` with HTTP 200 OK.
* **HTTP 429 (Rate Limit):** If TMDB tells Flick to slow down, Flick parses the `Retry-After` header and enforces a global cooldown in Redis/Memory via `record_tmdb_429()`.
* **Timeout / Network Reset:** If TMDB drops the connection (`ConnectionResetError(54)`), Flick fails closed, logs a warning, and retains candidate movies in `needs_review`.

#### 2. Redis
* **Production Mode (`DEBUG=False`):** Fails closed. If Redis dies, the rate limiter refuses requests (`RedisRateLimiterUnavailableError`) to protect upstream APIs.
* **Local Development (`DEBUG=True`):** Fails open into an in-memory dual-bucket rate limiter (`InMemoryTokenBucket`), allowing local development to work even if Redis is not installed.

#### 3. PostgreSQL & SQLite
* **Atomic Transactions:** All provenance transitions and queue updates run inside `transaction.atomic()`. If an error occurs halfway through, every database change rolls back.
* **Row Locking (`select_for_update(skip_locked=True)`):** When background workers claim jobs, they lock rows atomically so two workers never process the same movie at the same time.

---

## 7. Background Queue & Worker Numbers

Flick uses an asynchronous, PostgreSQL-backed queue service (`core/services/catalogue_queue.py`) driven by dedicated background workers (`core/management/commands/run_intelligence_worker.py`).

Here is what all the numerical metrics in the queue code control:

### Queue Priorities & Fair Scheduling Quotas

Jobs are given an integer priority (lower number = higher urgency):

| Priority Number | Classification | Example Task | Fair Scheduling Quota |
| :--- | :--- | :--- | :--- |
| **`<= 50`** | **High Priority** | User-triggered taste recomputations | **60% of batch** |
| **`51 – 150`** | **Normal Priority**| TMDB movie enrichment / classification | **30% of batch** |
| **`> 150`** | **Low Priority** | Nightly staleness sweeps, full syncs | **10% of batch** |

> [!NOTE]
> **Why Quotas Exist:** Without fair scheduling, a flood of 10,000 background movie enrichments would block user taste profile updates for hours. Flick reserves 60% of every claim batch for high-priority tasks while dynamically borrowing unused quota.

---

### Worker Leases, Fencing Tokens & Heartbeats

* **`batch_size = 10`**: A worker claims up to 10 jobs at a time from the database.
* **`lease_duration = 60` seconds**: When a worker claims a job, it owns the lease for 60 seconds. No other worker can touch it.
* **`heartbeat interval = 20` seconds (`lease_duration // 3`)**: While a worker is processing a long task, a background timer sends a heartbeat to the database every 20 seconds, extending the lease by another 60 seconds.
* **`claim_generation` (Fencing Token)**: An integer on each job that increases by `+1` every time the job is claimed. If a worker gets frozen by garbage collection and tries to finish a job whose generation has moved on, the database rejects the completion (`StaleLeaseOwnershipError`).

---

### Retry Limits, Exponential Backoff & Quarantine

When an external API or network error causes a job to fail:

* **`max_attempts = 5`**: A job is retried up to 5 times.
* **Exponential Backoff Formula**:
  $$\text{backoff\_seconds} = \min(300, 10 \times 2^{\text{attempts} - 1})$$
  * **Attempt 1 Failure:** Waits $10 \times 2^0 = \mathbf{10\text{ seconds}}$
  * **Attempt 2 Failure:** Waits $10 \times 2^1 = \mathbf{20\text{ seconds}}$
  * **Attempt 3 Failure:** Waits $10 \times 2^2 = \mathbf{40\text{ seconds}}$
  * **Attempt 4 Failure:** Waits $10 \times 2^3 = \mathbf{80\text{ seconds}}$
  * **Attempt 5 Failure:** Waits $10 \times 2^4 = \mathbf{160\text{ seconds}}$
* **`failed_permanent` (Dead Letter / Quarantine):** If a job fails all 5 attempts, it is quarantined with status `failed_permanent`. It stops consuming CPU cycles and awaits developer inspection in `job.last_error`.

---

### TMDB Dual-Bucket Rate Limiter Constants

Flick regulates all TMDB requests using a token bucket rate limiter (`core/services/tmdb_rate_limiter.py`):

```text
                  Total TMDB Budget: 4.0 tokens / sec
                                 |
                 +---------------+---------------+
                 |                               |
       Interactive Bucket               Background Bucket
       Fill Rate: 1.2 tokens/sec        Fill Rate: 2.8 tokens/sec
       Burst Max: 2.0 tokens            Burst Max: 2.0 tokens
       (User searches, details)         (Queue workers, enrichments)
```

* **`TARGET_BUDGET_RPS = 4.0`**: Flick limits overall TMDB consumption to 4 requests per second.
* **`BACKGROUND_FILL_RATE = 2.8` tokens/sec**: 70% of capacity is allocated to background workers.
* **`INTERACTIVE_FILL_RATE = 1.2` tokens/sec**: 30% of capacity is reserved for real-time user browsing.
* **Priority Borrowing:** If a user performs an interactive action (like viewing streaming providers) and the interactive bucket is empty, it is permitted to borrow tokens from the background bucket. Background jobs can never borrow from the interactive bucket!
* **`DEFAULT_COOLDOWN_SECONDS = 12.0`**: If TMDB returns an HTTP 429 without a `Retry-After` header, Flick halts all TMDB requests for 12 seconds + 0.5s–2.0s random jitter.

---

## 8. Frontend & Build-Related Numbers

### Port Numbers

A port number is like an apartment number in a large building. The IP address gets you to the computer; the port gets you to the specific application running on it:

| Port | Service | Purpose |
| :--- | :--- | :--- |
| **`5173`** | Vite Development Server | Serves Flick's React frontend UI and handles hot-module reloading. |
| **`8000`** | Django & Daphne Server | Serves the Python REST API, Admin portal, and WebSockets. |
| **`5432`** | PostgreSQL Database | The primary production database server. |
| **`6379`** | Redis Cache & Message Broker| Holds rate limit tokens, session chemistry, and Celery/Channels. |

> [!TIP]
> In `backend/flick-frontend/vite.config.ts`, Vite is configured with `strictPort: true`. If port 5173 is already in use, Vite will fail with an error rather than silently moving to port 5174, preventing CORS and cookie mismatch bugs.

---

### Vite Build Counts & Vitest Test Stats

When building or testing the frontend, you will see output like:

```text
✓ 142 modules transformed.
dist/index.html                   0.82 kB │ gzip:  0.41 kB
dist/assets/index-D7K9xQ.css      4.12 kB │ gzip:  1.32 kB
dist/assets/index-B2pLm1.js     148.24 kB │ gzip: 42.18 kB
✓ built in 420ms
```

* **`142 modules transformed`**: The number of individual TypeScript, JSX, and CSS files compiled into production bundles.
* **`dist/assets/... 148.24 kB │ gzip: 42.18 kB`**:
  * **148.24 kB (Uncompressed size):** The size of the code on disk.
  * **42.18 kB (Gzipped size):** The actual number of bytes transferred over the internet to the user's phone. A smaller gzipped number means faster page loads!
* **Vitest Stats (`Tests 109 passed (109)`):** Indicates that 109 automated regression assertions verified UI state, API errors, and authentication lifecycles with zero failures.

---

## 9. Practical Troubleshooting Playbook

When you see a specific status code or error in your logs, use this table to diagnose it immediately:

### 1. `200 55`
* **Plain English:** Successful response with a small 55-byte payload.
* **Severity:** ✅ Healthy / Normal.
* **Action Needed:** None. This is standard behavior for user profile lookups (`GET /api/users/profile/`).

### 2. `200 1989`
* **Plain English:** Successful response with a 1,989-byte payload.
* **Severity:** ✅ Healthy / Normal.
* **Action Needed:** None. This is standard behavior for movie recommendation lists (`GET /api/curators-selection/`).

### 3. `304 -` or `304 0`
* **Plain English:** Not Modified. The client used its cached copy.
* **Severity:** ✅ Healthy / Normal.
* **Action Needed:** None. If the client is displaying outdated data after a database edit, perform a hard refresh (`Cmd + Shift + R` or `Ctrl + F5`) to bypass browser caching.

### 4. `400 Bad Request`
* **Plain English:** Validation rejected by Django REST Framework serializer.
* **Severity:** ⚠️ Warning / User Error.
* **Action Needed:** Inspect the request payload in your browser DevTools Network tab. Check the JSON response for the exact field that failed validation (e.g. `{"errors": {"email": ["Invalid format"]}}`).

### 5. `401 Unauthorized`
* **Plain English:** The request lacked a valid `Authorization: Token <token>` header.
* **Severity:** ⚠️ Expected when sessions expire.
* **Action Needed:** In the frontend, check if `localStorage.getItem("auth_token")` exists. Log in again via `/login`.

### 6. `403 Forbidden`
* **Plain English:** Permission denied.
* **Severity:** ⚠️ Permission issue.
* **Action Needed:** If calling administrative endpoints (like movie reclassification), verify the user has `is_staff=True` in the database (`python manage.py correct_synthetic_m1_records`).

### 7. `404 Not Found`
* **Plain English:** Requested URL or record does not exist.
* **Severity:** ⚠️ Warning.
* **Action Needed:** Verify the URL spelling and check whether a trailing slash is required (e.g. `/api/movies/` instead of `/api/movies`). Verify the database record ID exists.

### 8. `429 Too Many Requests`
* **Plain English:** Client hit a rate limiter limit.
* **Severity:** ⚠️ Warning.
* **Action Needed:** Wait for the duration specified in the `Retry-After` header (typically 60 seconds). If encountered in tests, check if test fixtures are properly mocked.

### 9. `500 Internal Server Error`
* **Plain English:** Unhandled Python exception crashed the backend view.
* **Severity:** ❌ Critical Bug.
* **Action Needed:** Look at your backend terminal console. Locate the Python traceback to identify the exact file and line number that crashed.

### 10. `502 Bad Gateway`
* **Plain English:** Upstream third-party service (TMDB) failed.
* **Severity:** ❌ External Failure.
* **Action Needed:** Check TMDB API status. Check `core/services/tmdb.py` logs to see if TMDB returned an HTTP 500/503.

### 11. `503 Service Unavailable`
* **Plain English:** A core dependency (Postgres or Redis) is unreachable.
* **Severity:** ❌ Infrastructure Outage.
* **Action Needed:** In production, check if Redis is running and reachable via `REDIS_URL`. In development, ensure `DEBUG=True` to allow in-memory fallbacks.

### 12. `504 Gateway Timeout`
* **Plain English:** An upstream network request to TMDB took longer than 5 seconds.
* **Severity:** ❌ Upstream Timeout.
* **Action Needed:** Check your internet connection or verify TMDB API latency.

### 13. `ConnectionResetError(54, 'Connection reset by peer')`
* **Plain English:** The remote server (e.g. TMDB) suddenly closed the TCP connection while data was being transmitted.
* **Severity:** ⚠️ Network Transient.
* **Action Needed:** Safe to ignore on isolated occurrences. Flick's background worker catches this error, leaves the record in `needs_review`, and allows it to be retried on the next pass.

### 14. `ECONNREFUSED 127.0.0.1:8000`
* **Plain English:** The frontend tried to contact the backend, but the backend server is not running!
* **Severity:** ❌ Local Development Error.
* **Action Needed:** Start your Django development server: `cd backend && python manage.py runserver`.

### 15. `AbortError: The operation was aborted`
* **Plain English:** A frontend component unmounted or cancelled an in-flight network request before it finished.
* **Severity:** ✅ Healthy / Normal.
* **Action Needed:** None. Flick's `api.ts` implements caller cancellation safety, ensuring aborted components do not crash the app or cancel shared in-flight requests.

### 16. `CatalogueJob status = failed_permanent`
* **Plain English:** A background job failed all 5 retry attempts and was quarantined.
* **Severity:** ⚠️ Attention Required.
* **Action Needed:** Inspect `CatalogueJob.objects.filter(status='failed_permanent')` and read `job.last_error` to diagnose the root cause.

---

## 10. Glossary of Key Technical Terms

* **API (Application Programming Interface):** The set of rules and endpoints through which the React frontend asks the Django backend for data.
* **ASGI (Asynchronous Server Gateway Interface):** The modern Python standard for async web servers, used by Daphne to power Flick's WebSockets and real-time features.
* **Correlation ID:** A unique string (UUID) assigned to a request that tags every log line generated during that request's lifecycle.
* **Dead Letter / Quarantine:** A safe holding area for background jobs that have repeatedly failed, preventing them from looping infinitely and wasting server resources.
* **ETag (Entity Tag):** A cryptographic fingerprint of a web page or file used by browsers to determine if their cached copy is still fresh.
* **Fail-Closed:** A security principle where a system defaults to blocking access if its verification mechanism (like a rate limiter or auth service) is offline.
* **Fencing Token (`claim_generation`):** A monotonically increasing number used in distributed systems to prevent stale, delayed workers from overwriting newer data.
* **Idempotency:** A property of an operation where doing it once produces the same result as doing it ten times (e.g., classifying an already-classified movie).
* **Payload:** The actual data body sent inside an HTTP request or response (excluding headers).
* **Token Bucket:** A rate-limiting algorithm where tokens refill at a steady rate. Each request costs one token; if the bucket is empty, requests must wait.
* **WSGI (Web Server Gateway Interface):** The traditional synchronous Python standard for web applications, used by standard Django `runserver`.
