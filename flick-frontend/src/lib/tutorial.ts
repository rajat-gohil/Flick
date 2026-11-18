export type TourId = "home" | "session";
export type TourCompletionStatus = "completed" | "skipped";

export interface TourIdentityInput {
  userId?: string | number | null;
  username?: string | null;
  guestUuid?: string | null;
  isAuthenticated?: boolean;
}

export const ANON_ID_STORAGE_KEY = "flick_tour_anon_id_v1";

const TOUR_KEY_PREFIX = "flick_tour_";
const TOUR_KEY_VERSION = "_v1:";

/**
 * Fallback used when localStorage cannot be read at all (e.g. SecurityError, SSR).
 */
const memoryReadUnavailableStore = new Map<string, TourCompletionStatus>();

/**
 * Fallback used when localStorage reads succeed (returning null) but writes throw
 * (e.g. QuotaExceededError).
 */
const memoryWriteFallbackStore = new Map<string, TourCompletionStatus>();

let memoryAnonId: string | null = null;

interface StorageReadResult {
  ok: boolean;
  value: string | null;
}

function safeGetItem(key: string): StorageReadResult {
  if (typeof window === "undefined") {
    return { ok: false, value: null };
  }
  try {
    return { ok: true, value: window.localStorage.getItem(key) };
  } catch {
    return { ok: false, value: null };
  }
}

function safeSetItem(key: string, value: string): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

function safeRemoveItem(key: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore unavailable storage errors
  }
}

function normalizeToken(value: string | number | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  const normalized = String(value).trim();
  return normalized.length > 0 ? normalized : null;
}

function isTourCompletionStatus(value: string | null): value is TourCompletionStatus {
  return value === "completed" || value === "skipped";
}

function generateAnonymousId(): string {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      const uuid = crypto.randomUUID();
      if (uuid && uuid.trim().length > 0) {
        return uuid;
      }
    }
  } catch {
    // Fall through to deterministic-safe random fallback
  }
  return `anon_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function formatTourStorageKey(tourId: TourId, identity: string): string {
  return `${TOUR_KEY_PREFIX}${tourId}${TOUR_KEY_VERSION}${identity}`;
}

export function getOrCreateAnonymousBrowserId(): string {
  const existing = safeGetItem(ANON_ID_STORAGE_KEY);

  if (existing.ok) {
    const normalizedExisting = normalizeToken(existing.value);
    if (normalizedExisting) {
      memoryAnonId = null;
      return normalizedExisting;
    }

    const freshId = generateAnonymousId();
    if (safeSetItem(ANON_ID_STORAGE_KEY, freshId)) {
      memoryAnonId = null;
      return freshId;
    }

    // Storage is readable (returned null) but writes failed (e.g. QuotaExceededError).
    if (!memoryAnonId) {
      memoryAnonId = freshId;
    }
    return memoryAnonId;
  }

  // Storage is completely unavailable (e.g. SecurityError / SSR).
  if (!memoryAnonId) {
    memoryAnonId = generateAnonymousId();
  }
  return memoryAnonId;
}

export function resolveTutorialIdentity(input?: TourIdentityInput): string {
  const explicitUserId = normalizeToken(input?.userId);
  if (explicitUserId) {
    return explicitUserId;
  }

  const storedUserId = normalizeToken(safeGetItem("user_id").value);
  if (storedUserId) {
    return storedUserId;
  }

  const explicitUsername = normalizeToken(input?.username);
  if (explicitUsername) {
    return `user:${explicitUsername}`;
  }

  const authToken = normalizeToken(safeGetItem("auth_token").value);
  const storedUsername = normalizeToken(safeGetItem("username").value);
  if (authToken && storedUsername) {
    return `user:${storedUsername}`;
  }

  const explicitGuestUuid = normalizeToken(input?.guestUuid);
  if (explicitGuestUuid) {
    return `guest_${explicitGuestUuid}`;
  }

  const storedGuestUuid = normalizeToken(safeGetItem("guest_uuid").value);
  if (storedGuestUuid) {
    return `guest_${storedGuestUuid}`;
  }

  return getOrCreateAnonymousBrowserId();
}

export function getTourStorageKey(tourId: TourId, input?: TourIdentityInput): string {
  const identity = resolveTutorialIdentity(input);
  return formatTourStorageKey(tourId, identity);
}

export function getTourStatus(
  tourId: TourId,
  input?: TourIdentityInput
): TourCompletionStatus | null {
  const key = getTourStorageKey(tourId, input);
  const read = safeGetItem(key);

  if (read.ok) {
    if (isTourCompletionStatus(read.value)) {
      return read.value;
    }
    if (read.value === null) {
      return memoryWriteFallbackStore.get(key) ?? null;
    }
    return null;
  }

  return memoryReadUnavailableStore.get(key) ?? memoryWriteFallbackStore.get(key) ?? null;
}

export function hasSeenTour(tourId: TourId, input?: TourIdentityInput): boolean {
  return getTourStatus(tourId, input) !== null;
}

export function markTourFinished(
  tourId: TourId,
  status: TourCompletionStatus,
  input?: TourIdentityInput
): void {
  const key = getTourStorageKey(tourId, input);
  const wrote = safeSetItem(key, status);

  if (wrote) {
    memoryReadUnavailableStore.delete(key);
    memoryWriteFallbackStore.delete(key);
    return;
  }

  const readCheck = safeGetItem(key);
  if (!readCheck.ok) {
    memoryReadUnavailableStore.set(key, status);
  } else {
    memoryWriteFallbackStore.set(key, status);
  }
}

export function resetAllTours(input?: TourIdentityInput): void {
  const candidateIdentities = new Set<string>();
  candidateIdentities.add(resolveTutorialIdentity(input));

  const explicitUserId = normalizeToken(input?.userId);
  if (explicitUserId) {
    candidateIdentities.add(explicitUserId);
  }

  const storedUserId = normalizeToken(safeGetItem("user_id").value);
  if (storedUserId) {
    candidateIdentities.add(storedUserId);
  }

  const explicitUsername = normalizeToken(input?.username);
  if (explicitUsername) {
    candidateIdentities.add(`user:${explicitUsername}`);
  }

  const authToken = normalizeToken(safeGetItem("auth_token").value);
  const storedUsername = normalizeToken(safeGetItem("username").value);
  if (storedUsername && (authToken || explicitUserId || storedUserId)) {
    candidateIdentities.add(`user:${storedUsername}`);
  }

  const explicitGuestUuid = normalizeToken(input?.guestUuid);
  if (explicitGuestUuid) {
    candidateIdentities.add(`guest_${explicitGuestUuid}`);
  }

  const storedGuestUuid = normalizeToken(safeGetItem("guest_uuid").value);
  if (storedGuestUuid) {
    candidateIdentities.add(`guest_${storedGuestUuid}`);
  }

  const tourIds: readonly TourId[] = ["home", "session"];
  for (const identity of candidateIdentities) {
    for (const tourId of tourIds) {
      const key = formatTourStorageKey(tourId, identity);
      safeRemoveItem(key);
      memoryReadUnavailableStore.delete(key);
      memoryWriteFallbackStore.delete(key);
    }
  }
}
