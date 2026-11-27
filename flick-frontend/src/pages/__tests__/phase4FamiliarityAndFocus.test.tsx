import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://127.0.0.1:8000/ws/session/101/",
  getBaseUrl: () => "http://127.0.0.1:8000",
}));

const MOTION_PROPS = new Set([
  "layoutId", "layout", "whileTap", "whileHover", "whileFocus", "whileDrag",
  "initial", "animate", "exit", "transition", "variants",
]);

function stripMotionProps(props: Record<string, unknown>) {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (!MOTION_PROPS.has(k)) clean[k] = v;
  }
  return clean;
}

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, animate: anim, ...props }: Record<string, unknown>) => (
      <div
        data-motion-animate={anim ? JSON.stringify(anim) : undefined}
        {...stripMotionProps(props)}
      >
        {children as React.ReactNode}
      </div>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button {...stripMotionProps(props)}>{children as React.ReactNode}</button>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...stripMotionProps(props)}>{children as React.ReactNode}</span>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useMotionValue: (v: number) => ({ get: () => v, set: () => {} }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: () => ({ stop: () => {} }),
}));

import { getSessionPacing, useSessionFamiliarity } from "../../lib/motion";
import { CurtainCallMatchModal } from "../../components/session/CurtainCallMatchModal";
import DiscoverPage from "../DiscoverPage";

function FamiliarityHarness({ kind }: { kind: "swipe" | "match" | "action" }) {
  const { count, pacing, recordInteraction, resetFamiliarity } = useSessionFamiliarity(kind);
  return (
    <div>
      <span data-testid="fam-count">{count}</span>
      <span data-testid="fam-tier">{pacing.tier}</span>
      <span data-testid="fam-decorative">{String(pacing.allowDecorative)}</span>
      <button onClick={recordInteraction}>Record</button>
      <button onClick={resetFamiliarity}>Reset</button>
    </div>
  );
}

describe("Phase 4: Session-Level Familiarity Pacing & Staged Focus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    mockApiRequest.mockResolvedValue({ providers: [] });
  });

  describe("getSessionPacing & useSessionFamiliarity", () => {
    it("distinguishes first occurrence (theatrical), repeated actions (concise), and rapid swipes (quiet)", () => {
      expect(getSessionPacing(1, { kind: "match" })).toEqual({
        tier: "theatrical",
        allowDecorative: true,
        durationMultiplier: 1,
      });
      expect(getSessionPacing(2, { kind: "match" })).toEqual({
        tier: "concise",
        allowDecorative: false,
        durationMultiplier: 0.8,
      });
      expect(getSessionPacing(5, { kind: "swipe" })).toEqual({
        tier: "quiet",
        allowDecorative: false,
        durationMultiplier: 0.7,
      });
      expect(getSessionPacing(1, { isFirstOccurrence: false })).toEqual({
        tier: "concise",
        allowDecorative: false,
        durationMultiplier: 0.8,
      });
    });

    it("tracks ephemeral session familiarity in memory without touching localStorage", () => {
      const setItemSpy = vi.spyOn(Storage.prototype, "setItem");
      render(<FamiliarityHarness kind="swipe" />);

      expect(screen.getByTestId("fam-tier").textContent).toBe("theatrical");
      for (let i = 0; i < 5; i++) {
        act(() => {
          fireEvent.click(screen.getByText("Record"));
        });
      }
      expect(screen.getByTestId("fam-count").textContent).toBe("5");
      expect(screen.getByTestId("fam-tier").textContent).toBe("quiet");
      expect(screen.getByTestId("fam-decorative").textContent).toBe("false");
      expect(setItemSpy).not.toHaveBeenCalled();

      act(() => {
        fireEvent.click(screen.getByText("Reset"));
      });
      expect(screen.getByTestId("fam-tier").textContent).toBe("theatrical");
      setItemSpy.mockRestore();
    });
  });

  describe("CurtainCallMatchModal repeat-match pacing", () => {
    const baseProps = {
      matchedMovie: {
        id: 77,
        title: "Aftersun",
        poster_url: "https://example.com/aftersun.jpg",
        rating: 8.2,
        release_year: 2022,
        superlike_attribution: "none" as const,
        match_type: "ordinary" as const,
      },
      renderMode: "full" as const,
      shouldReduceMotion: false,
      isWatchlisted: false,
      watchlistLoading: false,
      onToggleWatchlist: vi.fn(),
      savedBurstId: null,
      onDismiss: vi.fn(),
      onEndSession: vi.fn().mockResolvedValue(undefined),
      endSessionLoading: false,
      sessionLocked: false,
      sessionEnded: false,
      onFetchMetadata: vi.fn(),
    };

    it("shows projector light sweep on first match and suppresses repeat flourish on 2nd+ match while keeping confirmation", () => {
      const { rerender } = render(<CurtainCallMatchModal {...baseProps} isRepeatMatch={false} />);
      expect(screen.getByTestId("projector-light-sweep")).toBeTruthy();
      expect(screen.getByTestId("match-poster-reveal")).toBeTruthy();

      rerender(<CurtainCallMatchModal {...baseProps} isRepeatMatch={true} />);
      expect(screen.queryByTestId("projector-light-sweep")).toBeNull();
      expect(screen.getByTestId("match-poster-reveal")).toBeTruthy();
      expect(screen.getByRole("button", { name: /^save$/i })).toBeTruthy();
    });
  });

  describe("DiscoverPage staged focus", () => {
    it("dims underlying discover stage when MovieDetailSheet opens and restores on close", async () => {
      mockApiRequest.mockImplementation((path: string) => {
        if (path.includes("/watchlist/")) return Promise.resolve({ results: [] });
        if (path.includes("/genres/")) return Promise.resolve({ genres: [] });
        if (path.includes("/discover/") || path.includes("/catalogue/")) {
          return Promise.resolve({
            results: [
              {
                id: 101,
                tmdb_id: 101,
                title: "Drive My Car",
                poster_url: "https://example.com/dmc.jpg",
                release_year: 2021,
                rating: 8.0,
              },
            ],
            total: 1,
          });
        }
        return Promise.resolve({ providers: [] });
      });

      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText("Drive My Car")).toBeTruthy();
      });

      const stage = screen.getByTestId("discover-stage");
      expect(stage.getAttribute("data-staged-focus")).toBe("restored");

      fireEvent.click(screen.getByText("Drive My Car"));
      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeTruthy();
      });
      expect(stage.getAttribute("data-staged-focus")).toBe("dimmed");
      expect(document.querySelector('[data-staged-focus="active"]')).toBeTruthy();

      fireEvent.keyDown(window, { key: "Escape" });
      await waitFor(() => {
        expect(screen.queryByRole("dialog")).toBeNull();
      });
      expect(stage.getAttribute("data-staged-focus")).toBe("restored");
    });
  });
});
