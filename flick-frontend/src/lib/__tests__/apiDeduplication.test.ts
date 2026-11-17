import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiRequest, ApiError, getInFlightRequestCount, clearInFlightRequests } from "../api";

describe("Client-Side Request Deduplication (Requirement 7)", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    clearInFlightRequests();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    clearInFlightRequests();
  });

  it("deduplicates identical concurrent GET requests into a single in-flight fetch", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      // Simulate network delay
      await new Promise((r) => setTimeout(r, 20));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true, count: fetchCount }),
      } as unknown as Response;
    });

    // Fire 3 simultaneous GET requests for the same endpoint
    const p1 = apiRequest("/api/sessions/recent/");
    const p2 = apiRequest("/api/sessions/recent/");
    const p3 = apiRequest("/api/sessions/recent/");

    // In-flight registry should contain exactly 1 entry
    expect(getInFlightRequestCount()).toBe(1);

    const [r1, r2, r3] = await Promise.all([p1, p2, p3]);

    expect(fetchCount).toBe(1);
    expect(r1).toEqual({ success: true, count: 1 });
    expect(r2).toEqual({ success: true, count: 1 });
    expect(r3).toEqual({ success: true, count: 1 });

    // After settlement, registry must be cleaned up
    expect(getInFlightRequestCount()).toBe(0);
  });

  it("does not deduplicate requests with different query parameters", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      await new Promise((r) => setTimeout(r, 10));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      } as unknown as Response;
    });

    const p1 = apiRequest("/api/movies/101/streaming-options/?region=IN");
    const p2 = apiRequest("/api/movies/101/streaming-options/?region=US");

    expect(getInFlightRequestCount()).toBe(2);

    await Promise.all([p1, p2]);
    expect(fetchCount).toBe(2);
    expect(getInFlightRequestCount()).toBe(0);
  });

  it("does not deduplicate across different authentication contexts", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      await new Promise((r) => setTimeout(r, 10));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      } as unknown as Response;
    });

    // Request 1: anonymous
    localStorage.removeItem("auth_token");
    const p1 = apiRequest("/api/genres/");

    // Request 2: authenticated user A
    localStorage.setItem("auth_token", "token-user-a");
    const p2 = apiRequest("/api/genres/");

    expect(getInFlightRequestCount()).toBe(2);

    await Promise.all([p1, p2]);
    expect(fetchCount).toBe(2);
  });

  it("never deduplicates mutation requests (POST, PUT, PATCH, DELETE)", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      await new Promise((r) => setTimeout(r, 10));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true }),
      } as unknown as Response;
    });

    const p1 = apiRequest("/api/sessions/join/", { method: "POST", body: JSON.stringify({ code: "ABC" }) });
    const p2 = apiRequest("/api/sessions/join/", { method: "POST", body: JSON.stringify({ code: "ABC" }) });

    // Mutations must not be registered in inFlightGetRequests
    expect(getInFlightRequestCount()).toBe(0);

    await Promise.all([p1, p2]);
    expect(fetchCount).toBe(2);
  });

  it("cleans up failed requests immediately and propagates ApiError to all concurrent callers", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      await new Promise((r) => setTimeout(r, 10));
      return {
        ok: false,
        status: 500,
        statusText: "Server Error",
        text: async () => JSON.stringify({ error: "Database offline" }),
      } as unknown as Response;
    });

    const p1 = apiRequest("/api/sessions/recent/");
    const p2 = apiRequest("/api/sessions/recent/");

    expect(getInFlightRequestCount()).toBe(1);

    const [e1, e2] = await Promise.allSettled([p1, p2]);

    expect(fetchCount).toBe(1);
    expect(e1.status).toBe("rejected");
    expect(e2.status).toBe("rejected");
    if (e1.status === "rejected" && e2.status === "rejected") {
      expect(e1.reason).toBeInstanceOf(ApiError);
      expect(e2.reason).toBeInstanceOf(ApiError);
      expect((e1.reason as ApiError).status).toBe(500);
      expect((e2.reason as ApiError).message).toBe("Database offline");
    }

    // Must be cleaned up on failure
    expect(getInFlightRequestCount()).toBe(0);

    // Subsequent call should initiate a fresh request, not serve cached failure
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      text: async () => JSON.stringify({ success: true }),
    } as unknown as Response);

    const p3 = await apiRequest("/api/sessions/recent/");
    expect(p3).toEqual({ success: true });
  });

  it("cleans up after settlement so subsequent requests make fresh calls", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ count: fetchCount }),
      } as unknown as Response;
    });

    const res1 = await apiRequest("/api/sessions/recent/");
    expect(res1.count).toBe(1);
    expect(getInFlightRequestCount()).toBe(0);

    const res2 = await apiRequest("/api/sessions/recent/");
    expect(res2.count).toBe(2);
    expect(fetchCount).toBe(2);
  });

  it("handles AbortSignal safely: aborting one caller does not cancel shared in-flight fetch for others", async () => {
    let fetchCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(async () => {
      fetchCount++;
      await new Promise((r) => setTimeout(r, 30));
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify({ success: true, count: fetchCount }),
      } as unknown as Response;
    });

    const abortController = new AbortController();

    // Caller 1: with AbortSignal that aborts early
    const p1 = apiRequest("/api/sessions/recent/", { signal: abortController.signal });
    // Caller 2: without AbortSignal
    const p2 = apiRequest("/api/sessions/recent/");

    expect(getInFlightRequestCount()).toBe(1);

    // Abort Caller 1 after 5ms
    setTimeout(() => {
      abortController.abort();
    }, 5);

    const [r1, r2] = await Promise.allSettled([p1, p2]);

    // Caller 1 must be rejected with AbortError
    expect(r1.status).toBe("rejected");
    if (r1.status === "rejected") {
      expect((r1.reason as DOMException).name).toBe("AbortError");
    }

    // Caller 2 must still receive the successful response!
    expect(r2.status).toBe("fulfilled");
    if (r2.status === "fulfilled") {
      expect(r2.value).toEqual({ success: true, count: 1 });
    }

    expect(fetchCount).toBe(1);
    expect(getInFlightRequestCount()).toBe(0);
  });
});
