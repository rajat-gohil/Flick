import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import SessionPage from "../SessionPage";
import { ConstraintExhaustionNoticeModal } from "../../components/session/ConstraintExhaustionNoticeModal";
import { ErrorBoundary } from "../../components/ErrorBoundary";

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: any[]) => mockApiRequest(...args),
  getApiUrl: () => "http://localhost:8000",
  getWsUrl: () => "ws://localhost:8000",
}));

describe("Localized Genre Retrieval & Recovery Frontend Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.clear();
    localStorage.clear();
  });

  // -------------------------------------------------------------------------
  // Scenario A: ConstraintExhaustionNoticeModal object-decision rendering
  // -------------------------------------------------------------------------
  it("A1: handles object decision formats {decision, decided_at} without React child crash", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/87/expand-constraints/")) {
        return Promise.resolve({
          success: true,
          active_proposal: {
            id: "prop-1234",
            session_id: 87,
            status: "pending",
            initiated_by_user_id: 1,
            initiated_by_username: "host_user",
            original_constraints: { shared_languages: ["gu"], shared_min_rating: "7.0" },
            proposed_constraints: { shared_languages: ["gu"], shared_min_rating: "6.50" },
            host_decision: { decision: "approve", decided_at: "2026-11-13T22:56:49Z" },
            guest_decision: { decision: "pending", decided_at: null },
            created_at: "2026-11-13T22:56:49Z",
            expires_at: "2026-11-13T23:06:49Z",
            is_expired: false,
            is_mutually_approved: false,
          },
        });
      }
      return Promise.resolve({});
    });

    render(
      <ConstraintExhaustionNoticeModal
        isOpen={true}
        sessionId="87"
        userRole="host"
        onClose={vi.fn()}
      />
    );

    // Verify modal rendered without crashing
    await waitFor(() => {
      expect(screen.getByText("Candidate Pool Exhausted")).toBeTruthy();
    });

    // Proves vote status labels render text strings, not crashing on objects
    const myVote = screen.getByTestId("my-vote-status");
    const partnerVote = screen.getByTestId("partner-vote-status");
    expect(myVote.textContent).toBe("approved");
    expect(partnerVote.textContent).toBe("pending");
  });

  it("A2: displays informative notice and Adjust Taste Parameters button when replenishment is insufficient", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/87/expand-constraints/")) {
        return Promise.resolve({
          success: true,
          active_proposal: {
            id: "prop-insufficient",
            session_id: 87,
            status: "replenishment_insufficient",
            initiated_by_user_id: 1,
            initiated_by_username: "host_user",
            original_constraints: { shared_languages: ["gu"] },
            proposed_constraints: { shared_languages: ["gu"], shared_min_rating: "6.0" },
            host_decision: { decision: "approve", decided_at: "2026-11-13T22:56:49Z" },
            guest_decision: { decision: "approve", decided_at: "2026-11-13T22:57:10Z" },
            created_at: "2026-11-13T22:56:49Z",
            expires_at: "2026-11-13T23:06:49Z",
            is_expired: false,
            is_mutually_approved: true,
          },
        });
      }
      return Promise.resolve({});
    });

    const onAdjust = vi.fn();
    render(
      <ConstraintExhaustionNoticeModal
        isOpen={true}
        sessionId="87"
        userRole="host"
        onClose={vi.fn()}
        onAdjustPreferences={onAdjust}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId("insufficient-exhaustion-notice")).toBeTruthy();
    });

    const adjustBtn = screen.getByTestId("adjust-taste-params-btn");
    expect(adjustBtn).toBeTruthy();
    fireEvent.click(adjustBtn);
    expect(onAdjust).toHaveBeenCalledTimes(1);
  });

  // -------------------------------------------------------------------------
  // Scenario B: TMDB Connection Reset in SessionPage
  // -------------------------------------------------------------------------
  it("B: handles transient_error from /deck/card/ as a retryable notice, never popping exhaustion modal", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url.includes("/api/sessions/87/deck/card/")) {
        return Promise.resolve({
          success: false,
          transient_error: true,
          error: "Unable to reach movie service during candidate replenishment. Please retry.",
        });
      }
      if (url.includes("/api/sessions/87/")) {
        return Promise.resolve({
          success: true,
          session: {
            id: 87,
            code: "GUJHOR",
            host_joined: true,
            guest_joined: true,
            ended: false,
            preferences_set: true,
            user_preferences_set: true,
            user_role: "host",
          },
        });
      }
      return Promise.resolve({});
    });

    render(
      <MemoryRouter initialEntries={["/session/87"]}>
        <Routes>
          <Route path="/session/:id" element={<SessionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // Displays screening deck unavailable with retry button
    await waitFor(() => {
      expect(screen.getByText("Screening Deck Unavailable")).toBeTruthy();
    });

    expect(screen.getByTestId("deck-error-message").textContent).toContain("Unable to reach movie service");
    expect(screen.getByTestId("deck-retry-button")).toBeTruthy();

    // Constraint exhaustion modal must NOT be open
    expect(screen.queryByText("Candidate Pool Exhausted")).toBeNull();
  });

  // -------------------------------------------------------------------------
  // Scenario C: ErrorBoundary catch-all protection
  // -------------------------------------------------------------------------
  it("C: catches child rendering errors and displays recovery UI instead of blank white screen", () => {
    const ProblematicChild = () => {
      throw new Error("Simulated uncaught render error in child component");
    };

    // Suppress console.error for expected test throw
    const originalConsoleError = console.error;
    console.error = vi.fn();

    render(
      <ErrorBoundary>
        <ProblematicChild />
      </ErrorBoundary>
    );

    expect(screen.getByTestId("screening-error-boundary-fallback")).toBeTruthy();
    expect(screen.getByText("Session Display Notice")).toBeTruthy();
    expect(screen.getByTestId("error-boundary-reload-btn")).toBeTruthy();

    console.error = originalConsoleError;
  });
});
