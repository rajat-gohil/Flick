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
import { useState, useEffect } from "react";

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
