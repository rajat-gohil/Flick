import { useEffect, useRef, useState, type RefObject } from "react";

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Provides accessible modal/dialog behavior:
 * - Captures previous focus and restores it on close/unmount
 * - Moves focus into the dialog on open
 * - Traps Tab / Shift+Tab within the dialog container
 * - Dismisses on Escape
 * - Locks body scroll while open
 */
export function useAccessibleDialog(
  isOpen: boolean,
  onClose: () => void,
  containerRef: RefObject<HTMLElement | null>
) {
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) return;

    previousActiveElementRef.current = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusTimer = window.requestAnimationFrame(() => {
      const container = containerRef.current;
      if (!container) return;
      if (!container.contains(document.activeElement)) {
        const focusable = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
        if (focusable.length > 0) {
          focusable[0].focus();
        } else {
          container.focus();
        }
      }
    });

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onCloseRef.current();
        return;
      }

      if (e.key === "Tab") {
        const container = containerRef.current;
        if (!container) return;
        const focusable = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
        if (focusable.length === 0) {
          e.preventDefault();
          container.focus();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first || document.activeElement === container || !container.contains(document.activeElement)) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last || !container.contains(document.activeElement)) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown, true);

    return () => {
      window.cancelAnimationFrame(focusTimer);
      document.removeEventListener("keydown", handleKeyDown, true);
      document.body.style.overflow = prevOverflow;
      const prev = previousActiveElementRef.current;
      if (prev && typeof prev.focus === "function") {
        try {
          prev.focus();
        } catch {
          // Ignore if previous element is detached
        }
      }
    };
  }, [isOpen, containerRef]);
}

/**
 * Provides swipe-to-dismiss pointer handling for a dedicated sheet drag-handle
 * without interfering with internal vertical scrolling.
 */
export function useSheetSwipeDismiss(onDismiss: () => void, disabled = false) {
  const [dragOffsetY, setDragOffsetY] = useState(0);
  const dragStateRef = useRef<{ startY: number; startTime: number; active: boolean }>({
    startY: 0,
    startTime: 0,
    active: false,
  });

  const handlePointerDown = (e: React.PointerEvent<HTMLElement>) => {
    if (disabled) return;
    dragStateRef.current = { startY: e.clientY, startTime: performance.now(), active: true };
    if (typeof e.currentTarget.setPointerCapture === "function") {
      try {
        e.currentTarget.setPointerCapture(e.pointerId);
      } catch {
        // Ignore in synthetic test environments
      }
    }
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLElement>) => {
    if (disabled || !dragStateRef.current.active) return;
    const delta = Math.max(0, e.clientY - dragStateRef.current.startY);
    setDragOffsetY(delta);
  };

  const handlePointerEnd = (e: React.PointerEvent<HTMLElement>) => {
    if (!dragStateRef.current.active) return;
    const delta = Math.max(0, e.clientY - dragStateRef.current.startY);
    const elapsed = Math.max(1, performance.now() - dragStateRef.current.startTime);
    const velocity = delta / elapsed; // px per ms
    dragStateRef.current.active = false;
    setDragOffsetY(0);

    if (!disabled && (delta > 80 || (delta > 48 && velocity > 0.65))) {
      onDismiss();
    }
  };

  return {
    dragOffsetY,
    handleProps: {
      onPointerDown: handlePointerDown,
      onPointerMove: handlePointerMove,
      onPointerUp: handlePointerEnd,
      onPointerCancel: handlePointerEnd,
    },
  };
}
