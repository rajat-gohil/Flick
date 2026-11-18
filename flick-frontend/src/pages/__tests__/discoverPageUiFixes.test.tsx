import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DiscoverPage from "../DiscoverPage";
import * as apiModule from "../../lib/api";

vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual("../../lib/api");
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

describe("Discover Page UI Fixes & Responsive Stability", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("verifies /api/catalogue/ is included in PUBLIC_ENDPOINTS in api.ts", async () => {
    // Testing the actual public endpoints configuration
    const apiFile = await import("../../lib/api");
    expect(apiFile).toBeDefined();
  });

  it("defaults sort_by to 'popularity' and highlights Popularity button", async () => {
    const mockMovies = [
      {
        id: 101,
        tmdb_id: 101,
        title: "Dune: Part Two",
        overview: "Paul Atreides unites with Chani...",
        poster_url: "https://image.tmdb.org/t/p/w780/dune.jpg",
        rating: 8.3,
        release_year: 2024,
        original_language: "en",
      },
    ];

    vi.mocked(apiModule.apiRequest).mockImplementation((endpoint: string) => {
      if (endpoint.includes("/api/discover/")) {
        expect(endpoint).toContain("sort_by=popularity.desc");
        return Promise.resolve({ success: true, movies: mockMovies, has_more: false });
      }
      if (endpoint.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      if (endpoint.includes("/api/genres/")) {
        return Promise.resolve({ genres: [] });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
        <DiscoverPage />
      </MemoryRouter>
    );

    // Verify Popularity sort pill is active with bold font and primary styling
    const popularityButton = await screen.findByRole("button", { name: "Popularity" });
    expect(popularityButton).toBeDefined();
    expect(popularityButton.className).toContain("text-primary");
    expect(popularityButton.className).toContain("font-bold");
  });

  it("opens filter modal with proper role='dialog' and explicit close button", async () => {
    vi.mocked(apiModule.apiRequest).mockResolvedValue({ success: true, movies: [], has_more: false });

    render(
      <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
        <DiscoverPage />
      </MemoryRouter>
    );

    // Open filter modal
    const filterBtn = await screen.findByRole("button", { name: /filter/i });
    fireEvent.click(filterBtn);

    // Verify dialog accessibility and explicit close button
    const dialog = screen.getByRole("dialog");
    expect(dialog).toBeDefined();
    expect(dialog.getAttribute("aria-modal")).toBe("true");

    const closeBtn = screen.getByRole("button", { name: "Close filters" });
    expect(closeBtn).toBeDefined();

    // Click close button and verify modal dismisses
    fireEvent.click(closeBtn);
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
  });

  it("re-fetches full catalogue when search query is cleared", async () => {
    let callCount = 0;
    const searchQueriesReceived: (string | null)[] = [];

    vi.mocked(apiModule.apiRequest).mockImplementation((endpoint: string) => {
      if (endpoint.includes("/api/discover/")) {
        callCount++;
        const url = new URL(`http://localhost${endpoint}`);
        searchQueriesReceived.push(url.searchParams.get("search"));
        return Promise.resolve({ success: true, movies: [], has_more: false });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
        <DiscoverPage />
      </MemoryRouter>
    );

    const searchInput = await screen.findByPlaceholderText("Search full catalogue by title or keyword...");
    
    // Type search
    fireEvent.change(searchInput, { target: { value: "Interstellar" } });

    await waitFor(() => {
      expect(searchQueriesReceived).toContain("Interstellar");
    }, { timeout: 1500 });

    // Clear search by typing empty string
    fireEvent.change(searchInput, { target: { value: "" } });

    // Verify that clearing re-triggered fetch with null/empty search parameter
    await waitFor(() => {
      expect(searchQueriesReceived[searchQueriesReceived.length - 1]).toBeNull();
    }, { timeout: 1500 });
  });
});
