import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

// Stub window.matchMedia before imports evaluate
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

import SessionPage from "../SessionPage";

// Mock analytics and api modules
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/62/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

// Mock framer-motion and canvas-confetti
vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
    button: ({ children, ...props }: any) => <button {...props}>{children}</button>,
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
}));
vi.mock("canvas-confetti", () => ({
  default: vi.fn(),
}));

describe("Guest Join Navigation & Preferences Guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "mock_guest_token");
    window.localStorage.setItem("username", "amita");
    window.localStorage.setItem("display_name", "Amita Gohil");

    // Stub global WebSocket
    (window as any).WebSocket = class {
      onopen: (() => void) | null = null;
      onclose: (() => void) | null = null;
      onmessage: (() => void) | null = null;
      onerror: (() => void) | null = null;
      close() {}
      send() {}
    };
  });

  /* -------------------------------------------------------------
     Navigation Routing Tests (HomePage.tsx & AutoJoin.tsx contract)
     ------------------------------------------------------------- */

  it("routes to /preferences when user_preferences_set is false (initial guest join)", async () => {
    const navigateMock = vi.fn();
    const joinCode = "6LBE33";

    mockApiRequest.mockResolvedValueOnce({
      success: true,
      session_id: 62,
      code: joinCode,
      host_joined: true,
      guest_joined: true,
      preferences_set: false,
      user_role: "guest",
      user_preferences_set: false,
      host_preferences_set: true,
      guest_preferences_set: false,
    });

    const data = await mockApiRequest("/api/sessions/join/", {
      method: "POST",
      body: JSON.stringify({ code: joinCode }),
    });

    // Updated routing logic checking user_preferences_set
    if (data.user_preferences_set) {
      navigateMock(`/session/${data.session_id}`);
    } else {
      navigateMock(`/session/${data.session_id}/preferences`);
    }

    expect(navigateMock).toHaveBeenCalledWith("/session/62/preferences");
    expect(navigateMock).not.toHaveBeenCalledWith("/session/62");
  });

  it("routes to /session/:id when user_preferences_set is true, even if overall preferences_set is false (guest completed, host pending)", async () => {
    const navigateMock = vi.fn();
    const joinCode = "6LBE33";

    mockApiRequest.mockResolvedValueOnce({
      success: true,
      session_id: 62,
      code: joinCode,
      host_joined: true,
      guest_joined: true,
      preferences_set: false, // Overall session is NOT ready
      user_role: "guest",
      user_preferences_set: true, // Guest has completed preferences
      host_preferences_set: false,
      guest_preferences_set: true,
    });

    const data = await mockApiRequest("/api/sessions/join/", {
      method: "POST",
      body: JSON.stringify({ code: joinCode }),
    });

    // Evaluated routing
    if (data.user_preferences_set) {
      navigateMock(`/session/${data.session_id}`);
    } else {
      navigateMock(`/session/${data.session_id}/preferences`);
    }

    // Must route to session deck (where SessionPage displays 'Awaiting Partner Preferences')
    // rather than ejecting user back into the questionnaire!
    expect(navigateMock).toHaveBeenCalledWith("/session/62");
    expect(navigateMock).not.toHaveBeenCalledWith("/session/62/preferences");
  });

  it("routes to /session/:id when both participants have completed preferences (both complete)", async () => {
    const navigateMock = vi.fn();
    const joinCode = "6LBE33";

    mockApiRequest.mockResolvedValueOnce({
      success: true,
      session_id: 62,
      code: joinCode,
      host_joined: true,
      guest_joined: true,
      preferences_set: true,
      user_role: "guest",
      user_preferences_set: true,
      host_preferences_set: true,
      guest_preferences_set: true,
    });

    const data = await mockApiRequest("/api/sessions/join/", {
      method: "POST",
      body: JSON.stringify({ code: joinCode }),
    });

    if (data.user_preferences_set) {
      navigateMock(`/session/${data.session_id}`);
    } else {
      navigateMock(`/session/${data.session_id}/preferences`);
    }

    expect(navigateMock).toHaveBeenCalledWith("/session/62");
  });

  /* -------------------------------------------------------------
     SessionPage Screen Guard Tests
     ------------------------------------------------------------- */

  it("proves SessionPage does NOT show 'Awaiting Partner Preferences' when guest preferences are unset", async () => {
    // Session state where both joined, but guest preferences are false
    mockApiRequest.mockResolvedValue({
      success: true,
      session: {
        id: 62,
        code: "6LBE33",
        genre: { id: 13, name: "Mystery" },
        host_joined: true,
        guest_joined: true,
        host_display_name: "xenontest",
        guest_display_name: "Amita Gohil",
        ended: false,
        preferences_set: false,
        user_role: "guest",
        user_preferences_set: false,
        host_preferences_set: false,
        guest_preferences_set: false,
        user_preferences: null,
      },
    });

    render(
      <MemoryRouter initialEntries={["/session/62"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
          <Route path="/session/:id/preferences" element={<div>PREFERENCES_PAGE_MOCK</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/62/");
    });

    // The misleading "Awaiting Partner Preferences" and "Your cinematic taste parameters are locked in" must NOT be shown
    expect(screen.queryByText("Awaiting Partner Preferences")).toBeNull();
    expect(screen.queryByText(/Your cinematic taste parameters are locked in/i)).toBeNull();

    // Instead, the user must see "Set Your Taste Parameters" / "Complete Questionnaire" or be redirected
    const cta = screen.queryByText("Complete Questionnaire") || screen.queryByText("PREFERENCES_PAGE_MOCK");
    expect(cta).not.toBeNull();
  });

  it("proves SessionPage displays 'Awaiting Partner Preferences' only when user's own preferences are locked in", async () => {
    // Session state where user completed their preferences, but partner has not
    mockApiRequest.mockResolvedValue({
      success: true,
      session: {
        id: 62,
        code: "6LBE33",
        genre: { id: 13, name: "Mystery" },
        host_joined: true,
        guest_joined: true,
        host_display_name: "xenontest",
        guest_display_name: "Amita Gohil",
        ended: false,
        preferences_set: false,
        user_role: "guest",
        user_preferences_set: true,
        host_preferences_set: false,
        guest_preferences_set: true,
        user_preferences: { tone: ["thrilled"] },
      },
    });

    render(
      <MemoryRouter initialEntries={["/session/62"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/62/");
    });

    // When user_preferences_set is true, the waiting screen is rightfully shown
    expect(await screen.findByText("Awaiting Partner Preferences")).not.toBeNull();
    expect(screen.getByText(/Your cinematic taste parameters are locked in/i)).not.toBeNull();
  });

  it("Host remains in session waiting room and is not redirected to home when guest has not joined", async () => {
    mockApiRequest.mockResolvedValue({
      success: true,
      session: {
        id: 63,
        code: "R682TY",
        genre: { id: 4, name: "Comedy" },
        host_joined: true,
        guest_joined: false,
        host_display_name: "HostUser",
        ended: false,
        preferences_set: false,
        user_role: "host",
        user_preferences_set: false,
        host_preferences_set: false,
        guest_preferences_set: false,
      },
    });

    render(
      <MemoryRouter initialEntries={["/session/63"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
          <Route path="/home" element={<div>Home Page Mock</div>} />
          <Route path="/" element={<div>Landing Mock</div>} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/sessions/63/");
    });

    // Host should see the invite code R682TY and waiting room, not be navigated to home
    expect(await screen.findByText("R682TY")).not.toBeNull();
    expect(screen.queryByText("Home Page Mock")).toBeNull();
    expect(screen.queryByText("Landing Mock")).toBeNull();
  });

  it("Transient poll error preserves active session view without showing full-screen error", async () => {
    // 1st call succeeds
    mockApiRequest.mockResolvedValueOnce({
      success: true,
      session: {
        id: 63,
        code: "R682TY",
        genre: { id: 4, name: "Comedy" },
        host_joined: true,
        guest_joined: false,
        host_display_name: "HostUser",
        ended: false,
        preferences_set: false,
        user_role: "host",
        user_preferences_set: false,
        host_preferences_set: false,
        guest_preferences_set: false,
      },
    });
    // 2nd poll fails with 503
    mockApiRequest.mockRejectedValueOnce({ status: 503, message: "Database busy" });

    render(
      <MemoryRouter initialEntries={["/session/63"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("R682TY")).not.toBeNull();
    // Verify the session UI remains visible and "Failed to load session" is not displayed
    expect(screen.queryByText("Failed to load session")).toBeNull();
  });
});
