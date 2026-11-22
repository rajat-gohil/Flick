import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useState } from "react";
import { ThemeProvider } from "../../context/ThemeContext";

// Configurable matchMedia mock (default: reduced motion false)
let reducedMotionMatches = false;
const matchMediaMock = vi.fn().mockImplementation((query: string) => ({
  matches: query === "(prefers-reduced-motion: reduce)" ? reducedMotionMatches : false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}));

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: matchMediaMock,
});

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

// Mock canvas-confetti
vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

// Mock apiRequest while preserving real exports
const mockApiRequest = vi.fn();
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    apiRequest: (...args: unknown[]) => mockApiRequest(...args),
    getWsUrl: () => "ws://127.0.0.1:8000/ws/session/100/",
    getBaseUrl: () => "http://127.0.0.1:8000",
  };
});

// Mock framer-motion (strip motion-only props cleanly without unused variables)
const MOTION_PROPS = new Set([
  "initial",
  "animate",
  "exit",
  "transition",
  "variants",
  "drag",
  "dragConstraints",
  "dragElastic",
  "onDragEnd",
  "whileTap",
  "whileHover",
  "custom",
  "layoutId",
]);

function filterDomProps(props: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props)) {
    if (!MOTION_PROPS.has(key)) {
      out[key] = value;
    }
  }
  return out;
}

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...filterDomProps(props)}>{children as React.ReactNode}</div>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button {...filterDomProps(props)}>{children as React.ReactNode}</button>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...filterDomProps(props)}>{children as React.ReactNode}</span>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: () => {},
}));

import HomePage from "../HomePage";
import ProfilePage from "../ProfilePage";
import SessionPage from "../SessionPage";
import SpotlightTour, { type SpotlightTourStep } from "../../components/SpotlightTour";
import {
  ANON_ID_STORAGE_KEY,
  getOrCreateAnonymousBrowserId,
  getTourStatus,
  getTourStorageKey,
  hasSeenTour,
  markTourFinished,
  resetAllTours,
} from "../../lib/tutorial";

const SAMPLE_CARD_1 = {
  card_index: 0,
  movie_id: 201,
  tmdb_id: 27205,
  title: "Inception",
  overview: "A thief who steals corporate secrets through dream-sharing technology.",
  poster_path: "/inception.jpg",
  backdrop_path: "/inception_bg.jpg",
  rating: 8.8,
  vote_count: 34000,
  release_date: "2010-07-15",
  slot_type: "consensus",
  turn: 1,
  scores: { consensus_score: 94.2 },
};

const SAMPLE_CARD_2 = {
  card_index: 1,
  movie_id: 202,
  tmdb_id: 157336,
  title: "Interstellar",
  overview: "A team of explorers travel through a wormhole in space.",
  poster_path: "/interstellar.jpg",
  backdrop_path: "/interstellar_bg.jpg",
  rating: 8.6,
  vote_count: 32000,
  release_date: "2014-11-05",
  slot_type: "host_priority",
  turn: 1,
  scores: { host_relevance: 96.0 },
};

const DEFAULT_SESSION = {
  id: 100,
  code: "TOUR01",
  host_id: 101,
  guest_id: 202,
  host_joined: true,
  guest_joined: true,
  preferences_set: true,
  user_role: "host" as const,
  user_preferences_set: true,
  host_preferences_set: true,
  guest_preferences_set: true,
  ended: false,
};

function setupAuthUser(userId: number, username: string) {
  window.localStorage.setItem("auth_token", `token_${userId}`);
  window.localStorage.setItem("user_id", String(userId));
  window.localStorage.setItem("username", username);
  window.localStorage.setItem("display_name", username);
}

function mockHomeApis(profile?: { id: number; username: string; display_name?: string }) {
  mockApiRequest.mockImplementation((endpoint: string) => {
    if (endpoint === "/api/users/profile/") {
      return Promise.resolve({
        success: true,
        user: profile ?? {
          id: 101,
          username: "alice",
          display_name: "Alice",
          email: "alice@flick.test",
          email_verified: true,
          is_guest: false,
        },
      });
    }
    if (endpoint.includes("/api/sessions/recent/")) {
      return Promise.resolve({ sessions: [] });
    }
    if (endpoint.includes("/api/discover/") || endpoint.includes("/api/movies/")) {
      return Promise.resolve({
        movies: [
          {
            id: 201,
            tmdb_id: 27205,
            title: "Inception",
            overview: "Dreams inside dreams.",
            poster_path: "/inception.jpg",
            backdrop_path: "/inception_bg.jpg",
            rating: 8.8,
            release_date: "2010-07-15",
          },
        ],
      });
    }
    if (endpoint.includes("/api/watchlist/")) {
      return Promise.resolve({ watchlist: [] });
    }
    return Promise.resolve({});
  });
}

function mockSessionApis(opts?: {
  sessionOverrides?: Partial<typeof DEFAULT_SESSION>;
  deckCardResponse?: Record<string, unknown> | Promise<Record<string, unknown>>;
  onSwipe?: (endpoint: string, options?: unknown) => Record<string, unknown>;
}) {
  let currentCard: {
    card_index: number;
    movie_id: number;
    tmdb_id: number;
    title: string;
    overview: string;
    poster_path: string;
    backdrop_path: string;
    rating: number;
    vote_count: number;
    release_date: string;
    slot_type: string;
    turn: number;
    scores: Record<string, number>;
  } = SAMPLE_CARD_1;
  const session = { ...DEFAULT_SESSION, ...opts?.sessionOverrides };

  mockApiRequest.mockImplementation((endpoint: string, options?: unknown) => {
    if (endpoint === "/api/sessions/100/") {
      return Promise.resolve({ session });
    }
    if (endpoint === "/api/sessions/100/deck/card/") {
      if (opts?.deckCardResponse) {
        return opts.deckCardResponse instanceof Promise
          ? opts.deckCardResponse
          : Promise.resolve(opts.deckCardResponse);
      }
      return Promise.resolve({
        success: true,
        session_id: 100,
        card_index: currentCard.card_index,
        total_cards: 40,
        has_more: true,
        is_completed: false,
        card: currentCard,
        resolved_card_index: 0,
        host_card_index: currentCard.card_index,
        guest_card_index: 0,
        partner_lag: 0,
        waiting_for_partner: false,
      });
    }
    if (endpoint === "/api/sessions/100/deck/swipe/" || endpoint === "/api/swipes/") {
      if (opts?.onSwipe) {
        return Promise.resolve(opts.onSwipe(endpoint, options));
      }
      currentCard = SAMPLE_CARD_2;
      return Promise.resolve({
        success: true,
        idempotent: false,
        card_index: 0,
        next_card_index: 1,
        jointly_resolved: false,
        match_formed: false,
        resolved_card_index: 0,
        host_card_index: 1,
        guest_card_index: 0,
        partner_lag: 1,
        waiting_for_partner: false,
        is_completed: false,
      });
    }
    if (endpoint === "/api/watchlist/") {
      return Promise.resolve({ watchlist: [] });
    }
    if (endpoint.includes("/matches/")) {
      return Promise.resolve({ matches: [] });
    }
    return Promise.resolve({});
  });
}

function renderHome() {
  return render(
    <MemoryRouter initialEntries={["/home"]}>
      <HomePage />
    </MemoryRouter>
  );
}

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={["/profile"]}>
      <ThemeProvider>
        <ProfilePage />
      </ThemeProvider>
    </MemoryRouter>
  );
}

function renderSession() {
  return render(
    <MemoryRouter initialEntries={["/session/100"]}>
      <Routes>
        <Route path="/session/:id" element={<SessionPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function parseTranslate3d(transform: string): { x: number; y: number } {
  const match = transform.match(/translate3d\(([-\d.]+)px,\s*([-\d.]+)px,\s*0(?:px)?\)/);
  if (!match) {
    throw new Error(`Unexpected transform value: "${transform}"`);
  }
  return { x: Number(match[1]), y: Number(match[2]) };
}

describe("Flick Two-Part Spotlight Tutorial System", () => {
  const originalInnerWidth = window.innerWidth;
  const originalInnerHeight = window.innerHeight;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.restoreAllMocks();
    reducedMotionMatches = false;
    window.localStorage.clear();
    resetAllTours({ userId: 101, username: "alice" });
    resetAllTours({ userId: 202, username: "bob" });
    resetAllTours({ userId: 303, username: "carol" });

    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 1024,
    });
    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: 768,
    });

    (window as unknown as { WebSocket: unknown }).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((ev: unknown) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();
    };
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    });
    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: originalInnerHeight,
    });
  });

  /* -----------------------------------------------------------------
     1. First visit shows Homepage tutorial & does NOT mark on open
     ----------------------------------------------------------------- */
  it("1. shows Homepage tutorial at Step 1 of 5 on first visit and does NOT mark completed merely on open", async () => {
    setupAuthUser(101, "alice");
    mockHomeApis({ id: 101, username: "alice" });

    const { unmount } = renderHome();

    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });

    expect(screen.getByText("Step 1 of 5")).not.toBeNull();
    expect(screen.getByText("Welcome to Flick")).not.toBeNull();

    // Opening must NOT persist completion or skip status
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBeNull();
    expect(hasSeenTour("home", { userId: 101 })).toBe(false);

    // Unmounting before completing/skipping leaves state unseen so it still opens on next mount
    unmount();
    renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBeNull();
  });

  /* -----------------------------------------------------------------
     2. Completion persistence across all 5 steps & remount
     ----------------------------------------------------------------- */
  it("2. persists flick_tour_home_v1:<user_id> after completing all 5 steps and does not re-open on remount", async () => {
    setupAuthUser(101, "alice");
    mockHomeApis({ id: 101, username: "alice" });

    const { unmount } = renderHome();

    await waitFor(() => {
      expect(screen.getByText("Welcome to Flick")).not.toBeNull();
    });
    expect(screen.getByText("Step 1 of 5")).not.toBeNull();

    // Step 1 -> Step 2
    fireEvent.click(screen.getByRole("button", { name: /Start Tour/i }));
    expect(screen.getByText("Step 2 of 5")).not.toBeNull();
    expect(screen.getByText("Launch a Screening Deck")).not.toBeNull();

    // Verify Back works
    fireEvent.click(screen.getByRole("button", { name: /^Back$/i }));
    expect(screen.getByText("Step 1 of 5")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Start Tour/i }));
    expect(screen.getByText("Step 2 of 5")).not.toBeNull();

    // Step 2 -> Step 3
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    expect(screen.getByText("Step 3 of 5")).not.toBeNull();
    expect(screen.getByText("Join with a Room Code")).not.toBeNull();

    // Step 3 -> Step 4
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    expect(screen.getByText("Step 4 of 5")).not.toBeNull();
    expect(screen.getByText("Curator's Selection & Catalogue")).not.toBeNull();

    // Step 4 -> Step 5
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    expect(screen.getByText("Step 5 of 5")).not.toBeNull();
    expect(screen.getByText("Navigate the App")).not.toBeNull();

    // Still not marked completed until Finish is clicked
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBeNull();

    // Finish closes tour & persists
    fireEvent.click(screen.getByRole("button", { name: /^Finish$/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBe("completed");
    expect(getTourStatus("home", { userId: 101 })).toBe("completed");

    // Remounting must NOT re-open the tour
    unmount();
    renderHome();
    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/users/profile/");
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  /* -----------------------------------------------------------------
     3. Skip persistence via Skip button and Escape key
     ----------------------------------------------------------------- */
  it("3. persists skipped status when clicking Skip or pressing Escape and does not re-open on remount", async () => {
    setupAuthUser(101, "alice");
    mockHomeApis({ id: 101, username: "alice" });

    // Case A: clicking Skip
    const firstRender = renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });

    fireEvent.click(screen.getByRole("button", { name: /Skip tutorial/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBe("skipped");

    firstRender.unmount();

    const secondRender = renderHome();
    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/users/profile/");
    });
    expect(screen.queryByRole("dialog")).toBeNull();
    secondRender.unmount();

    // Case B: pressing Escape for a fresh user
    window.localStorage.clear();
    setupAuthUser(202, "bob");
    mockHomeApis({ id: 202, username: "bob" });

    const thirdRender = renderHome();
    await waitFor(() => {
      const dialog = screen.getByRole("dialog");
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_home_v1:202")).toBe("skipped");
    thirdRender.unmount();

    renderHome();
    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/users/profile/");
    });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  /* -----------------------------------------------------------------
     4. Independent homepage & session states
     ----------------------------------------------------------------- */
  it("4. keeps homepage and session tutorial states independent in both directions", async () => {
    // Direction A: completing Homepage tutorial does NOT suppress Session tutorial
    setupAuthUser(101, "alice");
    markTourFinished("home", "completed", { userId: 101 });
    expect(hasSeenTour("home", { userId: 101 })).toBe(true);
    expect(hasSeenTour("session", { userId: 101 })).toBe(false);

    mockSessionApis();
    const sessionView = renderSession();

    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
      const dialog = screen.getByRole("dialog");
      expect(dialog.contains(document.activeElement)).toBe(true);
    });
    expect(screen.getByText("Swipe Right to Like")).not.toBeNull();
    sessionView.unmount();

    // Direction B: completing Session tutorial does NOT suppress Homepage tutorial
    window.localStorage.clear();
    setupAuthUser(303, "carol");
    markTourFinished("session", "completed", { userId: 303 });
    expect(hasSeenTour("session", { userId: 303 })).toBe(true);
    expect(hasSeenTour("home", { userId: 303 })).toBe(false);

    mockHomeApis({ id: 303, username: "carol" });
    renderHome();

    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });
    expect(screen.getByText("Welcome to Flick")).not.toBeNull();
  });

  /* -----------------------------------------------------------------
     5. Different authenticated accounts are scoped separately
     ----------------------------------------------------------------- */
  it("5. scopes tutorial completion per account (user 101 completion does NOT suppress user 202)", async () => {
    setupAuthUser(101, "alice");
    mockHomeApis({ id: 101, username: "alice" });

    const user101Render = renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });

    // Complete tour for user 101
    fireEvent.click(screen.getByRole("button", { name: /Start Tour/i }));
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^Finish$/i }));

    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBe("completed");
    expect(window.localStorage.getItem("flick_tour_home_v1:202")).toBeNull();
    user101Render.unmount();

    // Switch to authenticated account 202 (preserving existing tour keys in localStorage)
    setupAuthUser(202, "bob");
    mockHomeApis({ id: 202, username: "bob" });

    renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });
    expect(screen.getByText("Welcome to Flick")).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Skip tutorial/i }));
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBe("completed");
    expect(window.localStorage.getItem("flick_tour_home_v1:202")).toBe("skipped");
  });

  /* -----------------------------------------------------------------
     6. Guest / unauthenticated persistence with stable anonymous ID
     ----------------------------------------------------------------- */
  it("6. assigns a stable anonymous browser id (flick_tour_anon_id_v1) for unauthenticated guests and persists across remounts", async () => {
    // Unauthenticated guest: no auth_token, user_id, username, or guest_uuid
    mockHomeApis();

    const firstRender = renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });

    const anonId = window.localStorage.getItem(ANON_ID_STORAGE_KEY);
    expect(anonId).toBeTruthy();
    expect(getOrCreateAnonymousBrowserId()).toBe(anonId);
    expect(getTourStorageKey("home")).toBe(`flick_tour_home_v1:${anonId}`);

    fireEvent.click(screen.getByRole("button", { name: /Skip tutorial/i }));
    expect(window.localStorage.getItem(`flick_tour_home_v1:${anonId}`)).toBe("skipped");
    firstRender.unmount();

    // Remount as guest: same anon ID, tutorial does not re-open
    renderHome();
    await waitFor(() => {
      expect(screen.getByText(/Launch Screening Deck/i)).not.toBeNull();
    });
    expect(window.localStorage.getItem(ANON_ID_STORAGE_KEY)).toBe(anonId);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  /* -----------------------------------------------------------------
     7. Storage unavailable resilience (SecurityError)
     ----------------------------------------------------------------- */
  it("7. renders and dismisses tutorial cleanly without crashing when localStorage throws SecurityError", async () => {
    mockHomeApis();

    const securityError = new DOMException("Storage access denied", "SecurityError");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw securityError;
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw securityError;
    });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => {
      throw securityError;
    });

    const firstRender = renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });

    // Stepping and dismissing must not throw
    fireEvent.click(screen.getByRole("button", { name: /Start Tour/i }));
    expect(screen.getByText("Step 2 of 5")).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Skip tutorial/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(hasSeenTour("home")).toBe(true);

    // Remounting in the same session respects in-memory fallback
    firstRender.unmount();
    const secondRender = renderHome();
    await waitFor(() => {
      expect(screen.getByText(/Launch Screening Deck/i)).not.toBeNull();
    });
    expect(screen.queryByRole("dialog")).toBeNull();

    // Resetting clears the in-memory fallback too
    resetAllTours();
    expect(hasSeenTour("home")).toBe(false);
    secondRender.unmount();
  });

  /* -----------------------------------------------------------------
     8. Replay Tutorials on ProfilePage resets both tours
     ----------------------------------------------------------------- */
  it("8. clicking 'Replay Tutorials' on ProfilePage resets both homepage and session flags so tours appear again", async () => {
    setupAuthUser(101, "alice");
    markTourFinished("home", "completed", { userId: 101 });
    markTourFinished("session", "skipped", { userId: 101 });
    // Also seed a username-alias key to confirm multi-alias cleanup
    window.localStorage.setItem("flick_tour_home_v1:user:alice", "completed");

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/users/profile/") {
        return Promise.resolve({
          success: true,
          user: {
            id: 101,
            username: "alice",
            display_name: "Alice",
            email: "alice@flick.test",
            email_verified: true,
            total_matches: 4,
            total_swiped: 20,
          },
        });
      }
      return Promise.resolve({});
    });

    const profileView = renderProfile();

    await waitFor(() => {
      expect(screen.getByText(/@alice/)).not.toBeNull();
    });

    const replayBtn = screen.getByRole("button", { name: /Replay Tutorials/i });
    fireEvent.click(replayBtn);

    // Accessible confirmation status appears
    const statusBanner = screen.getByRole("status");
    expect(statusBanner.textContent).toMatch(/Tutorials reset/i);

    // Both keys (and alias) cleared
    expect(window.localStorage.getItem("flick_tour_home_v1:101")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_session_v1:101")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_home_v1:user:alice")).toBeNull();
    expect(hasSeenTour("home", { userId: 101 })).toBe(false);
    expect(hasSeenTour("session", { userId: 101 })).toBe(false);

    profileView.unmount();

    // Homepage tutorial now appears again
    mockHomeApis({ id: 101, username: "alice" });
    const homeView = renderHome();
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
    });
    expect(screen.getByText("Welcome to Flick")).not.toBeNull();
    homeView.unmount();

    // Session tutorial also appears again
    mockSessionApis();
    renderSession();
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
      const dialog = screen.getByRole("dialog");
      expect(dialog.contains(document.activeElement)).toBe(true);
    });
    expect(screen.getByText("Swipe Right to Like")).not.toBeNull();
  });

  /* -----------------------------------------------------------------
     9. Session tutorial trigger conditions
     ----------------------------------------------------------------- */
  describe("9. Session tutorial trigger conditions", () => {
    it("does NOT open while deck card is still loading, then opens once an active movie card is ready", async () => {
      setupAuthUser(101, "alice");
      let resolveDeckCard!: (value: Record<string, unknown>) => void;
      const pendingDeckPromise = new Promise<Record<string, unknown>>((resolve) => {
        resolveDeckCard = resolve;
      });

      mockSessionApis({ deckCardResponse: pendingDeckPromise });
      renderSession();

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/100/deck/card/");
      });
      // Still loading: tutorial must NOT open
      expect(screen.queryByRole("dialog")).toBeNull();

      // Now resolve active movie card
      resolveDeckCard({
        success: true,
        session_id: 100,
        card_index: 0,
        total_cards: 40,
        has_more: true,
        is_completed: false,
        card: SAMPLE_CARD_1,
        resolved_card_index: 0,
        host_card_index: 0,
        guest_card_index: 0,
        partner_lag: 0,
        waiting_for_partner: false,
      });

      await waitFor(() => {
        expect(screen.getByText("Inception")).not.toBeNull();
        expect(screen.getByRole("dialog")).not.toBeNull();
      });
      expect(screen.getByText("Step 1 of 5")).not.toBeNull();
      expect(screen.getByText("Swipe Right to Like")).not.toBeNull();
      // Must NOT auto-mark completed on open
      expect(window.localStorage.getItem("flick_tour_session_v1:101")).toBeNull();
    });

    it("does NOT open while waitingForPartner is true", async () => {
      setupAuthUser(101, "alice");
      mockSessionApis({
        deckCardResponse: {
          success: true,
          session_id: 100,
          card_index: 5,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: SAMPLE_CARD_1,
          resolved_card_index: 0,
          host_card_index: 5,
          guest_card_index: 0,
          partner_lag: 5,
          waiting_for_partner: true,
        },
      });

      renderSession();
      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/100/deck/card/");
      });
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("does NOT open when session has ended", async () => {
      setupAuthUser(101, "alice");
      mockSessionApis({
        sessionOverrides: { ended: true },
      });

      renderSession();
      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/100/");
      });
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("does NOT open when deck has no active movie card", async () => {
      setupAuthUser(101, "alice");
      mockSessionApis({
        deckCardResponse: {
          success: true,
          session_id: 100,
          card_index: 40,
          total_cards: 40,
          has_more: false,
          is_completed: true,
          card: null,
          waiting_for_partner: false,
        },
      });

      renderSession();
      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/100/deck/card/");
      });
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  /* -----------------------------------------------------------------
     10. Swipe & keyboard locking while Session tutorial is open
     ----------------------------------------------------------------- */
  it("10. locks swipe buttons and keyboard shortcuts during Session tutorial, makes zero swipe API calls, and unlocks immediately on dismiss", async () => {
    setupAuthUser(101, "alice");
    mockSessionApis();

    renderSession();

    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
      const dialog = screen.getByRole("dialog");
      expect(dialog.contains(document.activeElement)).toBe(true);
    });

    const likeBtn = screen.getByLabelText("Recommend") as HTMLButtonElement;
    const passBtn = screen.getByLabelText("Pass") as HTMLButtonElement;
    const superLikeBtn = screen.getByLabelText("Priority interest") as HTMLButtonElement;
    const undoBtn = screen.getByLabelText("Recall last action") as HTMLButtonElement;

    // All action buttons disabled while tutorial is open
    expect(likeBtn.disabled).toBe(true);
    expect(passBtn.disabled).toBe(true);
    expect(superLikeBtn.disabled).toBe(true);
    expect(undoBtn.disabled).toBe(true);

    // Clicking disabled buttons does NOT call swipe API
    fireEvent.click(likeBtn);
    fireEvent.click(passBtn);
    fireEvent.click(superLikeBtn);
    fireEvent.click(undoBtn);

    // ArrowUp & Space do NOT trigger superlike or info sheet
    fireEvent.keyDown(document.body, { key: "ArrowUp" });
    fireEvent.keyDown(document.body, { key: " ", code: "Space" });
    expect(screen.queryByText(/Synopsis/i)).toBeNull();

    // ArrowRight / ArrowLeft navigate tutorial steps instead of swiping
    expect(screen.getByText("Step 1 of 5")).not.toBeNull();
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByText("Step 2 of 5")).not.toBeNull();
    expect(screen.getByText("Swipe Left to Pass")).not.toBeNull();

    fireEvent.keyDown(window, { key: "ArrowLeft" });
    expect(screen.getByText("Step 1 of 5")).not.toBeNull();
    expect(screen.getByText("Swipe Right to Like")).not.toBeNull();

    // Verify ZERO swipe calls occurred during tutorial
    const swipeCallsDuringTour = mockApiRequest.mock.calls.filter(
      ([ep]) =>
        typeof ep === "string" &&
        (ep.includes("/deck/swipe/") || ep.includes("/api/swipes/"))
    );
    expect(swipeCallsDuringTour).toHaveLength(0);

    // Press Escape to dismiss tutorial
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(window.localStorage.getItem("flick_tour_session_v1:101")).toBe("skipped");

    // Still zero swipe calls on dismissal
    expect(
      mockApiRequest.mock.calls.filter(
        ([ep]) =>
          typeof ep === "string" &&
          (ep.includes("/deck/swipe/") || ep.includes("/api/swipes/"))
      )
    ).toHaveLength(0);

    // Buttons unlock immediately after tutorial dismissal
    expect(likeBtn.disabled).toBe(false);
    expect(passBtn.disabled).toBe(false);
    expect(superLikeBtn.disabled).toBe(false);

    // Normal button swipe works immediately
    fireEvent.click(likeBtn);
    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/sessions/100/deck/swipe/",
        expect.objectContaining({ method: "POST" })
      );
    });
    await waitFor(() => {
      expect(screen.getByText("Interstellar")).not.toBeNull();
    });

    // Normal keyboard swipe (ArrowRight) also works immediately on the next card
    const swipeCallsBeforeKey = mockApiRequest.mock.calls.filter(
      ([ep]) => typeof ep === "string" && ep.includes("/deck/swipe/")
    ).length;
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    await waitFor(() => {
      const swipeCallsAfterKey = mockApiRequest.mock.calls.filter(
        ([ep]) => typeof ep === "string" && ep.includes("/deck/swipe/")
      ).length;
      expect(swipeCallsAfterKey).toBe(swipeCallsBeforeKey + 1);
    });
  });

  /* -----------------------------------------------------------------
     11. Missing or unmounted spotlight targets fallback to center
     ----------------------------------------------------------------- */
  it("11. falls back cleanly to centered placement when target selector is missing or unmounted", () => {
    const steps: SpotlightTourStep[] = [
      {
        id: "missing-target",
        target: ['[data-tour="does-not-exist"]', '[data-tour="also-missing"]'],
        title: "Missing Target Step",
        description: "Should center cleanly without crashing.",
      },
    ];

    render(
      <SpotlightTour
        isOpen={true}
        steps={steps}
        ariaLabel="Fallback test tour"
        onComplete={vi.fn()}
        onSkip={vi.fn()}
      />
    );

    const dialog = screen.getByTestId("spotlight-tour-dialog");
    expect(dialog.getAttribute("data-tour-placement")).toBe("center");
    expect(screen.queryByTestId("spotlight-tour-mask")).toBeNull();
    expect(screen.getByTestId("spotlight-tour-backdrop")).not.toBeNull();
  });

  /* -----------------------------------------------------------------
     12. Mobile positioning clamps cleanly inside 375x667 viewport
     ----------------------------------------------------------------- */
  it("12. clamps tooltip coordinates inside narrow mobile viewport (375x667) without negative or overflowing values", () => {
    Object.defineProperty(window, "innerWidth", {
      writable: true,
      configurable: true,
      value: 375,
    });
    Object.defineProperty(window, "innerHeight", {
      writable: true,
      configurable: true,
      value: 667,
    });

    const targetEl = document.createElement("button");
    targetEl.setAttribute("data-tour", "edge-target");
    targetEl.textContent = "Edge Action";
    targetEl.getBoundingClientRect = () =>
      ({
        left: 330,
        top: 610,
        right: 370,
        bottom: 650,
        width: 40,
        height: 40,
        x: 330,
        y: 610,
        toJSON: () => ({}),
      }) as DOMRect;
    document.body.appendChild(targetEl);

    try {
      const steps: SpotlightTourStep[] = [
        {
          id: "edge-step",
          target: '[data-tour="edge-target"]',
          title: "Mobile Edge Target",
          description: "Tooltip should clamp cleanly inside the 375x667 viewport.",
        },
      ];

      render(
        <SpotlightTour
          isOpen={true}
          steps={steps}
          ariaLabel="Mobile layout tour"
          onComplete={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      const dialog = screen.getByTestId("spotlight-tour-dialog");
      const widthPx = parseFloat(dialog.style.width);
      const { x, y } = parseTranslate3d(dialog.style.transform);

      expect(widthPx).toBeGreaterThan(0);
      expect(widthPx).toBeLessThanOrEqual(375 - 24);
      expect(x).toBeGreaterThanOrEqual(12);
      expect(y).toBeGreaterThanOrEqual(12);
      expect(x + widthPx).toBeLessThanOrEqual(375 - 12);
      expect(y).toBeLessThan(667);
    } finally {
      targetEl.remove();
    }
  });

  /* -----------------------------------------------------------------
     13. Reduced-motion behavior
     ----------------------------------------------------------------- */
  it("13. respects prefers-reduced-motion (auto scrollIntoView and static gesture hint)", () => {
    reducedMotionMatches = true;

    const targetEl = document.createElement("div");
    targetEl.setAttribute("data-tour", "motion-target");
    const scrollIntoViewSpy = vi.fn();
    targetEl.scrollIntoView = scrollIntoViewSpy;
    targetEl.getBoundingClientRect = () =>
      ({
        left: 120,
        top: 200,
        right: 260,
        bottom: 260,
        width: 140,
        height: 60,
        x: 120,
        y: 200,
        toJSON: () => ({}),
      }) as DOMRect;
    document.body.appendChild(targetEl);

    try {
      const steps: SpotlightTourStep[] = [
        {
          id: "motion-step",
          target: '[data-tour="motion-target"]',
          title: "Reduced Motion Check",
          description: "No smooth scrolling or looping gesture animation.",
          gestureHint: "swipe-right",
        },
      ];

      render(
        <SpotlightTour
          isOpen={true}
          steps={steps}
          ariaLabel="Reduced motion tour"
          onComplete={vi.fn()}
          onSkip={vi.fn()}
        />
      );

      expect(screen.getByTestId("spotlight-tour-root").getAttribute("data-reduced-motion")).toBe(
        "true"
      );
      expect(scrollIntoViewSpy).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "auto" })
      );
      expect(screen.getByTestId("tour-gesture-hint").getAttribute("data-gesture-animated")).toBe(
        "false"
      );
    } finally {
      targetEl.remove();
    }
  });

  /* -----------------------------------------------------------------
     14. Accessibility: ARIA, focus management, focus trap & restoration
     ----------------------------------------------------------------- */
  it("14. enforces dialog ARIA semantics, moves focus in on open, traps Tab, supports keyboard nav, and restores focus on close", () => {
    const steps: SpotlightTourStep[] = [
      {
        id: "a11y-1",
        title: "Accessible Step One",
        description: "First accessible step description.",
      },
      {
        id: "a11y-2",
        title: "Accessible Step Two",
        description: "Second accessible step description.",
      },
    ];

    function TourHarness() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button type="button" onClick={() => setOpen(true)}>
            Open Tour Trigger
          </button>
          <SpotlightTour
            isOpen={open}
            steps={steps}
            ariaLabel="Accessibility verification tour"
            onComplete={() => setOpen(false)}
            onSkip={() => setOpen(false)}
          />
        </div>
      );
    }

    render(<TourHarness />);

    const triggerBtn = screen.getByRole("button", { name: "Open Tour Trigger" });
    triggerBtn.focus();
    expect(document.activeElement).toBe(triggerBtn);

    // Open tour -> focus moves inside dialog
    fireEvent.click(triggerBtn);

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-label")).toBe("Accessibility verification tour");
    expect(dialog.getAttribute("aria-labelledby")).toBeTruthy();
    expect(dialog.getAttribute("aria-describedby")).toBeTruthy();

    const liveRegion = dialog.querySelector('[aria-live="polite"]');
    expect(liveRegion).not.toBeNull();
    expect(liveRegion?.textContent).toContain("Step 1 of 2");

    // Focus moved inside dialog onto primary CTA
    const nextBtn = screen.getByRole("button", { name: /^Next$/i });
    const skipBtn = screen.getByRole("button", { name: /Skip tutorial/i });
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(nextBtn);

    // Tab wraps from last focusable (Next) to first focusable (Skip)
    fireEvent.keyDown(window, { key: "Tab" });
    expect(document.activeElement).toBe(skipBtn);

    // Shift+Tab wraps from first focusable (Skip) back to last focusable (Next)
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(nextBtn);

    // Advance via ArrowRight -> Back button now accessible, Finish button shown
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.getByRole("button", { name: /^Back$/i })).not.toBeNull();
    expect(screen.getByRole("button", { name: /^Finish$/i })).not.toBeNull();

    // Complete via ArrowRight on last step -> dialog closes & focus restores to trigger button
    fireEvent.keyDown(window, { key: "ArrowRight" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(triggerBtn);
  });

  /* -----------------------------------------------------------------
     15. UI/UX Pro Max polish: touch targets, desktop-only shortcuts,
         fixed/sticky scroll guard, tall mobile scroll, contrast ring,
         Replay Tutorials chevron & Session/Home Step 4 targets
     ----------------------------------------------------------------- */
  describe("15. UI/UX Pro Max audit remediation checks", () => {
    it("applies 44x44px touch targets, desktop-only <kbd> shortcut hints, dual-theme spotlight ring, and overscroll containment", () => {
      const targetEl = document.createElement("button");
      targetEl.type = "button";
      targetEl.setAttribute("data-tour", "sample-target");
      targetEl.textContent = "Sample Target";
      targetEl.getBoundingClientRect = () =>
        ({
          x: 40,
          y: 220,
          left: 40,
          top: 220,
          right: 200,
          bottom: 268,
          width: 160,
          height: 48,
          toJSON: () => ({}),
        }) as DOMRect;
      document.body.appendChild(targetEl);

      const steps: SpotlightTourStep[] = [
        {
          id: "step-a",
          target: '[data-tour="sample-target"]',
          title: "Step A",
          description: "First step",
          shortcutHint: "→",
          shortcutLabel: "Like",
        },
        {
          id: "step-b",
          target: '[data-tour="sample-target"]',
          title: "Step B",
          description: "Second step",
        },
      ];

      try {
        render(
          <SpotlightTour
            isOpen={true}
            steps={steps}
            ariaLabel="Polish verification tour"
            onComplete={vi.fn()}
            onSkip={vi.fn()}
          />
        );

        // Touch targets >= 44px with touch-manipulation on Skip & Next
        const skipBtn = screen.getByRole("button", { name: /Skip tutorial/i });
        const nextBtn = screen.getByRole("button", { name: /^Next$/i });
        expect(skipBtn.className).toContain("min-h-[44px]");
        expect(skipBtn.className).toContain("min-w-[44px]");
        expect(skipBtn.className).toContain("touch-manipulation");
        expect(nextBtn.className).toContain("min-h-[44px]");
        expect(nextBtn.className).toContain("touch-manipulation");

        // Desktop-only keyboard shortcut with <kbd> badge and clear label
        const shortcutRow = screen.getByTestId("tour-shortcut-hint");
        expect(shortcutRow.className).toContain("hidden");
        expect(shortcutRow.className).toContain("md:flex");
        const kbd = shortcutRow.querySelector("kbd");
        expect(kbd?.textContent).toBe("→");
        expect(shortcutRow.textContent).toContain("Like");

        // High-contrast dual-theme spotlight ring + touch-none backdrop + scrollable dialog
        const mask = screen.getByTestId("spotlight-tour-mask");
        expect(mask.getAttribute("class")).toContain("touch-none");
        expect(mask.getAttribute("class")).toContain("overscroll-none");
        const ring = screen.getByTestId("spotlight-tour-ring");
        expect(ring.getAttribute("class")).toContain("stroke-white/90");
        expect(ring.getAttribute("class")).toContain("dark:stroke-focus");

        const dialog = screen.getByTestId("spotlight-tour-dialog");
        expect(dialog.className).toContain("overflow-y-auto");
        expect(dialog.className).toContain("overscroll-contain");
        expect(document.documentElement.style.overscrollBehaviorY).toBe("none");

        // Advance to Step B -> Back button also gets 44px touch target
        fireEvent.click(nextBtn);
        const backBtn = screen.getByRole("button", { name: /^Back$/i });
        expect(backBtn.className).toContain("min-h-[44px]");
        expect(backBtn.className).toContain("touch-manipulation");
      } finally {
        targetEl.remove();
      }
    });

    it("skips scrollIntoView for fixed/sticky targets and uses block: 'start' for tall mobile targets", () => {
      const origInnerWidth = window.innerWidth;
      const origInnerHeight = window.innerHeight;
      Object.defineProperty(window, "innerWidth", { configurable: true, value: 375 });
      Object.defineProperty(window, "innerHeight", { configurable: true, value: 667 });

      const fixedScrollSpy = vi.fn();
      const tallScrollSpy = vi.fn();

      const { rerender } = render(
        <div>
          <nav data-tour="fixed-nav" style={{ position: "fixed", bottom: 0 }}>
            Nav
          </nav>
          <div data-tour="tall-card">Tall Card</div>
          <SpotlightTour
            isOpen={false}
            steps={[]}
            ariaLabel="Scroll guard tour"
            onComplete={vi.fn()}
            onSkip={vi.fn()}
          />
        </div>
      );

      const fixedNav = document.querySelector('[data-tour="fixed-nav"]') as HTMLElement;
      const tallCard = document.querySelector('[data-tour="tall-card"]') as HTMLElement;
      fixedNav.scrollIntoView = fixedScrollSpy;
      tallCard.scrollIntoView = tallScrollSpy;

      vi.spyOn(fixedNav, "getBoundingClientRect").mockReturnValue({
        x: 0, y: 595, left: 0, top: 595, right: 375, bottom: 667, width: 375, height: 72, toJSON: () => ({}),
      });
      vi.spyOn(tallCard, "getBoundingClientRect").mockReturnValue({
        x: 16, y: 120, left: 16, top: 120, right: 359, bottom: 420, width: 343, height: 300, toJSON: () => ({}),
      });

      const steps: SpotlightTourStep[] = [
        { id: "fixed-step", target: '[data-tour="fixed-nav"]', title: "Fixed Nav", description: "Bottom nav" },
        { id: "tall-step", target: '[data-tour="tall-card"]', title: "Tall Card", description: "Tall card" },
      ];

      rerender(
        <div>
          <nav data-tour="fixed-nav" style={{ position: "fixed", bottom: 0 }}>
            Nav
          </nav>
          <div data-tour="tall-card">Tall Card</div>
          <SpotlightTour
            isOpen={true}
            steps={steps}
            ariaLabel="Scroll guard tour"
            onComplete={vi.fn()}
            onSkip={vi.fn()}
          />
        </div>
      );

      // Step 1 targets a fixed element -> scrollIntoView must NOT be called
      expect(fixedScrollSpy).not.toHaveBeenCalled();

      // Step 2 targets a tall element on 375px mobile -> scrollIntoView uses block: "start"
      fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
      expect(tallScrollSpy).toHaveBeenCalledWith(
        expect.objectContaining({ block: "start", inline: "nearest" })
      );

      Object.defineProperty(window, "innerWidth", { configurable: true, value: origInnerWidth });
      Object.defineProperty(window, "innerHeight", { configurable: true, value: origInnerHeight });
    });

    it("ProfilePage Replay Tutorials omits misleading chevron and uses 44px Go to Home touch target", async () => {
      setupAuthUser(101, "alice");
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint === "/api/users/profile/") {
          return Promise.resolve({
            success: true,
            user: {
              id: 101,
              username: "alice",
              display_name: "Alice",
              email: "alice@flick.test",
              email_verified: true,
            },
          });
        }
        return Promise.resolve({});
      });

      renderProfile();
      await waitFor(() => {
        expect(screen.getByText(/Replay Tutorials/i)).not.toBeNull();
      });

      const replayBtn = screen.getByRole("button", { name: /Replay Tutorials/i });
      expect(replayBtn.textContent).not.toContain("chevron_right");

      fireEvent.click(replayBtn);
      const goHomeBtn = screen.getByRole("button", { name: /Go to Home/i });
      expect(goHomeBtn.className).toContain("min-h-[44px]");
      expect(goHomeBtn.className).toContain("touch-manipulation");
    });

    it("Session Step 4 spotlights the active movie card instead of the disabled Undo button, and HomePage Step 4 exposes curator feature content", async () => {
      // Session Step 4 check
      setupAuthUser(101, "alice");
      mockSessionApis();
      const sessionView = renderSession();

      await waitFor(() => {
        expect(screen.getByText("Inception")).not.toBeNull();
        expect(screen.getByRole("dialog")).not.toBeNull();
      });

      const cardEl = document.querySelector('[data-tour="session-card"]') as HTMLElement;
      const undoEl = document.querySelector('[data-tour="session-undo"]') as HTMLButtonElement;
      expect(cardEl).not.toBeNull();
      expect(undoEl.disabled).toBe(true);

      const cardRectSpy = vi.spyOn(cardEl, "getBoundingClientRect").mockReturnValue({
        x: 24, y: 80, left: 24, top: 80, right: 350, bottom: 480, width: 326, height: 400, toJSON: () => ({}),
      });
      const undoRectSpy = vi.spyOn(undoEl, "getBoundingClientRect").mockReturnValue({
        x: 32, y: 540, left: 32, top: 540, right: 80, bottom: 588, width: 48, height: 48, toJSON: () => ({}),
      });

      // Step 1 -> 2 -> 3 -> 4 (info-undo)
      fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
      fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));
      fireEvent.click(screen.getByRole("button", { name: /^Next$/i }));

      expect(screen.getByText("Film Info & Undo")).not.toBeNull();
      const ring = screen.getByTestId("spotlight-tour-ring");
      // Ring coordinates match session-card (x=24-8=16, y=80-8=72), NOT disabled undo button (y=532)
      expect(Number(ring.getAttribute("x"))).toBe(16);
      expect(Number(ring.getAttribute("y"))).toBe(72);
      expect(cardRectSpy).toHaveBeenCalled();
      expect(undoRectSpy).not.toHaveBeenCalled();

      sessionView.unmount();

      // HomePage Curator's Selection feature card target check
      window.localStorage.clear();
      setupAuthUser(101, "alice");
      mockHomeApis({ id: 101, username: "alice" });
      renderHome();

      await waitFor(() => {
        expect(document.querySelector('[data-tour="home-curator-feature"]')).not.toBeNull();
      });
    });
  });
});
