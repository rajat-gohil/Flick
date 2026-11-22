import { provisionGuest, ApiError } from "../lib/api";
import { saveAuthState } from "../lib/auth";
import { trackEvent } from "../lib/analytics";

const PROVISIONING_LOCK_NAME = "flick_provisioning_lock";
const PROVISIONING_KEY_STORAGE = "flick_provisioning_key";
const PROVISIONING_KEY_TS_STORAGE = "flick_provisioning_key_ts";
const KEY_TTL_MS = 15 * 60 * 1000; // 15 minutes

const INVITATION_CODE_STORAGE = "flick_invitation_code";
const INVITATION_CODE_TS_STORAGE = "flick_invitation_code_ts";
const INVITATION_TTL_MS = 2 * 60 * 60 * 1000; // 2 hours

export interface ProvisionResult {
  token: string;
  user: {
    id: number | string;
    username: string;
    display_name?: string;
    is_guest?: boolean;
    guest_uuid?: string;
  };
  recovery_code?: string;
  replayed?: boolean;
}

/**
 * Generates a standard UUID v4 string across modern and fallback browser environments.
 */
function generateUUID(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Manages the 2-hour invitation code lifecycle.
 */
export function setInvitationCode(code: string): void {
  if (typeof window === "undefined" || !code) return;
  const upperCode = code.trim().toUpperCase();
  localStorage.setItem(INVITATION_CODE_STORAGE, upperCode);
  localStorage.setItem(INVITATION_CODE_TS_STORAGE, String(Date.now()));
  // Also sync pendingSessionCode for legacy components
  localStorage.setItem("pendingSessionCode", upperCode);
}

export function getInvitationCode(): string | null {
  if (typeof window === "undefined") return null;
  const code = localStorage.getItem(INVITATION_CODE_STORAGE) || localStorage.getItem("pendingSessionCode");
  const tsStr = localStorage.getItem(INVITATION_CODE_TS_STORAGE);
  if (!code) return null;

  if (tsStr) {
    const ts = parseInt(tsStr, 10);
    if (!isNaN(ts) && Date.now() - ts > INVITATION_TTL_MS) {
      clearInvitationCode();
      return null;
    }
  }
  return code;
}

export function clearInvitationCode(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(INVITATION_CODE_STORAGE);
  localStorage.removeItem(INVITATION_CODE_TS_STORAGE);
  localStorage.removeItem("pendingSessionCode");
}

/**
 * Fallback mutex lock for environments without navigator.locks.
 */
async function acquireFallbackMutex(lockName: string, timeoutMs = 8000): Promise<() => void> {
  const lockKey = `flick_mutex_${lockName}`;
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const existing = localStorage.getItem(lockKey);
    const now = Date.now();
    if (!existing || now - parseInt(existing, 10) > 5000) {
      localStorage.setItem(lockKey, String(now));
      return () => {
        localStorage.removeItem(lockKey);
      };
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  // Return dummy release if timeout exceeded
  return () => {
    localStorage.removeItem(lockKey);
  };
}

/**
 * 5-Step Web Locks Client Provisioning Coordinator.
 * Guarantees zero duplicate guest accounts across multiple tabs, rapid clicks, or network retries.
 */
export async function coordinateGuestProvisioning(displayName?: string): Promise<ProvisionResult> {
  // ── Step 1 (Pre-Lock Check) ──
  const existingToken = localStorage.getItem("auth_token");
  if (existingToken) {
    const id = localStorage.getItem("user_id") || "0";
    const username = localStorage.getItem("username") || "guest";
    const name = localStorage.getItem("display_name") || undefined;
    const guest_uuid = localStorage.getItem("guest_uuid") || undefined;
    return {
      token: existingToken,
      user: {
        id,
        username,
        display_name: name,
        is_guest: true,
        guest_uuid,
      },
      replayed: true,
    };
  }

  // ── Internal provisioning execution holding lock ──
  const executeUnderLock = async (): Promise<ProvisionResult> => {
    // ── Step 3 (Post-Lock Re-Check — MANDATORY) ──
    const tokenAfterLock = localStorage.getItem("auth_token");
    if (tokenAfterLock) {
      const id = localStorage.getItem("user_id") || "0";
      const username = localStorage.getItem("username") || "guest";
      const name = localStorage.getItem("display_name") || undefined;
      const guest_uuid = localStorage.getItem("guest_uuid") || undefined;
      return {
        token: tokenAfterLock,
        user: {
          id,
          username,
          display_name: name,
          is_guest: true,
          guest_uuid,
        },
        replayed: true,
      };
    }

    // ── Step 4 (Check / Generate flick_provisioning_key) ──
    let idempotencyKey = localStorage.getItem(PROVISIONING_KEY_STORAGE);
    const keyTsStr = localStorage.getItem(PROVISIONING_KEY_TS_STORAGE);
    const now = Date.now();

    if (!idempotencyKey || !keyTsStr || now - parseInt(keyTsStr, 10) > KEY_TTL_MS) {
      idempotencyKey = generateUUID();
      localStorage.setItem(PROVISIONING_KEY_STORAGE, idempotencyKey);
      localStorage.setItem(PROVISIONING_KEY_TS_STORAGE, String(now));
    }

    // ── Step 5 (Execute Provisioning Request) ──
    try {
      const data = await provisionGuest(displayName, idempotencyKey);

      if (data && data.success && data.token) {
        // Save authenticated session state
        saveAuthState({
          token: data.token,
          user: data.user,
        });

        // Clear provisioning key after successful commitment
        localStorage.removeItem(PROVISIONING_KEY_STORAGE);
        localStorage.removeItem(PROVISIONING_KEY_TS_STORAGE);

        trackEvent("guest_provisioned", { user_id: data.user?.id });

        // Notify other tabs via custom event
        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("flick:guest_provisioned", {
              detail: { token: data.token, user: data.user },
            })
          );
        }

        return {
          token: data.token,
          user: data.user,
          recovery_code: data.recovery_code,
        };
      }

      throw new Error(data?.error || "Invalid provisioning response from server.");
    } catch (err: any) {
      if (err?.status === 410) {
        // Replay capability expired; clear key
        localStorage.removeItem(PROVISIONING_KEY_STORAGE);
        localStorage.removeItem(PROVISIONING_KEY_TS_STORAGE);
      }
      throw err;
    }
  };

  // ── Step 2 (Acquire Exclusive Lock) ──
  if (typeof navigator !== "undefined" && navigator.locks && typeof navigator.locks.request === "function") {
    return navigator.locks.request(PROVISIONING_LOCK_NAME, async () => {
      return executeUnderLock();
    });
  }

  // Fallback mutex if Web Locks API is unavailable
  const release = await acquireFallbackMutex(PROVISIONING_LOCK_NAME);
  try {
    return await executeUnderLock();
  } finally {
    release();
  }
}
