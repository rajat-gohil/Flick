import React, { useEffect, useRef, useCallback, useState } from "react";
import { motion } from "framer-motion";
import { Share2 } from "lucide-react";
import { ActionButton } from "../motion/ActionButton";
import { IconTransition } from "../motion/IconTransition";
import { SHARED_LAYOUT_SPRING, MASK_REVEAL, type ActionStatus } from "../../lib/motion";
import StreamingOptions from "../StreamingOptions";
import SalonPassShareModal from "./SalonPassShareModal";
import { resolveMatchStyle } from "../../lib/matchPresentation";

export interface MatchMovie {
  id: number;
  title: string;
  overview?: string;
  poster_url?: string;
  rating?: number;
  vote_count?: number;
  release_year?: number;
  trailer_url?: string;
  metadataStatus?: "pending" | "success" | "failed";
  superlike_attribution?: "none" | "host" | "guest" | "mutual" | "unknown";
  match_type?: "ordinary" | "superlike" | "mutual_superlike" | "unknown";
}

export interface CurtainCallMatchModalProps {
  matchedMovie: MatchMovie;
  renderMode: "full" | "reduced" | "minimal";
  shouldReduceMotion: boolean;
  userRole?: string | null;
  isWatchlisted: boolean;
  watchlistLoading: boolean;
  onToggleWatchlist: () => void;
  savedBurstId: number | null;
  watchlistStatus?: ActionStatus;
  watchlistError?: string | null;
  onDismiss: () => void;
  onEndSession: () => Promise<void>;
  endSessionLoading: boolean;
  sessionLocked: boolean;
  sessionEnded: boolean;
  onFetchMetadata: () => void;
  onTrailerClick?: () => void;
  sessionCode?: string;
  partnerNames?: string;
  onSharePassClick?: () => void;
  /** Session-level familiarity pacing: true for 2nd+ matches in the same session. */
  isRepeatMatch?: boolean;
}

export function CurtainCallMatchModal({
  matchedMovie,
  renderMode,
  shouldReduceMotion,
  userRole,
  isWatchlisted,
  watchlistLoading,
  onToggleWatchlist,
  savedBurstId,
  watchlistStatus,
  watchlistError = null,
  onDismiss,
  onEndSession,
  endSessionLoading,
  sessionLocked,
  sessionEnded,
  onFetchMetadata,
  onTrailerClick,
  sessionCode,
  partnerNames,
  onSharePassClick,
  isRepeatMatch = false,
}: CurtainCallMatchModalProps) {
  const [showSharePassModal, setShowSharePassModal] = useState(false);
  const [streamingProviders, setStreamingProviders] = useState<string[]>([]);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const isMinimal = renderMode === "minimal";
  const suppressMotion = shouldReduceMotion || isMinimal;
  const allowTheatricalFlourish = renderMode === "full" && !shouldReduceMotion && !isRepeatMatch;

  const styleTier = resolveMatchStyle(
    matchedMovie.superlike_attribution,
    matchedMovie.match_type
  );

  // Focus management: capture previous focus, set focus to modal, trap tab, restore on unmount
  useEffect(() => {
    previousActiveElementRef.current = document.activeElement as HTMLElement | null;

    // Move focus into the dialog
    if (dialogRef.current) {
      dialogRef.current.focus();
    }

    return () => {
      if (previousActiveElementRef.current && typeof previousActiveElementRef.current.focus === "function") {
        try {
          previousActiveElementRef.current.focus();
        } catch {
          // ignore potential focus restoration errors in detached containers
        }
      }
    };
  }, []);

  // Keyboard navigation & Focus Trap
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onDismiss();
        return;
      }

      if (e.key === "Tab") {
        if (!dialogRef.current) return;
        const focusableElements = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement || document.activeElement === dialogRef.current) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    },
    [onDismiss]
  );

  // Badge text, heading, and subtitle resolution
  let badgeLabel = "Consensus Reached";
  let headingTitle = "Film Selected";
  let subtitleText = "Both viewers expressed interest in this film.";

  if (styleTier === "antique_brass") {
    badgeLabel = "★ Mutual Super-Like ★";
    headingTitle = "Double Super-Like!";
    subtitleText = "Both viewers sent a Super-Like for this film!";
  } else if (styleTier === "amber") {
    badgeLabel = "★ Priority Selection ★";
    headingTitle = "Film Selected";
    subtitleText = "A Super-Like unlocked this film recommendation.";
  } else if (styleTier === "neutral") {
    badgeLabel = "Consensus Reached";
    headingTitle = "Film Selected";
    subtitleText = "Both viewers expressed interest in this film.";
  }

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-labelledby="curtain-call-title"
      tabIndex={-1}
      onKeyDown={handleKeyDown}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onDismiss();
        }
      }}
      className="fixed inset-0 z-50 bg-background/95 backdrop-blur-md overflow-y-auto overscroll-contain px-4 py-6 sm:p-6 sm:py-8 flex flex-col items-center outline-none"
    >
      {/* Prominent top-right Close button for instant dismissal & mobile navigation */}
      <button
        type="button"
        onClick={onDismiss}
        data-testid="curtain-call-close-btn"
        aria-label="Close match dialog"
        className="fixed top-3 right-3 sm:top-5 sm:right-5 z-50 size-10 rounded-full bg-surface-secondary/80 hover:bg-surface-secondary border border-border/60 text-foreground-secondary hover:text-foreground flex items-center justify-center transition-all cursor-pointer shadow-md active:scale-95 touch-manipulation"
      >
        <span className="material-symbols-outlined text-[20px]">close</span>
      </button>

      {/* Polite live region for assistive technologies */}
      <div aria-live="polite" className="sr-only">
        Mutual match found: {matchedMovie.title}
      </div>

      {/* Atmospheric Radial Spotlight (Static in repeat-match / reduced motion, omitted in Minimal Mode) */}
      {!isMinimal && (
        <motion.div
          aria-hidden="true"
          data-testid="match-theatre-spotlight"
          initial={suppressMotion || isRepeatMatch ? { opacity: 0.4 } : { opacity: 0, scale: 0.7 }}
          animate={{
            opacity: suppressMotion || isRepeatMatch ? 0.4 : [0.45, 0.75, 0.45],
            scale: suppressMotion || isRepeatMatch ? 1 : [0.95, 1.15, 0.95],
          }}
          transition={
            suppressMotion || isRepeatMatch
              ? { duration: 0.2 }
              : { duration: 4, repeat: Infinity, ease: "easeInOut" }
          }
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] sm:w-[480px] h-[340px] sm:h-[480px] rounded-full pointer-events-none -z-10"
          style={{
            background:
              styleTier === "antique_brass"
                ? "radial-gradient(circle, rgba(245, 158, 11, 0.28) 0%, rgba(217, 119, 6, 0.08) 50%, transparent 75%)"
                : styleTier === "amber"
                ? "radial-gradient(circle, rgba(245, 158, 11, 0.2) 0%, rgba(217, 119, 6, 0.06) 50%, transparent 75%)"
                : styleTier === "emerald"
                ? "radial-gradient(circle, rgba(16, 185, 129, 0.25) 0%, rgba(5, 150, 105, 0.08) 50%, transparent 75%)"
                : "radial-gradient(circle, rgba(255, 255, 255, 0.06) 0%, transparent 70%)",
          }}
        />
      )}

      <motion.div
        data-testid="match-presentation-card"
        initial={suppressMotion ? { opacity: 0 } : { opacity: 0, scale: 0.94, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={suppressMotion ? { duration: 0.15 } : SHARED_LAYOUT_SPRING}
        className="max-w-sm w-full my-auto flex flex-col py-1 relative z-10"
      >
        {/* Header with Badges */}
        <div className="text-center pt-0 mb-0.5">
          <span
            data-testid="match-stamp-badge"
            className={`text-[10px] font-semibold uppercase tracking-widest mb-0.5 inline-block ${
              styleTier === "antique_brass"
                ? "text-amber-400 font-bold"
                : styleTier === "amber"
                ? "text-amber-500"
                : styleTier === "emerald"
                ? "text-primary"
                : "text-foreground-secondary"
            }`}
          >
            {badgeLabel}
          </span>
          <h1
            id="curtain-call-title"
            className="font-editorial text-xl sm:text-2xl md:text-3xl font-semibold text-foreground tracking-tight mb-0.5"
          >
            {headingTitle}
          </h1>
          <p className="text-foreground-secondary text-[11px] sm:text-xs">
            {subtitleText}
          </p>

          {/* Attribution badge for priority interest */}
          {matchedMovie.superlike_attribution &&
            ["mutual", "host", "guest"].includes(matchedMovie.superlike_attribution) && (
              <div
                data-testid="match-attribution-badge"
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider mt-1.5 border ${
                  styleTier === "antique_brass"
                    ? "bg-amber-950/40 border-amber-500/50 text-amber-300"
                    : styleTier === "amber"
                    ? "bg-amber-950/30 border-amber-500/40 text-amber-400"
                    : "bg-surface-secondary border-border text-foreground-secondary"
                }`}
              >
                <span
                  className="material-symbols-outlined text-[13px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  star
                </span>
                <span>
                  {matchedMovie.superlike_attribution === "mutual"
                    ? "Mutual Priority Interest"
                    : matchedMovie.superlike_attribution === "host"
                    ? userRole === "host"
                      ? "Priority Interest (Your Selection)"
                      : "Priority Interest (Partner's Selection)"
                    : matchedMovie.superlike_attribution === "guest"
                    ? userRole === "guest"
                      ? "Priority Interest (Your Selection)"
                      : "Priority Interest (Partner's Selection)"
                    : ""}
                </span>
              </div>
            )}
        </div>

        {/* Theatrical Interlocking Ticket Pass (Omitted in Minimal Mode) */}
        {!isMinimal && (
          <div
            data-testid="theatrical-ticket-pass"
            className="relative w-full my-2 flex items-center justify-center overflow-hidden py-1 px-1"
          >
            {/* Soft 250ms amber projector light sweep (First match + Full Mode + !shouldReduceMotion ONLY) */}
            {allowTheatricalFlourish && (
              <motion.div
                data-testid="projector-light-sweep"
                aria-hidden="true"
                initial={{ x: "-100%", opacity: 0 }}
                animate={{ x: "200%", opacity: [0, 0.7, 0] }}
                transition={{ duration: 0.25, delay: 0.35, ease: "easeInOut" }}
                className="absolute inset-0 z-20 pointer-events-none bg-gradient-to-r from-transparent via-amber-400/40 to-transparent w-1/2 skew-x-[-20deg]"
              />
            )}

            {/* Ticket Pass Shell: Interlocking Left & Right Stubs */}
            <div className="flex items-center w-full max-w-[340px] justify-center relative">
              {/* Left Ticket Stub */}
              <motion.div
                data-testid="ticket-stub-left"
                initial={
                  renderMode === "full" && !shouldReduceMotion
                    ? { x: -140, opacity: 0 }
                    : { scale: 0.95, opacity: 0 }
                }
                animate={{ x: 0, scale: 1, opacity: 1 }}
                transition={
                  renderMode === "full" && !shouldReduceMotion
                    ? { type: "spring", stiffness: 380, damping: 22 }
                    : { duration: 0.2 }
                }
                className={`flex-1 flex items-center justify-center py-2 px-2.5 rounded-l-md border-y border-l text-[9px] sm:text-[10px] font-mono tracking-wider sm:tracking-widest relative overflow-hidden select-none border-dashed border-r-0 ${
                  styleTier === "antique_brass"
                    ? "bg-amber-500/15 dark:bg-[#181510] border-amber-500/60 text-amber-800 dark:text-amber-200 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                    : styleTier === "amber"
                    ? "bg-amber-500/10 dark:bg-[#19150e] border-amber-500/40 text-amber-800 dark:text-amber-300/90"
                    : styleTier === "emerald"
                    ? "bg-emerald-500/10 dark:bg-[#0d1712] border-emerald-500/30 text-emerald-800 dark:text-emerald-300/90"
                    : "bg-surface border-border text-foreground-secondary"
                }`}
              >
                {/* Outer notch */}
                <span
                  className="absolute -left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-background border-r border-border/40 pointer-events-none"
                  aria-hidden="true"
                />
                <span className="font-semibold truncate">ADMIT ONE · SCREENING A</span>
              </motion.div>

              {/* Center Blind-Embossed Cinema Society Seal */}
              <div
                data-testid="cinema-society-seal"
                className={`z-10 -mx-1.5 px-2 py-0.5 rounded-full border text-[7px] sm:text-[8px] font-bold tracking-wider uppercase shadow-md flex items-center gap-1 select-none shrink-0 ${
                  styleTier === "antique_brass"
                    ? "bg-gradient-to-r from-amber-600 via-amber-400 to-amber-600 border-amber-300 text-black font-extrabold shadow-[0_0_15px_rgba(245,158,11,0.45)]"
                    : styleTier === "amber"
                    ? "bg-amber-950/90 border-amber-500/60 text-amber-300"
                    : styleTier === "emerald"
                    ? "bg-emerald-950/90 border-emerald-500/50 text-emerald-300"
                    : "bg-surface-secondary border-border text-foreground-secondary"
                }`}
              >
                <span
                  className="material-symbols-outlined text-[10px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                  aria-hidden="true"
                >
                  {styleTier === "antique_brass" || styleTier === "amber" ? "stars" : "verified"}
                </span>
                <span>FLICK CINEMA SOCIETY · MUTUAL SELECTION</span>
              </div>

              {/* Right Ticket Stub */}
              <motion.div
                data-testid="ticket-stub-right"
                initial={
                  renderMode === "full" && !shouldReduceMotion
                    ? { x: 140, opacity: 0 }
                    : { scale: 0.95, opacity: 0 }
                }
                animate={{ x: 0, scale: 1, opacity: 1 }}
                transition={
                  renderMode === "full" && !shouldReduceMotion
                    ? { type: "spring", stiffness: 380, damping: 22 }
                    : { duration: 0.2 }
                }
                className={`flex-1 flex items-center justify-center py-2 px-2.5 rounded-r-md border-y border-r text-[9px] sm:text-[10px] font-mono tracking-wider sm:tracking-widest relative overflow-hidden select-none border-dashed border-l-0 ${
                  styleTier === "antique_brass"
                    ? "bg-amber-500/15 dark:bg-[#181510] border-amber-500/60 text-amber-800 dark:text-amber-200 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                    : styleTier === "amber"
                    ? "bg-amber-500/10 dark:bg-[#19150e] border-amber-500/40 text-amber-800 dark:text-amber-300/90"
                    : styleTier === "emerald"
                    ? "bg-emerald-500/10 dark:bg-[#0d1712] border-emerald-500/30 text-emerald-800 dark:text-emerald-300/90"
                    : "bg-surface border-border text-foreground-secondary"
                }`}
              >
                {/* Outer notch */}
                <span
                  className="absolute -right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-background border-l border-border/40 pointer-events-none"
                  aria-hidden="true"
                />
                <span className="font-semibold truncate">ADMIT ONE · SCREENING B</span>
              </motion.div>
            </div>
          </div>
        )}

        {/* Poster Stage */}
        <motion.div
          data-testid="match-poster-stage"
          initial={suppressMotion ? { opacity: 0 } : { opacity: 0, scale: 0.9, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={
            suppressMotion ? { duration: 0.15 } : { ...SHARED_LAYOUT_SPRING, delay: 0.06 }
          }
          className="relative w-full max-w-[120px] sm:max-w-[150px] md:max-w-[170px] aspect-[2/3] mx-auto my-1.5 sm:my-2 shrink-0"
        >
          {/* Back accent card (omitted in minimal mode) */}
          {!isMinimal && (
            <div className="absolute inset-0 -rotate-6 translate-x-2 -translate-y-2 rounded-2xl overflow-hidden shadow-lg border border-border bg-surface-secondary opacity-60">
              {matchedMovie.poster_url && (
                <img src={matchedMovie.poster_url} className="w-full h-full object-cover" alt="" />
              )}
            </div>
          )}

          {/* Front card with selective editorial curtain mask reveal */}
          <motion.div
            data-testid="match-poster-reveal"
            initial={suppressMotion ? MASK_REVEAL.reduced.initial : MASK_REVEAL.curtain.initial}
            animate={suppressMotion ? MASK_REVEAL.reduced.animate : MASK_REVEAL.curtain.animate}
            className={`absolute inset-0 rounded-2xl overflow-hidden shadow-2xl border-2 bg-surface z-10 ${
              isMinimal ? "" : "rotate-2"
            } ${
              styleTier === "antique_brass"
                ? "border-amber-500/70"
                : styleTier === "amber"
                ? "border-amber-500/50"
                : styleTier === "emerald"
                ? "border-primary/40"
                : "border-border"
            }`}
          >
            {matchedMovie.poster_url ? (
              <img
                src={matchedMovie.poster_url}
                className="w-full h-full object-cover"
                alt={matchedMovie.title}
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center bg-surface-secondary p-4 text-center">
                <span className="material-symbols-outlined text-foreground-secondary text-[40px]">
                  movie
                </span>
              </div>
            )}
          </motion.div>
        </motion.div>

        {/* Title & Metadata */}
        <div className="text-center mb-1.5">
          <h2 className="font-editorial text-base sm:text-lg md:text-xl font-bold text-foreground leading-snug mb-0.5">
            {matchedMovie.title}
          </h2>
          <div className="flex items-center justify-center gap-2 text-xs text-foreground-secondary">
            {matchedMovie.rating && (
              <span className="flex items-center gap-1 font-semibold text-foreground">
                <span
                  className="material-symbols-outlined text-primary text-[14px]"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  star
                </span>
                {matchedMovie.rating.toFixed(1)}
              </span>
            )}
            {matchedMovie.release_year && (
              <>
                <span>·</span>
                <span>{matchedMovie.release_year}</span>
              </>
            )}
          </div>
          {matchedMovie.metadataStatus === "pending" && (
            <span className="text-[10px] text-foreground-secondary animate-pulse mt-0.5 block">
              Loading film synopsis & details…
            </span>
          )}
          {matchedMovie.metadataStatus === "failed" && (
            <div className="flex items-center justify-center gap-1.5 mt-0.5">
              <span className="text-[10px] text-foreground-secondary">Basic title recorded.</span>
              <button
                type="button"
                onClick={onFetchMetadata}
                className="inline-flex items-center gap-0.5 text-[10px] text-primary hover:underline font-semibold cursor-pointer"
              >
                <span className="material-symbols-outlined text-[13px]">refresh</span>
                Retry details
              </button>
            </div>
          )}
        </div>

        {/* Action Suite (All 6 actions preserved with prerequisite rules) */}
        <div className="flex items-center justify-center gap-2 mb-2 w-full">
          {/* Action 1: Trailer (conditional on trailer_url) */}
          {matchedMovie.trailer_url && (
            <a
              href={matchedMovie.trailer_url}
              target="_blank"
              rel="noopener noreferrer"
              onClick={onTrailerClick}
              className="flex-1 flex items-center justify-center gap-1.5 py-1.5 sm:py-2 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground text-xs font-semibold uppercase tracking-wider transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-[16px]">play_circle</span>
              Trailer
            </a>
          )}

          {/* Action 2: Watchlist Toggle */}
          <ActionButton
            type="button"
            status={
              watchlistStatus ??
              (watchlistLoading
                ? "pending"
                : savedBurstId === matchedMovie.id
                ? "confirmed"
                : "idle")
            }
            onClick={onToggleWatchlist}
            disabled={watchlistLoading}
            showConfirmedPulse={!suppressMotion}
            confirmedClassName="border-primary bg-primary/10 text-primary"
            errorClassName="border-error/60 bg-error/10 text-error"
            title={watchlistError ?? undefined}
            className={`flex-1 flex items-center justify-center gap-1.5 min-h-11 py-1.5 sm:py-2 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-colors cursor-pointer ${
              isWatchlisted
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-surface hover:bg-surface-secondary text-foreground"
            }`}
          >
            <IconTransition
              iconKey={`${watchlistStatus ?? (watchlistLoading ? "pending" : isWatchlisted ? "saved" : "idle")}-${isWatchlisted}`}
              sizeClassName="size-4"
            >
              {watchlistStatus === "pending" || watchlistLoading ? (
                <span className="size-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <span
                  className="material-symbols-outlined text-[16px]"
                  style={{ fontVariationSettings: isWatchlisted ? "'FILL' 1" : undefined }}
                >
                  {watchlistStatus === "error" ? "error_outline" : "bookmark"}
                </span>
              )}
            </IconTransition>
            <span>
              {watchlistStatus === "pending" || watchlistLoading
                ? "Saving…"
                : watchlistStatus === "error"
                ? "Retry"
                : isWatchlisted
                ? "Saved"
                : "Save"}
            </span>
          </ActionButton>

          {/* Action 3: Share Theatrical Salon Pass */}
          <button
            type="button"
            onClick={() => {
              onSharePassClick?.();
              setShowSharePassModal(true);
            }}
            className="flex-1 flex items-center justify-center gap-1.5 py-1.5 sm:py-2 rounded-xl border border-primary/40 bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold uppercase tracking-wider transition-all active:scale-95 cursor-pointer"
            title="Generate & share Theatrical Salon Pass for Instagram Stories or WhatsApp"
          >
            <Share2 size={15} />
            <span>Pass</span>
          </button>
        </div>

        {watchlistError && (
          <p role="alert" className="w-full text-center text-[11px] font-medium text-error mb-2">
            {watchlistError}
          </p>
        )}

        {/* Action 4: Streaming Options Preview */}
        <div className="w-full mb-2 max-h-36 overflow-y-auto rounded-xl">
          <StreamingOptions
            movieId={matchedMovie.id}
            movieTitle={matchedMovie.title}
            onProvidersLoaded={setStreamingProviders}
          />
        </div>

        {/* Primary Action Buttons */}
        <div className="flex flex-col gap-2 w-full mt-1.5">
          {/* Action 5: Continue Screening Deck */}
          <button
            type="button"
            onClick={onDismiss}
            className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98] cursor-pointer touch-manipulation"
          >
            Continue Screening Deck
          </button>

          {/* Action 6: Conclude & View All Matches */}
          <button
            type="button"
            onClick={onEndSession}
            disabled={endSessionLoading || sessionLocked || sessionEnded}
            className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-all shadow-sm active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2 cursor-pointer touch-manipulation"
          >
            {endSessionLoading ? (
              <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
            ) : (
              "Conclude & View All Matches"
            )}
          </button>
        </div>

        {/* Theatrical Salon Pass Export Modal */}
        <SalonPassShareModal
          isOpen={showSharePassModal}
          onClose={() => setShowSharePassModal(false)}
          data={{
            movieTitle: matchedMovie.title,
            releaseYear: matchedMovie.release_year,
            rating: matchedMovie.rating,
            posterUrl: matchedMovie.poster_url,
            sessionCode,
            partnerNames,
            userRole,
            compatibilityScore:
              matchedMovie.match_type === "mutual_superlike"
                ? "100% Mutual Superlike"
                : matchedMovie.match_type === "superlike"
                ? "95% Superlike Harmony"
                : "92% Consensus Harmony",
            streamingProviders,
          }}
        />
      </motion.div>
    </div>
  );
}
