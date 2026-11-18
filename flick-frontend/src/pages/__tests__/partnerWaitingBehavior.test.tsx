/**
 * Slice D — Partner Waiting Experience
 * Slice E — Screening Termination Controls (frontend layer)
 *
 * Regression tests per Phase 3.1 spec.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SessionPage from "../SessionPage";
import SessionsListPage from "../SessionsListPage";

vi.mock("../../lib/analytics", () => ({ trackEvent: vi.fn() }));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/63/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {} }),
  useTransform: (_mv: any, _input: any, output: any) => ({
    get: () => (Array.isArray(output) ? output[1] : 0),
    set: () => {},
  }),
  useAnimation: () => ({ start: vi.fn() }),
  useSpring: () => ({ get: () => 0, set: () => {} }),
  useVelocity: () => ({ get: () => 0 }),
}));

vi.mock("canvas-confetti", () => ({ default: vi.fn() }));

// Active manifest session, host role, partner present.
// pollSession reads data.session from the response.
const hostSessionData = {
  id: 63,
  code: "ABC123",
  name: "Test Screening",
  host_joined: true,
  guest_joined: true,
  host_id: 4,
  guest_id: 5,
  preferences_set: true,
  host_preferences_set: true,
  guest_preferences_set: true,
  user_preferences_set: true,
  host_display_name: "Alice",
  guest_display_name: "Bob",
  user_role: "host",
  ended: false,
  is_legacy: false,
  created_at: "2026-11-04T10:00:00Z",
};

const hostSessionResponse = { success: true, session: hostSessionData };
const guestSessionResponse = { success: true, session: { ...hostSessionData, user_role: "guest" } };

// Manifest deck card: waiting for partner (no card yet)
const waitingManifestResponse = {
  success: true,
  waiting_for_partner: true,
  card_index: 8,
  total_cards: 40,
  card: null,
};

// Manifest deck card: partner caught up, card ready
const normalManifestResponse = {
  success: true,
  waiting_for_partner: false,
  card_index: 3,
  total_cards: 40,
  card: {
    movie_id: 12345,
    slot_type: "consensus_core",
    title: "Test Film",
    poster_url: "",
    overview: "",
    rating: 7.5,
    release_year: 2005,
  },
};

function makeWebSocketStub() {
  return class {
    onopen: any; onclose: any; onmessage: any; onerror: any;
    send = vi.fn(); close = vi.fn();
    constructor() { setTimeout(() => this.onopen?.(), 10); }
  };
}

function renderSessionPage(sessionId = "63") {
  return render(
    <MemoryRouter initialEntries={[`/session/${sessionId}`]}>
      <Routes>
        <Route path="/session/:id" element={<SessionPage />} />
        <Route path="/home" element={<div>Home</div>} />
        <Route path="/session/:id/preferences" element={<div>Preferences</div>} />
      </Routes>
    </MemoryRouter>
  );
}

function renderSessionsListPage() {
  return render(
    <MemoryRouter initialEntries={["/sessions"]}>
      <Routes>
        <Route path="/sessions" element={<SessionsListPage />} />
        <Route path="/session/:id" element={<div>Session</div>} />
        <Route path="/session/create" element={<div>Create</div>} />
      </Routes>
    </MemoryRouter>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SLICE D — PARTNER WAITING EXPERIENCE
// ─────────────────────────────────────────────────────────────────────────────

describe("Slice D — Partner Waiting Experience", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
    vi.stubGlobal("WebSocket", makeWebSocketStub());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function makeWaitingMock() {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("deck/card/")) return Promise.resolve(waitingManifestResponse);
      if (url.includes("deck/")) return Promise.resolve({});
      if (url.includes("/api/sessions/63/")) return Promise.resolve(hostSessionResponse);
      if (url.includes("/api/matches/")) return Promise.resolve({ matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ watchlist: [] });
      return Promise.resolve({});
    });
  }

  it("compact waiting banner appears (not full-screen takeover) when waitingForPartner is true", async () => {
    makeWaitingMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("partner-waiting-banner")).not.toBeNull();
    }, { timeout: 4000 });

    // Must NOT show the old full-screen heading
    expect(screen.queryByText(/Awaiting Partner Synchrony/i)).toBeNull();
  });

  it("compact banner contains Check and Leave action buttons", async () => {
    makeWaitingMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("check-partner-status-btn")).not.toBeNull();
    }, { timeout: 4000 });

    expect(screen.queryByTestId("waiting-leave-btn")).not.toBeNull();
  });

  it("banner auto-dismisses when partner catches up (deck returns a card)", async () => {
    let deckCallCount = 0;
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("deck/card/")) {
        deckCallCount++;
        return Promise.resolve(deckCallCount === 1 ? waitingManifestResponse : normalManifestResponse);
      }
      if (url.includes("deck/")) return Promise.resolve({});
      if (url.includes("/api/sessions/63/")) return Promise.resolve(hostSessionResponse);
      if (url.includes("/api/matches/")) return Promise.resolve({ matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ watchlist: [] });
      return Promise.resolve({});
    });

    renderSessionPage();

    // Banner appears first
    await waitFor(() => {
      expect(screen.queryByTestId("partner-waiting-banner")).not.toBeNull();
    }, { timeout: 4000 });

    // Click "Check" — simulates partner catching up
    fireEvent.click(screen.getByTestId("check-partner-status-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("partner-waiting-banner")).toBeNull();
    }, { timeout: 4000 });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// SLICE E — SCREENING TERMINATION CONTROLS
// ─────────────────────────────────────────────────────────────────────────────

describe("Slice E — Screening Termination Controls (SessionPage)", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
    vi.stubGlobal("WebSocket", makeWebSocketStub());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function makeNormalMock(sessionResp = hostSessionResponse) {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("deck/card/")) return Promise.resolve(normalManifestResponse);
      if (url.includes("deck/")) return Promise.resolve({});
      if (url.includes("/api/sessions/63/")) return Promise.resolve(sessionResp);
      if (url.includes("/api/matches/")) return Promise.resolve({ matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ watchlist: [] });
      if (url === "/api/sessions/end/") return Promise.resolve({ success: true, ended: true });
      if (url === "/api/sessions/leave/") return Promise.resolve({ success: true, left: true });
      return Promise.resolve({});
    });
  }

  it("host sees Conclude button (not Leave) in top bar", async () => {
    makeNormalMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("conclude-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    expect(screen.queryByTestId("leave-screening-btn")).toBeNull();
  });

  it("guest sees Leave button (not Conclude) in top bar", async () => {
    makeNormalMock(guestSessionResponse);
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("leave-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    expect(screen.queryByTestId("conclude-screening-btn")).toBeNull();
  });

  it("clicking Conclude opens confirmation modal (no immediate API call)", async () => {
    makeNormalMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("conclude-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    fireEvent.click(screen.getByTestId("conclude-screening-btn"));

    await waitFor(() => {
      expect(screen.queryByTestId("end-confirm-modal")).not.toBeNull();
    });

    // End API must NOT have been called yet
    const endCalls = mockApiRequest.mock.calls.filter((call: any[]) => call[0] === "/api/sessions/end/");
    expect(endCalls.length).toBe(0);
  });

  it("confirming End Screening calls /api/sessions/end/", async () => {
    makeNormalMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("conclude-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    fireEvent.click(screen.getByTestId("conclude-screening-btn"));
    await waitFor(() => expect(screen.queryByTestId("end-confirm-modal")).not.toBeNull());
    fireEvent.click(screen.getByTestId("end-confirm-proceed-btn"));

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/sessions/end/",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("guest Leave calls /api/sessions/leave/ and never /api/sessions/end/", async () => {
    makeNormalMock(guestSessionResponse);
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("leave-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    fireEvent.click(screen.getByTestId("leave-screening-btn"));

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/sessions/leave/",
        expect.objectContaining({ method: "POST" })
      );
    });

    const endCalls = mockApiRequest.mock.calls.filter((call: any[]) => call[0] === "/api/sessions/end/");
    expect(endCalls.length).toBe(0);
    // Guest sees honest exited-screening view (not fake "Screening Concluded")
    await waitFor(() => {
      expect(screen.queryByTestId("guest-left-session-view")).not.toBeNull();
    });
  });

  it("shows visible inline error inside confirmation modal and allows retry when /api/sessions/end/ fails", async () => {
    let attempts = 0;
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("deck/card/")) return Promise.resolve(normalManifestResponse);
      if (url.includes("deck/")) return Promise.resolve({});
      if (url.includes("/api/sessions/63/")) return Promise.resolve(hostSessionResponse);
      if (url.includes("/api/matches/")) return Promise.resolve({ matches: [] });
      if (url.includes("/api/watchlist/")) return Promise.resolve({ watchlist: [] });
      if (url === "/api/sessions/end/") {
        attempts += 1;
        if (attempts === 1) return Promise.reject(new Error("Temporary server error"));
        return Promise.resolve({ success: true, ended: true, matches: [] });
      }
      return Promise.resolve({});
    });

    renderSessionPage();
    await waitFor(() => {
      expect(screen.queryByTestId("conclude-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    fireEvent.click(screen.getByTestId("conclude-screening-btn"));
    await waitFor(() => expect(screen.queryByTestId("end-confirm-modal")).not.toBeNull());
    fireEvent.click(screen.getByTestId("end-confirm-proceed-btn"));

    // Modal stays open with visible error alert on failure
    await waitFor(() => {
      expect(screen.queryByTestId("end-confirm-error")).not.toBeNull();
    });
    expect(screen.getByTestId("end-confirm-error").textContent).toContain("Temporary server error");

    // Retry succeeds and concludes session
    fireEvent.click(screen.getByTestId("end-confirm-proceed-btn"));
    await waitFor(() => {
      expect(screen.queryByText(/Screening Concluded/i)).not.toBeNull();
    });
    expect(attempts).toBe(2);
  });

  it("Escape key closes the End Screening confirmation modal", async () => {
    window.localStorage.setItem("flick_tour_session_v1:4", "completed");
    makeNormalMock();
    renderSessionPage();

    await waitFor(() => {
      expect(screen.queryByTestId("conclude-screening-btn")).not.toBeNull();
    }, { timeout: 4000 });

    fireEvent.click(screen.getByTestId("conclude-screening-btn"));
    await waitFor(() => expect(screen.queryByTestId("end-confirm-modal")).not.toBeNull());

    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("end-confirm-modal")).toBeNull());
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// SLICE E — ARCHIVE STATUS BADGES & END ACTION (SessionsListPage)
// ─────────────────────────────────────────────────────────────────────────────

describe("Slice E — Archive Status Badges & End Action (SessionsListPage)", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
  });

  it("active session shows Active badge", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [{
        id: 63, code: "ABC", name: "My Screening", date: "Nov 4",
        matches: 2, ended: false, status: "active", is_host: true, user_role: "host",
        participants: [{ initials: "AL", username: "alice" }],
      }],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("session-status-badge-63")).not.toBeNull();
    });
    expect(screen.getByTestId("session-status-badge-63").textContent).toContain("Active");
  });

  it("ended_by_host session shows 'Ended by host' badge", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [{
        id: 64, code: "XYZ", name: "Old Screening", date: "Nov 3",
        matches: 5, ended: true, status: "ended_by_host", is_host: true, user_role: "host",
        participants: [{ initials: "AL", username: "alice" }],
      }],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("session-status-badge-64")).not.toBeNull();
    });
    expect(screen.getByTestId("session-status-badge-64").textContent).toContain("Ended by host");
  });

  it("completed session shows 'Completed' badge", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [{
        id: 65, code: "CCC", name: "Done Screening", date: "Nov 2",
        matches: 3, ended: true, status: "completed", is_host: false, user_role: "guest",
        participants: [{ initials: "BO", username: "bob" }],
      }],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("session-status-badge-65")).not.toBeNull();
    });
    expect(screen.getByTestId("session-status-badge-65").textContent).toContain("Completed");
  });

  it("host-active session shows End Room button", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [{
        id: 63, code: "ABC", name: "My Screening", date: "Nov 4",
        matches: 2, ended: false, status: "active", is_host: true, user_role: "host",
        participants: [{ initials: "AL", username: "alice" }],
      }],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-63")).not.toBeNull();
    });
  });

  it("guest active session ALSO shows End Room button with equal permission", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [{
        id: 65, code: "DEF", name: "Guest Screening", date: "Nov 4",
        matches: 1, ended: false, status: "active", is_host: false, user_role: "guest",
        participants: [{ initials: "BO", username: "bob" }],
      }],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-65")).not.toBeNull();
    });
    expect(screen.getByTestId("end-room-btn-65").textContent).toContain("End Room");
  });

  it("clicking End Room opens confirmation modal", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/recent/") return Promise.resolve({
        sessions: [{
          id: 63, code: "ABC", name: "My Screening", date: "Nov 4",
          matches: 2, ended: false, status: "active", is_host: true, user_role: "host",
          participants: [{ initials: "AL", username: "alice" }],
        }],
      });
      return Promise.resolve({});
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-63")).not.toBeNull();
    });

    fireEvent.click(screen.getByTestId("end-room-btn-63"));

    await waitFor(() => {
      expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull();
    });
  });

  it("confirming End in archive calls /api/sessions/end/ and updates badge to 'Ended by host'", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/recent/") return Promise.resolve({
        sessions: [{
          id: 63, code: "ABC", name: "My Screening", date: "Nov 4",
          matches: 2, ended: false, status: "active", is_host: true, user_role: "host",
          participants: [{ initials: "AL", username: "alice" }],
        }],
      });
      if (url === "/api/sessions/end/") return Promise.resolve({ success: true, ended: true });
      return Promise.resolve({});
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-63")).not.toBeNull();
    });

    fireEvent.click(screen.getByTestId("end-room-btn-63"));
    await waitFor(() => expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull());
    fireEvent.click(screen.getByTestId("archive-end-confirm-proceed-btn"));

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/sessions/end/",
        expect.objectContaining({ method: "POST" })
      );
    });

    // After end, badge should update
    await waitFor(() => {
      expect(screen.getByTestId("session-status-badge-63").textContent).toContain("Ended by host");
    });
  });
});
