import AnimatedFlickLogo from "./AnimatedFlickLogo";

interface CinematicLoaderProps {
  message?: string;
  submessage?: string;
  fullScreen?: boolean;
}

export default function CinematicLoader({
  message = "Curating Film Selection",
  submessage = "Synchronizing with global cinematic archive...",
  fullScreen = true,
}: CinematicLoaderProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center bg-background text-foreground select-none ${
        fullScreen ? "fixed inset-0 z-50 min-h-screen" : "py-16 w-full"
      }`}
      role="status"
      aria-live="polite"
    >
      <div className="relative flex items-center justify-center size-24 mb-6">
        {/* Soft glowing ambient aperture ring */}
        <div className="absolute inset-0 rounded-full border border-primary/20 animate-ping" style={{ animationDuration: "2.8s" }} />
        <div className="absolute inset-1.5 rounded-full border border-primary/35 animate-pulse" />

        {/* Animated Flick badge */}
        <AnimatedFlickLogo
          variant="badge"
          loop
          decorative
          className="size-16 rounded-2xl shadow-md relative z-10"
        />
      </div>

      <div className="text-center px-6 max-w-sm">
        <h2 className="font-editorial text-lg md:text-xl font-semibold tracking-tight text-foreground mb-1">
          {message}
        </h2>
        {submessage && (
          <p className="text-xs text-foreground-secondary leading-relaxed">
            {submessage}
          </p>
        )}
      </div>

      {/* Film reel dash indicator */}
      <div className="flex gap-1.5 mt-5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-primary/50 animate-pulse"
            style={{ animationDelay: `${i * 0.22}s`, animationDuration: "1.2s" }}
          />
        ))}
      </div>
    </div>
  );
}
