import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

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
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    apiRequest: (...args: any[]) => mockApiRequest(...args),
    getWsUrl: () => "ws://127.0.0.1:8000/ws/session/100/",
    getBaseUrl: () => "http://127.0.0.1:8000",
  };
});

// Mock framer-motion
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: () => {},
}));

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

import SessionPage from "../SessionPage";

describe("Phase 3: Frontend Deck Integration & State Machine Contract", () => {
  let wsInstances: any[] = [];

  const mockSessionDetails = {
    session: {
      id: 100,
      code: "PHASE3",
      host_joined: true,
      guest_joined: true,
      preferences_set: true,
      user_role: "host",
      user_preferences_set: true,
      host_preferences_set: true,
      guest_preferences_set: true,
      ended: false,
    },
  };

  const sampleCard1 = {
    card_index: 0,
    movie_id: 201,
    tmdb_id: 27205,
    title: "Inception",
    overview: "A thief who steals corporate secrets...",
    poster_path: "/inception.jpg",
    backdrop_path: "/inception_bg.jpg",
    rating: 8.8,
    vote_count: 34000,
    release_date: "2010-07-15",
    slot_type: "consensus",
    turn: 1,
    scores: { consensus_score: 94.2 },
  };

  const sampleCard2 = {
    card_index: 1,
    movie_id: 202,
    tmdb_id: 157336,
    title: "Interstellar",
    overview: "A team of explorers travel through a wormhole...",
    poster_path: "/interstellar.jpg",
    backdrop_path: "/interstellar_bg.jpg",
    rating: 8.6,
    vote_count: 32000,
    release_date: "2014-11-05",
    slot_type: "host_priority",
    turn: 1,
    scores: { host_relevance: 96.0 },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    wsInstances = [];
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "host_token");
    window.localStorage.setItem("username", "cinemahost");
    window.localStorage.setItem("display_name", "Cinema Host");
    window.localStorage.setItem("flick_tour_session_v1:user:cinemahost", "completed");

    (window as any).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();

      constructor() {
        wsInstances.push(this);
      }
    };
  });

  /* -----------------------------------------------------------------
     Slice 1: Manifest Deck Delivery & Initial Card Rendering
     ----------------------------------------------------------------- */
  it("Slice 1: delivers and renders active card from GET /deck/card/ endpoint", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: 0,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: sampleCard1,
          resolved_card_index: 0,
          host_card_index: 0,
          guest_card_index: 0,
          partner_lag: 0,
          waiting_for_partner: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Verifies movie title from backend deck card appears
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // Verifies film counter reflects 40-card manifest
    expect(screen.getByText(/Film 1 of 40/i)).not.toBeNull();

    // Verifies GET /api/sessions/100/deck/card/ was called
    expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/100/deck/card/");
  });

  /* -----------------------------------------------------------------
     Slice 2: Participant Responses & Cursor Progression
     ----------------------------------------------------------------- */
  it("Slice 2: posts participant reactions to /deck/swipe/ with card_index and movie_id", async () => {
    let currentDelivery: any = sampleCard1;

    mockApiRequest.mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: currentDelivery.card_index,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: currentDelivery,
          resolved_card_index: 0,
          host_card_index: currentDelivery.card_index,
          guest_card_index: 0,
          partner_lag: currentDelivery.card_index,
          waiting_for_partner: false,
        });
      }
      if (endpoint === "/api/sessions/100/deck/swipe/") {
        const body = JSON.parse(options.body);
        expect(body).toEqual({
          card_index: 0,
          movie_id: 201,
          reaction: "like",
        });
        currentDelivery = sampleCard2;
        return Promise.resolve({
          success: true,
          idempotent: false,
          card_index: 0,
          next_card_index: 1,
          jointly_resolved: false,
          match_formed: false,
          superlike_attribution: null,
          match_type: null,
          resolved_card_index: 0,
          host_card_index: 1,
          guest_card_index: 0,
          partner_lag: 1,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // Click "Recommend" (Like button)
    const likeButton = screen.getByLabelText("Recommend");
    fireEvent.click(likeButton);

    // Verifies next card renders seamlessly
    await waitFor(() => {
      expect(screen.getByText("Interstellar")).not.toBeNull();
    });

    // Counter updates to Film 2 of 40
    expect(screen.getByText(/Film 2 of 40/i)).not.toBeNull();
  });

  /* -----------------------------------------------------------------
     Slice 3: Joint Resolution & Super-Like Attribution Presentation
     ----------------------------------------------------------------- */
  it("Slice 3: displays authoritative Super-Like attribution when mutual match is formed", async () => {
    mockApiRequest.mockImplementation((endpoint: string, _options?: any) => {
      if (endpoint === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: 0,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: sampleCard1,
          resolved_card_index: 0,
          host_card_index: 0,
          guest_card_index: 1,
          partner_lag: 0,
          waiting_for_partner: false,
        });
      }
      if (endpoint === "/api/sessions/100/deck/swipe/") {
        return Promise.resolve({
          success: true,
          idempotent: false,
          card_index: 0,
          next_card_index: 1,
          jointly_resolved: true,
          match_formed: true,
          superlike_attribution: "host",
          match_type: "superlike",
          resolved_card_index: 1,
          host_card_index: 1,
          guest_card_index: 1,
          partner_lag: 0,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // Host submits Super-Like
    const superlikeButton = screen.getByLabelText("Priority interest");
    fireEvent.click(superlikeButton);

    // Mutual match banner appears with consensus text
    await waitFor(() => {
      expect(screen.getByText(/Consensus Reached|Mutual Selection/i)).not.toBeNull();
    });

    // Verifies match attribution displays priority interest indicator
    expect(screen.getByText(/Priority Interest/i)).not.toBeNull();
  });

  /* -----------------------------------------------------------------
     Slice 4: Participant Undo Operation
     ----------------------------------------------------------------- */
  it("Slice 4: calls /deck/undo/ and re-delivers regressed card", async () => {
    let currentDelivery: any = sampleCard1;

    mockApiRequest.mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: currentDelivery.card_index,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: currentDelivery,
          resolved_card_index: 0,
          host_card_index: currentDelivery.card_index,
          guest_card_index: 0,
          partner_lag: currentDelivery.card_index,
          waiting_for_partner: false,
        });
      }
      if (endpoint === "/api/sessions/100/deck/swipe/") {
        currentDelivery = sampleCard2;
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
      if (endpoint === "/api/sessions/100/deck/undo/") {
        const body = JSON.parse(options.body);
        expect(body).toEqual({ card_index: 0, movie_id: 201 });
        currentDelivery = sampleCard1;
        return Promise.resolve({
          success: true,
          card_index: 0,
          host_card_index: 0,
          guest_card_index: 0,
          resolved_card_index: 0,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // 1. Swipe card 0
    fireEvent.click(screen.getByLabelText("Recommend"));

    await waitFor(() => {
      expect(screen.getByText("Interstellar")).not.toBeNull();
    });

    // 2. Click Undo
    const undoButton = screen.getByLabelText("Recall last action");
    fireEvent.click(undoButton);

    // 3. Regressed card is restored
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });
    expect(mockApiRequest).toHaveBeenCalledWith(
      "/api/sessions/100/deck/undo/",
      expect.objectContaining({ method: "POST" })
    );
  });

  /* -----------------------------------------------------------------
     Slice 5: Unpartnered Buffer Limit (Waiting for Partner State)
     ----------------------------------------------------------------- */
  it("Slice 5: displays waiting screen when partner lag reaches unpartnered buffer limit", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/100/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: 5,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          card: sampleCard1,
          resolved_card_index: 0,
          host_card_index: 5,
          guest_card_index: 0,
          partner_lag: 5,
          waiting_for_partner: true,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Partner catching up|Waiting for partner/i)).not.toBeNull();
    });
  });

  /* -----------------------------------------------------------------
     Slice 6: Completed Manifest Deck & Summary Transition
     ----------------------------------------------------------------- */
  it("Slice 6: renders deck completion state when all 40 cards have been reviewed", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/100/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 100,
          card_index: 40,
          total_cards: 40,
          has_more: false,
          is_completed: true,
          card: null,
          resolved_card_index: 40,
          host_card_index: 40,
          guest_card_index: 40,
          partner_lag: 0,
          waiting_for_partner: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Screening Deck Concluded|Screening Concluded|All.*Reviewed/i)).not.toBeNull();
    });
  });
});
