import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
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

import SessionPage from "../SessionPage";

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/42/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

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
}));

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("WebSocket Match Metadata Fallback & Connection Stability", () => {
  let wsInstances: any[] = [];

  beforeEach(() => {
    vi.clearAllMocks();
    wsInstances = [];
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "mock_host_token");
    window.localStorage.setItem("username", "hostuser");
    window.localStorage.setItem("display_name", "Host User");

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

  it("falls back to deck movie metadata from moviesRef when match_event is sparse, without reconnecting WebSocket", async () => {
    const deckMovies = [
      {
        id: 701,
        title: "Inception",
        poster_url: "https://image.tmdb.org/t/p/w500/inception.jpg",
        rating: 8.8,
        release_year: 2010,
        synopsis: "A thief who steals corporate secrets...",
        genres: ["Sci-Fi", "Action"],
      },
    ];

    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/42/") {
        return Promise.resolve({
          session: {
            id: 42,
            code: "XYZ123",
            host_joined: true,
            guest_joined: true,
            preferences_set: true,
            user_role: "host",
            user_preferences_set: true,
            host_preferences_set: true,
            guest_preferences_set: true,
            ended: false,
            is_legacy: true,
          },
        });
      }
      if (endpoint.includes("/api/recommendations/")) {
        return Promise.resolve({
          movies: deckMovies,
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

    render(
      <MemoryRouter initialEntries={["/session/42"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Wait for the movie card to render in the deck
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // Check that exactly one WebSocket connection was opened
    expect(wsInstances.length).toBe(1);
    const activeWs = wsInstances[0];

    // Simulate an incoming match_event with sparse metadata (no poster_url, no release_year, no rating)
    await act(async () => {
      activeWs.onmessage?.({
        data: JSON.stringify({
          type: "match_event",
          movie_id: 701,
          movie_title: "Inception",
          match_type: "ordinary",
        }),
      });
    });

    // Modal should appear displaying consensus reached
    await waitFor(() => {
      expect(screen.getByText("Consensus Reached")).not.toBeNull();
    });

    // Verify poster img has the fallback poster url from deckMovies (via moviesRef)
    await waitFor(() => {
      const posterImg = screen.getByAltText("Inception") as HTMLImageElement;
      expect(posterImg).not.toBeNull();
      expect(posterImg.src).toContain("https://image.tmdb.org/t/p/w500/inception.jpg");
    });

    // Verify that WebSocket was NOT closed or re-instantiated
    expect(activeWs.close).not.toHaveBeenCalled();
    expect(wsInstances.length).toBe(1);
  });
});
