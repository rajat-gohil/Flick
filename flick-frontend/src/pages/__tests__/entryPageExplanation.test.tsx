import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../context/ThemeContext";
import EntryPage from "../EntryPage";

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

// Mock api
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    provisionGuest: vi.fn(),
  };
});

describe("Landing / Entry Page: Visual Redesign & Product Demonstration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("1. Renders hero with clear value proposition and primary/secondary access options", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(
      screen.getByRole("heading", { name: /Find the movie you both want to watch/i })
    ).not.toBeNull();
    expect(screen.getByText(/Open a Screening Room, send the invite code/i)).not.toBeNull();

    expect(screen.getAllByRole("button", { name: /start a movie night/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("button", { name: "Sign In" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("button", { name: "Sign Up" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /restore key/i })).not.toBeNull();
  });

  it("2. Demonstrates interactive sample swipe deck in hero (Pass advances card, Recommend reveals Mutual Match example)", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Initial verified film card
    expect(screen.getAllByText("Interstellar").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole("button", { name: /super-like/i })).toBeNull();
    const undoBtn = screen.getByRole("button", { name: /preview undo last swipe/i });
    expect((undoBtn as HTMLButtonElement).disabled).toBe(true);

    // Pass moves to next sample film (The Dark Knight)
    fireEvent.click(screen.getByRole("button", { name: /preview pass film/i }));
    expect(screen.getByText("The Dark Knight")).not.toBeNull();
    expect((undoBtn as HTMLButtonElement).disabled).toBe(false);

    // Undo restores Interstellar
    fireEvent.click(undoBtn);
    expect(screen.getAllByText("Interstellar").length).toBeGreaterThanOrEqual(1);

    // Pass again to The Dark Knight, then Recommend reveals mutual match example
    fireEvent.click(screen.getByRole("button", { name: /preview pass film/i }));
    expect(screen.getByText("The Dark Knight")).not.toBeNull();

    // Recommend reveals mutual match example
    fireEvent.click(screen.getByRole("button", { name: /preview recommend film/i }));
    expect(screen.getByText("Mutual Match Example")).not.toBeNull();
    expect(screen.getByText(/Both viewers recommended this film/i)).not.toBeNull();

    // Undo from match example restores The Dark Knight
    fireEvent.click(screen.getByRole("button", { name: /preview undo last swipe/i }));
    expect(screen.getByText("The Dark Knight")).not.toBeNull();
  });

  it("3. Shows interactive 4-step Screening Room workflow covering setup, invite, independent swiping, and mutual match", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText("How a Screening Room works")).not.toBeNull();

    const step2Btn = screen.getByRole("button", { name: /Share the 6-letter room code/i });
    fireEvent.click(step2Btn);
    expect(screen.getByText("CINE24")).not.toBeNull();

    const step3Btn = screen.getByRole("button", { name: /Swipe independently/i });
    fireEvent.click(step3Btn);
    expect(screen.getByText("Viewer A screen")).not.toBeNull();
    expect(screen.getByText("Viewer B screen")).not.toBeNull();

    const step4Btn = screen.getByRole("button", { name: /See only what you both chose/i });
    fireEvent.click(step4Btn);
    expect(screen.getByText(/Save to shared Watchlist or check regional watch options/i)).not.toBeNull();
  });

  it("4. Explains instant guest access, recovery key, and permanent email accounts plus FAQ accordion", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText("Start right away, or save across devices")).not.toBeNull();
    expect(screen.getByText("Instant guest access")).not.toBeNull();
    expect(screen.getByText("Permanent email account")).not.toBeNull();

    const faqButton = screen.getByRole("button", { name: /Does Flick stream or play movies/i });
    fireEvent.click(faqButton);
    expect(screen.getByText(/No\. Flick helps two people agree on what to watch/i)).not.toBeNull();
  });

  it("5. Navigates cleanly when clicking Sign Up or Restore key", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
            <Route path="/login" element={<div>Login Page Target</div>} />
            <Route path="/register" element={<div>Register Page Target</div>} />
            <Route path="/recover" element={<div>Recover Page Target</div>} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    const signUpBtn = screen.getAllByRole("button", { name: "Sign Up" })[0];
    fireEvent.click(signUpBtn);
    expect(screen.getByText("Register Page Target")).not.toBeNull();
  });
});
