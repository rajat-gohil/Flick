import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ApiError } from "../../lib/api";
import { ThemeProvider } from "../../context/ThemeContext";

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
}));

// Mock apiRequest while retaining real ApiError
const mockApiRequest = vi.fn();
vi.mock("../../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../lib/api")>();
  return {
    ...actual,
    apiRequest: (...args: any[]) => mockApiRequest(...args),
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

import HomePage from "../HomePage";
import LoginPage from "../LoginPage";
import ProfilePage from "../ProfilePage";
import UsernamePage from "../UsernamePage";

describe("Component-Level User-Visible API Error Handling", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.localStorage.setItem("auth_token", "test_token");
    window.localStorage.setItem("username", "testuser");
    window.localStorage.setItem("display_name", "Test User");
  });

  /* -----------------------------------------------------------------
     1. HomePage: Join Session Error Scenarios
     ----------------------------------------------------------------- */
  describe("HomePage error display", () => {
    it("displays backend-provided error message when session join is rejected with HTTP 400", async () => {
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint.includes("/api/sessions/recent/")) {
          return Promise.resolve({ sessions: [] });
        }
        if (endpoint.includes("/api/discover/")) {
          return Promise.resolve({ movies: [] });
        }
        if (endpoint.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        if (endpoint === "/api/sessions/join/") {
          return Promise.reject(new ApiError(400, { error: "Session is at maximum capacity" }));
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      const joinInput = screen.getByPlaceholderText("ENTER 6-DIGIT CODE");
      fireEvent.change(joinInput, { target: { value: "ABC123" } });

      const joinButton = screen.getByLabelText("Enter session");
      fireEvent.click(joinButton);

      await waitFor(() => {
        expect(screen.getByText("Session is at maximum capacity")).not.toBeNull();
      });
    });

    it("displays generic status fallback when backend returns ApiError without specific error text", async () => {
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint === "/api/sessions/join/") {
          return Promise.reject(new ApiError(500, null));
        }
        return Promise.resolve({ sessions: [], movies: [], watchlist: [] });
      });

      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      const joinInput = screen.getByPlaceholderText("ENTER 6-DIGIT CODE");
      fireEvent.change(joinInput, { target: { value: "ABC123" } });

      const joinButton = screen.getByLabelText("Enter session");
      fireEvent.click(joinButton);

      await waitFor(() => {
        expect(screen.getByText("Request failed with status 500")).not.toBeNull();
      });
    });

    it("navigates to session on successful join request", async () => {
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint === "/api/sessions/join/") {
          return Promise.resolve({
            success: true,
            session_id: 88,
            user_preferences_set: true,
          });
        }
        return Promise.resolve({ sessions: [], movies: [], watchlist: [] });
      });

      render(
        <MemoryRouter initialEntries={["/home"]}>
          <Routes>
            <Route path="/home" element={<HomePage />} />
            <Route path="/session/88" element={<div>Active Session 88 Deck</div>} />
          </Routes>
        </MemoryRouter>
      );

      const joinInput = screen.getByPlaceholderText("ENTER 6-DIGIT CODE");
      fireEvent.change(joinInput, { target: { value: "SUCC88" } });

      const joinButton = screen.getByLabelText("Enter session");
      fireEvent.click(joinButton);

      await waitFor(() => {
        expect(screen.getByText("Active Session 88 Deck")).not.toBeNull();
      }, { timeout: 4000 });
    });
  });

  /* -----------------------------------------------------------------
     2. LoginPage: Login Failure Scenarios
     ----------------------------------------------------------------- */
  describe("LoginPage error display", () => {
    it("surfaces server error message when login credentials fail with HTTP 401", async () => {
      mockApiRequest.mockRejectedValueOnce(
        new ApiError(401, { error: "Account suspended due to policy violation" })
      );

      render(
        <MemoryRouter initialEntries={["/login"]}>
          <LoginPage />
        </MemoryRouter>
      );

      const usernameInput = screen.getByPlaceholderText("Enter email or username");
      const passwordInput = screen.getByPlaceholderText("Enter your password");

      fireEvent.change(usernameInput, { target: { value: "alex@flick.com" } });
      fireEvent.change(passwordInput, { target: { value: "secret123" } });

      const submitButton = screen.getByRole("button", { name: "Sign In" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Account suspended due to policy violation")).not.toBeNull();
      });
    });

    it("uses safe generic message when a non-ApiError network failure occurs", async () => {
      mockApiRequest.mockRejectedValueOnce(new TypeError("Network down"));

      render(
        <MemoryRouter initialEntries={["/login"]}>
          <LoginPage />
        </MemoryRouter>
      );

      const usernameInput = screen.getByPlaceholderText("Enter email or username");
      const passwordInput = screen.getByPlaceholderText("Enter your password");

      fireEvent.change(usernameInput, { target: { value: "alex@flick.com" } });
      fireEvent.change(passwordInput, { target: { value: "secret123" } });

      const submitButton = screen.getByRole("button", { name: "Sign In" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Network down")).not.toBeNull();
      });
    });

    it("stores credentials and navigates to /home on successful login", async () => {
      mockApiRequest.mockResolvedValueOnce({
        success: true,
        token: "auth_token_xyz_999",
        username: "alex99",
        display_name: "Alex",
      });

      render(
        <MemoryRouter initialEntries={["/login"]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/home" element={<div>Welcome Home Alex</div>} />
          </Routes>
        </MemoryRouter>
      );

      const usernameInput = screen.getByPlaceholderText("Enter email or username");
      const passwordInput = screen.getByPlaceholderText("Enter your password");

      fireEvent.change(usernameInput, { target: { value: "alex99" } });
      fireEvent.change(passwordInput, { target: { value: "correctpassword" } });

      const submitButton = screen.getByRole("button", { name: "Sign In" });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(screen.getByText("Welcome Home Alex")).not.toBeNull();
      });

      expect(window.localStorage.getItem("auth_token")).toBe("auth_token_xyz_999");
      expect(window.localStorage.getItem("username")).toBe("alex99");
      expect(window.localStorage.getItem("display_name")).toBe("Alex");
    });
  });

  /* -----------------------------------------------------------------
     3. ProfilePage: Profile Update & Account Deletion Validation Errors
     ----------------------------------------------------------------- */
  describe("ProfilePage error display", () => {
    it("displays validation error when updating username fails with HTTP 400", async () => {
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint === "/api/users/profile/") {
          return Promise.resolve({
            success: true,
            user: {
              username: "currentuser",
              email: "test@flick.com",
              display_name: "Current User",
              avatar_url: null,
            },
          });
        }
        if (endpoint === "/api/users/update-username/") {
          return Promise.reject(new ApiError(400, { error: "This pen name is already reserved." }));
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/profile"]}>
          <ThemeProvider>
            <ProfilePage />
          </ThemeProvider>
        </MemoryRouter>
      );

      // Wait for profile to load
      await waitFor(() => {
        expect(screen.getByText(/@currentuser/)).not.toBeNull();
      });

      // Click "Edit Handle" button
      const editButton = screen.getByRole("button", { name: "Edit Handle" });
      fireEvent.click(editButton);

      const usernameInput = screen.getByPlaceholderText("New handle");
      fireEvent.change(usernameInput, { target: { value: "reservedname" } });

      const saveButton = screen.getByRole("button", { name: "Save" });
      fireEvent.click(saveButton);

      await waitFor(() => {
        expect(screen.getByText("This pen name is already reserved.")).not.toBeNull();
      });
    });

    it("displays validation error when account deletion fails due to wrong password", async () => {
      mockApiRequest.mockImplementation((endpoint: string) => {
        if (endpoint === "/api/users/profile/") {
          return Promise.resolve({
            success: true,
            user: {
              username: "currentuser",
              email: "test@flick.com",
              display_name: "Current User",
            },
          });
        }
        if (endpoint === "/api/users/delete-account/") {
          return Promise.reject(new ApiError(400, { error: "Incorrect password provided." }));
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/profile"]}>
          <ThemeProvider>
            <ProfilePage />
          </ThemeProvider>
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText("Delete Member Account")).not.toBeNull();
      });

      // Click "Delete Member Account" menu item
      const deleteMenuItem = screen.getByText("Delete Member Account");
      fireEvent.click(deleteMenuItem);

      // Enter password in deletion modal
      const passwordInput = screen.getByPlaceholderText("Enter current password");
      fireEvent.change(passwordInput, { target: { value: "wrongpassword" } });

      // Click confirm "Confirm Delete"
      const confirmDeleteBtn = screen.getByRole("button", { name: "Confirm Delete" });
      fireEvent.click(confirmDeleteBtn);

      await waitFor(() => {
        expect(screen.getByText("Incorrect password provided.")).not.toBeNull();
      });
    });
  });

  /* -----------------------------------------------------------------
     4. UsernamePage: Username Setup Rejection
     ----------------------------------------------------------------- */
  describe("UsernamePage error display", () => {
    it("displays server rejection message on invalid username submission", async () => {
      mockApiRequest.mockRejectedValueOnce(
        new ApiError(400, { error: "Username contains illegal characters." })
      );

      render(
        <MemoryRouter initialEntries={["/username"]}>
          <UsernamePage />
        </MemoryRouter>
      );

      const input = screen.getByPlaceholderText("e.g. moviebuff_42");
      fireEvent.change(input, { target: { value: "invalid_name" } });

      const submitBtn = screen.getByRole("button", { name: "Save & Continue" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText("Username contains illegal characters.")).not.toBeNull();
      });
    });

    it("navigates to /home on successful username claim", async () => {
      mockApiRequest.mockResolvedValueOnce({ success: true });

      render(
        <MemoryRouter initialEntries={["/username"]}>
          <Routes>
            <Route path="/username" element={<UsernamePage />} />
            <Route path="/home" element={<div>Welcome to Flick Home</div>} />
          </Routes>
        </MemoryRouter>
      );

      const input = screen.getByPlaceholderText("e.g. moviebuff_42");
      fireEvent.change(input, { target: { value: "valid_name" } });

      const submitBtn = screen.getByRole("button", { name: "Save & Continue" });
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getByText("Welcome to Flick Home")).not.toBeNull();
      });
    });
  });
});
