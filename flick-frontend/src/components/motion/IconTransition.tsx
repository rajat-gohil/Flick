import type { ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ICON_CROSSFADE, usePrefersReducedMotion } from "../../lib/motion";

export interface IconTransitionProps {
  /** Key identifying the visible icon state; changes trigger the 150ms crossfade. */
  iconKey: string | number;
  children: ReactNode;
  className?: string;
  /** Fixed square box sizing to keep parent button width/height stable during swaps. */
  sizeClassName?: string;
}

/**
 * Continuous 150ms opacity + subtle blur crossfade between icon states without layout shift.
 */
export function IconTransition({
  iconKey,
  children,
  className = "",
  sizeClassName = "size-4",
}: IconTransitionProps) {
  const shouldReduceMotion = usePrefersReducedMotion();
  const preset = shouldReduceMotion ? ICON_CROSSFADE.reduced : ICON_CROSSFADE.standard;

  return (
    <span
      aria-hidden="true"
      className={`relative inline-flex shrink-0 items-center justify-center ${sizeClassName} ${className}`.trim()}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={String(iconKey)}
          initial={preset.initial}
          animate={preset.animate}
          exit={preset.exit}
          transition={preset.transition}
          className="inline-flex items-center justify-center leading-none"
        >
          {children}
        </motion.span>
      </AnimatePresence>
    </span>
  );
}

export default IconTransition;
