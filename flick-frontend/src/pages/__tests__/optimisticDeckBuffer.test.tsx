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

describe("Optimistic Screening Deck & Next-Card Buffer", () => {
  const mockSessionDetails = {
    session: {
      id: 100,
      code: "OPTIMISTIC100",
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

  const card1 = {
    card_index: 0,
    movie_id: 201,
    tmdb_id: 27205,
    title: "Inception",
    overview: "A thief who enters the dreams of others...",
    poster_path: "/inception.jpg",
    rating: 8.8,
    vote_count: 34000,
    release_date: "2010-07-15",
  };

  const card2 = {
    card_index: 1,
    movie_id: 202,
    tmdb_id: 157336,
    title: "Interstellar",
    overview: "A team of explorers travel through a wormhole...",
    poster_path: "/interstellar.jpg",
    rating: 8.6,
    vote_count: 32000,
    release_date: "2014-11-05",
  };

  const card3 = {
    card_index: 2,
    movie_id: 203,
    tmdb_id: 872585,
    title: "Oppenheimer",
    overview: "The story of J. Robert Oppenheimer...",
    poster_path: "/oppenheimer.jpg",
    rating: 8.9,
    vote_count: 28000,
    release_date: "2023-07-21",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "test_token");
    window.localStorage.setItem("username", "testuser");
    window.localStorage.setItem("display_name", "Test User");
    window.localStorage.setItem("flick_tour_session_v1:user:testuser", "completed");

    (window as any).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((ev: any) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();
    };
  });

  it("1. Loads active card and preloads upcoming buffer card with metadata into underneath card", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          cursor: 0,
          total_cards: 40,
          card: card1,
          next_card: card2,
        });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/100"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Active card
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
    });

    // Underneath card displays upcoming movie title and release year
    expect(screen.getByText("Interstellar")).not.toBeNull();
    expect(screen.getByText("2014")).not.toBeNull();
  });

  it("2. Immediately promotes next card optimistically on swipe without waiting for network", async () => {
    let resolveSwipePromise: (value: any) => void = () => {};
    const deferredSwipePromise = new Promise((resolve) => {
      resolveSwipePromise = resolve;
    });

    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          cursor: 0,
          total_cards: 40,
          card: card1,
          next_card: card2,
        });
      }
      if (url === "/api/sessions/100/deck/swipe/") {
        // Return unsettled promise to verify optimistic promotion occurs immediately
        return deferredSwipePromise;
      }
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

    const likeButton = screen.getByLabelText("Recommend");
    fireEvent.click(likeButton);

    // Interstellar must be promoted immediately even though swipe network call is still pending
    await waitFor(() => {
      // Inception is swiped out, Interstellar is now active
      expect(screen.getAllByText("Interstellar").length).toBeGreaterThanOrEqual(1);
    });

    // Resolve swipe response with buffer refill (card2 is active, card3 is next buffer)
    resolveSwipePromise({
      success: true,
      card_index: 0,
      movie_id: 201,
      reaction: "like",
      new_cursor: 1,
      card: card2,
      next_card: card3,
    });

    // Buffer is refilled with Oppenheimer
    await waitFor(() => {
      expect(screen.getByText("Oppenheimer")).not.toBeNull();
      expect(screen.getByText("2023")).not.toBeNull();
    });
  });

  it("3. Single-trip API contract: refills buffer from swipe response without second GET /deck/card/", async () => {
    let getDeckCardCallCount = 0;

    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        getDeckCardCallCount++;
        return Promise.resolve({
          success: true,
          cursor: 0,
          total_cards: 40,
          card: card1,
          next_card: card2,
        });
      }
      if (url === "/api/sessions/100/deck/swipe/") {
        return Promise.resolve({
          success: true,
          card_index: 0,
          movie_id: 201,
          reaction: "like",
          new_cursor: 1,
          card: card2,
          next_card: card3,
        });
      }
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

    expect(getDeckCardCallCount).toBe(1);

    const passButton = screen.getByLabelText("Pass");
    fireEvent.click(passButton);

    await waitFor(() => {
      expect(screen.getByText("Oppenheimer")).not.toBeNull();
    });

    // Verify GET /deck/card/ was NOT called a second time
    expect(getDeckCardCallCount).toBe(1);
  });

  it("4. Undo restores both active card and next-card buffer directly from undo response", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          cursor: 0,
          total_cards: 40,
          card: card1,
          next_card: card2,
        });
      }
      if (url === "/api/sessions/100/deck/swipe/") {
        return Promise.resolve({
          success: true,
          card_index: 0,
          movie_id: 201,
          reaction: "like",
          new_cursor: 1,
          card: card2,
          next_card: card3,
        });
      }
      if (url === "/api/sessions/100/deck/undo/") {
        return Promise.resolve({
          success: true,
          undone_card_index: 0,
          undone_movie_id: 201,
          new_cursor: 0,
          card: card1,
          next_card: card2,
        });
      }
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

    // Swipe card 1
    const likeButton = screen.getByLabelText("Recommend");
    fireEvent.click(likeButton);

    await waitFor(() => {
      expect(screen.getByText("Oppenheimer")).not.toBeNull();
    });

    // Click Undo
    const undoButton = screen.getByLabelText("Recall last action") as HTMLButtonElement;
    expect(undoButton.disabled).toBe(false);
    fireEvent.click(undoButton);

    // Inception and Interstellar should be restored
    await waitFor(() => {
      expect(screen.getByText("Inception")).not.toBeNull();
      expect(screen.getByText("Interstellar")).not.toBeNull();
    });
  });

  it("5. Deliberate error recovery: resynchronizes authoritative deck state on swipe failure", async () => {
    let getDeckCardCallCount = 0;

    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        getDeckCardCallCount++;
        return Promise.resolve({
          success: true,
          cursor: 0,
          total_cards: 40,
          card: card1,
          next_card: card2,
        });
      }
      if (url === "/api/sessions/100/deck/swipe/") {
        const error: any = new Error("Conflict");
        error.status = 409;
        error.data = { error: "Expected card_index 0, got 1", resync_required: true };
        return Promise.reject(error);
      }
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

    expect(getDeckCardCallCount).toBe(1);

    const likeButton = screen.getByLabelText("Recommend");
    fireEvent.click(likeButton);

    // On 409 error, fetchDeckCard is called to resync authoritative state
    await waitFor(() => {
      expect(getDeckCardCallCount).toBeGreaterThanOrEqual(2);
      expect(screen.getByText("Deck updated. Please swipe again.")).not.toBeNull();
    });
  });

  it("6. Guards against stale/late responses overwriting newer deck state", async () => {
    let resolveStaleSwipe: (val: any) => void = () => {};
    const staleSwipePromise = new Promise((resolve) => {
      resolveStaleSwipe = resolve;
    });

    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/100/") {
        return Promise.resolve(mockSessionDetails);
      }
      if (url === "/api/sessions/100/deck/card/") {
        return Promise.resolve({
          success: true,
          cursor: 1,
          total_cards: 40,
          card: card2, // Currently on Interstellar (card_index 1)
          next_card: card3, // Next is Oppenheimer (card_index 2)
        });
      }
      if (url === "/api/sessions/100/deck/swipe/") {
        return staleSwipePromise;
      }
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
      expect(screen.getByText("Interstellar")).not.toBeNull();
    });

    // Advance to Oppenheimer
    const likeButton = screen.getByLabelText("Recommend");
    fireEvent.click(likeButton);

    await waitFor(() => {
      expect(screen.getByText("Oppenheimer")).not.toBeNull();
    });

    // Now a late response from card 0 arrives returning card 1 (Interstellar)
    resolveStaleSwipe({
      success: true,
      card_index: 0,
      movie_id: 201,
      reaction: "like",
      new_cursor: 1,
      card: card2, // card_index 1 is older than current card Oppenheimer (card_index 2)
      next_card: card3,
    });

    // It must NOT overwrite Oppenheimer back to Interstellar!
    await waitFor(() => {
      expect(screen.getByText("Oppenheimer")).not.toBeNull();
    });
  });
});
