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
    getWsUrl: () => "ws://127.0.0.1:8000/ws/session/200/",
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
import { ApiError } from "../../lib/api";

describe("Phase 3 Remediation: Safe Fallback, Candidate Exhaustion, and Boutique Curation", () => {
  const mockSessionDetails = {
    session: {
      id: 200,
      code: "REM200",
      host_joined: true,
      guest_joined: true,
      preferences_set: true,
      user_preferences_set: true,
      host_preferences_set: true,
      guest_preferences_set: true,
      ended: false,
      user_role: "host",
    },
  };

  const sampleCard = {
    movie_id: 42,
    title: "Portrait of a Lady on Fire",
    year: 2019,
    director: "Céline Sciamma",
    slot_type: "mutual_affinity",
    synopsis: "On an isolated island in Brittany...",
    poster_path: "/portrait.jpg",
    genres: ["Drama", "Romance"],
    rating: 8.1,
    vote_count: 2400,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "host_token_200");
    window.localStorage.setItem("username", "testuser");
    window.localStorage.setItem("display_name", "Test User");

    (window as any).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();
    };
  });

  /* -----------------------------------------------------------------
     Slice A (P0): Safe Fallback Remediation
     ----------------------------------------------------------------- */
  it("Slice A: network error on /deck/card/ displays screening deck retry view and NEVER calls /api/recommendations/", async () => {
    let recommendationsCalled = false;

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.reject(new TypeError("Failed to fetch"));
      }
      if (endpoint.includes("/api/recommendations/")) {
        recommendationsCalled = true;
        return Promise.resolve({ movies: [] });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Expect the Screening Deck Unavailable error screen with Retry button
    await waitFor(() => {
      expect(screen.getByText("Screening Deck Unavailable")).not.toBeNull();
      expect(screen.getByTestId("deck-retry-button")).not.toBeNull();
    });

    // CRITICAL: Ensure legacy /api/recommendations/ was NEVER called
    expect(recommendationsCalled).toBe(false);
  });

  it("Slice A: HTTP 500 error on /deck/card/ displays screening deck error and NEVER calls /api/recommendations/", async () => {
    let recommendationsCalled = false;

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.reject(
          new ApiError(500, { error: "Database internal connection timeout" }, "Database error")
        );
      }
      if (endpoint.includes("/api/recommendations/")) {
        recommendationsCalled = true;
        return Promise.resolve({ movies: [] });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Screening Deck Unavailable")).not.toBeNull();
    });

    expect(recommendationsCalled).toBe(false);
  });

  it("Slice A: clicking Retry button re-fetches deck card and recovers screening deck cleanly", async () => {
    let attemptCount = 0;

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        attemptCount++;
        if (attemptCount === 1) {
          return Promise.reject(new TypeError("Temporary network dropout"));
        }
        return Promise.resolve({
          success: true,
          session_id: 200,
          card_index: 0,
          total_cards: 40,
          card: sampleCard,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("deck-retry-button")).not.toBeNull();
    });

    // Tap retry button
    fireEvent.click(screen.getByTestId("deck-retry-button"));

    // Verify recovery to movie card
    await waitFor(() => {
      expect(screen.getByText("Portrait of a Lady on Fire")).not.toBeNull();
    });
  });

  it("Slice A: explicit legacy session (is_legacy: true) calls /api/recommendations/", async () => {
    let recommendationsCalled = false;

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") {
        return Promise.resolve({
          session: {
            ...mockSessionDetails.session,
            is_legacy: true,
          },
        });
      }
      if (endpoint.includes("/api/recommendations/")) {
        recommendationsCalled = true;
        return Promise.resolve({
          movies: [
            {
              id: 99,
              title: "Legacy Film",
              overview: "Legacy overview",
              poster_url: "/legacy.jpg",
            },
          ],
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Legacy Film")).not.toBeNull();
    });

    expect(recommendationsCalled).toBe(true);
  });

  /* -----------------------------------------------------------------
     Slice B & C (P0/P1): Candidate Exhaustion and Proposal Modal
     ----------------------------------------------------------------- */
  it("Slice B & C: allows user to initiate constraint expansion proposal when pool is exhausted", async () => {
    let proposeActionPayload: any = null;

    mockApiRequest.mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.resolve({
          success: false,
          exhausted: true,
          proposal_required: true,
          error: "Eligible candidate pool exhausted (< 16). Constraint expansion required.",
        });
      }
      if (endpoint === "/api/sessions/200/expand-constraints/") {
        if (options?.method === "POST") {
          proposeActionPayload = JSON.parse(options.body);
          return Promise.resolve({
            success: true,
            proposal_id: "prop-new-123",
            status: "pending",
          });
        }
        return Promise.resolve({
          success: true,
          active_proposal: null,
          latest_proposal: null,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Candidate Pool Exhausted")).not.toBeNull();
      expect(screen.getByRole("button", { name: /request constraint expansion/i })).not.toBeNull();
    });

    fireEvent.click(screen.getByRole("button", { name: /request constraint expansion/i }));

    await waitFor(() => {
      expect(proposeActionPayload).toEqual({ action: "propose", auto_approve: true });
    });
  });

  it("Slice B & C: candidate exhaustion opens ConstraintExhaustionNoticeModal with proposal details and voting actions", async () => {
    let respondActionPayload: any = null;

    mockApiRequest.mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.resolve({
          success: false,
          exhausted: true,
          proposal_required: true,
          error: "Eligible candidate pool exhausted (< 16). Constraint expansion required.",
        });
      }
      if (endpoint === "/api/sessions/200/expand-constraints/") {
        if (options?.method === "POST") {
          const body = JSON.parse(options.body);
          if (body.action === "respond") {
            respondActionPayload = body;
            return Promise.resolve({
              success: true,
              proposal_id: "prop-xyz-123",
              status: "approved_queued",
            });
          }
        }
        // GET returns active proposal
        return Promise.resolve({
          success: true,
          active_proposal: {
            id: "prop-xyz-123",
            session_id: 200,
            status: "pending",
            initiated_by_user_id: 1,
            initiated_by_username: "testuser",
            original_constraints: { min_rating: 7.5, max_runtime: 120 },
            proposed_constraints: { min_rating: 6.5, max_runtime: 140 },
            host_decision: "pending",
            guest_decision: "pending",
            created_at: new Date().toISOString(),
            expires_at: new Date(Date.now() + 600000).toISOString(),
            is_expired: false,
            is_mutually_approved: false,
          },
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Modal should be open and displaying title and proposal details
    await waitFor(() => {
      expect(screen.getByText("Candidate Pool Exhausted")).not.toBeNull();
      expect(screen.getByTestId("proposal-status").textContent).toContain("pending");
      expect(screen.getByTestId("my-vote-status").textContent).toContain("pending");
      expect(screen.getByText(/min rating/i)).not.toBeNull();
    });

    // Test voting approval
    const approveBtn = screen.getByRole("button", { name: /approve/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      expect(respondActionPayload).toEqual({
        action: "respond",
        proposal_id: "prop-xyz-123",
        decision: "approve",
      });
    });
  });

  /* -----------------------------------------------------------------
     Slice D (P2): Boutique Pool Informative Note
     ----------------------------------------------------------------- */
  it("Slice D: displays boutique note ('Curated boutique selection of 25 matching films') when total_cards < 40", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 200,
          card_index: 0,
          total_cards: 25,
          card: sampleCard,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId("boutique-selection-note").textContent).toContain(
        "Curated boutique selection of 25 matching films"
      );
    });
  });

  it("Slice D: does NOT display boutique note when total_cards is 40", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/200/") return Promise.resolve(mockSessionDetails);
      if (endpoint === "/api/sessions/200/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 200,
          card_index: 0,
          total_cards: 40,
          card: sampleCard,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/200"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Portrait of a Lady on Fire")).not.toBeNull();
    });

    expect(screen.queryByTestId("boutique-selection-note")).toBeNull();
  });
});
