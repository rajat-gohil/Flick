import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import fs from "node:fs";
import path from "node:path";
import CinemaHeader from "../components/CinemaHeader";
import { ThemeProvider, useTheme } from "../context/ThemeContext";
import { useAccessibleDialog, useSheetSwipeDismiss } from "../lib/useAccessibleDialog";
import AccountSettingsPage from "../pages/AccountSettingsPage";
import { useRef, useState } from "react";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockApiRequest = vi.fn();
vi.mock("../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
}));

vi.mock("../lib/auth", () => ({
  isGuest: () => true,
  isLoggedIn: () => true,
  getToken: () => "test-token",
}));

describe("Accessibility Remediation Regression Suite", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders CinemaHeader brand home control as a semantic button reachable and activatable by keyboard", () => {
    render(
      <MemoryRouter>
        <ThemeProvider>
          <CinemaHeader current="discover" />
        </ThemeProvider>
      </MemoryRouter>
    );

    const homeButton = screen.getByRole("button", { name: /flick home/i });
    expect(homeButton.tagName).toBe("BUTTON");
    homeButton.focus();
    expect(document.activeElement).toBe(homeButton);
    fireEvent.click(homeButton);
    expect(mockNavigate).toHaveBeenCalledWith("/home");
  });

  it("manages modal focus entry, Tab containment, Escape dismissal, and focus restoration", async () => {
    function Harness() {
      const [open, setOpen] = useState(false);
      const ref = useRef<HTMLDivElement>(null);
      useAccessibleDialog(open, () => setOpen(false), ref);
      return (
        <div>
          <button type="button" onClick={() => setOpen(true)}>
            Open Dialog
          </button>
          {open && (
            <div ref={ref} role="dialog" aria-modal="true" tabIndex={-1}>
              <button type="button">First</button>
              <button type="button" onClick={() => setOpen(false)}>
                Last
              </button>
            </div>
          )}
        </div>
      );
    }

    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Open Dialog" });
    trigger.focus();
    fireEvent.click(trigger);

    const first = screen.getByRole("button", { name: "First" });
    const last = screen.getByRole("button", { name: "Last" });

    await waitFor(() => {
      expect(document.activeElement).toBe(first);
    });

    // Shift+Tab from first wraps to last
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);

    // Tab from last wraps to first
    fireEvent.keyDown(document, { key: "Tab", shiftKey: false });
    expect(document.activeElement).toBe(first);

    // Escape closes and restores focus to trigger
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("follows system prefers-color-scheme changes when no explicit preference exists", () => {
    let listener: ((e: MediaQueryListEvent) => void) | null = null;
    const matchMediaMock = vi.fn().mockImplementation((query: string) => ({
      matches: query === "(prefers-color-scheme: light)",
      media: query,
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
        listener = cb;
      },
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal("matchMedia", matchMediaMock);

    function ThemeReader() {
      const { theme } = useTheme();
      return <span data-testid="theme-value">{theme}</span>;
    }

    render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme-value").textContent).toBe("light");

    act(() => {
      listener?.({ matches: false } as MediaQueryListEvent);
    });
    expect(screen.getByTestId("theme-value").textContent).toBe("dark");
  });

  it("preserves explicit saved theme preference even when OS appearance changes", () => {
    localStorage.setItem("flick_theme", "dark");
    let listener: ((e: MediaQueryListEvent) => void) | null = null;
    const matchMediaMock = vi.fn().mockImplementation((query: string) => ({
      matches: true, // OS prefers light
      media: query,
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
        listener = cb;
      },
      removeEventListener: vi.fn(),
    }));
    vi.stubGlobal("matchMedia", matchMediaMock);

    function ThemeReader() {
      const { theme } = useTheme();
      return <span data-testid="theme-value">{theme}</span>;
    }

    render(
      <ThemeProvider>
        <ThemeReader />
      </ThemeProvider>
    );

    expect(screen.getByTestId("theme-value").textContent).toBe("dark");
    act(() => {
      listener?.({ matches: true } as MediaQueryListEvent);
    });
    expect(screen.getByTestId("theme-value").textContent).toBe("dark");
  });

  it("defines prefers-reduced-transparency and prefers-contrast fallbacks in index.css", () => {
    const cssPath = path.resolve(__dirname, "../index.css");
    const css = fs.readFileSync(cssPath, "utf8");
    expect(css).toContain("@media (prefers-reduced-transparency: reduce)");
    expect(css).toContain("backdrop-filter: none !important");
    expect(css).toContain("@media (prefers-contrast: more)");
  });

  it("uses an in-app confirmation dialog for recovery code rotation instead of window.confirm", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    mockApiRequest.mockImplementation(async (url: string) => {
      if (url === "/api/users/profile/") {
        return {
          success: true,
          user: { username: "guest_1", email: "", is_guest: true, recovery_code: "OLD-CODE-1234" },
        };
      }
      if (url === "/api/auth/guest-rotate-code/") {
        return { success: true, recovery_code: "NEW-CODE-5678" };
      }
      return { success: true };
    });

    render(
      <MemoryRouter>
        <ThemeProvider>
          <AccountSettingsPage />
        </ThemeProvider>
      </MemoryRouter>
    );

    const rotateTrigger = await screen.findByRole("button", { name: /generate new code/i });
    fireEvent.click(rotateTrigger);

    // Confirmation dialog opens without calling window.confirm
    expect(confirmSpy).not.toHaveBeenCalled();
    const dialog = screen.getByRole("dialog", { name: /generate new recovery code/i });
    expect(dialog).toBeTruthy();

    // Cancel closes without calling rotation API
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mockApiRequest).not.toHaveBeenCalledWith("/api/auth/guest-rotate-code/", expect.anything());

    // Confirm triggers rotation API
    fireEvent.click(rotateTrigger);
    const confirmBtn = screen.getAllByRole("button", { name: /generate new code/i }).find(
      (el) => el.closest('[role="dialog"]') !== null
    )!;
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith("/api/auth/guest-rotate-code/", { method: "POST" });
    });
  });

  it("supports swipe-to-dismiss on dedicated drag handles without breaking internal scrolling", () => {
    const onDismiss = vi.fn();
    function SwipeHarness({ disabled = false }: { disabled?: boolean }) {
      const swipe = useSheetSwipeDismiss(onDismiss, disabled);
      return (
        <div>
          <div data-testid="sheet-handle" {...swipe.handleProps} />
          <div data-testid="sheet-scroll-body" className="overflow-y-auto overscroll-contain">
            Content
          </div>
        </div>
      );
    }

    const { rerender } = render(<SwipeHarness />);
    const handle = screen.getByTestId("sheet-handle");

    // Small drag does not dismiss
    fireEvent.pointerDown(handle, { clientY: 100 });
    fireEvent.pointerMove(handle, { clientY: 130 });
    fireEvent.pointerUp(handle, { clientY: 130 });
    expect(onDismiss).not.toHaveBeenCalled();

    // Downward drag > 80px dismisses
    fireEvent.pointerDown(handle, { clientY: 100 });
    fireEvent.pointerMove(handle, { clientY: 210 });
    fireEvent.pointerUp(handle, { clientY: 210 });
    expect(onDismiss).toHaveBeenCalledTimes(1);

    // Reduced-motion disabled state does not dismiss via swipe
    onDismiss.mockClear();
    rerender(<SwipeHarness disabled={true} />);
    fireEvent.pointerDown(handle, { clientY: 100 });
    fireEvent.pointerMove(handle, { clientY: 240 });
    fireEvent.pointerUp(handle, { clientY: 240 });
    expect(onDismiss).not.toHaveBeenCalled();

    // Verify DiscoverPage & SessionPage wire dedicated handleProps separately from overflow-y-auto
    const discoverSrc = fs.readFileSync(path.resolve(__dirname, "../pages/DiscoverPage.tsx"), "utf8");
    const sessionSrc = fs.readFileSync(path.resolve(__dirname, "../pages/SessionPage.tsx"), "utf8");
    expect(discoverSrc).toContain("{...filterSwipe.handleProps}");
    expect(discoverSrc).toContain("overflow-y-auto overscroll-contain");
    expect(sessionSrc).toContain("{...infoSwipe.handleProps}");
    expect(sessionSrc).toContain("{...streamingSwipe.handleProps}");
  });
});
