import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SessionsListPage from "../SessionsListPage";

// Mock apiRequest
vi.mock("../../lib/api", () => ({
  apiRequest: vi.fn(),
  getWsUrl: vi.fn(() => "ws://mock"),
  getBaseUrl: vi.fn(() => ""),
  ApiError: class extends Error {
    status: number;
    data: any;
    constructor(status: number, data: any, message?: string) {
      super(message || (data && data.error) || `Request failed with status ${status}`);
      this.status = status;
      this.data = data;
    }
  },
}));

// Mock CinemaHeader and BottomNav
vi.mock("../../components/CinemaHeader", () => ({
  default: ({ title, subtitle }: { title: string; subtitle?: string }) => (
    <div data-testid="cinema-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  ),
}));

vi.mock("../../components/BottomNav", () => ({
  default: () => <div data-testid="bottom-nav" />,
}));

import { apiRequest } from "../../lib/api";
const mockApiRequest = vi.mocked(apiRequest);

function renderSessionsListPage(initialEntries = ["/sessions"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/sessions" element={<SessionsListPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Screening Directory — Shared End Room Permission Verification", () => {
  beforeEach(() => {
    mockApiRequest.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // 1. Host sees End Room on active directory cards
  it("1. Host sees End Room on active directory cards", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [
        {
          id: 201,
          code: "HOST01",
          name: "Mystery Night",
          date: "Nov 04, 2026",
          matches: 2,
          ended: false,
          status: "active",
          is_host: true,
          user_role: "host",
          participants: [{ initials: "HO", username: "host_user" }],
        },
      ],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-201")).not.toBeNull();
    });
    expect(screen.getByTestId("end-room-btn-201").textContent).toContain("End Room");
    expect(screen.getByTestId("session-status-badge-201").textContent).toContain("Active");
  });

  // 2. Guest sees End Room on active directory cards
  it("2. Guest sees End Room on active directory cards with equal permission", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [
        {
          id: 202,
          code: "GUEST1",
          name: "Comedy Night",
          date: "Nov 04, 2026",
          matches: 1,
          ended: false,
          status: "active",
          is_host: false,
          user_role: "guest",
          participants: [
            { initials: "HO", username: "host_user" },
            { initials: "GU", username: "guest_user" },
          ],
        },
      ],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-202")).not.toBeNull();
    });
    expect(screen.getByTestId("end-room-btn-202").textContent).toContain("End Room");
  });

  // 3. Both can open the confirmation dialog
  it("3. Both participants can open the confirmation dialog with correct copy", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [
        {
          id: 203,
          code: "CONF01",
          name: "Shared Room",
          date: "Nov 04, 2026",
          matches: 0,
          ended: false,
          status: "active",
          is_host: false,
          user_role: "guest",
          participants: [{ initials: "GU", username: "guest_user" }],
        },
      ],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-203")).not.toBeNull();
    });

    // Modal not open initially
    expect(screen.queryByTestId("archive-end-confirm-modal")).toBeNull();

    // Click End Room
    fireEvent.click(screen.getByTestId("end-room-btn-203"));

    await waitFor(() => {
      expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull();
    });
    const modal = screen.getByTestId("archive-end-confirm-modal");
    expect(modal.textContent).toContain("End this screening?");
    expect(modal.textContent).toContain("Ending this room will terminate the screening for both participants. This action cannot be undone.");
    expect(screen.getByTestId("archive-end-confirm-proceed-btn").textContent).toContain("End Room");
    expect(modal.textContent).toContain("Cancel");
  });

  // 4. Confirmation calls the existing termination endpoint
  it("4. Confirming calls the existing termination endpoint /api/sessions/end/", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/recent/") {
        return Promise.resolve({
          sessions: [
            {
              id: 204,
              code: "TERM01",
              name: "Termination Target",
              date: "Nov 04, 2026",
              matches: 3,
              ended: false,
              status: "active",
              is_host: false,
              user_role: "guest",
              participants: [{ initials: "GU", username: "guest_user" }],
            },
          ],
        });
      }
      if (url === "/api/sessions/end/") {
        return Promise.resolve({ success: true, ended: true });
      }
      return Promise.resolve({});
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-204")).not.toBeNull();
    });

    fireEvent.click(screen.getByTestId("end-room-btn-204"));
    await waitFor(() => expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull());

    fireEvent.click(screen.getByTestId("archive-end-confirm-proceed-btn"));

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith(
        "/api/sessions/end/",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ session_id: 204 }),
        })
      );
    });
  });

  // 5. Clicking the button does not navigate into the room
  it("5. Clicking End Room stops propagation and does NOT navigate into the room", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [
        {
          id: 205,
          code: "NAV001",
          name: "Navigation Protection Room",
          date: "Nov 04, 2026",
          matches: 0,
          ended: false,
          status: "active",
          is_host: true,
          user_role: "host",
          participants: [{ initials: "HO", username: "host_user" }],
        },
      ],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-205")).not.toBeNull();
    });

    // Clicking End Room should only trigger confirmation modal
    fireEvent.click(screen.getByTestId("end-room-btn-205"));

    await waitFor(() => {
      expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull();
    });
    // Remains on /sessions without navigating to /session/205
    expect(screen.queryByTestId("cinema-header")).not.toBeNull();
  });

  // 6. Successful termination refreshes the directory
  it("6. Successful termination refreshes the directory and updates room status", async () => {
    let callCount = 0;
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/recent/") {
        callCount++;
        if (callCount === 1) {
          return Promise.resolve({
            sessions: [
              {
                id: 206,
                code: "REF001",
                name: "Refresh Test Room",
                date: "Nov 04, 2026",
                matches: 1,
                ended: false,
                status: "active",
                is_host: false,
                user_role: "guest",
                participants: [{ initials: "GU", username: "guest_user" }],
              },
            ],
          });
        }
        // Second call (directory refresh after end)
        return Promise.resolve({
          sessions: [
            {
              id: 206,
              code: "REF001",
              name: "Refresh Test Room",
              date: "Nov 04, 2026",
              matches: 1,
              ended: true,
              status: "ended_by_host",
              is_host: false,
              user_role: "guest",
              participants: [{ initials: "GU", username: "guest_user" }],
            },
          ],
        });
      }
      if (url === "/api/sessions/end/") {
        return Promise.resolve({ success: true, message: "Session ended successfully", ended: true });
      }
      return Promise.resolve({});
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-206")).not.toBeNull();
    });

    fireEvent.click(screen.getByTestId("end-room-btn-206"));
    await waitFor(() => expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull());

    fireEvent.click(screen.getByTestId("archive-end-confirm-proceed-btn"));

    // Modal closes
    await waitFor(() => {
      expect(screen.queryByTestId("archive-end-confirm-modal")).toBeNull();
    });

    // Directory refresh occurred (recent endpoint called again)
    expect(callCount).toBeGreaterThanOrEqual(2);

    // Status updated to Ended by host, button removed
    await waitFor(() => {
      expect(screen.getByTestId("session-status-badge-206").textContent).toContain("Ended by host");
    });
    expect(screen.queryByTestId("end-room-btn-206")).toBeNull();
  });

  // 7. Failed termination displays an error
  it("7. Failed termination displays an error message", async () => {
    mockApiRequest.mockImplementation((url: string) => {
      if (url === "/api/sessions/recent/") {
        return Promise.resolve({
          sessions: [
            {
              id: 207,
              code: "ERR001",
              name: "Error Scenario Room",
              date: "Nov 04, 2026",
              matches: 0,
              ended: false,
              status: "active",
              is_host: true,
              user_role: "host",
              participants: [{ initials: "HO", username: "host_user" }],
            },
          ],
        });
      }
      if (url === "/api/sessions/end/") {
        return Promise.reject(new Error("Database lock contention during room termination"));
      }
      return Promise.resolve({});
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("end-room-btn-207")).not.toBeNull();
    });

    fireEvent.click(screen.getByTestId("end-room-btn-207"));
    await waitFor(() => expect(screen.queryByTestId("archive-end-confirm-modal")).not.toBeNull());

    fireEvent.click(screen.getByTestId("archive-end-confirm-proceed-btn"));

    // Error banner should be displayed
    await waitFor(() => {
      expect(screen.queryByTestId("directory-action-error")).not.toBeNull();
    });
    expect(screen.getByTestId("directory-action-error").textContent).toContain(
      "Database lock contention during room termination"
    );
  });

  // 8. Ended rooms no longer display the action
  it("8. Ended rooms no longer display the End Room action", async () => {
    mockApiRequest.mockResolvedValue({
      sessions: [
        {
          id: 208,
          code: "ENDED1",
          name: "Concluded Screening",
          date: "Nov 03, 2026",
          matches: 5,
          ended: true,
          status: "ended_by_host",
          is_host: true,
          user_role: "host",
          participants: [{ initials: "HO", username: "host_user" }],
        },
      ],
    });

    renderSessionsListPage();

    await waitFor(() => {
      expect(screen.queryByTestId("session-status-badge-208")).not.toBeNull();
    });
    expect(screen.queryByTestId("end-room-btn-208")).toBeNull();
  });
});
