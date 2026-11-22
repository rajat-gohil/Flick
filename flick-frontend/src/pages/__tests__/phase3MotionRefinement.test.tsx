import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// Mock analytics module
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

// Mock api module
const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/101/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

// Filter out Framer Motion DOM attributes to prevent React DOM warnings
const MOTION_PROPS = new Set([
  "layoutId", "layout", "whileTap", "whileHover", "whileFocus", "whileDrag",
  "initial", "animate", "exit", "transition", "variants"
]);

function stripMotionProps(props: Record<string, unknown>) {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (!MOTION_PROPS.has(k)) clean[k] = v;
  }
  return clean;
}

// Mock framer-motion with clean DOM props
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...stripMotionProps(props)}>{children as React.ReactNode}</div>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button {...stripMotionProps(props)}>{children as React.ReactNode}</button>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...stripMotionProps(props)}>{children as React.ReactNode}</span>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: () => {},
}));

// Mock confetti
vi.mock("canvas-confetti", () => ({ default: vi.fn() }));

// Mock tutorial to avoid tour overlay locking user interactions
vi.mock("../../lib/tutorial", () => ({
  hasSeenTour: vi.fn(() => true),
  markTourFinished: vi.fn(),
}));

// Mock sound
vi.mock("../../lib/sound", () => ({
  sound: {
    playLike: vi.fn(),
    playPass: vi.fn(),
    playSuperlike: vi.fn(),
    playUndo: vi.fn(),
    playCommitTick: vi.fn(),
  },
}));

import SessionPage from "../SessionPage";
import WatchlistPage from "../WatchlistPage";

function makeWebSocketStub() {
  return class {
    onopen: (() => void) | null = null;
    onclose: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: (() => void) | null = null;
    send = vi.fn();
    close = vi.fn();
    constructor() {
      setTimeout(() => this.onopen?.(), 10);
    }
  };
}

describe("Phase 3 Motion Refinement: Screening Climax & Feedback Dynamics", () => {
  let matchMediaMock: ReturnType<typeof vi.fn>;
  let realWebSocket: typeof globalThis.WebSocket;

  const mockSessionData = {
    session: {
      id: 101,
      code: "TEST101",
      state: "swiping",
      ended: false,
      user_role: "host",
      host_joined: true,
      guest_joined: true,
      preferences_set: true,
      user_preferences_set: true,
      host_preferences_set: true,
      guest_preferences_set: true,
      participant_name: "Andrei",
      partner_name: "Natalya",
      affinity_percent: 75,
      matched_count: 1,
      reviewed_count: 1,
      manifest_version: 1,
    },
  };

  const mockDeckCardData = {
    success: true,
    session_id: 101,
    deck_card_index: 0,
    total_deck_cards: 10,
    card: {
      card_index: 0,
      movie_id: 55,
      title: "Solaris",
      overview: "A psychologist is sent to a station orbiting Solaris.",
      poster_path: "https://example.com/solaris.jpg",
      rating: 8.1,
      release_date: "1972-03-20",
      slot_type: "mutual_affinity",
    },
    next_card: {
      card_index: 1,
      movie_id: 56,
      title: "Stalker",
      overview: "A guide leads two men into the Zone.",
      poster_path: "https://example.com/stalker.jpg",
      rating: 8.2,
      release_date: "1979-05-13",
      slot_type: "curator_pick",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "mock-token-xyz");

    realWebSocket = globalThis.WebSocket;
    globalThis.WebSocket = makeWebSocketStub() as unknown as typeof WebSocket;

    matchMediaMock = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    window.matchMedia = matchMediaMock as unknown as typeof window.matchMedia;
  });

  afterEach(() => {
    globalThis.WebSocket = realWebSocket;
  });

  /* ==========================================================================
     1. THEATRE SPOTLIGHT & MATCH CELEBRATION MODAL
     ========================================================================== */

  it("1. renders theatre spotlight radial glow and elastic stamp badge on match reveal", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/deck/card/")) {
        return Promise.resolve(mockDeckCardData);
      }
      if (url.includes("/api/sessions/101/deck/swipe/")) {
        return Promise.resolve({
          success: true,
          match_formed: true,
          matched: true,
          match_type: "mutual_superlike",
          superlike_attribution: "mutual",
          matched_movie: {
            id: 55,
            title: "Solaris",
            poster_url: "https://example.com/solaris.jpg",
            rating: 8.1,
            release_year: 1972,
            match_type: "mutual_superlike",
            superlike_attribution: "mutual",
          },
          card: {
            id: 56,
            movie_id: 56,
            title: "Stalker",
            overview: "A guide leads two men into the Zone.",
            poster_url: "https://example.com/stalker.jpg",
            rating: 8.2,
            release_year: 1979,
            slot_type: "curator_pick",
          },
        });
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(mockSessionData);
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      if (url.includes("/api/streaming/")) {
        return Promise.resolve({ options: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for card to load
    await waitFor(() => {
      expect(screen.getByText("Solaris")).not.toBeNull();
    });

    // Click like to trigger match
    const likeBtn = screen.getByTitle("Recommend");
    fireEvent.click(likeBtn);

    // Wait for match modal with Theatre Spotlight
    await waitFor(() => {
      expect(screen.getByTestId("match-theatre-spotlight")).not.toBeNull();
      expect(screen.getByTestId("match-stamp-badge")).not.toBeNull();
      expect(screen.getByTestId("match-poster-stage")).not.toBeNull();
    });

    const badge = screen.getByTestId("match-stamp-badge");
    expect(badge.textContent).toContain("Mutual Super-Like");

    const attribution = screen.getByTestId("match-attribution-badge");
    expect(attribution.textContent).toContain("Mutual Priority Interest");
  });

  /* ==========================================================================
     2. PARTNER PRESENCE RADAR PULSE
     ========================================================================== */

  it("2. renders partner radar pulse when partner is online and suppresses in reduced-motion mode", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/deck/card/")) {
        return Promise.resolve(mockDeckCardData);
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(mockSessionData);
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    const { unmount } = render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Under standard motion, radar pulse should be active
    await waitFor(() => {
      expect(screen.getByTestId("partner-status-dot")).not.toBeNull();
      expect(screen.getByTestId("partner-radar-pulse")).not.toBeNull();
    });

    unmount();

    // Now test with prefers-reduced-motion = true
    matchMediaMock.mockImplementation((query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Status dot must still render, but radar pulse ring must be suppressed
    await waitFor(() => {
      expect(screen.getByTestId("partner-status-dot")).not.toBeNull();
    });
    expect(screen.queryByTestId("partner-radar-pulse")).toBeNull();
  });

  /* ==========================================================================
     3. LIVE AFFINITY BAR INTERPOLATION
     ========================================================================== */

  it("3. renders live affinity hairline bar during swiping and recap progress meter at conclusion", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/deck/card/")) {
        return Promise.resolve(mockDeckCardData);
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(mockSessionData);
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    const { unmount } = render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Verify live hairline bar renders with title and testId
    await waitFor(() => {
      const liveBar = screen.getByTestId("live-affinity-bar");
      expect(liveBar).not.toBeNull();
    });

    unmount();

    // Now test session concluded state
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/matches/")) {
        return Promise.resolve({
          matches: [
            {
              session_id: 101,
              movie_id: 55,
              movie_title: "Solaris",
              rating: 8.1,
              release_year: 1972,
              poster_url: "https://example.com/solaris.jpg",
            },
          ],
        });
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve({
          session: {
            ...mockSessionData.session,
            state: "concluded",
            ended: true,
            affinity_percent: 68,
            matched_count: 1,
            reviewed_count: 5,
          },
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).not.toBeNull();
    });

    expect(screen.getByTestId("stat-affinity-percent").textContent).toBe("68%");
    expect(screen.getByTestId("recap-affinity-progress")).not.toBeNull();
  });

  /* ==========================================================================
     4. WATCHLIST PAGE ANIMATIONS & EXIT DYNAMICS
     ========================================================================== */

  it("4. handles WatchlistPage filter switching, item removal, and viewing toggles", async () => {
    const mockWatchlist = [
      {
        id: 10,
        movie_id: 55,
        movie_title: "Solaris",
        poster_url: "https://example.com/solaris.jpg",
        rating: 8.1,
        release_year: 1972,
        trailer_url: "https://youtube.com/watch?v=123",
        session_id: 101,
        added_at: "2026-11-19T10:00:00Z",
        watched: false,
      },
      {
        id: 11,
        movie_id: 56,
        movie_title: "Stalker",
        poster_url: "https://example.com/stalker.jpg",
        rating: 8.2,
        release_year: 1979,
        trailer_url: null,
        session_id: 101,
        added_at: "2026-11-19T10:05:00Z",
        watched: true,
      },
    ];

    mockApiRequest.mockImplementation((url: string, opts?: { method?: string; body?: string }) => {
      if (url.includes("/api/watchlist/") && !opts?.method) {
        return Promise.resolve({ watchlist: mockWatchlist });
      }
      if (url.includes("/api/watchlist/55/") && opts?.method === "PATCH") {
        return Promise.resolve({ success: true, watched: true });
      }
      if (url.includes("/api/watchlist/55/") && opts?.method === "DELETE") {
        return Promise.resolve({ success: true });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/watchlist"]}>
        <Routes>
          <Route path="/watchlist" element={<WatchlistPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Initial load: 2 items
    await waitFor(() => {
      expect(screen.getByText("Solaris")).not.toBeNull();
      expect(screen.getByText("Stalker")).not.toBeNull();
    });

    // Check filter switching to Pending (unwatched only)
    const pendingFilterBtn = screen.getByRole("button", { name: /^pending$/i });
    fireEvent.click(pendingFilterBtn);

    await waitFor(() => {
      expect(screen.getByText("Solaris")).not.toBeNull();
      expect(screen.queryByText("Stalker")).toBeNull();
    });

    // Switch to Viewed filter
    const viewedFilterBtn = screen.getByRole("button", { name: /^viewed$/i });
    fireEvent.click(viewedFilterBtn);

    await waitFor(() => {
      expect(screen.queryByText("Solaris")).toBeNull();
      expect(screen.getByText("Stalker")).not.toBeNull();
    });

    // Switch back to All
    const allFilterBtn = screen.getByRole("button", { name: /^all$/i });
    fireEvent.click(allFilterBtn);

    await waitFor(() => {
      expect(screen.getByText("Solaris")).not.toBeNull();
      expect(screen.getByText("Stalker")).not.toBeNull();
    });

    // Toggle Mark Viewed on Solaris
    const markViewedBtn = screen.getByRole("button", { name: /mark viewed/i });
    fireEvent.click(markViewedBtn);

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/watchlist/55/",
        expect.objectContaining({ method: "PATCH" })
      );
    });

    // Remove Solaris from watchlist
    const removeBtns = screen.getAllByLabelText("Remove from watchlist");
    fireEvent.click(removeBtns[0]);

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/watchlist/55/",
        expect.objectContaining({ method: "DELETE" })
      );
      expect(screen.queryByText("Solaris")).toBeNull();
    });
  });
});
