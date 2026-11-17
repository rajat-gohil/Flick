/**
 * Normalizes and returns the API base URL.
 * In development, defaults to "" (relative URL) so all requests route through
 * Vite's development proxy on any Wi-Fi/LAN IP or localhost.
 * In production, requires VITE_API_BASE_URL (or logs an explicit configuration error if missing).
 */
export function getApiBaseUrl(): string {
  const envVal = import.meta.env.VITE_API_BASE_URL;

  // In production, require VITE_API_BASE_URL
  if (import.meta.env.PROD) {
    if (!envVal || typeof envVal !== "string" || !envVal.trim()) {
      console.error(
        "[Flick] Missing VITE_API_BASE_URL in production environment. API requests will fail."
      );
      return "";
    }
    return envVal.trim().replace(/\/+$/, "");
  }

  // In development:
  // If VITE_API_BASE_URL is explicitly set to an absolute URL, honor it;
  // otherwise, default to "" (relative URL) so all requests go through Vite's local dev proxy.
  if (envVal && typeof envVal === "string" && envVal.trim()) {
    return envVal.trim().replace(/\/+$/, "");
  }

  return "";
}

export const getBaseUrl = getApiBaseUrl;

/**
 * Returns the WebSocket base URL for real-time matchmaking & session events.
 * In production:
 *   1. Uses VITE_WS_BASE_URL if explicitly configured.
 *   2. Or derives from VITE_API_BASE_URL (http -> ws, https -> wss).
 * In development:
 *   1. If VITE_WS_BASE_URL is explicitly set to a non-empty string, honor it.
 *   2. Otherwise derives the WebSocket URL directly from window.location (current host & port)
 *      so it seamlessly routes through Vite's dev proxy on any Wi-Fi/LAN IP or localhost.
 */
export function getWsBaseUrl(): string {
  const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
  const wsEnv = import.meta.env.VITE_WS_BASE_URL;
  const apiEnv = import.meta.env.VITE_API_BASE_URL;

  // Explicit VITE_WS_BASE_URL takes precedence
  if (wsEnv && typeof wsEnv === "string" && wsEnv.trim()) {
    let clean = wsEnv.trim().replace(/\/+$/, "");
    if (clean.startsWith("https://")) clean = clean.replace(/^https:\/\//, "wss://");
    if (clean.startsWith("http://")) clean = clean.replace(/^http:\/\//, "ws://");
    if (isHttps && clean.startsWith("ws://")) {
      clean = clean.replace(/^ws:\/\//, "wss://");
    }
    return clean;
  }

  // In production, derive from VITE_API_BASE_URL if WS URL is not explicitly set
  if (import.meta.env.PROD) {
    if (apiEnv && typeof apiEnv === "string" && apiEnv.trim()) {
      let clean = apiEnv.trim().replace(/\/+$/, "");
      if (clean.startsWith("https://")) clean = clean.replace(/^https:\/\//, "wss://");
      else if (clean.startsWith("http://")) clean = clean.replace(/^http:\/\//, "ws://");
      else clean = (isHttps ? "wss://" : "ws://") + clean;
      if (isHttps && clean.startsWith("ws://")) {
        clean = clean.replace(/^ws:\/\//, "wss://");
      }
      return clean;
    }
    console.error(
      "[Flick] Missing VITE_WS_BASE_URL or VITE_API_BASE_URL in production environment. WebSocket connections will fail."
    );
  }

  // Development with Vite proxy:
  // Derive WebSocket URL directly from window.location (same host & port as Vite)
  // Vite proxy forwards ws:// to Django Channels on loopback
  if (typeof window !== "undefined") {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}`;
  }

  return "ws://127.0.0.1:5173";
}

export function getWsUrl(sessionId: string | number): string {
  const base = getWsBaseUrl();
  return `${base}/ws/session/${sessionId}/`;
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, data: any, message?: string) {
    const resolvedMessage =
      message ||
      ApiError.extractErrorMessage(data) ||
      `Request failed with status ${status}`;
    super(resolvedMessage);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  static extractErrorMessage(data: any): string | undefined {
    if (!data) return undefined;
    if (typeof data === "string") return data;
    if (typeof data.error === "string") return data.error;
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
    if (Array.isArray(data.non_field_errors) && data.non_field_errors.length > 0) {
      return String(data.non_field_errors[0]);
    }
    if (data.errors && typeof data.errors === "object") {
      if (typeof data.errors.detail === "string") return data.errors.detail;
      if (Array.isArray(data.errors.non_field_errors) && data.errors.non_field_errors.length > 0) {
        return String(data.errors.non_field_errors[0]);
      }
      for (const key of Object.keys(data.errors)) {
        const val = data.errors[key];
        if (Array.isArray(val) && val.length > 0 && typeof val[0] === "string") {
          return `${val[0]}`;
        }
        if (typeof val === "string") return val;
      }
    }
    if (typeof data === "object") {
      for (const key of Object.keys(data)) {
        if (key === "status" || key === "code") continue;
        const val = data[key];
        if (Array.isArray(val) && val.length > 0 && typeof val[0] === "string") {
          return `${val[0]}`;
        }
      }
    }
    return undefined;
  }
}

const PUBLIC_ENDPOINTS = [
  "/api/auth/login/",
  "/api/auth/register/",
  "/api/auth/password-reset/",
  "/api/auth/password-reset-confirm/",
  "/api/auth/verify-email/",
  "/api/auth/guest-provision/",
  "/api/auth/guest-recover/",
  "/api/genres/",
  "/api/discover/",
];

function isPublicEndpoint(endpoint: string): boolean {
  return PUBLIC_ENDPOINTS.some((pub) => endpoint.startsWith(pub));
}

/* ===================================================================
   Client-Side Safe GET In-Flight Request Deduplication
   =================================================================== */

const inFlightGetRequests = new Map<string, Promise<any>>();

export function getInFlightRequestCount(): number {
  return inFlightGetRequests.size;
}

export function clearInFlightRequests(): void {
  inFlightGetRequests.clear();
}

/**
 * Derives a deterministic deduplication key for safe in-flight GET requests.
 * Incorporates auth context (token identity) and normalized URL.
 */
function buildDeduplicationKey(
  fullUrl: string,
  token: string | null,
  customHeaders?: HeadersInit
): string {
  const authContext = token ? `auth:${token}` : "anon";
  let customHeaderStr = "";
  if (customHeaders && typeof customHeaders === "object" && !Array.isArray(customHeaders)) {
    const keys = Object.keys(customHeaders).sort();
    if (keys.length > 0) {
      customHeaderStr = "::" + keys.map((k) => `${k.toLowerCase()}=${(customHeaders as any)[k]}`).join("&");
    }
  }
  return `${authContext}::GET::${fullUrl}${customHeaderStr}`;
}

export async function apiRequest(
  endpoint: string,
  options: RequestInit = {}
) {
  const token = localStorage.getItem("auth_token");
  const method = (options.method || "GET").toUpperCase();
  const isGetRequest = method === "GET";

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Token ${token}` } : {}),
    ...(options.headers || {}),
  };

  const baseUrl = getBaseUrl();
  const normalizedEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const fullUrl = `${baseUrl}${normalizedEndpoint}`;

  // Execute underlying HTTP fetch
  const executeFetch = async (fetchSignal?: AbortSignal | null) => {
    const response = await fetch(fullUrl, {
      ...options,
      headers,
      signal: fetchSignal || undefined,
    });

    // Read response safely (handles empty bodies and non-JSON responses)
    const text = await response.text();
    let data: any = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { error: text };
      }
    }

    if (!response.ok) {
      // On 401 Unauthorized for authenticated endpoints, clear invalid auth state and redirect
      if (response.status === 401 && !isPublicEndpoint(normalizedEndpoint)) {
        localStorage.removeItem("auth_token");
        localStorage.removeItem("username");
        localStorage.removeItem("email");
        localStorage.removeItem("user_id");
        localStorage.removeItem("is_guest");
        localStorage.removeItem("guest_uuid");

        if (
          typeof window !== "undefined" &&
          window.location.pathname !== "/login" &&
          window.location.pathname !== "/register" &&
          window.location.pathname !== "/recover" &&
          window.location.pathname !== "/"
        ) {
          window.location.href = "/login";
        }
      }

      throw new ApiError(response.status, data);
    }

    return data;
  };

  // Only deduplicate safe GET requests
  if (!isGetRequest) {
    return executeFetch(options.signal);
  }

  const dedupKey = buildDeduplicationKey(fullUrl, token, options.headers);

  let sharedPromise = inFlightGetRequests.get(dedupKey);
  if (!sharedPromise) {
    sharedPromise = executeFetch(null).finally(() => {
      inFlightGetRequests.delete(dedupKey);
    });
    inFlightGetRequests.set(dedupKey, sharedPromise);
  }

  // Caller cancellation safety: individual AbortSignal rejects only this caller
  // without aborting the shared underlying fetch required by other callers.
  if (options.signal) {
    const signal = options.signal;
    if (signal.aborted) {
      return Promise.reject(new DOMException("The operation was aborted.", "AbortError"));
    }
    return new Promise((resolve, reject) => {
      const onAbort = () => {
        reject(new DOMException("The operation was aborted.", "AbortError"));
      };
      signal.addEventListener("abort", onAbort, { once: true });
      sharedPromise!
        .then((result) => {
          signal.removeEventListener("abort", onAbort);
          resolve(result);
        })
        .catch((err) => {
          signal.removeEventListener("abort", onAbort);
          reject(err);
        });
    });
  }

  return sharedPromise;
}

/* ===================================================================
   Guest Account API Helpers
   =================================================================== */

export interface GuestProvisionResponse {
  success: boolean;
  token: string;
  recovery_code: string;
  user: {
    id: number;
    username: string;
    display_name: string;
    guest_uuid: string;
    is_guest: boolean;
  };
}

export interface GuestRecoverResponse {
  success: boolean;
  token: string;
  recovery_code: string;
  user: {
    id: number;
    username: string;
    display_name: string;
    guest_uuid: string;
    is_guest: boolean;
  };
  handoff_pending: boolean;
}

export interface GuestRecoveryAckResponse {
  success: boolean;
  message: string;
  handoff_pending: boolean;
}

export interface GuestConvertResponse {
  success: boolean;
  message: string;
  token: string;
  user: {
    id: number;
    username: string;
    email: string;
    display_name: string;
    guest_uuid: string;
    is_guest: boolean;
  };
}

export async function provisionGuest(displayName?: string): Promise<GuestProvisionResponse> {
  return apiRequest("/api/auth/guest-provision/", {
    method: "POST",
    body: JSON.stringify(displayName ? { display_name: displayName } : {}),
  });
}

export async function recoverGuest(recoveryCode: string): Promise<GuestRecoverResponse> {
  return apiRequest("/api/auth/guest-recover/", {
    method: "POST",
    body: JSON.stringify({ recovery_code: recoveryCode }),
  });
}

export async function acknowledgeRecovery(): Promise<GuestRecoveryAckResponse> {
  return apiRequest("/api/auth/guest-recovery-ack/", {
    method: "POST",
  });
}

export async function convertGuestAccount(payload: {
  email: string;
  password: string;
  display_name?: string;
}): Promise<GuestConvertResponse> {
  return apiRequest("/api/auth/guest-convert/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

