import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "../../context/ThemeContext";
import { ApiError } from "../../lib/api";
import { isLoggedIn, isGuest, getCurrentUser, logout } from "../../lib/auth";
import RequireAuth from "../../components/RequireAuth";

// Stub window.matchMedia
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

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

// Mock apiRequest and helper functions while retaining real ApiError and export types
const mockApiRequest = vi.fn();
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    apiRequest: (...args: any[]) => mockApiRequest(...args),
    provisionGuest: (displayName?: string) =>
      mockApiRequest("/api/auth/guest-provision/", {
        method: "POST",
        body: JSON.stringify(displayName ? { display_name: displayName } : {}),
      }),
    recoverGuest: (recoveryCode: string) =>
      mockApiRequest("/api/auth/guest-recover/", {
        method: "POST",
        body: JSON.stringify({ recovery_code: recoveryCode }),
      }),
    acknowledgeRecovery: () =>
      mockApiRequest("/api/auth/guest-recovery-ack/", {
        method: "POST",
      }),
    convertGuestAccount: (payload: any) =>
      mockApiRequest("/api/auth/guest-convert/", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  };
});

// Mock framer-motion
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

import EntryPage from "../EntryPage";
import GuestRecoveryPage from "../GuestRecoveryPage";
import GuestConvertPage from "../GuestConvertPage";
import RecoveryCodeModal from "../../components/RecoveryCodeModal";

describe("Persistent Guest Accounts — Frontend Lifecycle Integration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockApiRequest.mockReset();
    vi.clearAllMocks();
  });

  /* ===================================================================
     1. GUEST ONBOARDING & PROVISIONING
     =================================================================== */
  describe("Guest Onboarding & Provisioning Flow", () => {
    it("provisions a guest account when 'Start Exploring' is clicked and displays the recovery code", async () => {
      mockApiRequest.mockResolvedValueOnce({
        success: true,
        token: "guest_token_12345",
        recovery_code: "4F9K-2M8P-7Q1X-0R5T",
        user: {
          id: 42,
          username: "guest_ab12cd34ef56",
          display_name: "Cinephile #42",
          guest_uuid: "uuid-42",
          is_guest: true,
        },
      });

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/"]}>
            <Routes>
              <Route path="/" element={<EntryPage />} />
              <Route path="/home" element={<div>Home Dashboard</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      const exploreBtn = screen.getByRole("button", { name: /start exploring/i });
      fireEvent.click(exploreBtn);

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith(
          "/api/auth/guest-provision/",
          expect.objectContaining({ method: "POST" })
        );
      });

      // Verify auth state is saved
      expect(window.localStorage.getItem("auth_token")).toBe("guest_token_12345");
      expect(window.localStorage.getItem("username")).toBe("guest_ab12cd34ef56");
      expect(window.localStorage.getItem("is_guest")).toBe("true");
      expect(isLoggedIn()).toBe(true);
      expect(isGuest()).toBe(true);

      // Verify RecoveryCodeModal is presented
      await waitFor(() => {
        expect(screen.getByText(/your guest recovery code/i)).toBeDefined();
        expect(screen.getByTestId("recovery-code-display").textContent).toContain("4F9K");
        expect(screen.getByTestId("recovery-code-display").textContent).toContain("0R5T");
      });

      // Raw recovery code must NEVER be saved in localStorage
      expect(window.localStorage.getItem("recovery_code")).toBeNull();
      expect(JSON.stringify(window.localStorage)).not.toContain("4F9K-2M8P");
    });

    it("requires explicit acknowledgment before dismissing the recovery code modal", async () => {
      mockApiRequest.mockResolvedValueOnce({
        success: true,
        token: "guest_token_12345",
        recovery_code: "4F9K-2M8P-7Q1X-0R5T",
        user: { id: 42, username: "guest_42", is_guest: true },
      });

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/"]}>
            <Routes>
              <Route path="/" element={<EntryPage />} />
              <Route path="/home" element={<div>Home Dashboard</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.click(screen.getByRole("button", { name: /start exploring/i }));

      await waitFor(() => {
        expect(screen.getByText(/your guest recovery code/i)).toBeDefined();
      });

      const continueBtn = screen.getByRole("button", { name: /i've saved my code/i });
      // Button must be disabled until user checks acknowledgment
      expect(continueBtn.hasAttribute("disabled")).toBe(true);

      // Check acknowledgment
      const checkbox = screen.getByRole("checkbox");
      fireEvent.click(checkbox);
      expect(continueBtn.hasAttribute("disabled")).toBe(false);

      fireEvent.click(continueBtn);

      // Navigates to home
      await waitFor(() => {
        expect(screen.getByText("Home Dashboard")).toBeDefined();
      });
    });

    it("handles clipboard copying with manual selection fallback", async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, {
        clipboard: { writeText: writeTextMock },
      });

      const onConfirm = vi.fn();
      render(
        <RecoveryCodeModal
          isOpen={true}
          recoveryCode="4F9K-2M8P-7Q1X-0R5T"
          onConfirm={onConfirm}
        />
      );

      const copyBtn = screen.getByRole("button", { name: /copy recovery code/i });
      fireEvent.click(copyBtn);

      await waitFor(() => {
        expect(writeTextMock).toHaveBeenCalledWith("4F9K-2M8P-7Q1X-0R5T");
        expect(screen.getByText(/copied to clipboard/i)).toBeDefined();
      });
    });

    it("displays error banner when guest provisioning fails", async () => {
      mockApiRequest.mockRejectedValueOnce(
        new ApiError(500, { error: "Database temporarily unavailable" })
      );

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/"]}>
            <Routes>
              <Route path="/" element={<EntryPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.click(screen.getByRole("button", { name: /start exploring/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert").textContent).toContain("Database temporarily unavailable");
      });

      expect(window.localStorage.getItem("auth_token")).toBeNull();
      expect(isLoggedIn()).toBe(false);
    });
  });

  /* ===================================================================
     2. GUEST ACCOUNT RESTORATION
     =================================================================== */
  describe("Guest Restoration & Recovery Handoff Flow", () => {
    it("submits recovery code, establishes authenticated session, and presents replacement code", async () => {
      mockApiRequest.mockResolvedValueOnce({
        success: true,
        token: "new_rotated_token_777",
        recovery_code: "9X2L-4M7Q-1V8K-3N0P",
        user: {
          id: 42,
          username: "guest_ab12cd34ef56",
          display_name: "Cinephile #42",
          guest_uuid: "uuid-42",
          is_guest: true,
        },
        handoff_pending: true,
      });

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/recover"]}>
            <Routes>
              <Route path="/recover" element={<GuestRecoveryPage />} />
              <Route path="/home" element={<div>Restored Home Dashboard</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      const input = screen.getByPlaceholderText(/4f9k/i);
      fireEvent.change(input, { target: { value: "4F9K-2M8P-7Q1X-0R5T" } });

      const restoreBtn = screen.getByRole("button", { name: /restore journal/i });
      fireEvent.click(restoreBtn);

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith(
          "/api/auth/guest-recover/",
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify({ recovery_code: "4F9K-2M8P-7Q1X-0R5T" }),
          })
        );
      });

      // Token was rotated and stored
      expect(window.localStorage.getItem("auth_token")).toBe("new_rotated_token_777");
      expect(isGuest()).toBe(true);

      // Replacement recovery code modal is displayed
      await waitFor(() => {
        expect(screen.getByText(/replacement recovery code/i)).toBeDefined();
        expect(screen.getByTestId("recovery-code-display").textContent).toContain("9X2L");
      });

      // Acknowledgment must NOT be called before user confirmation
      expect(mockApiRequest).not.toHaveBeenCalledWith(
        "/api/auth/guest-recovery-ack/",
        expect.anything()
      );
    });

    it("sends recovery acknowledgment only after explicit user confirmation", async () => {
      mockApiRequest
        .mockResolvedValueOnce({
          success: true,
          token: "rotated_token_888",
          recovery_code: "8R2W-9N4V-1M3P-6K0Q",
          user: { id: 42, username: "guest_42", is_guest: true },
          handoff_pending: true,
        })
        .mockResolvedValueOnce({
          success: true,
          message: "Recovery acknowledged successfully. Previous credentials retired.",
          handoff_pending: false,
        });

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/recover"]}>
            <Routes>
              <Route path="/recover" element={<GuestRecoveryPage />} />
              <Route path="/home" element={<div>Restored Home Dashboard</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.change(screen.getByPlaceholderText(/4f9k/i), {
        target: { value: "OLD-CODE-HERE-1234" },
      });
      fireEvent.click(screen.getByRole("button", { name: /restore journal/i }));

      await waitFor(() => {
        expect(screen.getByText(/replacement recovery code/i)).toBeDefined();
      });

      // Confirm checkbox
      fireEvent.click(screen.getByRole("checkbox"));

      // Click acknowledge
      const confirmBtn = screen.getByRole("button", { name: /i've saved my replacement code/i });
      fireEvent.click(confirmBtn);

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith(
          "/api/auth/guest-recovery-ack/",
          expect.objectContaining({ method: "POST" })
        );
      });

      // Navigates to home after acknowledgment
      await waitFor(() => {
        expect(screen.getByText("Restored Home Dashboard")).toBeDefined();
      });
    });

    it("handles rate limiting (429) cleanly with helpful message", async () => {
      mockApiRequest.mockRejectedValueOnce(
        new ApiError(429, { error: "Request was throttled. Expected available in 60 seconds." })
      );

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/recover"]}>
            <Routes>
              <Route path="/recover" element={<GuestRecoveryPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.change(screen.getByPlaceholderText(/4f9k/i), {
        target: { value: "INVALID-CODE-429" },
      });
      fireEvent.click(screen.getByRole("button", { name: /restore journal/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert").textContent).toMatch(
          /too many recovery attempts\. please wait a moment/i
        );
      });
    });

    it("handles network failure without corrupting local authentication state", async () => {
      window.localStorage.setItem("auth_token", "existing_valid_token");
      window.localStorage.setItem("username", "current_guest");
      window.localStorage.setItem("is_guest", "true");

      mockApiRequest.mockRejectedValueOnce(new TypeError("Failed to fetch"));

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/recover"]}>
            <Routes>
              <Route path="/recover" element={<GuestRecoveryPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.change(screen.getByPlaceholderText(/4f9k/i), {
        target: { value: "NET-FAIL-CODE-000" },
      });
      fireEvent.click(screen.getByRole("button", { name: /restore journal/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert").textContent).toMatch(
          /failed to fetch/i
        );
      });

      // Existing auth state was NOT erased
      expect(window.localStorage.getItem("auth_token")).toBe("existing_valid_token");
      expect(isLoggedIn()).toBe(true);
    });
  });

  /* ===================================================================
     3. PERMANENT ACCOUNT CONVERSION
     =================================================================== */
  describe("Permanent Account Conversion Flow", () => {
    it("converts guest account in-place and updates authentication state to permanent", async () => {
      // Start as an authenticated guest
      window.localStorage.setItem("auth_token", "active_guest_token_100");
      window.localStorage.setItem("username", "guest_original");
      window.localStorage.setItem("display_name", "Original Curator");
      window.localStorage.setItem("is_guest", "true");

      mockApiRequest.mockResolvedValueOnce({
        success: true,
        message: "Account successfully converted to permanent registered account.",
        token: "active_guest_token_100", // Token retained in place
        user: {
          id: 42,
          username: "member@cinema.com",
          email: "member@cinema.com",
          display_name: "Original Curator",
          guest_uuid: "uuid-42",
          is_guest: false,
        },
      });

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/convert"]}>
            <Routes>
              <Route path="/convert" element={<GuestConvertPage />} />
              <Route path="/profile" element={<div>Member Profile Page</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      // Fill in credentials
      fireEvent.change(screen.getByPlaceholderText("name@example.com"), {
        target: { value: "member@cinema.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
        target: { value: "MasterPassword123!" },
      });
      fireEvent.change(screen.getByPlaceholderText("Re-type your password"), {
        target: { value: "MasterPassword123!" },
      });

      const submitBtn = screen.getByRole("button", { name: /complete registration/i });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockApiRequest).toHaveBeenCalledWith(
          "/api/auth/guest-convert/",
          expect.objectContaining({
            method: "POST",
            body: JSON.stringify({
              email: "member@cinema.com",
              password: "MasterPassword123!",
              display_name: "Original Curator",
            }),
          })
        );
      });

      // Updated to permanent account in localStorage
      expect(window.localStorage.getItem("is_guest")).toBe("false");
      expect(window.localStorage.getItem("email")).toBe("member@cinema.com");
      expect(window.localStorage.getItem("auth_token")).toBe("active_guest_token_100");
      expect(isGuest()).toBe(false);

      // Shows success confirmation
      expect(screen.getByText(/membership activated/i)).toBeDefined();
    });

    it("validates mismatched passwords before submission", async () => {
      window.localStorage.setItem("auth_token", "active_guest_token");
      window.localStorage.setItem("is_guest", "true");

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/convert"]}>
            <Routes>
              <Route path="/convert" element={<GuestConvertPage />} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      fireEvent.change(screen.getByPlaceholderText("name@example.com"), {
        target: { value: "test@example.com" },
      });
      fireEvent.change(screen.getByPlaceholderText("Minimum 6 characters"), {
        target: { value: "Secret123" },
      });
      fireEvent.change(screen.getByPlaceholderText("Re-type your password"), {
        target: { value: "Mismatch456" },
      });

      fireEvent.click(screen.getByRole("button", { name: /complete registration/i }));

      await waitFor(() => {
        expect(screen.getByRole("alert").textContent).toMatch(/passwords do not match/i);
      });

      expect(mockApiRequest).not.toHaveBeenCalled();
    });

    it("redirects non-guest users away from /convert", async () => {
      // User is already a registered member (is_guest === "false")
      window.localStorage.setItem("auth_token", "member_token");
      window.localStorage.setItem("is_guest", "false");

      render(
        <ThemeProvider>
          <MemoryRouter initialEntries={["/convert"]}>
            <Routes>
              <Route path="/convert" element={<GuestConvertPage />} />
              <Route path="/profile" element={<div>Member Profile Page</div>} />
            </Routes>
          </MemoryRouter>
        </ThemeProvider>
      );

      await waitFor(() => {
        expect(screen.getByText("Member Profile Page")).toBeDefined();
      });
    });
  });

  /* ===================================================================
     4. AUTHENTICATION & ROUTE GUARD COMPATIBILITY
     =================================================================== */
  describe("Authentication Compatibility & Route Guards", () => {
    it("allows both guest and registered accounts through RequireAuth", () => {
      // Guest
      window.localStorage.setItem("auth_token", "guest_tok");
      window.localStorage.setItem("is_guest", "true");

      const { unmount } = render(
        <MemoryRouter>
          <RequireAuth>
            <div>Protected Content for Guest</div>
          </RequireAuth>
        </MemoryRouter>
      );
      expect(screen.getByText("Protected Content for Guest")).toBeDefined();
      unmount();

      // Registered
      window.localStorage.setItem("auth_token", "reg_tok");
      window.localStorage.setItem("is_guest", "false");

      render(
        <MemoryRouter>
          <RequireAuth>
            <div>Protected Content for Registered</div>
          </RequireAuth>
        </MemoryRouter>
      );
      expect(screen.getByText("Protected Content for Registered")).toBeDefined();
    });

    it("blocks unauthenticated visitors in RequireAuth and redirects to landing", () => {
      window.localStorage.clear();

      render(
        <MemoryRouter initialEntries={["/protected"]}>
          <Routes>
            <Route
              path="/protected"
              element={
                <RequireAuth>
                  <div>Secret Area</div>
                </RequireAuth>
              }
            />
            <Route path="/" element={<div>Landing Splash</div>} />
          </Routes>
        </MemoryRouter>
      );

      expect(screen.queryByText("Secret Area")).toBeNull();
      expect(screen.getByText("Landing Splash")).toBeDefined();
    });

    it("logout clears all authentication and guest credentials completely", () => {
      window.localStorage.setItem("auth_token", "tok123");
      window.localStorage.setItem("user_id", "42");
      window.localStorage.setItem("username", "guest_42");
      window.localStorage.setItem("display_name", "Curator");
      window.localStorage.setItem("email", "g@flick.test");
      window.localStorage.setItem("is_guest", "true");
      window.localStorage.setItem("guest_uuid", "uuid-42");

      expect(isLoggedIn()).toBe(true);
      expect(isGuest()).toBe(true);

      logout();

      expect(window.localStorage.getItem("auth_token")).toBeNull();
      expect(window.localStorage.getItem("user_id")).toBeNull();
      expect(window.localStorage.getItem("is_guest")).toBeNull();
      expect(isLoggedIn()).toBe(false);
      expect(isGuest()).toBe(false);
      expect(getCurrentUser()).toBeNull();
    });
  });
});
