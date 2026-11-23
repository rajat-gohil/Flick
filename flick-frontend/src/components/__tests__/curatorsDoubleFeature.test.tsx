import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CuratorsDoubleFeature, { type DoubleFeatureResponse } from "../CuratorsDoubleFeature";
import * as api from "../../lib/api";

const mockDoubleFeatureData: DoubleFeatureResponse = {
  success: true,
  source: "daily_editorial",
  is_personalized: false,
  theme: "Neo-Noir & Investigation",
  curator_note: "Two procedural masterclasses from David Fincher exploring the psychological toll of hunting an elusive killer.",
  film_1: {
    id: 799,
    tmdb_id: 1949,
    title: "Zodiac",
    overview: "A cartoonist becomes obsessed with tracking down the Zodiac Killer.",
    poster_url: "https://image.tmdb.org/t/p/w780/zodiac.jpg",
    rating: 7.5,
    release_year: 2007,
    genres: ["Crime", "Mystery", "Thriller"],
  },
  film_2: {
    id: 366,
    tmdb_id: 807,
    title: "Se7en",
    overview: "Two detectives hunt a serial killer who uses the seven deadly sins.",
    poster_url: "https://image.tmdb.org/t/p/w780/se7en.jpg",
    rating: 8.4,
    release_year: 1995,
    genres: ["Crime", "Mystery", "Thriller"],
  },
};

describe("CuratorsDoubleFeature Component", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("1. Displays skeleton loading state initially", () => {
    vi.spyOn(api, "apiRequest").mockImplementation(() => new Promise(() => {}));
    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
      />
    );
    expect(screen.getByTestId("double-feature-loading")).not.toBeNull();
  });

  it("2. Renders double feature data successfully", async () => {
    vi.spyOn(api, "apiRequest").mockResolvedValueOnce(mockDoubleFeatureData);
    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Neo-Noir & Investigation")).not.toBeNull();
    });

    expect(screen.getByText("Zodiac")).not.toBeNull();
    expect(screen.getByText("Se7en")).not.toBeNull();
    expect(screen.getByText(/Two procedural masterclasses from David Fincher/i)).not.toBeNull();
    expect(screen.getByText("FEATURE NO. 1")).not.toBeNull();
    expect(screen.getByText("FEATURE NO. 2")).not.toBeNull();
  });

  it("3. Clicking a film card triggers onMovieClick with that movie", async () => {
    vi.spyOn(api, "apiRequest").mockResolvedValueOnce(mockDoubleFeatureData);
    const handleMovieClick = vi.fn();

    render(
      <CuratorsDoubleFeature
        onMovieClick={handleMovieClick}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Zodiac")).not.toBeNull();
    });

    const zodiacCard = screen.getByLabelText("Inspect film: Zodiac");
    fireEvent.click(zodiacCard);
    expect(handleMovieClick).toHaveBeenCalledTimes(1);
    expect(handleMovieClick).toHaveBeenCalledWith(mockDoubleFeatureData.film_1);
  });

  it("4. Clicking 'Screen Double Feature' triggers onScreenDoubleFeature callback", async () => {
    vi.spyOn(api, "apiRequest").mockResolvedValueOnce(mockDoubleFeatureData);
    const handleScreen = vi.fn();

    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={handleScreen}
        watchlistIds={new Set()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Screen Double Feature")).not.toBeNull();
    });

    fireEvent.click(screen.getByText("Screen Double Feature"));
    expect(handleScreen).toHaveBeenCalledTimes(1);
    expect(handleScreen).toHaveBeenCalledWith(
      mockDoubleFeatureData.film_1,
      mockDoubleFeatureData.film_2
    );
  });

  it("5. Batch watchlist addition sends atomic request and updates UI state", async () => {
    vi.spyOn(api, "apiRequest")
      .mockResolvedValueOnce(mockDoubleFeatureData)
      .mockResolvedValueOnce({ success: true, batch: true });

    const handleWatchlistUpdated = vi.fn();

    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
        onWatchlistUpdated={handleWatchlistUpdated}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Save Both to Watchlist")).not.toBeNull();
    });

    const saveButton = screen.getByText("Save Both to Watchlist");
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText("Both Saved in Watchlist")).not.toBeNull();
    });

    expect(handleWatchlistUpdated).toHaveBeenCalledWith([799, 366]);
  });

  it("6. Watchlist failure displays error message without false success feedback", async () => {
    vi.spyOn(api, "apiRequest")
      .mockResolvedValueOnce(mockDoubleFeatureData)
      .mockRejectedValueOnce(new Error("Network Error"));

    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Save Both to Watchlist")).not.toBeNull();
    });

    fireEvent.click(screen.getByText("Save Both to Watchlist"));

    await waitFor(() => {
      expect(
        screen.getByText("Network error while adding to watchlist. Please retry.")
      ).not.toBeNull();
    });

    expect(screen.queryByText("Both Saved in Watchlist")).toBeNull();
  });

  it("7. Displays already saved status if both IDs exist in watchlistIds", async () => {
    vi.spyOn(api, "apiRequest").mockResolvedValueOnce(mockDoubleFeatureData);

    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set([799, 366])}
      />
    );

    await waitFor(() => {
      expect(screen.getByText("Both Saved in Watchlist")).not.toBeNull();
    });
  });

  it("8. Displays graceful error view and allows retry when API fails", async () => {
    vi.spyOn(api, "apiRequest")
      .mockRejectedValueOnce(new Error("Server 500"))
      .mockResolvedValueOnce(mockDoubleFeatureData);

    render(
      <CuratorsDoubleFeature
        onMovieClick={vi.fn()}
        onScreenDoubleFeature={vi.fn()}
        watchlistIds={new Set()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("double-feature-error")).not.toBeNull();
    });

    fireEvent.click(screen.getByText("Retry Curatorial Retrieval"));

    await waitFor(() => {
      expect(screen.getByText("Neo-Noir & Investigation")).not.toBeNull();
    });
  });
});
