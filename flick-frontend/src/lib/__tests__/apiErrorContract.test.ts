import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiRequest, ApiError } from "../api";

describe("ApiError Contract & apiRequest Error Normalization", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("ApiError class correctly inherits from Error and preserves status and data", () => {
    const error = new ApiError(400, { error: "Custom validation error" });
    expect(error).toBeInstanceOf(Error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.name).toBe("ApiError");
    expect(error.status).toBe(400);
    expect(error.data).toEqual({ error: "Custom validation error" });
    expect(error.message).toBe("Custom validation error");
  });

  it("extracts error message from data.detail on HTTP 404", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: async () => JSON.stringify({ detail: "Session not found." }),
    } as unknown as Response);

    let thrown: any = null;
    try {
      await apiRequest("/api/sessions/999/");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(404);
    expect(thrown.data).toEqual({ detail: "Session not found." });
    expect(thrown.message).toBe("Session not found.");
  });

  it("extracts error message from data.error on HTTP 400", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
      text: async () => JSON.stringify({ error: "Room is already full" }),
    } as unknown as Response);

    let thrown: any = null;
    try {
      await apiRequest("/api/sessions/join/", { method: "POST" });
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(400);
    expect(thrown.data).toEqual({ error: "Room is already full" });
    expect(thrown.message).toBe("Room is already full");
  });

  it("extracts error message from data.non_field_errors on HTTP 409", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 409,
      statusText: "Conflict",
      text: async () => JSON.stringify({ non_field_errors: ["Session is already full."] }),
    } as unknown as Response);

    let thrown: any = null;
    try {
      await apiRequest("/api/sessions/join/", { method: "POST" });
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(409);
    expect(thrown.message).toBe("Session is already full.");
  });

  it("handles non-JSON error bodies gracefully on HTTP 500", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: async () => "Internal server error occurred",
    } as unknown as Response);

    let thrown: any = null;
    try {
      await apiRequest("/api/sessions/crash/");
    } catch (err) {
      thrown = err;
    }

    expect(thrown).toBeInstanceOf(Error);
    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown.status).toBe(500);
    expect(thrown.message).toBe("Internal server error occurred");
  });
});
