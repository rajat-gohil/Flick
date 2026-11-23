import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import CreateSessionPage from "../CreateSessionPage";
import * as api from "../../lib/api";

const mockCuratorMovie = {
  id: 42,
  tmdb_id: 9942,
  title: "Past Lives",
  original_language: "en",
  genres: ["Drama", "Romance"],
  genre_ids: [7, 14],
  overview: "Nora and Hae Sung, two deeply connected childhood friends, are reunited.",
  poster_url: "https://image.tmdb.org/t/p/w780/pastlives.jpg",
  rating: 8.2,
  release_year: 2023,
};

describe("Curator Selection Pre-seeded Session Creation", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.setItem("auth_token", "test-token");
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("automatically creates a session with the pre-seeded movie criteria without manual questionnaire steps", async () => {
    const apiRequestSpy = vi.spyOn(api, "apiRequest").mockImplementation((url: string, init?: RequestInit) => {
      if (url === "/api/sessions/create/") {
        return Promise.resolve({ success: true, id: 999, code: "PLV42X" });
      }
      if (url === "/api/sessions/genre/") {
        const body = JSON.parse(init?.body as string || "{}");
        expect(body.session_id).toBe(999);
        expect(body.industry).toBe("hollywood");
        expect(body.languages).toEqual(["en"]);
        expect(body.genre_ids).toContain(7); // Drama
        expect(body.genre_ids).toContain(14); // Romance
        expect(body.prioritized_movie_ids).toEqual([42]);
        return Promise.resolve({
          success: true,
          session_id: 999,
          genre: { id: 7, name: "Drama" },
          genres: [{ id: 7, name: "Drama" }, { id: 14, name: "Romance" }],
          industry: "hollywood",
          languages: ["en"],
        });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: "/session/create",
            state: { preseedMovie: mockCuratorMovie },
          },
        ]}
      >
        <Routes>
          <Route path="/session/create" element={<CreateSessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Verify it automatically creates and transitions to the ready screen with code
    await waitFor(() => {
      expect(screen.getByText("PLV42X")).not.toBeNull();
    });

    expect(screen.getByText(/Curator's Spotlight Active/i)).not.toBeNull();
    expect(screen.getByText(/Past Lives/i)).not.toBeNull();
    expect(screen.getByText("Screening Ready")).not.toBeNull();
    expect(screen.getByText(/Enter Screening Deck/i)).not.toBeNull();

    // Verify it did NOT show manual questionnaire steps
    expect(screen.queryByText(/Step 1 of 3/i)).toBeNull();
    expect(screen.queryByText(/Step 2 of 3/i)).toBeNull();
    expect(screen.queryByText(/What cinema tradition\?/i)).toBeNull();

    expect(apiRequestSpy).toHaveBeenCalledWith("/api/sessions/create/", expect.anything());
    expect(apiRequestSpy).toHaveBeenCalledWith("/api/sessions/genre/", expect.anything());
  });
});
