/**
 * Screening Session Results and Statistics Persistence Tests
 *
 * Verifies that:
 * 1. Session completes with nine reviewed movies and zero matches.
 * 2. Completion screen immediately displays the correct results without refresh.
 * 3. Page refresh restores the same results.
 * 4. Reviewed count remains nine after refresh (does not reset to 0).
 * 5. Matched count remains accurate.
 * 6. Affinity percentage remains consistent (does not reset to 0%).
 * 7. A session with mutual matches displays the correct matched movies.
 * 8. Reopening from screening archives restores the same session data and statistics.
 * 9. Empty-result sessions display the correct empty state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SessionPage from "../SessionPage";
import SessionsListPage from "../SessionsListPage";

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/99/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: (_mv: any, _input: any, output: any) => ({
    get: () => (Array.isArray(output) ? output[1] : 0),
    set: () => {},
  }),
  useAnimation: () => ({ start: vi.fn() }),
  useSpring: () => ({ get: () => 0, set: () => {} }),
  useVelocity: () => ({ get: () => 0 }),
}));

vi.mock("canvas-confetti", () => ({ default: vi.fn() }));

function makeWebSocketStub() {
  return class {
    onopen: any; onclose: any; onmessage: any; onerror: any;
    send = vi.fn(); close = vi.fn();
    constructor() { setTimeout(() => this.onopen?.(), 10); }
  };
}

function renderSessionPage(sessionId = "99") {
  return render(
    <MemoryRouter initialEntries={[`/session/${sessionId}`]}>
      <Routes>
        <Route path="/session/:id" element={<SessionPage />} />
        <Route path="/home" element={<div>Home</div>} />
        <Route path="/session/:id/preferences" element={<div>Preferences</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const mockMatch1 = {
  session_id: 99,
  movie_id: 101,
  tmdb_id: 201,
  movie_title: "Interstellar Odyssey",
  matched_at: "2026-11-13T20:00:00Z",
  poster_url: "https://image.tmdb.org/t/p/w780/poster1.jpg",
  rating: 8.8,
  vote_count: 500,
  release_year: 2024,
  overview: "A journey across time and space.",
  genres: ["Sci-Fi", "Drama"],
  original_language: "en",
  superlike_attribution: "none",
  match_type: "ordinary",
};

const mockMatch2 = {
  session_id: 99,
  movie_id: 102,
  tmdb_id: 202,
  movie_title: "Solaris Dreams",
  matched_at: "2026-11-13T20:05:00Z",
  poster_url: "https://image.tmdb.org/t/p/w780/poster2.jpg",
  rating: 8.4,
  vote_count: 320,
  release_year: 2023,
  overview: "Consciousness meets the cosmos.",
  genres: ["Sci-Fi", "Mystery"],
  original_language: "en",
  superlike_attribution: "host",
  match_type: "superlike",
};

describe("Screening Session Results & Statistics Persistence", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
    vi.stubGlobal("WebSocket", makeWebSocketStub());
    localStorage.setItem("username", "test_host");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("1. displays Reviewed: 9, Matched: 0, Affinity: 0% and empty state when 9 movies reviewed with zero matches", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/99/deck/card/")) {
        return Promise.resolve({ success: false, is_legacy: true });
      }
      if (url.includes("/api/sessions/99/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 99,
            code: "SCN009",
            host_joined: true,
            guest_joined: true,
            ended: true,
            preferences_set: true,
            user_preferences_set: true,
            host_display_name: "test_host",
            guest_display_name: "test_guest",
            user_role: "host",
            reviewed_count: 9,
            matched_count: 0,
            affinity_percent: 0,
          },
        });
      }
      if (url.includes("/api/matches/?session_id=99")) {
        return Promise.resolve({
          success: true,
          matches: [],
          reviewed_count: 9,
          matched_count: 0,
          affinity_percent: 0,
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    renderSessionPage("99");

    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).toBeTruthy();
    });

    const reviewedStat = screen.getByTestId("stat-reviewed-count");
    const matchedStat = screen.getByTestId("stat-matched-count");
    const affinityStat = screen.getByTestId("stat-affinity-percent");

    expect(reviewedStat.textContent).toBe("9");
    expect(matchedStat.textContent).toBe("0");
    expect(affinityStat.textContent).toBe("0%");

    expect(
      screen.getByText(/No matching titles found in this session/i)
    ).toBeTruthy();
  });

  it("2. immediately displays results and statistics upon ending session without requiring page refresh", async () => {
    let sessionEnded = false;

    mockApiRequest.mockImplementation((url: string, _opts?: any) => {
      if (url.includes("/api/sessions/99/deck/card/")) {
        return Promise.resolve({
          success: true,
          card_index: 8,
          total_cards: 40,
          waiting_for_partner: false,
          is_completed: false,
          card: {
            movie_id: 101,
            title: "Card 9",
            rating: 8.0,
            poster_url: "",
            overview: "",
            release_year: 2024,
          },
        });
      }
      if (url.includes("/api/sessions/99/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 99,
            code: "SCN009",
            host_joined: true,
            guest_joined: true,
            ended: sessionEnded,
            preferences_set: true,
            user_preferences_set: true,
            host_display_name: "test_host",
            guest_display_name: "test_guest",
            user_role: "host",
            reviewed_count: sessionEnded ? 9 : 8,
            matched_count: sessionEnded ? 2 : 0,
            affinity_percent: sessionEnded ? 22 : 0,
          },
        });
      }
      if (url.includes("/api/sessions/end/")) {
        sessionEnded = true;
        return Promise.resolve({
          success: true,
          ended: true,
          matches: [mockMatch1, mockMatch2],
          reviewed_count: 9,
          matched_count: 2,
          affinity_percent: 22,
        });
      }
      if (url.includes("/api/matches/?session_id=99")) {
        return Promise.resolve({
          success: true,
          matches: sessionEnded ? [mockMatch1, mockMatch2] : [],
          reviewed_count: 9,
          matched_count: 2,
          affinity_percent: 22,
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    renderSessionPage("99");

    // Wait for active room to mount
    await waitFor(() => {
      expect(screen.getByText("Card 9")).toBeTruthy();
    });

    // Click Conclude in the header
    const concludeBtn = screen.getByTestId("conclude-screening-btn");
    fireEvent.click(concludeBtn);

    // Confirmation modal appears
    await waitFor(() => {
      expect(screen.getByTestId("end-confirm-modal")).toBeTruthy();
    });

    // Confirm end
    const proceedBtn = screen.getByTestId("end-confirm-proceed-btn");
    fireEvent.click(proceedBtn);

    // Completion view appears IMMEDIATELY with movies and accurate stats!
    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).toBeTruthy();
    });

    expect(screen.getByTestId("stat-reviewed-count").textContent).toBe("9");
    expect(screen.getByTestId("stat-matched-count").textContent).toBe("2");
    expect(screen.getByTestId("stat-affinity-percent").textContent).toBe("22%");

    // Movie results appear immediately without refresh
    expect(screen.getByText("Interstellar Odyssey")).toBeTruthy();
    expect(screen.getByText("Solaris Dreams")).toBeTruthy();
  });

  it("3. restores the exact same results and non-zero statistics after page refresh", async () => {
    // Simulating mount after browser reload of an ended session
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/99/deck/card/")) {
        return Promise.resolve({ success: false, is_legacy: true });
      }
      if (url.includes("/api/sessions/99/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 99,
            code: "SCN009",
            host_joined: true,
            guest_joined: true,
            ended: true,
            preferences_set: true,
            user_preferences_set: true,
            host_display_name: "test_host",
            guest_display_name: "test_guest",
            user_role: "host",
            reviewed_count: 9,
            matched_count: 2,
            affinity_percent: 22,
          },
        });
      }
      if (url.includes("/api/matches/?session_id=99")) {
        return Promise.resolve({
          success: true,
          matches: [mockMatch1, mockMatch2],
          reviewed_count: 9,
          matched_count: 2,
          affinity_percent: 22,
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    renderSessionPage("99");

    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).toBeTruthy();
    });

    // CRITICAL: Reviewed and Affinity MUST NOT reset to 0
    expect(screen.getByTestId("stat-reviewed-count").textContent).toBe("9");
    expect(screen.getByTestId("stat-matched-count").textContent).toBe("2");
    expect(screen.getByTestId("stat-affinity-percent").textContent).toBe("22%");

    // Matches must be restored
    expect(screen.getByText("Interstellar Odyssey")).toBeTruthy();
    expect(screen.getByText("Solaris Dreams")).toBeTruthy();
  });

  it("4. restores session data and statistics when opened from screening archives", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/recent/")) {
        return Promise.resolve({
          success: true,
          sessions: [
            {
              id: 99,
              code: "SCN009",
              name: "Sci-Fi Night",
              date: "Nov 13, 2026",
              matches: 2,
              ended: true,
              status: "completed",
              is_host: true,
              user_role: "host",
              participants: [{ initials: "TH", username: "test_host" }],
            },
          ],
        });
      }
      if (url.includes("/api/sessions/99/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 99,
            code: "SCN009",
            host_joined: true,
            guest_joined: true,
            ended: true,
            preferences_set: true,
            user_preferences_set: true,
            host_display_name: "test_host",
            guest_display_name: "test_guest",
            user_role: "host",
            reviewed_count: 9,
            matched_count: 2,
            affinity_percent: 22,
          },
        });
      }
      if (url.includes("/api/matches/?session_id=99")) {
        return Promise.resolve({
          success: true,
          matches: [mockMatch1, mockMatch2],
          reviewed_count: 9,
          matched_count: 2,
          affinity_percent: 22,
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    // Render archive list and click into session
    render(
      <MemoryRouter initialEntries={["/sessions"]}>
        <Routes>
          <Route path="/sessions" element={<SessionsListPage />} />
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("Sci-Fi Night")).toBeTruthy();
    });

    // Click card to open session
    fireEvent.click(screen.getByText("Sci-Fi Night"));

    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).toBeTruthy();
    });

    expect(screen.getByTestId("stat-reviewed-count").textContent).toBe("9");
    expect(screen.getByTestId("stat-matched-count").textContent).toBe("2");
    expect(screen.getByTestId("stat-affinity-percent").textContent).toBe("22%");
    expect(screen.getByText("Interstellar Odyssey")).toBeTruthy();
    expect(screen.getByText("Solaris Dreams")).toBeTruthy();
  });

  it("5. enforces mathematical invariant Reviewed >= Matched on refresh even if incoming reviewed_count is 0", async () => {
    // Edge case: incoming reviewed_count is 0, but 3 matches exist
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/99/deck/card/")) {
        return Promise.resolve({ success: false, is_legacy: true });
      }
      if (url.includes("/api/sessions/99/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 99,
            code: "SCN009",
            host_joined: true,
            guest_joined: true,
            ended: true,
            preferences_set: true,
            user_preferences_set: true,
            host_display_name: "test_host",
            guest_display_name: "test_guest",
            user_role: "host",
            reviewed_count: 0, // Faulty/missing raw counter
            matched_count: 2,
            affinity_percent: 0,
          },
        });
      }
      if (url.includes("/api/matches/?session_id=99")) {
        return Promise.resolve({
          success: true,
          matches: [mockMatch1, mockMatch2],
          reviewed_count: 0,
          matched_count: 2,
          affinity_percent: 0,
        });
      }
      if (url.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({});
    });

    renderSessionPage("99");

    await waitFor(() => {
      expect(screen.getByText("Screening Concluded")).toBeTruthy();
    });

    // Invariant recovery: Reviewed MUST be at least 2 (not 0), and Affinity MUST NOT be 0%
    const reviewedStat = screen.getByTestId("stat-reviewed-count");
    const matchedStat = screen.getByTestId("stat-matched-count");
    const affinityStat = screen.getByTestId("stat-affinity-percent");

    expect(reviewedStat.textContent).toBe("2");
    expect(matchedStat.textContent).toBe("2");
    expect(affinityStat.textContent).toBe("100%");
  });
});
