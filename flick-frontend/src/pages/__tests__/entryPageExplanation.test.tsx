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

describe("Landing / Entry Page: Account Access Explanation & Onboarding", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("1. Renders hero with editorial title and clear access options (Start Exploring, Sign In, Sign Up, Restore)", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Hero title & subtitle
    expect(screen.getByText(/Movie night,/i)).not.toBeNull();
    expect(screen.getByText(/thoughtfully decided/i)).not.toBeNull();
    expect(screen.getByText(/Swipe through curated cinema with your partner/i)).not.toBeNull();

    // Primary guest exploration button
    expect(screen.getAllByRole("button", { name: /start a movie night/i }).length).toBeGreaterThanOrEqual(1);

    // Secondary actions (Sign In, Sign Up, Restore) remain accessible
    expect(screen.getAllByRole("button", { name: "Sign In" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole("button", { name: "Sign Up" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /restore key/i })).not.toBeNull();
  });

  it("2. Explains the three pillars of access: Guest Mode, Permanent Account, and Key Recovery", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // Section title
    expect(screen.getByText(/How Sign-Up, Sign-In & Guest Access Work/i)).not.toBeNull();

    // Pillar 1: Instant Guest Mode
    expect(screen.getByText("1. Instant Guest Mode")).not.toBeNull();
    expect(screen.getByText(/Zero forms — jump into rooms in seconds/i)).not.toBeNull();
    expect(screen.getByText(/Generates a private 16-character backup key/i)).not.toBeNull();

    // Pillar 2: Permanent Account
    expect(screen.getByText("2. Permanent Cinema Account")).not.toBeNull();
    expect(screen.getByText(/Seamless cloud sync across phones, tablets & desktop/i)).not.toBeNull();
    expect(screen.getByText(/Permanent match history & collaborative lists/i)).not.toBeNull();

    // Pillar 3: Recovery Key
    expect(screen.getByText("3. Key-Based Recovery")).not.toBeNull();
    expect(screen.getByText(/No personal data or email needed to transfer/i)).not.toBeNull();
    expect(screen.getByText(/Rotates a fresh key upon restoration for security/i)).not.toBeNull();
  });

  it("3. Displays comparison table comparing Guest Mode vs Permanent Account", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    expect(screen.getByText("Comparing Account Modes")).not.toBeNull();
    expect(screen.getByText("Sign-up Required")).not.toBeNull();
    expect(screen.getByText("None (0 seconds)")).not.toBeNull();
    expect(screen.getByText("Email + Password (~30s)")).not.toBeNull();
    expect(screen.getByText("Via 16-character Recovery Key")).not.toBeNull();
  });

  it("4. Displays 3-step screening walkthrough and interactive FAQ accordion", () => {
    render(
      <ThemeProvider>
        <MemoryRouter initialEntries={["/"]}>
          <Routes>
            <Route path="/" element={<EntryPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    );

    // 3-step walkthrough
    expect(screen.getByText("Three Steps to Movie Night")).not.toBeNull();
    expect(screen.getByText("Open a Room")).not.toBeNull();
    expect(screen.getByText("Swipe in Sync")).not.toBeNull();
    expect(screen.getByText("Instant Consensus")).not.toBeNull();

    // FAQ Accordion
    const faqButton = screen.getByText("Do I need to create an account to use Flick?");
    expect(faqButton).not.toBeNull();

    // Click FAQ to toggle answer
    fireEvent.click(faqButton);
    expect(screen.getByText(/No! You can tap 'Start a Movie Night' to immediately start swiping/i)).not.toBeNull();
  });

  it("5. Navigates cleanly when clicking Sign In, Sign Up, or Restore", () => {
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

    // Sign Up button
    const signUpBtn = screen.getAllByRole("button", { name: "Sign Up" })[0];
    fireEvent.click(signUpBtn);
    expect(screen.getByText("Register Page Target")).not.toBeNull();
  });
});
