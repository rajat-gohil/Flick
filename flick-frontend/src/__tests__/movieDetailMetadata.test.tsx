import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { formatRuntime } from "../lib/formatRuntime";
import { MovieDetailSheet, type Movie } from "../pages/DiscoverPage";
import SessionPage from "../pages/SessionPage";

const mockApiRequest = vi.fn();

vi.mock("../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://localhost:8000/ws/session/42/",
}));

vi.mock("../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

vi.mock("../lib/tutorial", () => ({
  hasSeenTour: () => true,
  markTourFinished: vi.fn(),
}));

vi.mock("../lib/sound", () => ({
  sound: {
    swipe: vi.fn(),
    match: vi.fn(),
    tap: vi.fn(),
  },
}));

vi.mock("../components/StreamingOptions", () => ({
  default: () => <div data-testid="streaming-options-stub" />,
}));

describe("formatRuntime", () => {
  it("formats hours and minutes cleanly", () => {
    expect(formatRuntime(134)).toBe("2h 14m");
    expect(formatRuntime(45)).toBe("45m");
    expect(formatRuntime(120)).toBe("2h");
  });

  it("returns null for missing, invalid, or non-positive values", () => {
    expect(formatRuntime(null)).toBeNull();
    expect(formatRuntime(undefined)).toBeNull();
    expect(formatRuntime(0)).toBeNull();
    expect(formatRuntime(-15)).toBeNull();
    expect(formatRuntime(Number.NaN)).toBeNull();
  });
});

describe("MovieDetailSheet metadata", () => {
  it("renders genres above synopsis and formatted runtime in metadata row", () => {
    const movie: Movie = {
      id: 10,
      tmdb_id: 550,
      title: "Inception",
      overview: "A thief steals corporate secrets through dream-sharing.",
      poster_url: "/poster.jpg",
      rating: 8.8,
      release_year: 2010,
      original_language: "en",
      genres: ["Action", "Sci-Fi"],
      runtime: 148,
    };

    render(
      <MovieDetailSheet
        movie={movie}
        inWatchlist={false}
        onWatchlist={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.getByTestId("detail-runtime").textContent).toContain("2h 28m");
    const genresEl = screen.getByTestId("detail-genres");
    expect(genresEl.textContent).toContain("Action");
    expect(genresEl.textContent).toContain("Sci-Fi");
  });

  it("omits runtime and genre containers cleanly when metadata is missing", () => {
    const legacyMovie: Movie = {
      id: 11,
      tmdb_id: 551,
      title: "Legacy Film",
      overview: "Older record without runtime or genres.",
      poster_url: null,
      rating: 7.2,
      release_year: 1998,
      genres: [],
      runtime: null,
    };

    render(
      <MovieDetailSheet
        movie={legacyMovie}
        inWatchlist={false}
        onWatchlist={vi.fn()}
        onClose={vi.fn()}
      />
    );

    expect(screen.queryByTestId("detail-runtime")).toBeNull();
    expect(screen.queryByTestId("detail-genres")).toBeNull();
  });
});

describe("SessionPage Film Overview and Match Details metadata", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "test-token");
    localStorage.setItem("user_id", "1");
    localStorage.setItem("username", "hostuser");
    localStorage.setItem("flick_tour_session_v1:user:hostuser", "completed");

    (window as unknown as { WebSocket: unknown }).WebSocket = class MockWebSocket {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: ((ev: unknown) => void) | null = null;
      onerror: (() => void) | null = null;
      close = vi.fn();
      send = vi.fn();
    };
  });

  it("renders genres and runtime in Film Overview and Match Details, and omits missing metadata on legacy matches", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/42/") {
        return Promise.resolve({
          success: true,
          session: {
            id: 42,
            code: "ABC123",
            host_joined: true,
            guest_joined: true,
            ended: false,
            preferences_set: true,
            user_preferences_set: true,
            host_preferences_set: true,
            guest_preferences_set: true,
            user_role: "host",
            host_id: 1,
            guest_id: 2,
          },
        });
      }
      if (url === "/api/sessions/42/deck/card/") {
        return Promise.resolve({
          success: true,
          session_id: 42,
          card_index: 0,
          total_cards: 40,
          has_more: true,
          is_completed: false,
          resolved_card_index: 0,
          host_card_index: 0,
          guest_card_index: 0,
          partner_lag: 0,
          waiting_for_partner: false,
          card: {
            card_index: 0,
            movie_id: 101,
            tmdb_id: 603,
            title: "The Matrix",
            overview: "A hacker discovers reality is a simulation.",
            poster_path: "/matrix.jpg",
            rating: 8.7,
            vote_count: 24000,
            release_date: "1999-03-31",
            genres: ["Action", "Sci-Fi"],
            runtime: 136,
          },
          next_card: null,
        });
      }
      if (url === "/api/sessions/42/matches/") {
        return Promise.resolve({
          success: true,
          matches: [
            {
              session_id: 42,
              movie_id: 201,
              movie_title: "Parasite",
              poster_url: "/parasite.jpg",
              rating: 8.5,
              vote_count: 17000,
              release_year: 2019,
              overview: "Greed and class discrimination threaten a symbiotic bond.",
              genres: ["Thriller", "Drama"],
              runtime: 132,
              original_language: "ko",
            },
            {
              session_id: 42,
              movie_id: 202,
              movie_title: "Legacy Match",
              poster_url: "/legacy.jpg",
              rating: 7.0,
              release_year: 1995,
              overview: "Legacy match without runtime or genres.",
              genres: [],
              runtime: null,
            },
          ],
        });
      }
      if (url === "/api/watchlist/") {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/42"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText("The Matrix")).toBeTruthy();
    });

    // Open Film Overview sheet
    fireEvent.click(screen.getByRole("button", { name: /view film details/i }));

    await waitFor(() => {
      expect(screen.getByTestId("film-overview-runtime").textContent).toBe("2h 16m");
      const genres = screen.getByTestId("film-overview-genres");
      expect(genres.textContent).toContain("Action");
      expect(genres.textContent).toContain("Sci-Fi");
    });

    // Close Film Overview sheet
    fireEvent.click(screen.getByRole("button", { name: /close film overview/i }));
  });

  it("renders genres and runtime in Match Details and omits missing metadata on legacy matches", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/42/") {
        return Promise.resolve({
          success: true,
          session: {
            id: 42,
            code: "ABC123",
            host_joined: true,
            guest_joined: true,
            ended: true,
            preferences_set: true,
            user_preferences_set: true,
            host_preferences_set: true,
            guest_preferences_set: true,
            user_role: "host",
            host_id: 1,
            guest_id: 2,
          },
        });
      }
      if (url.includes("/api/matches/")) {
        return Promise.resolve({
          success: true,
          matches: [
            {
              session_id: 42,
              movie_id: 201,
              movie_title: "Parasite",
              poster_url: "/parasite.jpg",
              rating: 8.5,
              vote_count: 17000,
              release_year: 2019,
              overview: "Greed and class discrimination threaten a symbiotic bond.",
              genres: ["Thriller", "Drama"],
              runtime: 132,
              original_language: "ko",
            },
            {
              session_id: 42,
              movie_id: 202,
              movie_title: "Legacy Match",
              poster_url: "/legacy.jpg",
              rating: 7.0,
              release_year: 1995,
              overview: "Legacy match without runtime or genres.",
              genres: [],
              runtime: null,
            },
          ],
        });
      }
      if (url === "/api/watchlist/") {
        return Promise.resolve({ watchlist: [] });
      }
      return Promise.resolve({ success: true });
    });

    render(
      <MemoryRouter initialEntries={["/session/42"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Open Match Details for Parasite
    await waitFor(() => {
      expect(screen.getByText("Parasite")).toBeTruthy();
    });
    fireEvent.click(screen.getByText("Parasite"));

    await waitFor(() => {
      expect(screen.getByTestId("match-detail-runtime").textContent).toContain("2h 12m");
    });
    fireEvent.click(screen.getByRole("button", { name: /close match details/i }));

    // Open Match Details for Legacy Match (no runtime)
    fireEvent.click(screen.getByText("Legacy Match"));
    await waitFor(() => {
      expect(screen.getByText("Legacy match without runtime or genres.")).toBeTruthy();
    });
    expect(screen.queryByTestId("match-detail-runtime")).toBeNull();
  });
});
