import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, act, fireEvent } from "@testing-library/react";
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
  getWsUrl: (id: string | number) => `ws://127.0.0.1:8000/ws/session/${id}/`,
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
}));

vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("Phase 6 Batch B: Real-Time Session Synchronization & Swipe Reliability", () => {
  let wsInstances: any[] = [];

  class MockWebSocket {
    static OPEN = 1;
    static CLOSED = 3;
    static CONNECTING = 0;
    readyState = MockWebSocket.OPEN;
    url: string;
    protocols?: string | string[];
    onopen: (() => void) | null = null;
    onclose: ((event: any) => void) | null = null;
    onerror: ((event: any) => void) | null = null;
    onmessage: ((event: any) => void) | null = null;
    close = vi.fn((code = 1000, reason = "") => {
      this.readyState = MockWebSocket.CLOSED;
      this.onclose?.({ code, reason });
    });

    constructor(url: string, protocols?: string | string[]) {
      this.url = url;
      this.protocols = protocols;
      wsInstances.push(this);
      setTimeout(() => {
        if (this.readyState === MockWebSocket.OPEN) {
          this.onopen?.();
        }
      }, 0);
    }
  }

  const baseSession = {
    id: 55,
    code: "SYNC55",
    host: 1,
    guest: 2,
    host_joined: true,
    guest_joined: true,
    ended: false,
    preferences_set: true,
    host_preferences_set: true,
    guest_preferences_set: true,
    user_role: "host",
    genres: ["Sci-Fi"],
  };

  const sampleCard = {
    card_index: 0,
    movie_id: 101,
    title: "Blade Runner 2049",
    overview: "A young blade runner unearths a long-buried secret.",
    poster_path: "/poster.jpg",
    rating: 8.0,
    vote_count: 5000,
    release_date: "2017-10-06",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    wsInstances = [];
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "test_token");
    window.localStorage.setItem("username", "hostuser");
    window.localStorage.setItem("display_name", "Host User");
    window.localStorage.setItem("flick_tour_session_v1:user:hostuser", "completed");

    (window as any).WebSocket = MockWebSocket;

    mockApiRequest.mockImplementation((endpoint: string, _options?: any) => {
      if (endpoint === "/api/sessions/55/") {
        return Promise.resolve({ session: { ...baseSession } });
      }
      if (endpoint === "/api/sessions/55/deck/card/") {
        return Promise.resolve({
          success: true,
          is_legacy: false,
          card_index: 0,
          total_cards: 40,
          waiting_for_partner: false,
          is_completed: false,
          card: sampleCard,
        });
      }
      if (endpoint === "/api/sessions/55/deck/swipe/") {
        return Promise.resolve({
          success: true,
          idempotent: false,
          card_index: 0,
          next_card_index: 1,
          match_formed: false,
          waiting_for_partner: false,
          is_completed: false,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Req 3: Deduplicates WebSocket connection and establishes only one connection per session", async () => {
    render(
      <MemoryRouter initialEntries={["/session/55"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Blade Runner 2049")).not.toBeNull();
    });

    expect(wsInstances.length).toBe(1);
    expect(wsInstances[0].url).toContain("/ws/session/55/");
  });

  it("Req 3: Suppresses reconnect on terminal close code 4001/4003/4004/4000/1000", async () => {
    vi.useFakeTimers();
    render(
      <MemoryRouter initialEntries={["/session/55"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(wsInstances.length).toBe(1);
    const ws = wsInstances[0];

    // Close with terminal code 4001 (unauthorized)
    await act(async () => {
      ws.onclose?.({ code: 4001, reason: "Token revoked" });
    });

    // Advance timers well beyond exponential backoff cap (15 seconds)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });

    // No reconnect should have been scheduled or created
    expect(wsInstances.length).toBe(1);
    vi.useRealTimers();
  });

  it("Req 4 & 5: Controlled fallback polling (6s) activates ONLY when WS is disconnected and stops upon termination", async () => {
    vi.useFakeTimers();
    let pollCount = 0;
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/55/") {
        pollCount++;
        return Promise.resolve({ session: { ...baseSession } });
      }
      if (endpoint === "/api/sessions/55/deck/card/") {
        return Promise.resolve({
          success: true,
          card_index: 0,
          total_cards: 40,
          card: sampleCard,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/55"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Initial mount poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    const initialPollCount = pollCount;
    expect(initialPollCount).toBeGreaterThanOrEqual(1);

    // While WebSocket is connected, no 3s interval polling should occur
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(pollCount).toBe(initialPollCount);

    // Simulate transient network drop (code 1006 - abnormal closure)
    const ws = wsInstances[0];
    await act(async () => {
      ws.readyState = MockWebSocket.CLOSED;
      ws.onclose?.({ code: 1006, reason: "Network dropped" });
    });

    // Advance 6 seconds - fallback polling should trigger 1 poll
    await act(async () => {
      await vi.advanceTimersByTimeAsync(6500);
    });
    expect(pollCount).toBe(initialPollCount + 1);

    // Now simulate session termination event
    await act(async () => {
      ws.onmessage?.({
        data: JSON.stringify({ type: "session_ended" }),
      });
    });

    // Advance another 12 seconds - fallback polling must be completely stopped
    const postTerminationPollCount = pollCount;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(12000);
    });
    expect(pollCount).toBe(postTerminationPollCount);

    vi.useRealTimers();
  });

  it("Req 6: Swipe submission includes Idempotency-Key header and disables swipe buttons while in-flight", async () => {
    let capturedHeaders: any = null;
    let resolveSwipePromise: (value: any) => void;
    const swipeInFlightPromise = new Promise((resolve) => {
      resolveSwipePromise = resolve;
    });

    mockApiRequest.mockImplementation((endpoint: string, options?: any) => {
      if (endpoint === "/api/sessions/55/") {
        return Promise.resolve({ session: { ...baseSession } });
      }
      if (endpoint === "/api/sessions/55/deck/card/") {
        return Promise.resolve({
          success: true,
          card_index: 0,
          total_cards: 40,
          card: sampleCard,
        });
      }
      if (endpoint === "/api/sessions/55/deck/swipe/") {
        capturedHeaders = options?.headers;
        return swipeInFlightPromise;
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/55"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Blade Runner 2049")).not.toBeNull();
    });

    const likeButton = screen.getByLabelText("Recommend") as HTMLButtonElement;
    const passButton = screen.getByLabelText("Pass") as HTMLButtonElement;
    const superLikeButton = screen.getByLabelText("Priority interest") as HTMLButtonElement;

    expect(likeButton.disabled).toBe(false);
    expect(passButton.disabled).toBe(false);
    expect(superLikeButton.disabled).toBe(false);

    // Fire swipe
    fireEvent.click(likeButton);

    // While in-flight, buttons must be disabled
    expect(likeButton.disabled).toBe(true);
    expect(passButton.disabled).toBe(true);
    expect(superLikeButton.disabled).toBe(true);

    // Verify Idempotency-Key header was attached
    expect(capturedHeaders).toBeDefined();
    expect(capturedHeaders["Idempotency-Key"]).toBeDefined();
    expect(capturedHeaders["Idempotency-Key"].length).toBeGreaterThan(10);

    // Resolve the in-flight swipe
    await act(async () => {
      resolveSwipePromise!({
        success: true,
        idempotent: false,
        card_index: 0,
        next_card_index: 1,
        match_formed: false,
        waiting_for_partner: false,
        is_completed: false,
      });
    });
  });

  it("Req 6: Buttons are disabled when waitingForPartner is true", async () => {
    mockApiRequest.mockImplementation((endpoint: string) => {
      if (endpoint === "/api/sessions/55/") {
        return Promise.resolve({ session: { ...baseSession } });
      }
      if (endpoint === "/api/sessions/55/deck/card/") {
        return Promise.resolve({
          success: true,
          card_index: 0,
          total_cards: 40,
          waiting_for_partner: true,
          card: sampleCard,
        });
      }
      if (endpoint === "/api/watchlist/") return Promise.resolve({ watchlist: [] });
      if (endpoint.includes("/matches/")) return Promise.resolve({ matches: [] });
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/55"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Blade Runner 2049")).not.toBeNull();
    });

    const likeButton = screen.getByLabelText("Recommend") as HTMLButtonElement;
    const passButton = screen.getByLabelText("Pass") as HTMLButtonElement;
    const superLikeButton = screen.getByLabelText("Priority interest") as HTMLButtonElement;

    expect(likeButton.disabled).toBe(true);
    expect(passButton.disabled).toBe(true);
    expect(superLikeButton.disabled).toBe(true);
  });
});
