import type { MouseEventHandler, ReactNode } from "react";
import { motion } from "framer-motion";
import {
  ACTION_FEEDBACK,
  EASING,
  usePrefersReducedMotion,
  type ActionStatus,
} from "../../lib/motion";

export interface ActionButtonProps {
  /** Caller-controlled UI status; ActionButton never triggers API work on its own. */
  status?: ActionStatus;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  type?: "button" | "submit" | "reset";
  disabled?: boolean;
  className?: string;
  confirmedClassName?: string;
  errorClassName?: string;
  pendingClassName?: string;
  children: ReactNode;
  pendingContent?: ReactNode;
  confirmedContent?: ReactNode;
  errorContent?: ReactNode;
  /** Enforces >=44px mobile touch height unless caller passes explicit override. */
  enforceTouchTarget?: boolean;
  /** Renders a one-shot ring flash strictly on "confirmed" (never while "pending"). */
  showConfirmedPulse?: boolean;
  ariaLabel?: string;
  title?: string;
  dataTestId?: string;
}

/**
 * Reusable action button separating immediate press acknowledgment (~100ms),
 * pending wait state, post-confirmation pulse, and distinct error feedback.
 */
export function ActionButton({
  status = "idle",
  onClick,
  type = "button",
  disabled = false,
  className = "",
  confirmedClassName = "",
  errorClassName = "",
  pendingClassName = "",
  children,
  pendingContent,
  confirmedContent,
  errorContent,
  enforceTouchTarget = true,
  showConfirmedPulse = true,
  ariaLabel,
  title,
  dataTestId,
}: ActionButtonProps) {
  const shouldReduceMotion = usePrefersReducedMotion();
  const isBusy = status === "pending";
  const isDisabled = disabled || isBusy;

  const statusClasses =
    status === "confirmed"
      ? confirmedClassName
      : status === "error"
      ? errorClassName
      : status === "pending"
      ? pendingClassName
      : "";

  const baseTouchClass = enforceTouchTarget ? "min-h-11" : "";

  const content =
    status === "pending" && pendingContent !== undefined
      ? pendingContent
      : status === "confirmed" && confirmedContent !== undefined
      ? confirmedContent
      : status === "error" && errorContent !== undefined
      ? errorContent
      : children;

  const buttonAnimate = shouldReduceMotion
    ? { scale: 1, x: 0 }
    : status === "confirmed"
    ? { scale: ACTION_FEEDBACK.confirmedPulse.scale, x: 0 }
    : status === "error"
    ? { x: ACTION_FEEDBACK.errorShake.x, scale: 1 }
    : { scale: 1, x: 0 };

  const buttonTransition = shouldReduceMotion
    ? { duration: 0 }
    : status === "confirmed"
    ? ACTION_FEEDBACK.confirmedPulse.transition
    : status === "error"
    ? ACTION_FEEDBACK.errorShake.transition
    : ACTION_FEEDBACK.tapTransition;

  return (
    <motion.button
      type={type}
      onClick={onClick}
      disabled={isDisabled}
      aria-busy={isBusy || undefined}
      aria-label={ariaLabel}
      title={title}
      data-testid={dataTestId}
      data-action-status={status}
      whileTap={!isDisabled && !shouldReduceMotion ? ACTION_FEEDBACK.tap : undefined}
      animate={buttonAnimate}
      transition={buttonTransition}
      className={`relative overflow-hidden ${baseTouchClass} ${className} ${statusClasses}`.trim()}
    >
      {status === "confirmed" && showConfirmedPulse && !shouldReduceMotion && (
        <motion.span
          data-testid="action-confirmed-pulse"
          aria-hidden="true"
          initial={{ opacity: 0.45, scale: 0.96 }}
          animate={{ opacity: 0, scale: 1.08 }}
          transition={{ duration: 0.42, ease: EASING.easeOutCubic }}
          className="pointer-events-none absolute inset-0 rounded-[inherit] ring-2 ring-primary/50"
        />
      )}
      {content}
    </motion.button>
  );
}

export default ActionButton;
