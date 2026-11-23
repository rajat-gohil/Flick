import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";
import SessionPage from "../SessionPage";

// Filter out Framer Motion DOM attributes to prevent React DOM warnings in jsdom
const MOTION_PROPS = new Set([
  "layoutId", "layout", "whileTap", "whileHover", "whileFocus", "whileDrag",
  "initial", "animate", "exit", "transition", "variants",
  "drag", "dragConstraints", "dragElastic", "onDragEnd", "onDragStart", "custom"
]);

function stripMotionProps(props: Record<string, unknown>) {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (!MOTION_PROPS.has(k)) clean[k] = v;
  }
  return clean;
}

// Stub window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getWsUrl: (id: string | number) => `ws://127.0.0.1:8000/ws/session/${id}/`,
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...stripMotionProps(props)}>{children}</div>,
    button: ({ children, ...props }: any) => <button {...stripMotionProps(props)}>{children}</button>,
    span: ({ children, ...props }: any) => <span {...stripMotionProps(props)}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {}, on: vi.fn() }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: vi.fn(),
}));

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("Session Theatrical Elevation: Phase 1 Infrastructure & Deduplication", () => {
  let wsInstances: any[] = [];

  class MockWebSocket {
    static OPEN = 1;
    static CLOSED = 3;
    static CONNECTING = 0;
    readyState = MockWebSocket.OPEN;
    url: string;
    protocols?: string | string[];
    onopen: (() => void) | null = null;
    onmessage: ((event: { data: string }) => void) | null = null;
    onerror: ((err: any) => void) | null = null;
    onclose: ((event: { code: number; reason: string }) => void) | null = null;

    constructor(url: string, protocols?: string | string[]) {
      this.url = url;
      this.protocols = protocols;
      wsInstances.push(this);
      setTimeout(() => {
        if (this.onopen) this.onopen();
      }, 0);
    }

    send() {}
    close(code = 1000, reason = "") {
      this.readyState = MockWebSocket.CLOSED;
      if (this.onclose) this.onclose({ code, reason });
    }
  }

  beforeEach(() => {
    wsInstances = [];
    (globalThis as any).WebSocket = MockWebSocket as any;
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const baseSessionData = {
    session: {
      id: 101,
      code: "CINEMA-99",
      host_joined: true,
      guest_joined: true,
      preferences_set: true,
      user_preferences_set: true,
      user_role: "host",
      ended: false,
      matched_count: 0,
      reviewed_count: 0,
      affinity_percent: 0,
    },
    recommendations: [
      {
        id: 550,
        title: "Fight Club",
        overview: "An insomniac office worker...",
        poster_url: "https://image.tmdb.org/t/p/w780/fightclub.jpg",
        rating: 8.4,
        release_year: 1999,
      },
    ],
  };

  it("1. Deduplicates concurrent match events arriving while metadata is pending", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/deck/card/")) {
        return Promise.resolve({
          success: true,
          is_legacy: true,
        });
      }
      if (url.includes("/api/recommendations/")) {
        return Promise.resolve({
          movies: baseSessionData.recommendations,
        });
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(baseSessionData);
      }
      if (url.includes("/api/matches/")) {
        return Promise.resolve({ success: true, matches: [] });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ success: true, watchlist: [] });
      }
      if (url.includes("/api/movies/807/")) {
        // Return a delayed promise simulating in-flight metadata retrieval
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve({
              id: 807,
              title: "Se7en",
              overview: "Two detectives hunt a serial killer...",
              poster_url: "https://image.tmdb.org/t/p/w780/se7en.jpg",
              rating: 8.6,
              release_year: 1995,
            });
          }, 50);
        });
      }
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(wsInstances.length).toBeGreaterThan(0);
    });

    const ws = wsInstances[0];

    // Deliver first match_event (metadata retrieval will be pending)
    act(() => {
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: "match_event",
            session_id: 101,
            movie_id: 807,
            movie_title: "Se7en",
            superlike_attribution: "mutual",
            match_type: "mutual_superlike",
          }),
        });
      }
    });

    // Deliver exact duplicate match_event while metadata is still pending
    act(() => {
      if (ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: "match_event",
            session_id: 101,
            movie_id: 807,
            movie_title: "Se7en",
            superlike_attribution: "mutual",
            match_type: "mutual_superlike",
          }),
        });
      }
    });

    // Assert that the CurtainCallMatchModal dialog renders
    await waitFor(() => {
      expect(screen.getByRole("dialog")).not.toBeNull();
      expect(screen.getByText("Se7en")).not.toBeNull();
    });

    // Modal should only render once, not duplicated
    const dialogs = screen.getAllByRole("dialog");
    expect(dialogs.length).toBe(1);
  });

  it("2. Renders 3-tier deck layers and 35mm sprocket borders in Full Mode", async () => {
    const multiMovieSession = {
      ...baseSessionData,
      recommendations: [
        {
          id: 1,
          title: "Blade Runner",
          overview: "A blade runner must pursue replicants...",
          poster_url: "https://image.tmdb.org/t/p/w780/bladerunner.jpg",
          rating: 8.1,
          release_year: 1982,
        },
        {
          id: 2,
          title: "Stalker",
          overview: "A guide leads two men into the Zone...",
          poster_url: "https://image.tmdb.org/t/p/w780/stalker.jpg",
          rating: 8.2,
          release_year: 1979,
        },
        {
          id: 3,
          title: "Metropolis",
          overview: "In a futuristic city sharply divided...",
          poster_url: "https://image.tmdb.org/t/p/w780/metropolis.jpg",
          rating: 8.3,
          release_year: 1927,
        },
      ],
    };

    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/101/deck/card/")) {
        return Promise.resolve({
          success: true,
          is_legacy: true,
        });
      }
      if (url.includes("/api/recommendations/")) {
        return Promise.resolve({
          movies: multiMovieSession.recommendations,
        });
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(multiMovieSession);
      }
      if (url.includes("/api/matches/")) {
        return Promise.resolve({ success: true, matches: [] });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ success: true, watchlist: [] });
      }
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Blade Runner")).not.toBeNull();
    });

    // Layer 1: Active Card
    expect(screen.getByText("Blade Runner")).not.toBeNull();

    // Layer 2: Next Card
    expect(screen.getByTestId("next-card-layer")).not.toBeNull();
    expect(screen.getByText("Stalker")).not.toBeNull();

    // Layer 3: Deep Deck Layer
    expect(screen.getByTestId("deep-deck-layer")).not.toBeNull();

    // 35mm Sprocket Borders
    const leftSprocket = screen.getByTestId("sprocket-border-left");
    const rightSprocket = screen.getByTestId("sprocket-border-right");
    expect(leftSprocket).not.toBeNull();
    expect(rightSprocket).not.toBeNull();
    expect(leftSprocket.getAttribute("aria-hidden")).toBe("true");
    expect(rightSprocket.getAttribute("aria-hidden")).toBe("true");

    // Letterpress stamps
    expect(screen.getByText("Considered for Screening")).not.toBeNull();
    expect(screen.getByText("Passed to Vault")).not.toBeNull();
    expect(screen.getByText("★ Super-Like · Priority Selection ★")).not.toBeNull();

    // Ambient Projector Spill
    expect(screen.getByTestId("ambient-projector-spill")).not.toBeNull();
  });

  it("3. Resets session identity state when route param id changes", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/deck/card/")) {
        return Promise.resolve({ success: true, is_legacy: true });
      }
      if (url.includes("/api/recommendations/")) {
        return Promise.resolve({ movies: baseSessionData.recommendations });
      }
      if (url.includes("/api/sessions/101/")) {
        return Promise.resolve(baseSessionData);
      }
      if (url.includes("/api/sessions/102/")) {
        return Promise.resolve({
          ...baseSessionData,
          session: { ...baseSessionData.session, id: 102, code: "CINEMA-102" },
        });
      }
      if (url.includes("/api/matches/")) {
        return Promise.resolve({ success: true, matches: [] });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ success: true, watchlist: [] });
      }
      return Promise.resolve({ success: true });
    });

    const TestHarness = () => {
      const navigate = useNavigate();
      return (
        <div>
          <button data-testid="switch-session-btn" onClick={() => navigate("/session/102")}>
            Switch Session
          </button>
          <Routes>
            <Route path="/session/:id" element={<SessionPage />} />
          </Routes>
        </div>
      );
    };

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <TestHarness />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(wsInstances.length).toBeGreaterThan(0);
    });

    // Navigate to session 102
    const switchBtn = screen.getByTestId("switch-session-btn");
    act(() => {
      switchBtn.click();
    });

    await waitFor(() => {
      expect(wsInstances.length).toBeGreaterThan(1);
    });

    // Session 102 should establish its own connection cleanly
    const latestWs = wsInstances[wsInstances.length - 1];
    expect(latestWs.url).toContain("102");
  });

  it("4. Enforces layer count invariant when only 1 or 2 cards exist in deck", async () => {
    // 2-card session
    const twoCardSession = {
      ...baseSessionData,
      recommendations: [
        {
          id: 1,
          title: "Blade Runner",
          poster_url: "https://image.tmdb.org/t/p/w780/bladerunner.jpg",
        },
        {
          id: 2,
          title: "Stalker",
          poster_url: "https://image.tmdb.org/t/p/w780/stalker.jpg",
        },
      ],
    };

    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/deck/card/")) return Promise.resolve({ success: true, is_legacy: true });
      if (url.includes("/api/recommendations/")) return Promise.resolve({ movies: twoCardSession.recommendations });
      if (url.includes("/api/sessions/101/")) return Promise.resolve(twoCardSession);
      if (url.includes("/api/matches/")) return Promise.resolve({ success: true, matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ success: true, watchlist: [] });
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Blade Runner")).not.toBeNull();
    });

    // Layer 1 and 2 exist
    expect(screen.getByText("Blade Runner")).not.toBeNull();
    expect(screen.getByTestId("next-card-layer")).not.toBeNull();
    // Layer 3 does NOT exist because there are only 2 cards in deck
    expect(screen.queryByTestId("deep-deck-layer")).toBeNull();
  });

  it("5. Renders fallback gradient when poster_url is null without canvas pixel access", async () => {
    const nullPosterSession = {
      ...baseSessionData,
      recommendations: [
        {
          id: 1,
          title: "The Mystery Film",
          poster_url: null,
        },
      ],
    };

    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/deck/card/")) return Promise.resolve({ success: true, is_legacy: true });
      if (url.includes("/api/recommendations/")) return Promise.resolve({ movies: nullPosterSession.recommendations });
      if (url.includes("/api/sessions/101/")) return Promise.resolve(nullPosterSession);
      if (url.includes("/api/matches/")) return Promise.resolve({ success: true, matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ success: true, watchlist: [] });
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/101"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("The Mystery Film")).not.toBeNull();
    });

    // Ambient projector spill still renders safe neutral fallback gradient
    const ambientSpill = screen.getByTestId("ambient-projector-spill");
    expect(ambientSpill).not.toBeNull();
    // Both next-card and deep-deck layers are absent since only 1 card exists
    expect(screen.queryByTestId("next-card-layer")).toBeNull();
    expect(screen.queryByTestId("deep-deck-layer")).toBeNull();
  });
});
