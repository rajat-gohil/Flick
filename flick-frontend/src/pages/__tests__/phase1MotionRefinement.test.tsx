import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import BottomNav from "../../components/BottomNav";
import HomePage from "../HomePage";

// Mock the API client
vi.mock("../../lib/api", () => ({
  apiRequest: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number;
    data: unknown;
    constructor(message: string, status: number, data: unknown) {
      super(message);
      this.status = status;
      this.data = data;
    }
  },
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

// Mock auth module
vi.mock("../../lib/auth", () => ({
  isGuest: vi.fn(() => false),
  isLoggedIn: vi.fn(() => true),
  getToken: vi.fn(() => "mock-token-xyz"),
  getUser: vi.fn(() => ({ id: 42, username: "cinephile", display_name: "Auteur" })),
  logout: vi.fn(),
}));

// Mock tutorial
vi.mock("../../lib/tutorial", () => ({
  hasSeenTour: vi.fn(() => true),
  markTourFinished: vi.fn(),
  useSpotlightTour: vi.fn(() => ({
    isOpen: false,
    currentStep: 0,
    steps: [],
    next: vi.fn(),
    prev: vi.fn(),
    skip: vi.fn(),
    finish: vi.fn(),
  })),
}));

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
  trackEvent: vi.fn(),
}));

import { apiRequest } from "../../lib/api";

describe("Phase 1 Motion Refinement: BottomNav & HomePage Motion", () => {
  let matchMediaMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    // Default matchMedia mock returning reducedMotion = false
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
      if (endpoint.includes("curators-selection") || endpoint.includes("/movies/recommendations/curators/")) {
        return Promise.resolve({
          movies: [
            {
              id: 101,
              title: "Stalker",
              release_year: 1979,
              poster_url: "https://example.com/stalker.jpg",
              overview: "A guide leads two men through an area known as the Zone.",
              rating: 8.4,
              vote_count: 1400,
              director: "Andrei Tarkovsky",
              runtime: 162,
              genres: [{ id: 878, name: "Science Fiction" }],
              explanation: {
                summary: "A contemplative masterpiece exploring faith and desire.",
                confidence: "HIGH",
                matched_signals: ["Philosophical", "Atmospheric"],
              },
            },
            {
              id: 102,
              title: "Solaris",
              release_year: 1972,
              poster_url: "https://example.com/solaris.jpg",
              rating: 8.1,
              explanation: {
                matched_signals: ["Psychological"],
              },
            },
          ],
        });
      }
      if (endpoint.includes("/movies/history/")) {
        return Promise.resolve({ history: [] });
      }
      if (endpoint.includes("/movies/watchlist/")) {
        return Promise.resolve({ watchlist: [] });
      }
      if (endpoint.includes("/movies/categories/")) {
        return Promise.resolve({ movies: [] });
      }
      return Promise.resolve({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("1. Bottom Navigation Motion & Active Tab Pill", () => {
    it("renders active tab with sliding pill and font variation settings", () => {
      render(
        <MemoryRouter initialEntries={["/home"]}>
          <BottomNav current="home" />
        </MemoryRouter>
      );

      const homeBtn = screen.getByRole("button", { name: /home/i });
      expect(homeBtn).not.toBeNull();
      expect(homeBtn.getAttribute("aria-current")).toBe("page");

      // Verify active pill styling exists within the active button
      const activePill = homeBtn.querySelector(".bg-primary\\/10");
      expect(activePill).not.toBeNull();
      expect(activePill?.classList.contains("rounded-xl")).toBe(true);
      expect(activePill?.classList.contains("border-primary/20")).toBe(true);

      // Inactive buttons do not contain the active pill
      const sessionsBtn = screen.getByRole("button", { name: /screenings/i });
      expect(sessionsBtn.getAttribute("aria-current")).toBeNull();
      expect(sessionsBtn.querySelector(".bg-primary\\/10")).toBeNull();
    });

    it("moves the active pill when current tab switches to 'sessions'", () => {
      const { rerender } = render(
        <MemoryRouter initialEntries={["/home"]}>
          <BottomNav current="home" />
        </MemoryRouter>
      );

      let homeBtn = screen.getByRole("button", { name: /home/i });
      let sessionsBtn = screen.getByRole("button", { name: /screenings/i });
      expect(homeBtn.querySelector(".bg-primary\\/10")).not.toBeNull();
      expect(sessionsBtn.querySelector(".bg-primary\\/10")).toBeNull();

      rerender(
        <MemoryRouter initialEntries={["/sessions"]}>
          <BottomNav current="sessions" />
        </MemoryRouter>
      );

      homeBtn = screen.getByRole("button", { name: /home/i });
      sessionsBtn = screen.getByRole("button", { name: /screenings/i });
      expect(homeBtn.querySelector(".bg-primary\\/10")).toBeNull();
      expect(sessionsBtn.querySelector(".bg-primary\\/10")).not.toBeNull();
      expect(sessionsBtn.getAttribute("aria-current")).toBe("page");
    });

    it("respects prefers-reduced-motion: reduce by rendering without crashing", () => {
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
        <MemoryRouter initialEntries={["/home"]}>
          <BottomNav current="home" />
        </MemoryRouter>
      );

      const homeBtn = screen.getByRole("button", { name: /home/i });
      expect(homeBtn).not.toBeNull();
      expect(homeBtn.getAttribute("aria-current")).toBe("page");
      // Pill still renders as a clean static element
      const activePill = homeBtn.querySelector(".bg-primary\\/10");
      expect(activePill).not.toBeNull();
    });
  });

  describe("2. Home Dashboard Stagger & Ambient Glows", () => {
    it("renders primary screening action card with ambient breathing glow in standard motion", async () => {
      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      // Verify Launch Screening Deck button is present
      const launchBtn = await screen.findByRole("button", { name: /launch screening deck/i });
      expect(launchBtn).not.toBeNull();

      // Ambient glow element is present as an aria-hidden motion element behind the button
      const glowElement = launchBtn.parentElement?.querySelector(".bg-primary\\/25.blur-md");
      expect(glowElement).not.toBeNull();
      expect(glowElement?.getAttribute("aria-hidden")).toBe("true");
    });

    it("renders direct salon entry ticket card without continuous ambient pulsing glow", async () => {
      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      const joinCard = await screen.findByText(/direct salon entry/i);
      expect(joinCard).not.toBeNull();

      // Continuous decorative pulsing blur behind the join card is intentionally omitted
      const cardContainer = joinCard.closest('[data-tour="home-join-code"]')?.parentElement;
      const glowElement = cardContainer?.querySelector(".bg-primary\\/20.blur-xl");
      expect(glowElement).toBeNull();
    });

    it("suppresses ambient breathing glows when prefers-reduced-motion is active", async () => {
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
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      const launchBtn = await screen.findByRole("button", { name: /launch screening deck/i });
      expect(launchBtn).not.toBeNull();

      // In reduced motion mode, ambient breathing glow is omitted to prevent distracting motion
      const glowElement = launchBtn.parentElement?.querySelector(".bg-primary\\/25.blur-md");
      expect(glowElement).toBeNull();
    });

    it("switches curator recommendations with crossfade container when alternate pick is clicked", async () => {
      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      // Wait for Stalker to be loaded in the feature card
      const initialFeatureTitle = await screen.findByRole("heading", { name: "Stalker" });
      expect(initialFeatureTitle).not.toBeNull();

      // Alternate pick Solaris should be in the Curator's Notebook (level 5)
      const alternatePick = screen.getByRole("heading", { name: "Solaris", level: 5 });
      expect(alternatePick).not.toBeNull();

      // Click alternate pick to switch recommendation
      await act(async () => {
        fireEvent.click(alternatePick.closest(".cursor-pointer")!);
      });

      // Feature card should now display Solaris as the main spotlight (level 3)
      const updatedFeatureTitle = await screen.findByRole("heading", { name: "Solaris", level: 3 });
      expect(updatedFeatureTitle).not.toBeNull();

      // The feature card element has data-tour="home-curator-feature"
      const featureCard = updatedFeatureTitle.closest('[data-tour="home-curator-feature"]');
      expect(featureCard).not.toBeNull();
    });
  });
});
