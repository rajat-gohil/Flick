import type { CSSProperties } from "react";

interface SkeletonProps {
  className?: string;
  variant?: "shimmer" | "pulse";
  style?: CSSProperties;
}

export function Skeleton({ className = "", variant = "shimmer", style }: SkeletonProps) {
  const animClass = variant === "shimmer" ? "animate-shimmer" : "animate-pulse-subtle bg-surface-secondary";
  return (
    <div
      className={`rounded-md ${animClass} ${className}`}
      style={style}
      aria-hidden="true"
    />
  );
}

/**
 * Skeleton for Movie Card in Discover Grid (aspect 2/3)
 */
export function MovieCardSkeleton() {
  return (
    <div className="rounded-xl bg-surface border border-border overflow-hidden">
      <Skeleton className="w-full aspect-[2/3] rounded-none" />
      <div className="p-2 space-y-1.5">
        <Skeleton className="h-3 w-4/5 rounded" />
        <Skeleton className="h-2.5 w-1/2 rounded" />
      </div>
    </div>
  );
}

/**
 * Skeleton for horizontal discovery shelf
 */
export function ShelfSkeleton() {
  return (
    <div className="mb-6 px-4">
      <Skeleton className="h-4 w-36 mb-3 rounded" />
      <div className="flex gap-3 overflow-hidden">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="shrink-0 w-28 rounded-xl bg-surface border border-border overflow-hidden">
            <Skeleton className="w-full aspect-[2/3] rounded-none" />
            <div className="p-2 space-y-1.5">
              <Skeleton className="h-2.5 w-4/5 rounded" />
              <Skeleton className="h-2 w-1/2 rounded" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Skeleton for Curated Matches row
 */
export function MatchItemSkeleton() {
  return (
    <div className="flex items-center gap-3.5 py-3 rounded-xl px-2">
      <Skeleton className="shrink-0 w-12 aspect-[2/3] rounded-md" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3.5 w-3/4 rounded" />
        <Skeleton className="h-2.5 w-1/3 rounded" />
      </div>
      <Skeleton className="size-9 rounded-full shrink-0" />
    </div>
  );
}

/**
 * Skeleton for single Movie Deck card (SessionPage)
 */
export function DeckCardSkeleton() {
  return (
    <div className="relative w-full max-w-sm h-[63vh] rounded-2xl overflow-hidden border border-border bg-surface shadow-lg flex flex-col justify-between p-5">
      <Skeleton className="absolute inset-0 rounded-none" />
      <div className="relative z-10 flex justify-between">
        <Skeleton className="h-5 w-20 rounded-full" />
      </div>
      <div className="relative z-10 space-y-2">
        <Skeleton className="h-6 w-3/4 rounded" />
        <Skeleton className="h-4 w-1/3 rounded" />
      </div>
    </div>
  );
}

/**
 * Skeleton for streaming provider item
 */
export function StreamingItemSkeleton() {
  return (
    <div className="flex items-center gap-3 bg-surface-secondary/40 rounded-xl px-3 py-2.5 border border-border">
      <Skeleton className="size-7 rounded-md shrink-0" />
      <Skeleton className="h-3.5 w-1/2 rounded" />
    </div>
  );
}
