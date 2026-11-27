/**
 * Flick Motion System
 * Built on UI/UX Pro Max guidelines for cinematic, premium web & mobile interactions.
 * 
 * Rules:
 * - Decelerated entry (easeOutCubic), accelerated exit (easeInCubic).
 * - Durations: 150ms for micro-interactions, 250ms for cards/sheets, 350ms for reveals.
 * - Tactile spring physics for drag release and snapback.
 * - Strict reduced-motion support.
 */

import { type Transition, type Variants } from "framer-motion";
import { useState, useEffect, useRef, useCallback } from "react";

/* ==========================================================================
   TIMING & EASING TOKENS
   ========================================================================== */

export const DURATION = {
  instant: 0,
  micro: 0.15,
  standard: 0.25,
  gentle: 0.35,
  cinematic: 0.5,
} as const;

export const EASING = {
  // Natural cubic decel for entering components
  easeOutCubic: [0.215, 0.61, 0.355, 1] as const,
  // Accelerated exit
  easeInCubic: [0.55, 0.055, 0.675, 0.19] as const,
  // Balanced bidirectional motion
  easeInOutCubic: [0.645, 0.045, 0.355, 1] as const,
  // Smooth filmic deceleration
  editorial: [0.16, 1, 0.3, 1] as const,
};

export const SPRING = {
  // Snappy button press / chip click
  snappy: { type: "spring", stiffness: 500, damping: 30 } as Transition,
  // Tactile card dragging / snapback
  tactile: { type: "spring", stiffness: 350, damping: 26, mass: 0.8 } as Transition,
  // Gentle bottom sheet / modal entry
  gentle: { type: "spring", stiffness: 260, damping: 28 } as Transition,
  // Bouncy celebration / match icon
  celebration: { type: "spring", stiffness: 380, damping: 18 } as Transition,
};

/* ==========================================================================
   SHARED TRANSITIONS
   ========================================================================== */

export const TRANSITION = {
  micro: { duration: DURATION.micro, ease: EASING.easeOutCubic } as Transition,
  standard: { duration: DURATION.standard, ease: EASING.easeOutCubic } as Transition,
  gentle: { duration: DURATION.gentle, ease: EASING.editorial } as Transition,
  cinematic: { duration: DURATION.cinematic, ease: EASING.editorial } as Transition,
};

/* ==========================================================================
   REUSABLE MOTION VARIANTS
   ========================================================================== */

/**
 * Route / Page transition: subtle opacity + minor vertical shift
 */
export const pageVariants: Variants = {
  initial: {
    opacity: 0,
    y: 6,
  },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: DURATION.standard,
      ease: EASING.editorial,
    },
  },
  exit: {
    opacity: 0,
    y: -4,
    transition: {
      duration: DURATION.micro,
      ease: EASING.easeInCubic,
    },
  },
};

/**
 * Reduced-motion page transition (opacity only, zero translation)
 */
export const pageVariantsReduced: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: DURATION.micro } },
  exit: { opacity: 0, transition: { duration: DURATION.micro } },
};

/**
 * Bottom Sheet modal variants
 */
export const bottomSheetVariants: Variants = {
  initial: {
    y: "100%",
    opacity: 0.9,
  },
  animate: {
    y: 0,
    opacity: 1,
    transition: SPRING.gentle,
  },
  exit: {
    y: "100%",
    opacity: 0,
    transition: {
      duration: DURATION.standard,
      ease: EASING.easeInCubic,
    },
  },
};

/**
 * Centered dialog / modal variants
 */
export const dialogVariants: Variants = {
  initial: {
    opacity: 0,
    scale: 0.95,
    y: 8,
  },
  animate: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: SPRING.gentle,
  },
  exit: {
    opacity: 0,
    scale: 0.96,
    y: 4,
    transition: {
      duration: DURATION.micro,
      ease: EASING.easeInCubic,
    },
  },
};

/**
 * Modal backdrop fade
 */
export const backdropVariants: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: DURATION.standard, ease: EASING.easeOutCubic } },
  exit: { opacity: 0, transition: { duration: DURATION.micro, ease: EASING.easeInCubic } },
};

export const backdropVariantsReduced: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.12 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

/* ==========================================================================
   PHASE 2 SHARED-ELEMENT & INLINE EXPANSION TOKENS
   ========================================================================== */

export const SHARED_LAYOUT_SPRING: Transition = {
  type: "spring",
  stiffness: 360,
  damping: 32,
  mass: 0.85,
};

/**
 * Container entrance/exit for modals hosting a shared-element layoutId child
 * (avoids competing vertical y:100% slide during poster/card morphing).
 */
export const expandModalVariants: Variants = {
  initial: { opacity: 0, scale: 0.96 },
  animate: {
    opacity: 1,
    scale: 1,
    transition: { duration: DURATION.standard, ease: EASING.editorial },
  },
  exit: {
    opacity: 0,
    scale: 0.97,
    transition: { duration: DURATION.micro, ease: EASING.easeInCubic },
  },
};

export const expandModalVariantsReduced: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.15 } },
  exit: { opacity: 0, transition: { duration: 0.12 } },
};

/**
 * Expand-in-place tray transition for room invitations and sharing options.
 */
export const inlineExpandVariants: Variants = {
  initial: { opacity: 0, height: 0, y: -4 },
  animate: {
    opacity: 1,
    height: "auto",
    y: 0,
    transition: { duration: 0.22, ease: EASING.editorial },
  },
  exit: {
    opacity: 0,
    height: 0,
    y: -4,
    transition: { duration: 0.16, ease: EASING.easeInCubic },
  },
};

export const inlineExpandVariantsReduced: Variants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: 0.12 } },
  exit: { opacity: 0, transition: { duration: 0.1 } },
};

/**
 * Staggered container for list items, chips, or movie grids
 */
export const staggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.04,
      delayChildren: 0.02,
    },
  },
};

export const staggerItem: Variants = {
  initial: { opacity: 0, y: 10 },
  animate: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.standard, ease: EASING.editorial },
  },
};

/**
 * Helper to check reduced-motion in client environment
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Reactive hook to detect OS-level prefers-reduced-motion changes dynamically
 */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => prefersReducedMotion());

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  return reduced;
}

/* ==========================================================================
   PHASE 1 ACTION FEEDBACK & ICON CROSSFADE PRIMITIVES
   ========================================================================== */

/**
 * Caller-controlled lifecycle states for async UI actions.
 * Buttons display these states without owning API or side-effect logic.
 */
export type ActionStatus = "idle" | "pending" | "confirmed" | "error";

export const TOUCH_TARGET_MIN_PX = 44;

export const ACTION_TIMING = {
  ackTargetMs: 100,
  iconCrossfade: DURATION.micro, // 150ms
  confirmedHoldMs: 1800,
  errorHoldMs: 2600,
} as const;

export const ACTION_FEEDBACK = {
  tap: { scale: 0.96 },
  tapTransition: { duration: 0.08, ease: EASING.easeOutCubic } as Transition,
  confirmedPulse: {
    scale: [1, 1.04, 1] as number[],
    transition: { duration: 0.34, times: [0, 0.42, 1], ease: EASING.easeOutCubic } as Transition,
  },
  iconConfirmedPulse: {
    scale: [1, 1.18, 1] as number[],
    transition: { duration: 0.32, times: [0, 0.45, 1], ease: EASING.easeOutCubic } as Transition,
  },
  errorShake: {
    x: [0, -5, 5, -3, 2, 0] as number[],
    transition: { duration: 0.32, ease: EASING.easeOutCubic } as Transition,
  },
} as const;

export const ICON_CROSSFADE = {
  standard: {
    initial: { opacity: 0, scale: 0.86, filter: "blur(2px)" },
    animate: { opacity: 1, scale: 1, filter: "blur(0px)" },
    exit: { opacity: 0, scale: 0.86, filter: "blur(2px)" },
    transition: { duration: DURATION.micro, ease: EASING.easeOutCubic } as Transition,
  },
  reduced: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
    transition: { duration: 0.12 } as Transition,
  },
} as const;

/**
 * Manages a single action button's controlled status with automatic timer cleanup on unmount.
 */
export function useActionStatus(options?: {
  confirmedDurationMs?: number;
  errorDurationMs?: number;
}) {
  const confirmedDefaultMs = options?.confirmedDurationMs ?? ACTION_TIMING.confirmedHoldMs;
  const errorDefaultMs = options?.errorDurationMs ?? ACTION_TIMING.errorHoldMs;

  const [status, setStatus] = useState<ActionStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearTimer(), [clearTimer]);

  const setPending = useCallback(() => {
    clearTimer();
    setErrorMessage(null);
    setStatus("pending");
  }, [clearTimer]);

  const setConfirmed = useCallback(
    (durationMs: number = confirmedDefaultMs) => {
      clearTimer();
      setErrorMessage(null);
      setStatus("confirmed");
      if (durationMs > 0) {
        timerRef.current = setTimeout(() => {
          setStatus("idle");
          timerRef.current = null;
        }, durationMs);
      }
    },
    [clearTimer, confirmedDefaultMs]
  );

  const setError = useCallback(
    (message?: string, durationMs: number = errorDefaultMs) => {
      clearTimer();
      setErrorMessage(message ?? null);
      setStatus("error");
      if (durationMs > 0) {
        timerRef.current = setTimeout(() => {
          setStatus("idle");
          setErrorMessage(null);
          timerRef.current = null;
        }, durationMs);
      }
    },
    [clearTimer, errorDefaultMs]
  );

  const reset = useCallback(() => {
    clearTimer();
    setErrorMessage(null);
    setStatus("idle");
  }, [clearTimer]);

  return { status, errorMessage, setPending, setConfirmed, setError, reset };
}

/**
 * Manages independent action statuses for keyed items (e.g. rows or movie cards) with timer cleanup.
 */
export function useKeyedActionStatus<TKey extends string | number>(options?: {
  confirmedDurationMs?: number;
  errorDurationMs?: number;
}) {
  const confirmedDefaultMs = options?.confirmedDurationMs ?? ACTION_TIMING.confirmedHoldMs;
  const errorDefaultMs = options?.errorDurationMs ?? ACTION_TIMING.errorHoldMs;

  const [statuses, setStatuses] = useState<Record<string, ActionStatus>>({});
  const [errorState, setErrorState] = useState<{ key: TKey; message: string } | null>(null);
  const timersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const clearKeyTimer = useCallback((keyStr: string) => {
    const existing = timersRef.current[keyStr];
    if (existing) {
      clearTimeout(existing);
      delete timersRef.current[keyStr];
    }
  }, []);

  useEffect(() => {
    const timers = timersRef.current;
    return () => {
      Object.values(timers).forEach((t) => clearTimeout(t));
    };
  }, []);

  const getStatus = useCallback(
    (key: TKey): ActionStatus => statuses[String(key)] ?? "idle",
    [statuses]
  );

  const setPending = useCallback(
    (key: TKey) => {
      const keyStr = String(key);
      clearKeyTimer(keyStr);
      setErrorState((prev) => (prev && String(prev.key) === keyStr ? null : prev));
      setStatuses((prev) => ({ ...prev, [keyStr]: "pending" }));
    },
    [clearKeyTimer]
  );

  const setConfirmed = useCallback(
    (key: TKey, durationMs: number = confirmedDefaultMs) => {
      const keyStr = String(key);
      clearKeyTimer(keyStr);
      setErrorState((prev) => (prev && String(prev.key) === keyStr ? null : prev));
      setStatuses((prev) => ({ ...prev, [keyStr]: "confirmed" }));
      if (durationMs > 0) {
        timersRef.current[keyStr] = setTimeout(() => {
          setStatuses((prev) => ({ ...prev, [keyStr]: "idle" }));
          delete timersRef.current[keyStr];
        }, durationMs);
      }
    },
    [clearKeyTimer, confirmedDefaultMs]
  );

  const setError = useCallback(
    (key: TKey, message: string, durationMs: number = errorDefaultMs) => {
      const keyStr = String(key);
      clearKeyTimer(keyStr);
      setErrorState({ key, message });
      setStatuses((prev) => ({ ...prev, [keyStr]: "error" }));
      if (durationMs > 0) {
        timersRef.current[keyStr] = setTimeout(() => {
          setStatuses((prev) => ({ ...prev, [keyStr]: "idle" }));
          setErrorState((prev) => (prev && String(prev.key) === keyStr ? null : prev));
          delete timersRef.current[keyStr];
        }, durationMs);
      }
    },
    [clearKeyTimer, errorDefaultMs]
  );

  const clearError = useCallback(() => setErrorState(null), []);

  return { getStatus, errorState, setPending, setConfirmed, setError, clearError };
}

/* ==========================================================================
   PHASE 3 SELECTIVE MASK REVEALS & BOUNDED OVERSCROLL
   ========================================================================== */

/**
 * Editorial clip-path reveals for high-value cinematic moments
 * (e.g., match poster presentation, Salon Pass ticket generation, room ticket).
 * Intentionally NOT applied to dense card grids to avoid paint overhead.
 */
export const MASK_REVEAL = {
  curtain: {
    initial: { clipPath: "inset(14% 0% 0% 0% round 16px)", opacity: 0 },
    animate: {
      clipPath: "inset(0% 0% 0% 0% round 16px)",
      opacity: 1,
      transition: { duration: 0.42, ease: EASING.editorial } as Transition,
    },
  },
  ticketPrint: {
    initial: { clipPath: "inset(0% 0% 100% 0% round 12px)", opacity: 0.4 },
    animate: {
      clipPath: "inset(0% 0% 0% 0% round 12px)",
      opacity: 1,
      transition: { duration: 0.45, ease: EASING.editorial } as Transition,
    },
  },
  reduced: {
    initial: { opacity: 0 },
    animate: {
      opacity: 1,
      transition: { duration: DURATION.micro } as Transition,
    },
  },
} as const;

export const OVERSCROLL_CONFIG = {
  maxOffsetPx: 28,
  resistance: 0.34,
  wheelSettleMs: 140,
  snapTransition: SPRING.tactile,
} as const;

/**
 * Computes a smooth, asymptotically bounded rubber-band offset so edge
 * overscroll never exceeds `maxOffset` regardless of drag/wheel velocity.
 */
export function computeBoundedOverscroll(
  delta: number,
  maxOffset: number = OVERSCROLL_CONFIG.maxOffsetPx,
  resistance: number = OVERSCROLL_CONFIG.resistance
): number {
  if (!Number.isFinite(delta) || delta === 0 || maxOffset <= 0 || resistance <= 0) {
    return 0;
  }
  const absDelta = Math.abs(delta);
  const magnitude = maxOffset * (1 - Math.exp((-absDelta * resistance) / maxOffset));
  return Math.sign(delta) * magnitude;
}

/* ==========================================================================
   PHASE 4 SESSION-LEVEL FAMILIARITY PACING & STAGED FOCUS
   ========================================================================== */

export type FamiliarityTier = "theatrical" | "concise" | "quiet";

export interface SessionPacing {
  tier: FamiliarityTier;
  allowDecorative: boolean;
  durationMultiplier: number;
}

/**
 * Lightweight, non-persistent session-level pacing resolver.
 * - First-time / milestone occurrences -> "theatrical" (full presentation)
 * - Repeated successful actions / subsequent matches -> "concise" (retains confirmation, drops repeat flourish)
 * - Rapid repeated swipes (>= 5) -> "quiet" (no decorative animation, keeps physics & confirmation)
 */
export function getSessionPacing(
  interactionCount: number,
  options?: { isFirstOccurrence?: boolean; kind?: "swipe" | "match" | "action" }
): SessionPacing {
  const kind = options?.kind ?? "action";
  const isFirst = options?.isFirstOccurrence ?? interactionCount <= 1;

  if (kind === "swipe" && interactionCount >= 5) {
    return { tier: "quiet", allowDecorative: false, durationMultiplier: 0.7 };
  }

  if (isFirst) {
    return { tier: "theatrical", allowDecorative: true, durationMultiplier: 1 };
  }

  return { tier: "concise", allowDecorative: false, durationMultiplier: 0.8 };
}

/**
 * Ephemeral in-memory counter for session-level familiarity pacing.
 * Intentionally never writes to localStorage/sessionStorage.
 */
export function useSessionFamiliarity(kind: "swipe" | "match" | "action" = "action") {
  const [count, setCount] = useState(0);

  const recordInteraction = useCallback(() => {
    setCount((prev) => prev + 1);
  }, []);

  const resetFamiliarity = useCallback(() => {
    setCount(0);
  }, []);

  const pacing = getSessionPacing(count, {
    isFirstOccurrence: count <= 1,
    kind,
  });

  return { count, pacing, recordInteraction, resetFamiliarity };
}

/**
 * Staged focus tokens: dim inactive background surfaces without introducing
 * transform containing-blocks that could skew shared-element projections.
 */
export const STAGED_FOCUS = {
  backdropClassName: "bg-black/70 backdrop-blur-md",
  inactiveDimmed: {
    opacity: 0.52,
    transition: { duration: 0.22, ease: EASING.editorial } as Transition,
  },
  inactiveDimmedReduced: {
    opacity: 0.65,
    transition: { duration: 0.12 } as Transition,
  },
  activeRestored: {
    opacity: 1,
    transition: { duration: 0.22, ease: EASING.editorial } as Transition,
  },
} as const;
