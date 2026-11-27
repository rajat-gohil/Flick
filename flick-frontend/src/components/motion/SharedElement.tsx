import type { CSSProperties, MouseEventHandler, ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { SHARED_LAYOUT_SPRING, usePrefersReducedMotion } from "../../lib/motion";

export interface SharedElementProps {
  layoutId?: string;
  className?: string;
  style?: CSSProperties;
  onClick?: MouseEventHandler<HTMLDivElement>;
  children: ReactNode;
}

/**
 * Shared-element layout projection container.
 * Uses an inner AnimatePresence boundary when a layoutId is active inside an exiting modal
 * so Framer Motion's MeasureLayout relegate() does not defer parent modal unmount in zero-rect environments.
 */
export function SharedElement({
  layoutId,
  className = "",
  style,
  onClick,
  children,
}: SharedElementProps) {
  const shouldReduceMotion = usePrefersReducedMotion();
  const activeLayoutId = shouldReduceMotion ? undefined : layoutId;

  const content = (
    <motion.div
      layoutId={activeLayoutId}
      transition={SHARED_LAYOUT_SPRING}
      className={className}
      style={style}
      onClick={onClick}
    >
      {children}
    </motion.div>
  );

  if (!activeLayoutId) {
    return content;
  }

  return <AnimatePresence>{content}</AnimatePresence>;
}

export default SharedElement;
