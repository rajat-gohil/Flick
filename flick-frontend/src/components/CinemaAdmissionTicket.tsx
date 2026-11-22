import React, { useRef, useState, useCallback, useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { usePrefersReducedMotion } from "../lib/motion";

interface CinemaAdmissionTicketProps {
  onLaunch: () => void;
  onExplore?: () => void;
  className?: string;
}

export default function CinemaAdmissionTicket({
  onLaunch,
  onExplore,
  className = "",
}: CinemaAdmissionTicketProps) {
  const isReduced = usePrefersReducedMotion();
  const cardRef = useRef<HTMLDivElement>(null);
  const [isActive, setIsActive] = useState(false);
  const isActiveRef = useRef(false);

  // Normalized position (-1 to 1) for 3D tilt
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Position percentage (0% to 100%) for specular highlight
  const [sheenPos, setSheenPos] = useState({ x: 50, y: 50 });

  // Damped spring physics for weight and physical card feel
  const springConfig = { damping: 20, stiffness: 150, mass: 0.7 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  // Expressive but controlled tilt: max ±7° on X, ±8° on Y
  const rotateX = useTransform(smoothY, [-1, 1], [7, -7]);
  const rotateY = useTransform(smoothX, [-1, 1], [-8, 8]);

  // Keep ref in sync for event listeners
  useEffect(() => {
    isActiveRef.current = isActive;
  }, [isActive]);

  const updateCoordinates = useCallback(
    (clientX: number, clientY: number) => {
      if (isReduced) return;
      const el = cardRef.current;
      if (!el) return;

      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;

      const relativeX = clientX - rect.left;
      const relativeY = clientY - rect.top;

      // Normalized -1 to 1 for tilt
      const normX = (relativeX / rect.width) * 2 - 1;
      const normY = (relativeY / rect.height) * 2 - 1;

      mouseX.set(Math.max(-1, Math.min(1, normX)));
      mouseY.set(Math.max(-1, Math.min(1, normY)));

      // Sheen percentage
      const pctX = Math.max(0, Math.min(100, (relativeX / rect.width) * 100));
      const pctY = Math.max(0, Math.min(100, (relativeY / rect.height) * 100));
      setSheenPos({ x: pctX, y: pctY });
      setIsActive(true);
    },
    [isReduced, mouseX, mouseY]
  );

  const resetCoordinates = useCallback(() => {
    mouseX.set(0);
    mouseY.set(0);
    setIsActive(false);
  }, [mouseX, mouseY]);

  // Pointer events (Desktop mouse / stylus)
  const handlePointerDown = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      updateCoordinates(e.clientX, e.clientY);
    },
    [updateCoordinates]
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      updateCoordinates(e.clientX, e.clientY);
    },
    [updateCoordinates]
  );

  const handlePointerLeave = useCallback(() => {
    resetCoordinates();
  }, [resetCoordinates]);

  // Touch events (Mobile touchscreens)
  const handleTouchStart = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      const touch = e.touches[0];
      if (touch) {
        updateCoordinates(touch.clientX, touch.clientY);
      }
    },
    [updateCoordinates]
  );

  const handleTouchMove = useCallback(
    (e: React.TouchEvent<HTMLDivElement>) => {
      const touch = e.touches[0];
      if (touch) {
        updateCoordinates(touch.clientX, touch.clientY);
      }
    },
    [updateCoordinates]
  );

  const handleTouchEnd = useCallback(() => {
    resetCoordinates();
  }, [resetCoordinates]);

  // Gyroscope ambient response for mobile devices when not actively touching
  useEffect(() => {
    if (isReduced) return;
    if (typeof window === "undefined") return;

    const handleOrientation = (e: DeviceOrientationEvent) => {
      if (isActiveRef.current) return;
      if (e.gamma === null || e.beta === null) return;

      // Natural resting phone angle: beta ~ 35deg. Gamma: -30 to 30deg
      const normX = Math.max(-0.8, Math.min(0.8, e.gamma / 22));
      const normY = Math.max(-0.8, Math.min(0.8, (e.beta - 38) / 22));

      mouseX.set(normX);
      mouseY.set(normY);
      setSheenPos({
        x: 50 + normX * 35,
        y: 50 + normY * 35,
      });
      setIsActive(true);
    };

    if ("DeviceOrientationEvent" in window) {
      window.addEventListener("deviceorientation", handleOrientation, { passive: true });
      return () => window.removeEventListener("deviceorientation", handleOrientation);
    }
  }, [isReduced, mouseX, mouseY]);

  return (
    <div
      style={{
        perspective: 1200,
        WebkitPerspective: 1200,
        touchAction: "pan-y",
      }}
      className={`relative w-full max-w-xl select-none ${className}`}
    >
      <motion.div
        ref={cardRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        onTouchCancel={handleTouchEnd}
        style={{
          rotateX: isReduced ? 0 : rotateX,
          rotateY: isReduced ? 0 : rotateY,
          transformStyle: "preserve-3d",
          WebkitTransformStyle: "preserve-3d",
        }}
        className="relative w-full rounded-2xl border border-border/90 bg-[#FBF9F4] dark:bg-[#222721] text-foreground shadow-lg overflow-hidden transition-shadow duration-300 hover:shadow-xl active:shadow-md cursor-grab active:cursor-grabbing"
      >
        {/* Subtle Tactile Paper Texture (SVG noise overlay) */}
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none opacity-[0.035] dark:opacity-[0.05] mix-blend-multiply dark:mix-blend-screen bg-repeat z-0"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          }}
        />

        {/* Specular Light Reflection (reactive to finger touch and cursor) */}
        {!isReduced && (
          <div
            aria-hidden="true"
            className={`absolute inset-0 pointer-events-none transition-opacity duration-300 z-20 ${
              isActive ? "opacity-100" : "opacity-0"
            }`}
            style={{
              background: `radial-gradient(circle 260px at ${sheenPos.x}% ${sheenPos.y}%, rgba(255, 255, 255, 0.42) 0%, rgba(216, 194, 157, 0.22) 38%, rgba(255, 255, 255, 0) 70%)`,
            }}
          />
        )}

        {/* Ticket Outer Border Rules (Letterpress Double Framing) */}
        <div
          aria-hidden="true"
          className="absolute inset-1.5 rounded-[12px] border border-border/50 pointer-events-none z-10"
        />

        {/* ── Two-Part Ticket Composition ── */}
        <div
          style={{ transformStyle: "preserve-3d", WebkitTransformStyle: "preserve-3d" }}
          className="relative z-10 flex flex-row items-stretch min-h-[210px] sm:min-h-[240px]"
        >
          {/* ══════════════════════════════════════════════════════
              PART 1 — MAIN BODY (approx 74% desktop, 78% mobile)
          ══════════════════════════════════════════════════════ */}
          <div
            style={{ transform: "translateZ(4px)" }}
            className="flex-1 min-w-0 p-4 sm:p-7 flex flex-col justify-between pr-3 sm:pr-6"
          >
            {/* Header: Issuer Mark & Salon */}
            <div className="flex items-center justify-between gap-1.5 border-b border-border/60 pb-2.5 sm:pb-3">
              <div className="flex items-center gap-1.5 sm:gap-2 min-w-0">
                <span
                  className="material-symbols-outlined text-[14px] sm:text-[15px] text-primary shrink-0"
                  style={{ fontVariationSettings: "'FILL' 1" }}
                >
                  theaters
                </span>
                <span className="font-mono text-[9px] sm:text-[11px] font-bold tracking-wider sm:tracking-widest uppercase text-foreground/90 truncate">
                  FLICK CINEMA SOCIETY
                </span>
              </div>
              <span className="font-mono text-[8px] sm:text-[10px] font-semibold tracking-wider sm:tracking-widest uppercase text-[#8F754F] dark:text-[#C5A880] px-1.5 sm:px-2 py-0.5 rounded border border-[#8F754F]/30 dark:border-[#C5A880]/30 bg-[#8F754F]/5 dark:bg-[#C5A880]/10 shrink-0">
                SALON NO. 04
              </span>
            </div>

            {/* Middle Narrative: Invitation & Discovery */}
            <div
              style={{ transform: "translateZ(8px)" }}
              className="py-3 sm:py-4 space-y-1 sm:space-y-1.5"
            >
              <h2 className="font-editorial text-xl sm:text-3xl font-semibold text-foreground tracking-tight leading-tight">
                An Invitation to the Movies
              </h2>
              <p className="font-serif italic text-xs sm:text-sm text-foreground-secondary leading-snug">
                Admit Two. One shared discovery.
              </p>
            </div>

            {/* Lower Section: Action Callout & Launch Button */}
            <div className="pt-1.5 sm:pt-2 space-y-2 sm:space-y-2.5">
              <div className="flex items-center gap-1.5 sm:gap-2">
                <span className="size-1.5 rounded-full bg-primary inline-block shrink-0" />
                <span className="font-mono text-[8px] sm:text-[10px] uppercase tracking-wider sm:tracking-widest text-foreground-secondary/80 font-medium truncate">
                  YOUR NEXT SCREENING BEGINS HERE.
                </span>
              </div>

              <div
                style={{ transform: "translateZ(14px)" }}
                className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 sm:gap-3"
              >
                <div className="relative group w-full sm:w-auto">
                  {!isReduced && (
                    <motion.div
                      aria-hidden="true"
                      animate={{
                        opacity: [0.35, 0.7, 0.35],
                        scale: [0.98, 1.03, 0.98],
                      }}
                      transition={{
                        duration: 4,
                        repeat: Infinity,
                        ease: "easeInOut",
                      }}
                      className="absolute -inset-1 rounded-2xl bg-primary/25 blur-md pointer-events-none -z-10"
                    />
                  )}
                  <button
                    type="button"
                    data-tour="home-launch-deck"
                    onClick={onLaunch}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl min-h-[44px] h-11 sm:h-12 px-4 sm:px-6 bg-primary hover:bg-primary-hover text-surface font-semibold text-[11px] sm:text-xs uppercase tracking-wider shadow-sm transition-all active:scale-[0.98] cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/50 focus:ring-offset-1 focus:ring-offset-surface whitespace-nowrap"
                  >
                    <span className="material-symbols-outlined text-[16px] sm:text-[17px]">
                      confirmation_number
                    </span>
                    LAUNCH SCREENING DECK
                  </button>
                </div>

                {onExplore && (
                  <button
                    type="button"
                    data-tour="home-explore-catalogue"
                    onClick={onExplore}
                    className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 rounded-xl min-h-[40px] h-10 sm:h-12 px-3 sm:px-4 border border-border/80 hover:border-primary/50 bg-surface/60 hover:bg-surface text-foreground font-semibold text-[11px] sm:text-xs uppercase tracking-wider transition-all active:scale-[0.98] cursor-pointer whitespace-nowrap"
                  >
                    <span className="material-symbols-outlined text-[15px] sm:text-[16px] text-foreground-secondary">
                      explore
                    </span>
                    Explore Catalogue
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* ══════════════════════════════════════════════════════
              DIVIDER — PERFORATION & 35MM SPROCKET NOTCHES
          ══════════════════════════════════════════════════════ */}
          <div className="relative w-5 sm:w-8 shrink-0 flex flex-col items-center justify-between py-1">
            {/* Top Scallop Cutout (circular notch cut into ticket) */}
            <div
              aria-hidden="true"
              className="absolute -top-2.5 sm:-top-3 left-1/2 -translate-x-1/2 size-4 sm:size-6 rounded-full bg-background border-b border-border/80 z-20"
            />

            {/* Vertical Perforation Line with 35mm Celluloid Sprockets */}
            <div className="w-full flex-1 flex flex-col items-center justify-around my-3 py-1">
              {Array.from({ length: 6 }).map((_, idx) => (
                <div
                  key={idx}
                  aria-hidden="true"
                  className="w-1 sm:w-1.5 h-2.5 sm:h-3 rounded-[1px] bg-background/90 dark:bg-background/80 border border-border/60 my-0.5 shrink-0"
                  title="35mm perforation"
                />
              ))}
            </div>

            {/* Bottom Scallop Cutout */}
            <div
              aria-hidden="true"
              className="absolute -bottom-2.5 sm:-bottom-3 left-1/2 -translate-x-1/2 size-4 sm:size-6 rounded-full bg-background border-t border-border/80 z-20"
            />
          </div>

          {/* ══════════════════════════════════════════════════════
              PART 2 — DETACHABLE STUB (compact on mobile, ~22%)
          ══════════════════════════════════════════════════════ */}
          <div
            style={{ transform: "translateZ(6px)" }}
            className="w-14 sm:w-28 shrink-0 bg-surface-secondary/35 dark:bg-surface-secondary/20 p-2 sm:p-4 flex flex-col items-center justify-between border-l border-dashed border-border/70 relative"
          >
            {/* Blind-Embossed Issuer Mark */}
            <div
              aria-hidden="true"
              className="size-7 sm:size-9 rounded-full border border-border/80 flex items-center justify-center text-foreground-secondary/70 shadow-2xs bg-surface/50 mt-0.5 sm:mt-1"
            >
              <span className="material-symbols-outlined text-[13px] sm:text-[16px] text-primary/80">
                movie
              </span>
            </div>

            {/* Vertical Stub Typography */}
            <div className="my-auto py-2 flex flex-col items-center justify-center text-center">
              <span className="font-mono text-[7px] sm:text-[10px] uppercase tracking-widest text-foreground-secondary font-semibold [writing-mode:vertical-rl] rotate-180 select-none whitespace-nowrap">
                ONE SHARED SCREENING
              </span>
            </div>

            {/* Issue Number in Muted Antique Brass */}
            <div className="text-center pb-0.5 sm:pb-1">
              <span className="block font-mono text-[7px] sm:text-[8px] uppercase tracking-wider text-foreground-secondary/60">
                STAMP
              </span>
              <span className="font-mono text-[9px] sm:text-[11px] font-bold text-[#8F754F] dark:text-[#C5A880] tracking-wider whitespace-nowrap">
                ISSUE 004
              </span>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
