import React, { useRef, useEffect, useCallback, useImperativeHandle } from "react";
import { motion, useMotionValue, animate, type HTMLMotionProps } from "framer-motion";
import {
  OVERSCROLL_CONFIG,
  computeBoundedOverscroll,
  usePrefersReducedMotion,
} from "../../lib/motion";

export interface BoundedOverscrollProps
  extends Omit<React.HTMLAttributes<HTMLDivElement>, "onAnimationStart"> {
  /** Scroll axis where edge rubber-banding is active. */
  axis?: "x" | "y";
  /** Maximum elastic displacement in pixels at the boundary. */
  maxOffset?: number;
  /** Optional external ref to the scrollable element (e.g., for programmatic scrollBy). */
  scrollRef?: React.RefObject<HTMLDivElement | null>;
  /** Extra classes applied to the inner elastic container. */
  innerClassName?: string;
  /** Optional motion props forwarded to the inner container if needed. */
  innerMotionProps?: Omit<HTMLMotionProps<"div">, "children" | "className" | "style">;
  children: React.ReactNode;
}

/**
 * Scroll container that applies a bounded, spring-snapping rubber-band stretch
 * when users drag or wheel past the start/end edges of horizontal shelves or
 * scrollable lists, while leaving normal mid-list scrolling untouched.
 * Respects `prefers-reduced-motion` by keeping displacement at 0.
 */
export function BoundedOverscroll({
  axis = "x",
  maxOffset = OVERSCROLL_CONFIG.maxOffsetPx,
  scrollRef,
  className = "",
  innerClassName = "",
  innerMotionProps,
  onScroll,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
  onTouchCancel,
  onWheel,
  children,
  ...rest
}: BoundedOverscrollProps) {
  const shouldReduceMotion = usePrefersReducedMotion();
  const internalRef = useRef<HTMLDivElement | null>(null);
  const offset = useMotionValue(0);

  const touchStartRef = useRef<{ x: number; y: number } | null>(null);
  const lastTouchPosRef = useRef<number | null>(null);
  const axisLockRef = useRef<"x" | "y" | null>(null);
  const edgeAnchorPosRef = useRef<number | null>(null);
  const wheelAccumRef = useRef(0);
  const wheelResetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useImperativeHandle(scrollRef, () => internalRef.current as HTMLDivElement, []);

  const snapBack = useCallback(() => {
    touchStartRef.current = null;
    lastTouchPosRef.current = null;
    axisLockRef.current = null;
    edgeAnchorPosRef.current = null;
    wheelAccumRef.current = 0;
    if (offset.get() !== 0) {
      animate(offset, 0, OVERSCROLL_CONFIG.snapTransition);
    }
  }, [offset]);

  useEffect(() => {
    return () => {
      if (wheelResetTimerRef.current !== null) {
        clearTimeout(wheelResetTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (shouldReduceMotion && offset.get() !== 0) {
      offset.set(0);
    }
  }, [shouldReduceMotion, offset]);

  const isAtEdge = useCallback(
    (el: HTMLDivElement, directionDelta: number): boolean => {
      if (axis === "x") {
        const atStart = el.scrollLeft <= 1;
        const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 1;
        return (directionDelta > 0 && atStart) || (directionDelta < 0 && atEnd);
      }
      const atTop = el.scrollTop <= 1;
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1;
      return (directionDelta > 0 && atTop) || (directionDelta < 0 && atBottom);
    },
    [axis]
  );

  const handleTouchStart = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      onTouchStart?.(e);
      if (shouldReduceMotion || e.touches.length !== 1) return;
      const touch = e.touches[0];
      touchStartRef.current = { x: touch.clientX, y: touch.clientY };
      lastTouchPosRef.current = axis === "x" ? touch.clientX : touch.clientY;
      axisLockRef.current = null;
      edgeAnchorPosRef.current = null;
    },
    [axis, onTouchStart, shouldReduceMotion]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      onTouchMove?.(e);
      if (shouldReduceMotion || !touchStartRef.current || e.touches.length !== 1) return;
      const el = internalRef.current;
      if (!el) return;

      const touch = e.touches[0];
      const totalDx = touch.clientX - touchStartRef.current.x;
      const totalDy = touch.clientY - touchStartRef.current.y;

      // Determine primary scroll intent before engaging overscroll so perpendicular
      // page scrolling over a horizontal shelf never triggers horizontal rubber-band.
      if (axisLockRef.current === null) {
        if (Math.abs(totalDx) < 4 && Math.abs(totalDy) < 4) return;
        axisLockRef.current = Math.abs(totalDx) >= Math.abs(totalDy) ? "x" : "y";
      }
      if (axisLockRef.current !== axis) return;

      const currentPos = axis === "x" ? touch.clientX : touch.clientY;
      const stepDelta = lastTouchPosRef.current !== null ? currentPos - lastTouchPosRef.current : 0;
      lastTouchPosRef.current = currentPos;

      if (edgeAnchorPosRef.current !== null) {
        const edgeDelta = currentPos - edgeAnchorPosRef.current;
        // If user reversed back past the anchor, release overscroll and resume normal scroll
        if (Math.sign(edgeDelta) !== 0 && Math.sign(edgeDelta) !== Math.sign(offset.get()) && offset.get() !== 0) {
          edgeAnchorPosRef.current = null;
          offset.set(0);
          return;
        }
        offset.set(computeBoundedOverscroll(edgeDelta, maxOffset));
        return;
      }

      if (stepDelta !== 0 && isAtEdge(el, stepDelta)) {
        // Anchor at the exact moment the edge is reached so displacement starts smoothly at 0px
        edgeAnchorPosRef.current = currentPos - stepDelta;
        offset.set(computeBoundedOverscroll(stepDelta, maxOffset));
      }
    },
    [axis, isAtEdge, maxOffset, offset, onTouchMove, shouldReduceMotion]
  );

  const handleTouchEnd = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      onTouchEnd?.(e);
      snapBack();
    },
    [onTouchEnd, snapBack]
  );

  const handleTouchCancel = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      onTouchCancel?.(e);
      snapBack();
    },
    [onTouchCancel, snapBack]
  );

  const handleWheel = useCallback(
    (e: React.WheelEvent<HTMLDivElement>) => {
      onWheel?.(e);
      if (shouldReduceMotion) return;
      const el = internalRef.current;
      if (!el) return;

      const wheelDelta = axis === "x" ? e.deltaX : e.deltaY;
      const crossDelta = axis === "x" ? e.deltaY : e.deltaX;
      if (Math.abs(wheelDelta) < 0.5 || Math.abs(wheelDelta) < Math.abs(crossDelta)) return;

      const directionDelta = -wheelDelta;
      if (!isAtEdge(el, directionDelta)) {
        if (offset.get() !== 0) {
          snapBack();
        }
        return;
      }

      // If user reverses wheel direction while overscrolled, decay quickly instead of sticking
      if (wheelAccumRef.current !== 0 && Math.sign(directionDelta) !== Math.sign(wheelAccumRef.current)) {
        wheelAccumRef.current = 0;
      }

      const clampLimit = maxOffset * 6;
      wheelAccumRef.current = Math.max(
        -clampLimit,
        Math.min(clampLimit, wheelAccumRef.current + directionDelta)
      );
      offset.set(computeBoundedOverscroll(wheelAccumRef.current, maxOffset));

      if (wheelResetTimerRef.current !== null) {
        clearTimeout(wheelResetTimerRef.current);
      }
      wheelResetTimerRef.current = setTimeout(() => {
        wheelResetTimerRef.current = null;
        snapBack();
      }, OVERSCROLL_CONFIG.wheelSettleMs);
    },
    [axis, isAtEdge, maxOffset, offset, onWheel, shouldReduceMotion, snapBack]
  );

  const elasticStyle = shouldReduceMotion
    ? undefined
    : axis === "x"
    ? { x: offset }
    : { y: offset };

  return (
    <div
      ref={internalRef}
      data-overscroll-axis={axis}
      onScroll={onScroll}
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      onTouchCancel={handleTouchCancel}
      onWheel={handleWheel}
      className={className}
      {...rest}
    >
      <motion.div
        style={elasticStyle}
        className={innerClassName || (axis === "x" ? "flex items-stretch w-max min-w-full" : "w-full")}
        {...innerMotionProps}
      >
        {children}
      </motion.div>
    </div>
  );
}
