import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type JSX,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { DURATION, EASING, usePrefersReducedMotion } from "../lib/motion";

export type TourPlacement = "auto" | "top" | "bottom" | "center";
export type TourGestureHint =
  | "swipe-right"
  | "swipe-left"
  | "superlike"
  | "info-undo"
  | null;

export interface SpotlightTourStep {
  id: string;
  target?: string | string[];
  title: string;
  description: string;
  icon?: string;
  shortcutHint?: string;
  shortcutLabel?: string;
  gestureHint?: TourGestureHint;
  placement?: TourPlacement;
  nextLabel?: string;
}

export interface SpotlightTourProps {
  isOpen: boolean;
  steps: SpotlightTourStep[];
  ariaLabel: string;
  onComplete: () => void;
  onSkip: () => void;
  onStepChange?: (stepIndex: number, step: SpotlightTourStep) => void;
}

interface SpotlightRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

interface ComputedLayout {
  spotlight: SpotlightRect | null;
  tooltipX: number;
  tooltipY: number;
  tooltipWidth: number;
  resolvedPlacement: "center" | "top" | "bottom";
}

const EDGE_MARGIN = 12;
const SAFE_BOTTOM = 16;
const SPOTLIGHT_PADDING = 8;
const TOOLTIP_GAP = 14;
const MAX_TOOLTIP_WIDTH = 360;
const FALLBACK_TOOLTIP_HEIGHT = 272;

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const BUTTON_FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface";

function getViewportSize(): { width: number; height: number } {
  if (typeof window === "undefined") {
    return { width: 1024, height: 768 };
  }
  return {
    width: window.innerWidth || document.documentElement.clientWidth || 1024,
    height: window.innerHeight || document.documentElement.clientHeight || 768,
  };
}

function getClampedTooltipWidth(viewportWidth: number): number {
  return Math.max(0, Math.min(MAX_TOOLTIP_WIDTH, viewportWidth - EDGE_MARGIN * 2));
}

function findVisibleTarget(target?: string | string[]): HTMLElement | null {
  if (!target || typeof document === "undefined") {
    return null;
  }

  const selectors = Array.isArray(target) ? target : [target];
  for (const selector of selectors) {
    if (!selector) continue;
    let matches: NodeListOf<Element>;
    try {
      matches = document.querySelectorAll(selector);
    } catch {
      continue;
    }

    for (const node of matches) {
      if (!(node instanceof HTMLElement)) continue;
      const computed = window.getComputedStyle(node);
      if (computed.display === "none" || computed.visibility === "hidden") {
        continue;
      }
      const rect = node.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        return node;
      }
    }
  }

  return null;
}

function isFixedOrStickyElement(el: HTMLElement): boolean {
  let current: HTMLElement | null = el;
  while (current && current !== document.body && current !== document.documentElement) {
    const position = window.getComputedStyle(current).position;
    if (position === "fixed" || position === "sticky") {
      return true;
    }
    current = current.parentElement;
  }
  return false;
}

function computeTourLayout(
  step: SpotlightTourStep,
  targetEl: HTMLElement | null,
  dialogEl: HTMLElement | null
): ComputedLayout {
  const { width: vw, height: vh } = getViewportSize();
  const tooltipWidth = getClampedTooltipWidth(vw);
  const measuredDialog = dialogEl?.getBoundingClientRect();
  const effectiveWidth =
    measuredDialog && measuredDialog.width > 0
      ? Math.min(measuredDialog.width, tooltipWidth)
      : tooltipWidth;
  const effectiveHeight =
    measuredDialog && measuredDialog.height > 0
      ? measuredDialog.height
      : FALLBACK_TOOLTIP_HEIGHT;

  const placement: TourPlacement = step.placement ?? "auto";
  const maxX = Math.max(EDGE_MARGIN, vw - effectiveWidth - EDGE_MARGIN);
  const maxY = Math.max(EDGE_MARGIN, vh - effectiveHeight - SAFE_BOTTOM);

  if (!targetEl || placement === "center") {
    const centeredX = Math.round(
      Math.min(Math.max((vw - effectiveWidth) / 2, EDGE_MARGIN), maxX)
    );
    const centeredY = Math.round(
      Math.min(Math.max((vh - effectiveHeight) / 2, EDGE_MARGIN), maxY)
    );
    return {
      spotlight: null,
      tooltipX: centeredX,
      tooltipY: centeredY,
      tooltipWidth,
      resolvedPlacement: "center",
    };
  }

  const rect = targetEl.getBoundingClientRect();
  if (rect.width <= 0 || rect.height <= 0) {
    const centeredX = Math.round(
      Math.min(Math.max((vw - effectiveWidth) / 2, EDGE_MARGIN), maxX)
    );
    const centeredY = Math.round(
      Math.min(Math.max((vh - effectiveHeight) / 2, EDGE_MARGIN), maxY)
    );
    return {
      spotlight: null,
      tooltipX: centeredX,
      tooltipY: centeredY,
      tooltipWidth,
      resolvedPlacement: "center",
    };
  }

  const spotLeft = Math.max(4, rect.left - SPOTLIGHT_PADDING);
  const spotTop = Math.max(4, rect.top - SPOTLIGHT_PADDING);
  const spotRight = Math.min(vw - 4, rect.right + SPOTLIGHT_PADDING);
  const spotBottom = Math.min(vh - 4, rect.bottom + SPOTLIGHT_PADDING);
  const spotlight: SpotlightRect = {
    left: Math.round(spotLeft),
    top: Math.round(spotTop),
    width: Math.max(0, Math.round(spotRight - spotLeft)),
    height: Math.max(0, Math.round(spotBottom - spotTop)),
  };

  const spaceBelow = vh - spotBottom - TOOLTIP_GAP - SAFE_BOTTOM;
  const spaceAbove = spotTop - TOOLTIP_GAP - EDGE_MARGIN;

  let chosenSide: "top" | "bottom";
  if (placement === "top") {
    chosenSide =
      spaceAbove >= effectiveHeight || spaceAbove >= spaceBelow ? "top" : "bottom";
  } else if (placement === "bottom") {
    chosenSide =
      spaceBelow >= effectiveHeight || spaceBelow >= spaceAbove ? "bottom" : "top";
  } else {
    if (spaceBelow >= effectiveHeight) {
      chosenSide = "bottom";
    } else if (spaceAbove >= effectiveHeight) {
      chosenSide = "top";
    } else {
      chosenSide = spaceBelow >= spaceAbove ? "bottom" : "top";
    }
  }

  const targetCenterX = (spotLeft + spotRight) / 2;
  const rawX = targetCenterX - effectiveWidth / 2;
  const rawY =
    chosenSide === "bottom"
      ? spotBottom + TOOLTIP_GAP
      : spotTop - TOOLTIP_GAP - effectiveHeight;

  const tooltipX = Math.round(Math.min(Math.max(rawX, EDGE_MARGIN), maxX));
  const tooltipY = Math.round(Math.min(Math.max(rawY, EDGE_MARGIN), maxY));

  return {
    spotlight,
    tooltipX,
    tooltipY,
    tooltipWidth,
    resolvedPlacement: chosenSide,
  };
}

function isSameLayout(a: ComputedLayout, b: ComputedLayout): boolean {
  if (
    a.tooltipX !== b.tooltipX ||
    a.tooltipY !== b.tooltipY ||
    a.tooltipWidth !== b.tooltipWidth ||
    a.resolvedPlacement !== b.resolvedPlacement
  ) {
    return false;
  }
  if (a.spotlight === null && b.spotlight === null) {
    return true;
  }
  if (a.spotlight === null || b.spotlight === null) {
    return false;
  }
  return (
    a.spotlight.left === b.spotlight.left &&
    a.spotlight.top === b.spotlight.top &&
    a.spotlight.width === b.spotlight.width &&
    a.spotlight.height === b.spotlight.height
  );
}

function GestureHintCue({
  hint,
  reducedMotion,
}: {
  hint: Exclude<TourGestureHint, null>;
  reducedMotion: boolean;
}): JSX.Element {
  if (hint === "info-undo") {
    return (
      <div
        className="pointer-events-none grid grid-cols-2 gap-2 rounded-xl border border-border bg-surface-secondary/80 p-2.5"
        data-testid="tour-gesture-hint"
        data-gesture-hint={hint}
        data-gesture-animated="false"
      >
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2">
          <span
            className="material-symbols-outlined text-[18px] text-primary shrink-0"
            aria-hidden="true"
          >
            info
          </span>
          <span className="text-[11px] font-medium leading-tight text-foreground">
            Tap card for Details
          </span>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-border bg-surface px-2.5 py-2">
          <span
            className="material-symbols-outlined text-[18px] text-primary shrink-0"
            aria-hidden="true"
          >
            undo
          </span>
          <span className="text-[11px] font-medium leading-tight text-foreground">
            Undo last swipe
          </span>
        </div>
      </div>
    );
  }

  const config =
    hint === "swipe-right"
      ? {
          icon: "favorite",
          directionIcon: "arrow_forward",
          label: "Swipe right · Like",
          iconColorClass: "text-primary",
          animate: { x: [0, 12, 0], rotate: [0, 3, 0] },
        }
      : hint === "swipe-left"
        ? {
            icon: "close",
            directionIcon: "arrow_back",
            label: "Swipe left · Pass",
            iconColorClass: "text-error",
            animate: { x: [0, -12, 0], rotate: [0, -3, 0] },
          }
        : {
            icon: "star",
            directionIcon: "arrow_upward",
            label: "Super-like · Must watch",
            iconColorClass: "text-primary",
            animate: { y: [0, -7, 0] },
          };

  const cardInner = (
    <div className="flex items-center gap-1.5 rounded-lg border border-border bg-surface px-2.5 py-1.5 shadow-2xs">
      <span
        className={`material-symbols-outlined text-[17px] ${config.iconColorClass}`}
        aria-hidden="true"
      >
        {config.icon}
      </span>
      <span
        className="material-symbols-outlined text-[14px] text-foreground-secondary"
        aria-hidden="true"
      >
        {config.directionIcon}
      </span>
    </div>
  );

  return (
    <div
      className="pointer-events-none flex items-center justify-between gap-3 rounded-xl border border-border bg-surface-secondary/80 px-3.5 py-2.5"
      data-testid="tour-gesture-hint"
      data-gesture-hint={hint}
      data-gesture-animated={reducedMotion ? "false" : "true"}
    >
      <div className="flex items-center gap-2.5">
        {reducedMotion ? (
          <div>{cardInner}</div>
        ) : (
          <motion.div
            animate={config.animate}
            transition={{
              duration: 1.8,
              repeat: Infinity,
              repeatDelay: 0.6,
              ease: "easeInOut",
            }}
          >
            {cardInner}
          </motion.div>
        )}
        <span className="text-xs font-semibold text-foreground">
          {config.label}
        </span>
      </div>
    </div>
  );
}

function SpotlightTourPortal({
  steps,
  ariaLabel,
  onComplete,
  onSkip,
  onStepChange,
}: Omit<SpotlightTourProps, "isOpen">): JSX.Element {
  const reducedMotion = usePrefersReducedMotion();
  const [stepIndex, setStepIndex] = useState(0);

  const safeIndex = Math.min(stepIndex, Math.max(0, steps.length - 1));
  const currentStep = steps[safeIndex];
  const isFirstStep = safeIndex === 0;
  const isLastStep = safeIndex === steps.length - 1;

  const dialogRef = useRef<HTMLDivElement | null>(null);
  const primaryButtonRef = useRef<HTMLButtonElement | null>(null);
  const targetElRef = useRef<HTMLElement | null>(null);

  const onCompleteRef = useRef(onComplete);
  const onSkipRef = useRef(onSkip);
  const onStepChangeRef = useRef(onStepChange);
  const currentStepRef = useRef(currentStep);

  useLayoutEffect(() => {
    onCompleteRef.current = onComplete;
    onSkipRef.current = onSkip;
    onStepChangeRef.current = onStepChange;
    currentStepRef.current = currentStep;
  });

  const targetKey = Array.isArray(currentStep.target)
    ? currentStep.target.join("||")
    : (currentStep.target ?? "");
  const stepId = currentStep.id;
  const stepPlacement = currentStep.placement ?? "auto";

  const maskId = useId();
  const labelId = useId();
  const titleId = useId();
  const descriptionId = useId();

  const [layout, setLayout] = useState<ComputedLayout>(() =>
    computeTourLayout(currentStep, null, null)
  );

  const handleNext = useCallback(() => {
    if (safeIndex >= steps.length - 1) {
      onCompleteRef.current();
      return;
    }
    setStepIndex((prev) => Math.min(prev + 1, steps.length - 1));
  }, [safeIndex, steps.length]);

  const handleBack = useCallback(() => {
    setStepIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const handleSkip = useCallback(() => {
    onSkipRef.current();
  }, []);

  // Notify caller when active step changes
  useEffect(() => {
    onStepChangeRef.current?.(safeIndex, currentStepRef.current);
  }, [safeIndex, stepId]);

  // Prevent pull-to-refresh / overscroll chaining on the background document while open
  useEffect(() => {
    const root = document.documentElement;
    const prevOverscrollY = root.style.overscrollBehaviorY;
    root.style.overscrollBehaviorY = "none";
    return () => {
      root.style.overscrollBehaviorY = prevOverscrollY;
    };
  }, []);

  // Save focus on open, move focus into dialog, restore focus on close
  useEffect(() => {
    const previouslyFocused =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;

    const focusTarget = primaryButtonRef.current ?? dialogRef.current;
    if (focusTarget) {
      try {
        focusTarget.focus({ preventScroll: true });
      } catch {
        focusTarget.focus();
      }
    }

    return () => {
      if (previouslyFocused && document.contains(previouslyFocused)) {
        try {
          previouslyFocused.focus({ preventScroll: true });
        } catch {
          previouslyFocused.focus();
        }
      }
    };
  }, []);

  // Locate target, scroll into view, and measure spotlight & tooltip layout
  useLayoutEffect(() => {
    let rafId: number | null = null;
    let settleTimerId: number | null = null;
    let lateSettleTimerId: number | null = null;

    const measure = () => {
      const step = currentStepRef.current;
      const targetEl = findVisibleTarget(step.target);
      targetElRef.current = targetEl;
      const next = computeTourLayout(step, targetEl, dialogRef.current);
      setLayout((prev) => (isSameLayout(prev, next) ? prev : next));
    };

    const scheduleMeasure = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        measure();
      });
    };

    const initialTarget = findVisibleTarget(currentStepRef.current.target);
    targetElRef.current = initialTarget;

    let didScroll = false;
    if (
      initialTarget &&
      typeof initialTarget.scrollIntoView === "function" &&
      !isFixedOrStickyElement(initialTarget)
    ) {
      const { width: vw, height: vh } = getViewportSize();
      const targetRect = initialTarget.getBoundingClientRect();
      const isMobileViewport = vw < 768;
      const isTallMobileTarget =
        isMobileViewport && targetRect.height > Math.min(180, vh * 0.3);
      const scrollBlock: ScrollLogicalPosition = isTallMobileTarget
        ? "start"
        : "center";
      didScroll = true;
      try {
        initialTarget.scrollIntoView({
          behavior: reducedMotion ? "auto" : "smooth",
          block: scrollBlock,
          inline: "nearest",
        });
      } catch {
        initialTarget.scrollIntoView();
      }
    }

    measure();

    if (didScroll && !reducedMotion) {
      settleTimerId = window.setTimeout(measure, 320);
      lateSettleTimerId = window.setTimeout(measure, 550);
    }

    window.addEventListener("resize", scheduleMeasure, { passive: true });
    window.addEventListener("scroll", scheduleMeasure, {
      passive: true,
      capture: true,
    });
    window.addEventListener("scrollend", scheduleMeasure, { passive: true });

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(scheduleMeasure);
      if (initialTarget) {
        resizeObserver.observe(initialTarget);
      }
      if (dialogRef.current) {
        resizeObserver.observe(dialogRef.current);
      }
    }

    return () => {
      if (rafId !== null) {
        window.cancelAnimationFrame(rafId);
      }
      if (settleTimerId !== null) {
        window.clearTimeout(settleTimerId);
      }
      if (lateSettleTimerId !== null) {
        window.clearTimeout(lateSettleTimerId);
      }
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("scroll", scheduleMeasure, true);
      window.removeEventListener("scrollend", scheduleMeasure);
      resizeObserver?.disconnect();
    };
  }, [stepId, targetKey, stepPlacement, reducedMotion]);

  // Capture-phase window keyboard handler: navigate tour, trap Tab, block page shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
        onSkipRef.current();
        return;
      }

      if (e.key === "ArrowRight") {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (safeIndex >= steps.length - 1) {
          onCompleteRef.current();
        } else {
          setStepIndex((prev) => Math.min(prev + 1, steps.length - 1));
        }
        return;
      }

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        e.stopImmediatePropagation();
        if (safeIndex > 0) {
          setStepIndex((prev) => Math.max(prev - 1, 0));
        }
        return;
      }

      if (e.key === "ArrowUp" || e.key === "i" || e.key === "I") {
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      if (e.key === " " || e.key === "Spacebar" || e.code === "Space") {
        const dialog = dialogRef.current;
        const active = document.activeElement;
        const isFocusedTourButton =
          active instanceof HTMLButtonElement &&
          Boolean(dialog?.contains(active)) &&
          e.target instanceof Node &&
          Boolean(dialog?.contains(e.target));

        if (!isFocusedTourButton) {
          e.preventDefault();
          e.stopImmediatePropagation();
        }
        return;
      }

      if (e.key === "Tab") {
        const dialog = dialogRef.current;
        if (!dialog) return;

        const focusables = Array.from(
          dialog.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        );
        if (focusables.length === 0) {
          e.preventDefault();
          dialog.focus();
          return;
        }

        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;

        if (e.shiftKey) {
          if (!dialog.contains(active) || active === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (!dialog.contains(active) || active === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [safeIndex, steps.length]);

  const swallowBackdropInteraction = (
    e: ReactMouseEvent | ReactPointerEvent
  ) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDialogKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === " " || e.key === "Spacebar" || e.code === "Space") {
      e.stopPropagation();
    }
  };

  const progress = (safeIndex + 1) / steps.length;
  const nextButtonLabel =
    currentStep.nextLabel ?? (isLastStep ? "Finish" : "Next");

  const stepBody = (
    <div className="flex flex-col gap-3">
      {/* Step Title & Description */}
      <div className="flex flex-col gap-1.5">
        <h2
          id={titleId}
          className="font-editorial text-xl sm:text-2xl font-normal leading-snug text-foreground"
        >
          {currentStep.title}
        </h2>
        <p
          id={descriptionId}
          className="text-sm leading-relaxed text-foreground-secondary"
        >
          {currentStep.description}
        </p>
      </div>

      {/* Subtle Gesture Demonstration */}
      {currentStep.gestureHint && (
        <GestureHintCue
          hint={currentStep.gestureHint}
          reducedMotion={reducedMotion}
        />
      )}

      {/* Optional Desktop-Only Keyboard Shortcut Hint */}
      {currentStep.shortcutHint && (
        <div
          data-testid="tour-shortcut-hint"
          className="hidden md:flex items-center gap-2 rounded-lg border border-border/80 bg-surface-secondary/60 px-3 py-1.5 text-xs text-foreground-secondary"
        >
          <span
            className="material-symbols-outlined text-[15px] text-primary shrink-0"
            aria-hidden="true"
          >
            keyboard
          </span>
          <span className="leading-snug">Keyboard shortcut</span>
          <kbd className="inline-flex min-w-[24px] items-center justify-center rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[11px] font-semibold text-foreground shadow-2xs">
            {currentStep.shortcutHint}
          </kbd>
          {currentStep.shortcutLabel && (
            <span className="font-medium text-foreground">
              {currentStep.shortcutLabel}
            </span>
          )}
        </div>
      )}
    </div>
  );

  const cardContent = (
    <div className="flex flex-col gap-4 p-5">
      {/* Top Row: Step progress + Skip */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          {currentStep.icon && (
            <span
              className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-secondary text-primary"
              aria-hidden="true"
            >
              <span className="material-symbols-outlined text-[17px]">
                {currentStep.icon}
              </span>
            </span>
          )}
          <span className="text-[11px] font-semibold uppercase tracking-widest text-foreground-secondary">
            Step {safeIndex + 1} of {steps.length}
          </span>
        </div>

        <button
          type="button"
          onClick={handleSkip}
          aria-label="Skip tutorial"
          className={`inline-flex min-h-[44px] min-w-[44px] -my-2 -mr-2 shrink-0 items-center justify-center rounded-full px-3 text-xs font-medium text-foreground-secondary hover:bg-surface-secondary hover:text-foreground transition-colors cursor-pointer touch-manipulation ${BUTTON_FOCUS_RING}`}
        >
          Skip
        </button>
      </div>

      {/* Progress Bar (transform-only scaling, never width animation) */}
      <div
        className="h-1 w-full overflow-hidden rounded-full bg-surface-secondary"
        aria-hidden="true"
      >
        <div
          className={`h-full w-full origin-left rounded-full bg-primary ${
            reducedMotion ? "" : "transition-transform duration-200 ease-out"
          }`}
          style={{ transform: `scaleX(${progress})` }}
        />
      </div>

      {/* Animated step body only — keeps buttons mounted so keyboard focus never drops across steps */}
      {reducedMotion ? (
        stepBody
      ) : (
        <motion.div
          key={currentStep.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: DURATION.micro,
            ease: EASING.easeOutCubic,
          }}
        >
          {stepBody}
        </motion.div>
      )}

      {/* Footer Actions */}
      <div className="flex items-center justify-end gap-2 pt-1">
        {!isFirstStep && (
          <button
            type="button"
            onClick={handleBack}
            className={`inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-full border border-border bg-surface px-4 text-xs font-semibold text-foreground hover:bg-surface-secondary transition-colors cursor-pointer touch-manipulation ${BUTTON_FOCUS_RING}`}
          >
            Back
          </button>
        )}
        <button
          ref={primaryButtonRef}
          type="button"
          onClick={handleNext}
          className={`inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-1.5 rounded-full bg-primary px-5 text-xs font-semibold tracking-wide text-primary-foreground hover:bg-primary-hover transition-colors shadow-xs cursor-pointer touch-manipulation ${BUTTON_FOCUS_RING}`}
        >
          <span>{nextButtonLabel}</span>
          {!isLastStep && (
            <span
              className="material-symbols-outlined text-[16px]"
              aria-hidden="true"
            >
              arrow_forward
            </span>
          )}
        </button>
      </div>
    </div>
  );

  return createPortal(
    <div
      className="fixed inset-0 z-[120] overscroll-none"
      data-testid="spotlight-tour-root"
      data-reduced-motion={reducedMotion ? "true" : "false"}
    >
      {/* Dimmed Backdrop / Spotlight Cutout Layer */}
      {layout.spotlight ? (
        <svg
          className="fixed inset-0 h-full w-full pointer-events-auto touch-none overscroll-none"
          aria-hidden="true"
          data-testid="spotlight-tour-mask"
          onClick={swallowBackdropInteraction}
          onPointerDown={swallowBackdropInteraction}
        >
          <defs>
            <mask id={maskId}>
              <rect x="0" y="0" width="100%" height="100%" fill="white" />
              <rect
                x={layout.spotlight.left}
                y={layout.spotlight.top}
                width={layout.spotlight.width}
                height={layout.spotlight.height}
                rx={14}
                ry={14}
                fill="black"
              />
            </mask>
          </defs>
          <rect
            x="0"
            y="0"
            width="100%"
            height="100%"
            fill="rgba(0, 0, 0, 0.72)"
            mask={`url(#${maskId})`}
          />
          {/* Outer theme accent halo */}
          <rect
            x={layout.spotlight.left}
            y={layout.spotlight.top}
            width={layout.spotlight.width}
            height={layout.spotlight.height}
            rx={14}
            ry={14}
            fill="none"
            stroke="var(--primary)"
            strokeOpacity="0.48"
            strokeWidth="7"
          />
          {/* High-contrast dual-theme border (crisp bright ring in light mode, sage-bright focus ring in dark mode) */}
          <rect
            x={layout.spotlight.left}
            y={layout.spotlight.top}
            width={layout.spotlight.width}
            height={layout.spotlight.height}
            rx={14}
            ry={14}
            fill="none"
            data-testid="spotlight-tour-ring"
            className="stroke-white/90 dark:stroke-focus"
            strokeWidth="2.5"
          />
        </svg>
      ) : (
        <div
          className="fixed inset-0 pointer-events-auto touch-none overscroll-none"
          style={{ backgroundColor: "rgba(0, 0, 0, 0.72)" }}
          aria-hidden="true"
          data-testid="spotlight-tour-backdrop"
          onClick={swallowBackdropInteraction}
          onPointerDown={swallowBackdropInteraction}
        />
      )}

      {/* Positioned Tooltip Dialog (transform-only placement, never animating top/left/width/height) */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={`${labelId} ${titleId}`}
        aria-describedby={descriptionId}
        tabIndex={-1}
        onKeyDown={handleDialogKeyDown}
        data-testid="spotlight-tour-dialog"
        data-tour-step={currentStep.id}
        data-tour-placement={layout.resolvedPlacement}
        className="fixed top-0 left-0 z-[122] pointer-events-auto max-h-[calc(100dvh-28px)] overflow-y-auto overscroll-contain touch-pan-y rounded-2xl border border-border bg-surface text-foreground shadow-2xl focus:outline-none"
        style={{
          width: `${layout.tooltipWidth}px`,
          maxWidth: "calc(100% - 24px)",
          transform: `translate3d(${layout.tooltipX}px, ${layout.tooltipY}px, 0)`,
        }}
      >
        <span id={labelId} className="sr-only">
          {ariaLabel}
        </span>
        <div className="sr-only" aria-live="polite" aria-atomic="true">
          {`Step ${safeIndex + 1} of ${steps.length}: ${currentStep.title}`}
        </div>

        {cardContent}
      </div>
    </div>,
    document.body
  );
}

export default function SpotlightTour(
  props: SpotlightTourProps
): JSX.Element | null {
  if (!props.isOpen || props.steps.length === 0 || typeof document === "undefined") {
    return null;
  }

  return (
    <SpotlightTourPortal
      steps={props.steps}
      ariaLabel={props.ariaLabel}
      onComplete={props.onComplete}
      onSkip={props.onSkip}
      onStepChange={props.onStepChange}
    />
  );
}
