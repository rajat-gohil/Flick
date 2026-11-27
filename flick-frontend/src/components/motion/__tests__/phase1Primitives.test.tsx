import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { ActionButton } from "../ActionButton";
import { IconTransition } from "../IconTransition";
import { useActionStatus, useKeyedActionStatus } from "../../../lib/motion";

const MOTION_PROPS = new Set([
  "initial",
  "animate",
  "exit",
  "transition",
  "variants",
  "whileTap",
  "whileHover",
  "layout",
  "layoutId",
]);

vi.mock("framer-motion", () => ({
  motion: {
    button: ({ children, ...props }: Record<string, unknown>) => {
      const domProps: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(props)) {
        if (!MOTION_PROPS.has(k)) domProps[k] = v;
      }
      return (
        <button
          {...domProps}
          data-motion-animate={props.animate ? JSON.stringify(props.animate) : undefined}
          data-motion-tap={props.whileTap ? JSON.stringify(props.whileTap) : undefined}
          data-motion-transition={props.transition ? JSON.stringify(props.transition) : undefined}
        >
          {children as ReactNode}
        </button>
      );
    },
    span: ({ children, ...props }: Record<string, unknown>) => {
      const domProps: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(props)) {
        if (!MOTION_PROPS.has(k)) domProps[k] = v;
      }
      return (
        <span
          {...domProps}
          data-motion-initial={props.initial ? JSON.stringify(props.initial) : undefined}
          data-motion-animate={props.animate ? JSON.stringify(props.animate) : undefined}
          data-motion-exit={props.exit ? JSON.stringify(props.exit) : undefined}
          data-motion-transition={props.transition ? JSON.stringify(props.transition) : undefined}
        >
          {children as ReactNode}
        </span>
      );
    },
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

function mockMatchMedia(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduced && query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("Phase 1 Motion Primitives: ActionButton, IconTransition & Status Hooks", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockMatchMedia(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe("ActionButton", () => {
    it("enforces min-h-11 touch target and immediate whileTap ack in idle state", () => {
      render(<ActionButton>Save</ActionButton>);
      const btn = screen.getByRole("button", { name: "Save" });
      expect(btn.className).toContain("min-h-11");
      expect(btn.getAttribute("data-action-status")).toBe("idle");
      expect(JSON.parse(btn.getAttribute("data-motion-tap")!)).toEqual({ scale: 0.96 });
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
    });

    it("shows pending state cleanly WITHOUT premature confirmation pulse", () => {
      render(
        <ActionButton status="pending" pendingContent={<span>Saving…</span>}>
          Save
        </ActionButton>
      );
      const btn = screen.getByRole("button", { name: "Saving…" });
      expect(btn.hasAttribute("disabled")).toBe(true);
      expect(btn.getAttribute("aria-busy")).toBe("true");
      expect(btn.getAttribute("data-action-status")).toBe("pending");
      expect(JSON.parse(btn.getAttribute("data-motion-animate")!)).toEqual({ scale: 1, x: 0 });
      expect(btn.getAttribute("data-motion-tap")).toBeNull();
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
    });

    it("triggers confirmation pulse ONLY when status transitions to confirmed", () => {
      const { rerender } = render(
        <ActionButton status="pending" confirmedClassName="border-primary" confirmedContent={<span>Saved</span>}>
          Save
        </ActionButton>
      );
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();

      rerender(
        <ActionButton status="confirmed" confirmedClassName="border-primary" confirmedContent={<span>Saved</span>}>
          Save
        </ActionButton>
      );

      const btn = screen.getByRole("button", { name: "Saved" });
      expect(btn.getAttribute("data-action-status")).toBe("confirmed");
      expect(btn.className).toContain("border-primary");
      expect(screen.getByTestId("action-confirmed-pulse")).not.toBeNull();
      expect(JSON.parse(btn.getAttribute("data-motion-animate")!)).toEqual({
        scale: [1, 1.04, 1],
        x: 0,
      });
    });

    it("renders distinct error shake and styling WITHOUT confirmation pulse", () => {
      render(
        <ActionButton status="error" errorClassName="border-error text-error" errorContent={<span>Retry</span>}>
          Save
        </ActionButton>
      );
      const btn = screen.getByRole("button", { name: "Retry" });
      expect(btn.getAttribute("data-action-status")).toBe("error");
      expect(btn.className).toContain("border-error");
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
      expect(JSON.parse(btn.getAttribute("data-motion-animate")!)).toEqual({
        x: [0, -5, 5, -3, 2, 0],
        scale: 1,
      });
    });

    it("suppresses tap transform, pulse ring, and motion keyframes under prefers-reduced-motion while preserving labels", () => {
      mockMatchMedia(true);
      const { rerender } = render(
        <ActionButton
          status="idle"
          confirmedClassName="border-primary text-primary"
          confirmedContent={<span>Saved</span>}
          errorClassName="border-error text-error"
          errorContent={<span>Retry</span>}
        >
          Save
        </ActionButton>
      );
      const btnIdle = screen.getByRole("button", { name: "Save" });
      expect(btnIdle.getAttribute("data-motion-tap")).toBeNull();

      rerender(
        <ActionButton
          status="confirmed"
          confirmedClassName="border-primary text-primary"
          confirmedContent={<span>Saved</span>}
          errorClassName="border-error text-error"
          errorContent={<span>Retry</span>}
        >
          Save
        </ActionButton>
      );
      const btnConfirmed = screen.getByRole("button", { name: "Saved" });
      expect(btnConfirmed.getAttribute("data-action-status")).toBe("confirmed");
      expect(btnConfirmed.className).toContain("border-primary");
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
      expect(JSON.parse(btnConfirmed.getAttribute("data-motion-animate")!)).toEqual({ scale: 1, x: 0 });

      rerender(
        <ActionButton
          status="error"
          confirmedClassName="border-primary text-primary"
          confirmedContent={<span>Saved</span>}
          errorClassName="border-error text-error"
          errorContent={<span>Retry</span>}
        >
          Save
        </ActionButton>
      );
      const btnError = screen.getByRole("button", { name: "Retry" });
      expect(btnError.getAttribute("data-action-status")).toBe("error");
      expect(btnError.className).toContain("border-error");
      expect(JSON.parse(btnError.getAttribute("data-motion-animate")!)).toEqual({ scale: 1, x: 0 });
    });
  });

  describe("IconTransition", () => {
    it("uses 150ms opacity + blur crossfade inside stable box and removes blur under reduced motion", () => {
      const { unmount } = render(
        <IconTransition iconKey="copy" sizeClassName="size-4">
          <span>content_copy</span>
        </IconTransition>
      );

      const glyph = screen.getByText("content_copy").parentElement!;
      const initialStandard = JSON.parse(glyph.getAttribute("data-motion-initial")!);
      const transitionStandard = JSON.parse(glyph.getAttribute("data-motion-transition")!);
      expect(initialStandard.filter).toBe("blur(2px)");
      expect(transitionStandard.duration).toBe(0.15);
      expect(glyph.parentElement!.className).toContain("size-4");
      unmount();

      mockMatchMedia(true);
      render(
        <IconTransition iconKey="check" sizeClassName="size-4">
          <span>check</span>
        </IconTransition>
      );
      const reducedGlyph = screen.getByText("check").parentElement!;
      const initialReduced = JSON.parse(reducedGlyph.getAttribute("data-motion-initial")!);
      expect(initialReduced.filter).toBeUndefined();
      expect(initialReduced).toEqual({ opacity: 0 });
    });
  });

  describe("useActionStatus & useKeyedActionStatus", () => {
    it("auto-resets confirmed/error states back to idle cleanly", () => {
      const { result } = renderHook(() =>
        useActionStatus({ confirmedDurationMs: 1500, errorDurationMs: 2000 })
      );

      act(() => result.current.setPending());
      expect(result.current.status).toBe("pending");

      act(() => result.current.setConfirmed());
      expect(result.current.status).toBe("confirmed");

      act(() => vi.advanceTimersByTime(1500));
      expect(result.current.status).toBe("idle");

      act(() => result.current.setError("Copy failed"));
      expect(result.current.status).toBe("error");
      expect(result.current.errorMessage).toBe("Copy failed");

      act(() => vi.advanceTimersByTime(2000));
      expect(result.current.status).toBe("idle");
      expect(result.current.errorMessage).toBeNull();
    });

    it("tracks independent per-key statuses in useKeyedActionStatus", () => {
      const { result } = renderHook(() =>
        useKeyedActionStatus<number>({ confirmedDurationMs: 1200, errorDurationMs: 2000 })
      );

      act(() => {
        result.current.setPending(55);
        result.current.setConfirmed(56);
      });
      expect(result.current.getStatus(55)).toBe("pending");
      expect(result.current.getStatus(56)).toBe("confirmed");

      act(() => {
        result.current.setError(55, "Network error");
      });
      expect(result.current.getStatus(55)).toBe("error");
      expect(result.current.errorState).toEqual({ key: 55, message: "Network error" });
      expect(result.current.getStatus(56)).toBe("confirmed");
    });

    it("cleans up confirmation/error timers on unmount and cancels stale timers on rapid repeated actions", () => {
      const clearTimeoutSpy = vi.spyOn(globalThis, "clearTimeout");
      const { result, unmount } = renderHook(() =>
        useActionStatus({ confirmedDurationMs: 1500, errorDurationMs: 2000 })
      );

      // Action 1 confirms (schedules 1500ms timer)
      act(() => result.current.setConfirmed());
      expect(result.current.status).toBe("confirmed");

      // Advance 1200ms (only 300ms remaining on Timer 1), then rapidly start Action 2
      act(() => vi.advanceTimersByTime(1200));
      act(() => result.current.setPending());
      expect(result.current.status).toBe("pending");

      // Advance past Timer 1's remaining 300ms: stale Timer 1 MUST NOT reset "pending" -> "idle"
      act(() => vi.advanceTimersByTime(500));
      expect(result.current.status).toBe("pending");

      // Action 2 confirms (schedules fresh 1500ms Timer 2)
      act(() => result.current.setConfirmed());
      expect(result.current.status).toBe("confirmed");

      const callsBeforeUnmount = clearTimeoutSpy.mock.calls.length;
      unmount();
      expect(clearTimeoutSpy.mock.calls.length).toBeGreaterThan(callsBeforeUnmount);

      // Advancing timers after unmount triggers zero errors or updates
      act(() => vi.advanceTimersByTime(5000));
    });
  });
});
