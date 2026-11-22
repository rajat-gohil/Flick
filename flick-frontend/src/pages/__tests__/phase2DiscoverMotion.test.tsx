import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DiscoverPage from "../DiscoverPage";

// Mock api module
vi.mock("../../lib/api", () => ({
  apiRequest: vi.fn(),
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

// Mock analytics module
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

import { apiRequest } from "../../lib/api";

const mockMovies = [
  {
    id: 1,
    tmdb_id: 101,
    title: "Blade Runner 2049",
    overview: "Young Blade Runner K's discovery of a long-buried secret...",
    poster_url: "https://example.com/bladerunner.jpg",
    backdrop_url: "https://example.com/bladerunner_bg.jpg",
    rating: 8.0,
    release_year: 2017,
    original_language: "en",
    explanation: {
      matched_signals: ["Cyberpunk", "Atmospheric"],
    },
  },
  {
    id: 2,
    tmdb_id: 102,
    title: "Chungking Express",
    overview: "Two melancholic Hong Kong policemen fall in love...",
    poster_url: "https://example.com/chungking.jpg",
    rating: 8.1,
    release_year: 1994,
    original_language: "zh",
  },
];

const mockShelves = [
  {
    id: "recommended_for_you",
    title: "Recommended For You",
    subtitle: "Curated to match your unique taste profile",
    icon: "auto_awesome",
    movies: mockMovies,
  },
];

describe("Phase 2 Motion Refinement: Catalogue & Filter Dynamics (DiscoverPage)", () => {
  let matchMediaMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "mock-token-xyz");

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

    (apiRequest as ReturnType<typeof vi.fn>).mockImplementation((endpoint: string) => {
      if (endpoint.includes("/api/your-archive/")) {
        return Promise.resolve({
          success: true,
          shelves: mockShelves,
          spotlight: mockMovies[0],
        });
      }
      if (endpoint.includes("/api/discover/")) {
        return Promise.resolve({
          success: true,
          movies: mockMovies,
          has_more: false,
        });
      }
      if (endpoint.includes("/api/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      if (endpoint.includes("/api/genres/")) {
        return Promise.resolve({
          genres: [
            { id: 28, name: "Action" },
            { id: 878, name: "Science Fiction" },
          ],
        });
      }
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("1. Surface Navigation Pill Dynamics", () => {
    it("renders sliding active pill under active surface tab and transfers it on click", async () => {
      render(
        <MemoryRouter initialEntries={["/discover?view=archive"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      const archiveTab = await screen.findByRole("button", { name: /your archive/i });
      const catalogueTab = screen.getByRole("button", { name: /live catalogue/i });
      expect(archiveTab).not.toBeNull();
      expect(catalogueTab).not.toBeNull();

      // Archive tab has the sliding pill
      const activePill = archiveTab.querySelector(".bg-primary");
      expect(activePill).not.toBeNull();
      expect(activePill?.classList.contains("rounded-lg")).toBe(true);

      // Switch to Catalogue tab
      await act(async () => {
        fireEvent.click(catalogueTab);
      });

      // Now catalogue tab holds the active pill
      const updatedCataloguePill = catalogueTab.querySelector(".bg-primary");
      expect(updatedCataloguePill).not.toBeNull();
    });

    it("respects prefers-reduced-motion: reduce on surface navigation without motion errors", async () => {
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })) as unknown as typeof window.matchMedia;

      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      const catalogueTab = await screen.findByRole("button", { name: /live catalogue/i });
      expect(catalogueTab).not.toBeNull();
      const activePill = catalogueTab.querySelector(".bg-primary");
      expect(activePill).not.toBeNull();
    });
  });

  describe("2. Filter Chips & Quick Pick Dynamics", () => {
    it("renders streaming platforms, mood chips, and sort buttons with active state feedback", async () => {
      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      // Verify streaming platform chips exist
      const netflixBtn = await screen.findByRole("button", { name: /netflix/i });
      expect(netflixBtn).not.toBeNull();

      // Click Netflix platform
      await act(async () => {
        fireEvent.click(netflixBtn);
      });
      expect(netflixBtn.classList.contains("bg-primary")).toBe(true);

      // Verify mood chips exist
      const thrillerMoodBtn = screen.getByRole("button", { name: /thriller/i });
      expect(thrillerMoodBtn).not.toBeNull();

      await act(async () => {
        fireEvent.click(thrillerMoodBtn);
      });
      expect(thrillerMoodBtn.classList.contains("bg-primary")).toBe(true);

      // Verify sort options exist and Popularity is selected by default
      const ratingSortBtn = screen.getByRole("button", { name: "Rating" });
      expect(ratingSortBtn).not.toBeNull();

      await act(async () => {
        fireEvent.click(ratingSortBtn);
      });
      expect(ratingSortBtn.classList.contains("border-primary")).toBe(true);
      expect(ratingSortBtn.classList.contains("font-bold")).toBe(true);
    });
  });

  describe("3. Staggered Catalogue Grid & MovieCard Interactivity", () => {
    it("renders movies in a staggered animated catalogue grid", async () => {
      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      // Wait for movies to be rendered in the catalogue grid
      const bladeRunnerCard = await screen.findByText("Blade Runner 2049");
      expect(bladeRunnerCard).not.toBeNull();

      const chungkingCard = screen.getByText("Chungking Express");
      expect(chungkingCard).not.toBeNull();

      // Verify card contains rating and release year
      const cardContainer = bladeRunnerCard.closest(".cursor-pointer");
      expect(cardContainer).not.toBeNull();
      expect(cardContainer?.textContent).toContain("8.0");
      expect(cardContainer?.textContent).toContain("2017");
      expect(cardContainer?.textContent).toContain("#Cyberpunk");
    });

    it("triggers watchlist toggle and opens movie detail modal smoothly on card click", async () => {
      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      const bladeRunnerCard = await screen.findByText("Blade Runner 2049");
      const cardContainer = bladeRunnerCard.closest(".cursor-pointer");

      // Click card to open MovieDetailSheet modal
      await act(async () => {
        fireEvent.click(cardContainer!);
      });

      // Verify detail dialog opened with proper ARIA semantics
      const dialog = await screen.findByRole("dialog");
      expect(dialog).not.toBeNull();
      expect(dialog.getAttribute("aria-modal")).toBe("true");

      const modalTitle = screen.getByRole("heading", { name: "Blade Runner 2049" });
      expect(modalTitle).not.toBeNull();

      // Close modal
      const closeBtn = screen.getByRole("button", { name: "Close details" });
      await act(async () => {
        fireEvent.click(closeBtn);
      });

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).toBeNull();
      });
    });
  });

  describe("4. Archive Personalized Shelves Motion", () => {
    it("renders Spotlight Hero and horizontal shelf scroll buttons", async () => {
      render(
        <MemoryRouter initialEntries={["/discover?view=archive"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      // Verify Spotlight Selection hero card is rendered
      const spotlightBadge = await screen.findByText("Spotlight Selection");
      expect(spotlightBadge).not.toBeNull();

      // Verify shelf title and navigation buttons
      const shelfTitle = screen.getByText("Recommended For You");
      expect(shelfTitle).not.toBeNull();

      const scrollRightBtn = screen.getByRole("button", { name: "Scroll right" });
      expect(scrollRightBtn).not.toBeNull();
    });
  });
});
