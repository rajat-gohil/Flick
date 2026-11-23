import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import {
  CurtainCallMatchModal,
  resolveMatchStyle,
  type MatchMovie,
  type CurtainCallMatchModalProps,
} from "../CurtainCallMatchModal";

// Filter out Framer Motion DOM attributes to prevent React DOM warnings in jsdom
const MOTION_PROPS = new Set([
  "layoutId", "layout", "whileTap", "whileHover", "whileFocus", "whileDrag",
  "initial", "animate", "exit", "transition", "variants",
  "drag", "dragConstraints", "dragElastic", "onDragEnd", "onDragStart", "custom"
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
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...stripMotionProps(props)}>{children as React.ReactNode}</div>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...stripMotionProps(props)}>{children as React.ReactNode}</span>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button {...stripMotionProps(props)}>{children as React.ReactNode}</button>
    ),
  },
}));

vi.mock("../../StreamingOptions", () => ({
  default: ({ movieId, movieTitle }: { movieId: number; movieTitle: string }) => (
    <div data-testid="mock-streaming-options">
      Streaming for {movieTitle} ({movieId})
    </div>
  ),
}));

const baseMockMovie: MatchMovie = {
  id: 42,
  title: "Solaris",
  overview: "A psychologist is sent to a space station orbiting a mysterious planet.",
  poster_url: "https://image.tmdb.org/t/p/w780/solaris.jpg",
  rating: 8.1,
  release_year: 1972,
  trailer_url: "https://youtube.com/watch?v=sample",
  metadataStatus: "success",
  superlike_attribution: "none",
  match_type: "ordinary",
};

describe("CurtainCallMatchModal Component", () => {
  const defaultProps: CurtainCallMatchModalProps = {
    matchedMovie: baseMockMovie,
    renderMode: "full",
    shouldReduceMotion: false,
    userRole: "host",
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
    onTrailerClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Accessibility & Dialog Contract", () => {
    it("renders with role='dialog' and aria-modal='true'", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const dialog = screen.getByRole("dialog");
      expect(dialog).not.toBeNull();
      expect(dialog.getAttribute("aria-modal")).toBe("true");
      expect(dialog.getAttribute("aria-labelledby")).toBe("curtain-call-title");
    });

    it("announces match title via polite live region", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const liveRegion = screen.getByText(/Mutual match found: Solaris/i);
      expect(liveRegion).not.toBeNull();
      expect(liveRegion.getAttribute("aria-live")).toBe("polite");
    });

    it("dismisses on Escape key press", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const dialog = screen.getByRole("dialog");
      fireEvent.keyDown(dialog, { key: "Escape" });
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });

    it("dismisses on top-right close button click", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const closeBtn = screen.getByTestId("curtain-call-close-btn");
      expect(closeBtn).not.toBeNull();
      fireEvent.click(closeBtn);
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });

    it("dismisses on backdrop click outside the dialog card", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const dialog = screen.getByRole("dialog");
      fireEvent.click(dialog);
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });

    it("traps Tab focus within the modal", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const dialog = screen.getByRole("dialog");
      const focusable = dialog.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      expect(focusable.length).toBeGreaterThan(0);

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      // Shift+Tab on first element wraps to last
      first.focus();
      fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
      expect(document.activeElement).toBe(last);

      // Tab on last element wraps to first
      last.focus();
      fireEvent.keyDown(dialog, { key: "Tab", shiftKey: false });
      expect(document.activeElement).toBe(first);
    });
  });

  describe("Exhaustive Attribution Mapping & Contradiction Handling", () => {
    it("applies antique brass styling when mutual + mutual_superlike", () => {
      const movie: MatchMovie = {
        ...baseMockMovie,
        superlike_attribution: "mutual",
        match_type: "mutual_superlike",
      };
      render(<CurtainCallMatchModal {...defaultProps} matchedMovie={movie} />);
      expect(screen.getByText("★ Mutual Super-Like ★")).not.toBeNull();
      expect(screen.getByText("Double Super-Like!")).not.toBeNull();
      expect(screen.getByText("Both viewers sent a Super-Like for this film!")).not.toBeNull();
    });

    it("applies amber priority styling when host + superlike", () => {
      const movie: MatchMovie = {
        ...baseMockMovie,
        superlike_attribution: "host",
        match_type: "superlike",
      };
      render(<CurtainCallMatchModal {...defaultProps} matchedMovie={movie} />);
      expect(screen.getByText("★ Priority Selection ★")).not.toBeNull();
      expect(screen.getByText("Film Selected")).not.toBeNull();
      expect(screen.getByText("Priority Interest (Your Selection)")).not.toBeNull();
    });

    it("applies amber priority styling when guest + superlike", () => {
      const movie: MatchMovie = {
        ...baseMockMovie,
        superlike_attribution: "guest",
        match_type: "superlike",
      };
      render(<CurtainCallMatchModal {...defaultProps} matchedMovie={movie} userRole="guest" />);
      expect(screen.getByText("★ Priority Selection ★")).not.toBeNull();
      expect(screen.getByText("Priority Interest (Your Selection)")).not.toBeNull();
    });

    it("applies emerald consensus styling when none + ordinary", () => {
      const movie: MatchMovie = {
        ...baseMockMovie,
        superlike_attribution: "none",
        match_type: "ordinary",
      };
      render(<CurtainCallMatchModal {...defaultProps} matchedMovie={movie} />);
      expect(screen.getByText("Consensus Reached")).not.toBeNull();
      expect(screen.getByText("Film Selected")).not.toBeNull();
    });

    it("fails closed to neutral fallback on contradictory mismatches", () => {
      // Mismatch: mutual attribution with superlike match_type
      expect(resolveMatchStyle("mutual", "superlike")).toBe("neutral");
      // Mismatch: host attribution with mutual_superlike
      expect(resolveMatchStyle("host", "mutual_superlike")).toBe("neutral");
      // Mismatch: none attribution with superlike
      expect(resolveMatchStyle("none", "superlike")).toBe("neutral");
      // Unknown values
      expect(resolveMatchStyle("unknown", "unknown")).toBe("neutral");
      expect(resolveMatchStyle(undefined, undefined)).toBe("neutral");

      const movie: MatchMovie = {
        ...baseMockMovie,
        superlike_attribution: "mutual",
        match_type: "ordinary", // contradiction
      };
      render(<CurtainCallMatchModal {...defaultProps} matchedMovie={movie} />);
      // Must NOT display "★ Mutual Super-Like ★"
      expect(screen.queryByText("★ Mutual Super-Like ★")).toBeNull();
      expect(screen.getByText("Consensus Reached")).not.toBeNull();
    });
  });

  describe("Preservation of All 6 Actions with Prerequisite Rules", () => {
    it("renders Trailer link when trailer_url is present, omits when null", () => {
      const { rerender } = render(<CurtainCallMatchModal {...defaultProps} />);
      const trailer = screen.getByText("Trailer");
      expect(trailer).not.toBeNull();

      rerender(
        <CurtainCallMatchModal
          {...defaultProps}
          matchedMovie={{ ...baseMockMovie, trailer_url: undefined }}
        />
      );
      expect(screen.queryByText("Trailer")).toBeNull();
    });

    it("handles Watchlist toggle action", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const saveBtn = screen.getByText("Save");
      fireEvent.click(saveBtn);
      expect(defaultProps.onToggleWatchlist).toHaveBeenCalledTimes(1);
    });

    it("renders Streaming Options preview", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      expect(screen.getByTestId("mock-streaming-options")).not.toBeNull();
    });

    it("handles Continue Screening Deck dismiss action", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const continueBtn = screen.getByText("Continue Screening Deck");
      fireEvent.click(continueBtn);
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });

    it("handles Conclude Session action", () => {
      render(<CurtainCallMatchModal {...defaultProps} />);
      const endBtn = screen.getByText("Conclude & View All Matches");
      fireEvent.click(endBtn);
      expect(defaultProps.onEndSession).toHaveBeenCalledTimes(1);
    });

    it("renders Metadata Retry only when metadataStatus is failed", () => {
      const { rerender } = render(<CurtainCallMatchModal {...defaultProps} />);
      expect(screen.queryByText("Retry details")).toBeNull();

      rerender(
        <CurtainCallMatchModal
          {...defaultProps}
          matchedMovie={{ ...baseMockMovie, metadataStatus: "failed" }}
        />
      );
      const retryBtn = screen.getByText("Retry details");
      expect(retryBtn).not.toBeNull();
      fireEvent.click(retryBtn);
      expect(defaultProps.onFetchMetadata).toHaveBeenCalledTimes(1);
    });
  });

  describe("Minimal Mode presentation", () => {
    it("omits background spotlight and rotates in Minimal Mode", () => {
      render(<CurtainCallMatchModal {...defaultProps} renderMode="minimal" />);
      expect(screen.queryByTestId("match-theatre-spotlight")).toBeNull();
      // Actions remain fully clickable
      const continueBtn = screen.getByText("Continue Screening Deck");
      expect(continueBtn).not.toBeNull();
      fireEvent.click(continueBtn);
      expect(defaultProps.onDismiss).toHaveBeenCalledTimes(1);
    });
  });

  describe("Theatrical Ticket Stub Interlock & Motion Decoupling", () => {
    it("renders participant-neutral ticket stubs and blind-embossed cinema seal in Full Mode", () => {
      render(<CurtainCallMatchModal {...defaultProps} renderMode="full" shouldReduceMotion={false} />);
      
      const leftStub = screen.getByTestId("ticket-stub-left");
      expect(leftStub).not.toBeNull();
      expect(leftStub.textContent).toContain("ADMIT ONE · SCREENING A");

      const rightStub = screen.getByTestId("ticket-stub-right");
      expect(rightStub).not.toBeNull();
      expect(rightStub.textContent).toContain("ADMIT ONE · SCREENING B");

      const seal = screen.getByTestId("cinema-society-seal");
      expect(seal).not.toBeNull();
      expect(seal.textContent).toContain("FLICK CINEMA SOCIETY · MUTUAL SELECTION");

      // Soft amber light sweep is rendered in Full Mode with motion enabled
      expect(screen.getByTestId("projector-light-sweep")).not.toBeNull();
    });

    it("omits projector light sweep when shouldReduceMotion is true", () => {
      render(<CurtainCallMatchModal {...defaultProps} renderMode="full" shouldReduceMotion={true} />);
      
      // Stubs and seal are still rendered
      expect(screen.getByTestId("ticket-stub-left")).not.toBeNull();
      expect(screen.getByTestId("ticket-stub-right")).not.toBeNull();
      expect(screen.getByTestId("cinema-society-seal")).not.toBeNull();

      // Light sweep is omitted when user prefers reduced motion
      expect(screen.queryByTestId("projector-light-sweep")).toBeNull();
    });

    it("omits projector light sweep in Reduced Mode", () => {
      render(<CurtainCallMatchModal {...defaultProps} renderMode="reduced" shouldReduceMotion={false} />);
      
      // Stubs and seal are preserved
      expect(screen.getByTestId("ticket-stub-left")).not.toBeNull();
      expect(screen.getByTestId("ticket-stub-right")).not.toBeNull();

      // Light sweep is omitted in Reduced Mode
      expect(screen.queryByTestId("projector-light-sweep")).toBeNull();
    });

    it("omits ticket pass completely in Minimal Mode", () => {
      render(<CurtainCallMatchModal {...defaultProps} renderMode="minimal" shouldReduceMotion={false} />);
      
      expect(screen.queryByTestId("theatrical-ticket-pass")).toBeNull();
      expect(screen.queryByTestId("ticket-stub-left")).toBeNull();
      expect(screen.queryByTestId("ticket-stub-right")).toBeNull();
      expect(screen.queryByTestId("cinema-society-seal")).toBeNull();
      expect(screen.queryByTestId("projector-light-sweep")).toBeNull();
    });
  });
});
