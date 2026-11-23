import React, { useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import StreamingOptions from "../StreamingOptions";

export type MatchPresentationStyle = "antique_brass" | "amber" | "emerald" | "neutral";

/**
 * Strict fail-closed resolution matching backend properties:
 * - 'mutual' + 'mutual_superlike' -> 'antique_brass'
 * - 'host' | 'guest' + 'superlike' -> 'amber'
 * - 'none' + 'ordinary' -> 'emerald'
 * - 'unknown' + 'unknown' or any contradictory mismatch -> 'neutral' (fail-closed)
 */
export function resolveMatchStyle(
  superlikeAttr?: string,
  matchType?: string
): MatchPresentationStyle {
  if (superlikeAttr === "mutual" && matchType === "mutual_superlike") {
    return "antique_brass";
  }
  if ((superlikeAttr === "host" || superlikeAttr === "guest") && matchType === "superlike") {
    return "amber";
  }
  if (superlikeAttr === "none" && matchType === "ordinary") {
    return "emerald";
  }
  return "neutral";
}

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
  onDismiss: () => void;
  onEndSession: () => Promise<void>;
  endSessionLoading: boolean;
  sessionLocked: boolean;
  sessionEnded: boolean;
  onFetchMetadata: () => void;
  onTrailerClick?: () => void;
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
  onDismiss,
  onEndSession,
  endSessionLoading,
  sessionLocked,
  sessionEnded,
  onFetchMetadata,
  onTrailerClick,
}: CurtainCallMatchModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousActiveElementRef = useRef<HTMLElement | null>(null);
  const isMinimal = renderMode === "minimal";
  const suppressMotion = shouldReduceMotion || isMinimal;

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
      className="fixed inset-0 z-50 bg-[#0D0F0D]/96 backdrop-blur-md overflow-y-auto overscroll-contain px-4 py-6 sm:p-6 sm:py-8 flex flex-col items-center outline-none"
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

      {/* Atmospheric Radial Spotlight (Omitted in Minimal Mode) */}
      {!isMinimal && (
        <motion.div
          aria-hidden="true"
          data-testid="match-theatre-spotlight"
          initial={suppressMotion ? { opacity: 0.4 } : { opacity: 0, scale: 0.7 }}
          animate={{
            opacity: suppressMotion ? 0.4 : [0.45, 0.75, 0.45],
            scale: suppressMotion ? 1 : [0.95, 1.15, 0.95],
          }}
          transition={
            suppressMotion
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

      <div className="max-w-sm w-full my-auto flex flex-col py-1 relative z-10">
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
            {/* Soft 250ms amber projector light sweep (Full Mode + !shouldReduceMotion ONLY) */}
            {renderMode === "full" && !shouldReduceMotion && (
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
                    ? "bg-[#181510] border-amber-500/60 text-amber-200 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                    : styleTier === "amber"
                    ? "bg-[#19150e] border-amber-500/40 text-amber-300/90"
                    : styleTier === "emerald"
                    ? "bg-[#0d1712] border-emerald-500/30 text-emerald-300/90"
                    : "bg-surface border-border text-foreground-secondary"
                }`}
              >
                {/* Outer notch */}
                <span
                  className="absolute -left-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-[#0D0F0D] border-r border-border/40 pointer-events-none"
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
                    ? "bg-[#181510] border-amber-500/60 text-amber-200 shadow-[0_0_12px_rgba(245,158,11,0.2)]"
                    : styleTier === "amber"
                    ? "bg-[#19150e] border-amber-500/40 text-amber-300/90"
                    : styleTier === "emerald"
                    ? "bg-[#0d1712] border-emerald-500/30 text-emerald-300/90"
                    : "bg-surface border-border text-foreground-secondary"
                }`}
              >
                {/* Outer notch */}
                <span
                  className="absolute -right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-[#0D0F0D] border-l border-border/40 pointer-events-none"
                  aria-hidden="true"
                />
                <span className="font-semibold truncate">ADMIT ONE · SCREENING B</span>
              </motion.div>
            </div>
          </div>
        )}

        {/* Poster Stage */}
        <div
          data-testid="match-poster-stage"
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

          {/* Front card */}
          <div
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
          </div>
        </div>

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
          <button
            type="button"
            onClick={onToggleWatchlist}
            disabled={watchlistLoading}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 sm:py-2 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all relative overflow-hidden cursor-pointer ${
              isWatchlisted
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-surface hover:bg-surface-secondary text-foreground"
            }`}
          >
            {savedBurstId === matchedMovie.id && !suppressMotion && (
              <span
                className="absolute inset-0 bg-primary/25 animate-ping pointer-events-none rounded-xl"
                aria-hidden="true"
              />
            )}
            <span
              className="material-symbols-outlined text-[16px]"
              style={{ fontVariationSettings: isWatchlisted ? "'FILL' 1" : undefined }}
            >
              bookmark
            </span>
            <span>{isWatchlisted ? "Saved" : "Save"}</span>
          </button>
        </div>

        {/* Action 3: Streaming Options Preview */}
        <div className="w-full mb-2 max-h-36 overflow-y-auto rounded-xl">
          <StreamingOptions movieId={matchedMovie.id} movieTitle={matchedMovie.title} />
        </div>

        {/* Primary Action Buttons */}
        <div className="flex flex-col gap-2 w-full mt-1.5">
          {/* Action 4: Continue Screening Deck */}
          <button
            type="button"
            onClick={onDismiss}
            className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98] cursor-pointer touch-manipulation"
          >
            Continue Screening Deck
          </button>

          {/* Action 5: Conclude & View All Matches */}
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
      </div>
    </div>
  );
}
