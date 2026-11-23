import React, { useRef, useState, useCallback, useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { usePrefersReducedMotion } from "../lib/motion";

interface CinemaSalonPassProps {
  joinCode: string;
  setJoinCode: (code: string) => void;
  onJoin: () => void;
  loading: boolean;
  error?: string | null;
  className?: string;
}

export default function CinemaSalonPass({
  joinCode,
  setJoinCode,
  onJoin,
  loading,
  error,
  className = "",
}: CinemaSalonPassProps) {
  const isReduced = usePrefersReducedMotion();
  const cardRef = useRef<HTMLDivElement>(null);
  const [isActive, setIsActive] = useState(false);
  const isActiveRef = useRef(false);

  // Normalized position (-1 to 1) for 3D tilt
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);

  // Position percentage (0% to 100%) for specular highlight
  const [sheenPos, setSheenPos] = useState({ x: 50, y: 50 });

  // Damped spring physics matching the admission ticket
  const springConfig = { damping: 20, stiffness: 150, mass: 0.7 };
  const smoothX = useSpring(mouseX, springConfig);
  const smoothY = useSpring(mouseY, springConfig);

  // Expressive but controlled tilt: max ±7° on X, ±8° on Y
  const rotateX = useTransform(smoothY, [-1, 1], [7, -7]);
  const rotateY = useTransform(smoothX, [-1, 1], [-8, 8]);

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

  // Secure sanitized input handler (alphanumeric uppercase, max 6 chars)
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value;
    const sanitized = raw.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
    setJoinCode(sanitized);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !loading && joinCode.trim().length > 0) {
      onJoin();
    }
  };

  return (
    <div
      data-tour="home-join-code"
      style={{
        perspective: 1200,
        WebkitPerspective: 1200,
        touchAction: "pan-y",
      }}
      className={`relative mx-auto w-full select-none h-full ${className}`}
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
        className="relative w-full h-full rounded-2xl border border-border/90 bg-[#FBF9F4] dark:bg-[#222721] p-5 sm:p-7 shadow-lg overflow-hidden transition-shadow duration-300 hover:shadow-xl active:shadow-md cursor-grab active:cursor-grabbing text-foreground flex flex-col justify-between"
      >
        {/* Tactile Paper Texture (SVG noise overlay) */}
        <div
          aria-hidden="true"
          className="absolute inset-0 pointer-events-none opacity-[0.035] dark:opacity-[0.05] mix-blend-multiply dark:mix-blend-screen bg-repeat z-0"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          }}
        />

        {/* Specular Light Reflection (reactive to touch and cursor) */}
        {!isReduced && (
          <div
            aria-hidden="true"
            className={`absolute inset-0 pointer-events-none transition-opacity duration-300 z-20 ${
              isActive ? "opacity-100" : "opacity-0"
            }`}
            style={{
              background: `radial-gradient(circle 240px at ${sheenPos.x}% ${sheenPos.y}%, rgba(255, 255, 255, 0.42) 0%, rgba(216, 194, 157, 0.22) 38%, rgba(255, 255, 255, 0) 70%)`,
            }}
          />
        )}

        {/* Ticket Outer Border Rules (Letterpress Double Framing) */}
        <div
          aria-hidden="true"
          className="absolute inset-1.5 rounded-[12px] border border-border/50 pointer-events-none z-10"
        />

        {/* Decorative 35mm Celluloid Sprocket Header Strip */}
        <div className="absolute top-0 inset-x-0 h-2.5 flex justify-between px-3 gap-1 overflow-hidden opacity-35 z-10">
          {Array.from({ length: 24 }).map((_, i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-[1px] bg-foreground/80 dark:bg-foreground/60 shrink-0"
            />
          ))}
        </div>

        {/* ── Pass Header ── */}
        <div
          style={{ transform: "translateZ(8px)" }}
          className="relative z-10 flex items-center justify-between mb-3.5 pt-1.5 border-b border-border/60 pb-3"
        >
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[20px]">
              meeting_room
            </span>
            <h2 className="font-editorial text-lg sm:text-xl font-semibold text-foreground tracking-tight">
              Direct Salon Entry
            </h2>
          </div>
          <span className="font-mono text-[9px] sm:text-[10px] font-semibold tracking-widest uppercase text-[#8F754F] dark:text-[#C5A880] px-2 py-0.5 rounded border border-[#8F754F]/30 dark:border-[#C5A880]/30 bg-[#8F754F]/5 dark:bg-[#C5A880]/10">
            ROOM INVITATION
          </span>
        </div>

        {/* Narrative Description */}
        <p
          style={{ transform: "translateZ(6px)" }}
          className="relative z-10 text-xs text-foreground-secondary mb-4 leading-relaxed"
        >
          Have a 6-character room passcode from a co-viewer? Enter below to join their active screening deck immediately.
        </p>

        {/* Error Notice */}
        {error && (
          <div
            style={{ transform: "translateZ(10px)" }}
            className="relative z-10 mb-3.5 p-2.5 bg-error/10 border border-error/20 rounded-xl text-center"
            role="alert"
          >
            <p className="text-xs text-error font-medium">{error}</p>
          </div>
        )}

        {/* ── Input & Submit Field (Layered 3D Depth) ── */}
        <div
          style={{ transform: "translateZ(14px)" }}
          className="relative z-10 flex w-full items-stretch rounded-xl shadow-xs border border-border bg-surface focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary transition-all overflow-hidden"
        >
          <input
            id="salon-passcode-input"
            type="text"
            value={joinCode}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="ENTER 6-DIGIT CODE"
            maxLength={6}
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            autoCapitalize="characters"
            aria-label="Enter 6-digit room passcode"
            aria-invalid={!!error}
            className="flex-1 bg-transparent text-foreground placeholder:text-foreground-secondary/40 px-4 text-sm font-mono font-semibold tracking-widest uppercase focus:outline-none min-h-[48px] h-12"
          />
          <button
            type="button"
            onClick={onJoin}
            disabled={loading || joinCode.trim().length === 0}
            className="flex items-center justify-center px-5 bg-surface-secondary/70 border-l border-border hover:bg-primary hover:text-surface disabled:opacity-40 transition-colors text-foreground font-semibold text-xs tracking-wider min-h-[48px] min-w-[48px] cursor-pointer disabled:cursor-not-allowed active:scale-[0.98]"
            aria-label="Enter session"
          >
            {loading ? (
              <span className="size-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
            )}
          </button>
        </div>

        {/* ── Sub-note & Verified Live Presence ── */}
        <div
          style={{ transform: "translateZ(6px)" }}
          className="relative z-10 mt-4 pt-3.5 border-t border-border/50 flex items-center justify-between text-[11px] text-foreground-secondary"
        >
          <span className="flex items-center gap-1.5 font-medium">
            <span className="material-symbols-outlined text-[14px] text-foreground-secondary/70">
              key
            </span>
            No account needed for guests
          </span>
          <span className="font-mono text-primary flex items-center gap-1.5 font-semibold text-[10px] tracking-wider uppercase">
            <span className="size-1.5 rounded-full bg-primary inline-block animate-pulse" />
            Synced Live
          </span>
        </div>
      </motion.div>
    </div>
  );
}
