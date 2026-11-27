import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HomePage from "../pages/HomePage";

const mockApiRequest = vi.fn();
const mockNavigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
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

vi.mock("../components/CuratorsDoubleFeature", () => ({
  default: () => <div data-testid="double-feature-stub" />,
}));

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );
}

describe("HomePage Collaborative Screening & Curator's Selection fixes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "test-token");
    localStorage.setItem("username", "testuser");
  });

  it("renders Collaborative Screening card with semantic theme tokens instead of hardcoded dark colors", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("curators-selection")) {
        return Promise.resolve({ success: true, movies: [] });
      }
      if (url.includes("/api/discover/")) {
        return Promise.resolve({ success: true, movies: [] });
      }
      return Promise.resolve({ success: true, sessions: [], watchlist: [] });
    });

    renderHome();

    const card = await screen.findByTestId("collaborative-screening-card");
    expect(card.className).toContain("bg-surface");
    expect(card.className).toContain("text-foreground");
    expect(card.className).not.toContain("bg-[#141614]");
    expect(card.innerHTML).not.toContain("bg-stone-900");
    expect(card.innerHTML).not.toContain("bg-black/40");
  });

  it("renders editorial fallback card on empty curator response with Full Archive link", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("curators-selection")) {
        return Promise.resolve({ success: true, movies: [] });
      }
      if (url.includes("/api/discover/")) {
        return Promise.resolve({ success: true, movies: [] });
      }
      return Promise.resolve({ success: true, sessions: [], watchlist: [] });
    });

    renderHome();

    const fallback = await screen.findByTestId("curator-fallback-card");
    expect(fallback.getAttribute("data-state")).toBe("empty");
    expect(fallback.textContent).toContain("Today's selection is temporarily unavailable");

    fireEvent.click(within(fallback).getByRole("button", { name: /full archive/i }));
    expect(mockNavigate).toHaveBeenCalledWith("/discover?view=catalogue");
  });

  it("renders editorial fallback card on error, deduplicates concurrent retries, and recovers on success", async () => {
    let attempt = 0;
    let resolveRetry: ((v: unknown) => void) | null = null;

    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("curators-selection")) {
        attempt += 1;
        if (attempt === 1) {
          return Promise.reject(new Error("Network error"));
        }
        return new Promise((res) => {
          resolveRetry = res;
        });
      }
      if (url.includes("/api/discover/")) {
        return Promise.reject(new Error("Fallback error"));
      }
      return Promise.resolve({ success: true, sessions: [], watchlist: [] });
    });

    renderHome();

    const fallback = await screen.findByTestId("curator-fallback-card");
    expect(fallback.getAttribute("data-state")).toBe("error");

    const retryBtn = screen.getByRole("button", { name: /retry/i });
    fireEvent.click(retryBtn);
    fireEvent.click(retryBtn);

    // Concurrent click is ignored: only 2 curators-selection calls total (initial + 1 retry)
    expect(
      mockApiRequest.mock.calls.filter(([u]) => String(u).includes("curators-selection")).length
    ).toBe(2);

    // Loading skeleton shown during retry
    expect(screen.getByText(/consulting the archive index/i)).toBeTruthy();

    resolveRetry!({
      success: true,
      confidence: "HIGH",
      movies: [
        {
          id: 99,
          tmdb_id: 999,
          title: "Recovered Spotlight Film",
          overview: "A recovered selection.",
          poster_url: "/recovered.jpg",
          rating: 8.4,
          release_year: 2021,
        },
      ],
    });

    await waitFor(() => {
      expect(screen.getByText("Recovered Spotlight Film")).toBeTruthy();
    });
    expect(screen.queryByTestId("curator-fallback-card")).toBeNull();
  });
});
