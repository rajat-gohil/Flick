import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Mock analytics & api
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

vi.mock("../../lib/salonPassCanvas", () => ({
  renderSalonPassToCanvas: vi.fn().mockResolvedValue(undefined),
  getCanvasBlob: vi.fn().mockResolvedValue(new Blob(["pass"], { type: "image/png" })),
  triggerFileDownload: vi.fn(),
  shareOrDownloadSalonPass: vi.fn().mockResolvedValue({ success: true, method: "download" }),
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

const mockAnimate = vi.fn((mv: { set?: (v: number) => void }, target: number) => {
  mv?.set?.(target);
  return { stop: vi.fn() };
});

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, initial, animate: anim, style, ...props }: Record<string, unknown>) => (
      <div
        data-motion-initial={initial ? JSON.stringify(initial) : undefined}
        data-motion-animate={anim ? JSON.stringify(anim) : undefined}
        style={style as React.CSSProperties}
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
  useMotionValue: (initial: number) => {
    let current = initial;
    return {
      get: () => current,
      set: (v: number) => {
        current = v;
      },
    };
  },
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: (mv: { set?: (v: number) => void }, target: number) => mockAnimate(mv, target),
}));

import { computeBoundedOverscroll, OVERSCROLL_CONFIG } from "../../lib/motion";
import { BoundedOverscroll } from "../../components/motion/BoundedOverscroll";
import { CurtainCallMatchModal } from "../../components/session/CurtainCallMatchModal";
import SalonPassShareModal from "../../components/session/SalonPassShareModal";
import CreateSessionPage from "../CreateSessionPage";

function mockMatchMedia(reducedMotion: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("prefers-reduced-motion") ? reducedMotion : false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("Phase 3: Selective Mask Reveals & Bounded Overscroll", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia(false);
    mockApiRequest.mockResolvedValue({ providers: [] });
    localStorage.setItem("access_token", "test-token");
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-pass");
    } else {
      vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock-pass");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
  });

  afterEach(() => {
    vi.useRealTimers();
    localStorage.clear();
  });

  describe("computeBoundedOverscroll math", () => {
    it("returns 0 for zero or non-finite input", () => {
      expect(computeBoundedOverscroll(0)).toBe(0);
      expect(computeBoundedOverscroll(Number.NaN)).toBe(0);
      expect(computeBoundedOverscroll(Number.POSITIVE_INFINITY)).toBe(0);
    });

    it("bounds extreme deltas strictly within maxOffset while preserving sign", () => {
      const pos = computeBoundedOverscroll(5000, 28, 0.34);
      const neg = computeBoundedOverscroll(-5000, 28, 0.34);
      expect(pos).toBeGreaterThan(20);
      expect(pos).toBeLessThanOrEqual(28);
      expect(neg).toBeLessThan(-20);
      expect(neg).toBeGreaterThanOrEqual(-28);
    });

    it("applies gentler displacement for small deltas", () => {
      const small = computeBoundedOverscroll(10, OVERSCROLL_CONFIG.maxOffsetPx, OVERSCROLL_CONFIG.resistance);
      expect(small).toBeGreaterThan(0);
      expect(small).toBeLessThan(10);
    });
  });

  describe("BoundedOverscroll component", () => {
    it("applies horizontal edge rubber-band on touch drag at start edge and snaps back on release", () => {
      render(
        <BoundedOverscroll axis="x" data-testid="shelf-overscroll" maxOffset={24}>
          <div>Item 1</div>
          <div>Item 2</div>
        </BoundedOverscroll>
      );

      const container = screen.getByTestId("shelf-overscroll");
      Object.defineProperty(container, "scrollLeft", { value: 0, configurable: true });
      Object.defineProperty(container, "clientWidth", { value: 300, configurable: true });
      Object.defineProperty(container, "scrollWidth", { value: 600, configurable: true });

      fireEvent.touchStart(container, { touches: [{ clientX: 100, clientY: 0 }] });
      fireEvent.touchMove(container, { touches: [{ clientX: 200, clientY: 0 }] });

      // Inner elastic wrapper receives motionValue x > 0
      const inner = container.firstElementChild as HTMLElement;
      expect(inner).toBeTruthy();

      fireEvent.touchEnd(container);
      expect(mockAnimate).toHaveBeenCalled();
    });

    it("does not trigger overscroll when scrolled away from edges", () => {
      render(
        <BoundedOverscroll axis="x" data-testid="shelf-mid">
          <div>Item 1</div>
        </BoundedOverscroll>
      );

      const container = screen.getByTestId("shelf-mid");
      Object.defineProperty(container, "scrollLeft", { value: 120, configurable: true });
      Object.defineProperty(container, "clientWidth", { value: 300, configurable: true });
      Object.defineProperty(container, "scrollWidth", { value: 600, configurable: true });

      fireEvent.touchStart(container, { touches: [{ clientX: 100, clientY: 0 }] });
      fireEvent.touchMove(container, { touches: [{ clientX: 160, clientY: 0 }] });
      fireEvent.touchEnd(container);

      // Offset was never displaced, so snapBack does not call animate
      expect(mockAnimate).not.toHaveBeenCalled();
    });

    it("snaps back after wheel overscroll settle timeout", () => {
      vi.useFakeTimers();
      render(
        <BoundedOverscroll axis="y" data-testid="list-overscroll">
          <div>Row 1</div>
        </BoundedOverscroll>
      );

      const container = screen.getByTestId("list-overscroll");
      Object.defineProperty(container, "scrollTop", { value: 0, configurable: true });
      Object.defineProperty(container, "clientHeight", { value: 400, configurable: true });
      Object.defineProperty(container, "scrollHeight", { value: 900, configurable: true });

      fireEvent.wheel(container, { deltaY: -40 });
      expect(mockAnimate).not.toHaveBeenCalled();

      act(() => {
        vi.advanceTimersByTime(OVERSCROLL_CONFIG.wheelSettleMs + 20);
      });

      expect(mockAnimate).toHaveBeenCalled();
    });

    it("disables elastic displacement when prefers-reduced-motion is enabled", () => {
      mockMatchMedia(true);
      render(
        <BoundedOverscroll axis="x" data-testid="shelf-reduced">
          <div>Item 1</div>
        </BoundedOverscroll>
      );

      const container = screen.getByTestId("shelf-reduced");
      Object.defineProperty(container, "scrollLeft", { value: 0, configurable: true });
      Object.defineProperty(container, "clientWidth", { value: 300, configurable: true });
      Object.defineProperty(container, "scrollWidth", { value: 600, configurable: true });

      fireEvent.touchStart(container, { touches: [{ clientX: 100, clientY: 0 }] });
      fireEvent.touchMove(container, { touches: [{ clientX: 220, clientY: 0 }] });
      fireEvent.touchEnd(container);

      expect(mockAnimate).not.toHaveBeenCalled();
    });

    it("ignores perpendicular vertical touch drags on a horizontal shelf", () => {
      render(
        <BoundedOverscroll axis="x" data-testid="shelf-perpendicular">
          <div>Item 1</div>
        </BoundedOverscroll>
      );

      const container = screen.getByTestId("shelf-perpendicular");
      Object.defineProperty(container, "scrollLeft", { value: 0, configurable: true });
      Object.defineProperty(container, "clientWidth", { value: 300, configurable: true });
      Object.defineProperty(container, "scrollWidth", { value: 600, configurable: true });

      // Primarily vertical page scroll (dy=40, dx=8)
      fireEvent.touchStart(container, { touches: [{ clientX: 100, clientY: 100 }] });
      fireEvent.touchMove(container, { touches: [{ clientX: 108, clientY: 140 }] });
      fireEvent.touchEnd(container);

      expect(mockAnimate).not.toHaveBeenCalled();
    });
  });

  describe("Selective Mask Reveals", () => {
    it("applies curtain clip-path reveal on CurtainCallMatchModal poster and falls back to opacity-only in reduced motion", () => {
      const baseProps = {
        matchedMovie: {
          id: 42,
          title: "In the Mood for Love",
          poster_url: "https://example.com/poster.jpg",
          rating: 8.5,
          release_year: 2000,
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

      const { rerender } = render(<CurtainCallMatchModal {...baseProps} />);
      const posterReveal = screen.getByTestId("match-poster-reveal");
      expect(posterReveal.getAttribute("data-motion-initial")).toContain("clipPath");

      rerender(<CurtainCallMatchModal {...baseProps} shouldReduceMotion={true} />);
      const reducedPosterReveal = screen.getByTestId("match-poster-reveal");
      expect(reducedPosterReveal.getAttribute("data-motion-initial")).not.toContain("clipPath");
      expect(reducedPosterReveal.getAttribute("data-motion-initial")).toContain("opacity");
    });

    it("applies ticketPrint clip-path reveal on SalonPassShareModal preview and respects reduced motion", async () => {
      const passData = {
        movieTitle: "Past Lives",
        releaseYear: 2023,
        rating: 8.1,
        posterUrl: "https://example.com/poster.jpg",
        sessionCode: "ABC123",
        partnerNames: "Alex & Sam",
      };

      const { unmount } = render(
        <SalonPassShareModal isOpen={true} onClose={vi.fn()} data={passData} />
      );

      const reveal = await screen.findByTestId("salon-pass-preview-reveal");
      expect(reveal.getAttribute("data-motion-initial")).toContain("clipPath");
      unmount();

      mockMatchMedia(true);
      render(<SalonPassShareModal isOpen={true} onClose={vi.fn()} data={passData} />);
      const reducedReveal = await screen.findByTestId("salon-pass-preview-reveal");
      expect(reducedReveal.getAttribute("data-motion-initial")).not.toContain("clipPath");
    });

    it("applies curtain clip-path reveal on CreateSessionPage room ticket", async () => {
      mockApiRequest.mockImplementation((path: string) => {
        if (path.includes("/genres/")) return Promise.resolve({ genres: [] });
        if (path.includes("/sessions/create/")) {
          return Promise.resolve({ id: 99, code: "ROOM99" });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/create-session",
              state: {
                preseedMovie: { tmdb_id: 55, title: "Arrival", poster_url: "" },
              },
            },
          ]}
        >
          <CreateSessionPage />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId("session-code-ticket")).toBeTruthy();
      });
      const ticket = screen.getByTestId("session-code-ticket");
      expect(ticket.getAttribute("data-motion-initial")).toContain("clipPath");
    });
  });
});
