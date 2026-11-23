import { useState, useEffect, useCallback } from "react";
import { apiRequest } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { usePrefersReducedMotion } from "../lib/motion";
import type { Movie } from "../pages/DiscoverPage";

export type DoubleFeatureResponse = {
  success: boolean;
  source: "personalized" | "daily_editorial";
  is_personalized: boolean;
  confidence?: "HIGH" | "MEDIUM";
  theme: string;
  curator_note: string;
  total_runtime_minutes?: number | null;
  film_1: Movie;
  film_2: Movie;
};

interface CuratorsDoubleFeatureProps {
  onMovieClick: (movie: Movie) => void;
  onScreenDoubleFeature: (movie1: Movie, movie2: Movie) => void;
  watchlistIds: Set<number>;
  onWatchlistUpdated?: (addedIds: number[]) => void;
  className?: string;
}

export default function CuratorsDoubleFeature({
  onMovieClick,
  onScreenDoubleFeature,
  watchlistIds,
  onWatchlistUpdated,
  className = "",
}: CuratorsDoubleFeatureProps) {
  const isReduced = usePrefersReducedMotion();

  const [data, setData] = useState<DoubleFeatureResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Batch watchlist state
  const [isSavingWatchlist, setIsSavingWatchlist] = useState<boolean>(false);
  const [watchlistSaveSuccess, setWatchlistSaveSuccess] = useState<boolean>(false);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  const fetchDoubleFeature = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiRequest("/api/double-feature/");
      if (res && res.success && res.film_1 && res.film_2) {
        setData(res);
      } else {
        setError(res?.error || "Unable to curate today's double feature.");
      }
    } catch {
      setError("Unable to connect to the Salon archive. Please retry.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDoubleFeature();
  }, [fetchDoubleFeature]);

  // Check if both films are already saved
  const id1 = data?.film_1 ? (data.film_1.id || data.film_1.tmdb_id) : null;
  const id2 = data?.film_2 ? (data.film_2.id || data.film_2.tmdb_id) : null;
  const bothSaved = Boolean(
    id1 && id2 && watchlistIds.has(id1) && watchlistIds.has(id2)
  );

  const handleSaveBothToWatchlist = async () => {
    if (!data?.film_1 || !data?.film_2 || isSavingWatchlist) return;

    const targetId1 = data.film_1.id || data.film_1.tmdb_id;
    const targetId2 = data.film_2.id || data.film_2.tmdb_id;
    if (!targetId1 || !targetId2) return;

    setIsSavingWatchlist(true);
    setWatchlistError(null);

    try {
      const res = await apiRequest("/api/watchlist/", {
        method: "POST",
        body: JSON.stringify({
          movie_ids: [targetId1, targetId2],
        }),
      });

      if (res && res.success) {
        setWatchlistSaveSuccess(true);
        if (onWatchlistUpdated) {
          onWatchlistUpdated([targetId1, targetId2]);
        }
        trackEvent("double_feature_watchlist_batch_added", {
          film_1_id: targetId1,
          film_2_id: targetId2,
          theme: data.theme,
          source: data.source,
        });
      } else {
        setWatchlistError(res?.error || "Failed to save both titles.");
      }
    } catch {
      setWatchlistError("Network error while adding to watchlist. Please retry.");
    } finally {
      setIsSavingWatchlist(false);
    }
  };

  const handleScreenDoubleFeature = () => {
    if (!data?.film_1 || !data?.film_2) return;
    trackEvent("double_feature_screen_clicked", {
      theme: data.theme,
      source: data.source,
      film_1_id: data.film_1.id || data.film_1.tmdb_id,
      film_2_id: data.film_2.id || data.film_2.tmdb_id,
    });
    onScreenDoubleFeature(data.film_1, data.film_2);
  };

  /* ── Skeleton Loading State ── */
  if (isLoading) {
    return (
      <div
        data-testid="double-feature-loading"
        className={`rounded-3xl border border-border/70 bg-[#FBF9F4] dark:bg-[#1E221E] p-6 sm:p-8 animate-pulse ${className}`}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="h-4 w-36 bg-foreground/10 rounded" />
          <div className="h-4 w-28 bg-foreground/10 rounded" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          <div className="h-64 sm:h-72 bg-foreground/10 rounded-2xl" />
          <div className="h-64 sm:h-72 bg-foreground/10 rounded-2xl" />
        </div>
      </div>
    );
  }

  /* ── Error State ── */
  if (error || !data) {
    return (
      <div
        data-testid="double-feature-error"
        className={`rounded-3xl border border-destructive/30 bg-destructive/5 p-6 sm:p-8 text-center ${className}`}
      >
        <span className="material-symbols-outlined text-3xl text-destructive/80 mb-2">
          theaters
        </span>
        <h3 className="font-editorial text-lg font-bold text-foreground mb-1">
          The Salon Archive
        </h3>
        <p className="text-xs text-foreground-secondary mb-4 max-w-md mx-auto">
          {error || "Could not retrieve the double feature at this time."}
        </p>
        <button
          onClick={fetchDoubleFeature}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-mono uppercase tracking-wider bg-foreground text-background font-semibold hover:opacity-90 transition-opacity min-h-[44px]"
        >
          <span className="material-symbols-outlined text-[16px]">refresh</span>
          Retry Curatorial Retrieval
        </button>
      </div>
    );
  }

  const { film_1, film_2, theme, curator_note, source, is_personalized } = data;

  return (
    <section
      aria-labelledby="double-feature-heading"
      data-testid="curators-double-feature"
      className={`relative rounded-3xl border border-[#D5CEBE]/80 dark:border-[#383F37] bg-[#FBF9F4] dark:bg-[#1C201C] text-foreground shadow-sm overflow-hidden p-5 sm:p-8 md:p-10 transition-colors duration-200 ${className}`}
    >
      {/* Subtle Analog Texture Layer */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.035] dark:opacity-[0.05]"
        style={{
          backgroundImage: `radial-gradient(circle at 50% 50%, #000 1px, transparent 1px)`,
          backgroundSize: "16px 16px",
        }}
        aria-hidden="true"
      />

      {/* Top Header Badge & Curatorial Origin */}
      <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 pb-5 mb-6 border-b border-[#E6E1D5] dark:border-[#2C322B]">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-[18px] text-primary">
            local_activity
          </span>
          <span className="text-[10px] sm:text-xs font-mono uppercase tracking-widest text-primary font-bold">
            THE CURATOR’S DOUBLE BILL
          </span>
          <span className="text-foreground-secondary text-xs">·</span>
          <span className="text-[10px] sm:text-xs font-mono uppercase tracking-wider text-foreground-secondary">
            {is_personalized ? "Personalized Pairing" : "Daily Salon Selection"}
          </span>
        </div>

        {/* Edition Stamp */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-primary/30 bg-primary/5 text-primary text-[10px] font-mono tracking-widest uppercase">
          <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
          <span>{source === "personalized" ? "MEMBER PROFILE" : "ISSUE SALON · 35MM"}</span>
        </div>
      </div>

      {/* Thematic Header & Curator's Note */}
      <div className="relative z-10 max-w-3xl mb-8">
        <h2
          id="double-feature-heading"
          className="font-editorial text-2xl sm:text-3xl md:text-4xl font-bold tracking-tight text-foreground leading-tight"
        >
          {theme}
        </h2>
        <div className="mt-3 pl-3 sm:pl-4 border-l-2 border-primary/50">
          <p className="text-[10px] font-mono uppercase tracking-widest text-primary font-semibold mb-1">
            THE CURATOR’S NOTE
          </p>
          <p className="font-editorial text-sm sm:text-base text-foreground/90 italic leading-relaxed">
            {curator_note}
          </p>
        </div>
      </div>

      {/* Dual Movie Cards Framing the Perforated Celluloid Bridge */}
      <div className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-5 sm:gap-6 items-stretch mb-8">
        
        {/* Film 1 Card */}
        <div className="md:col-span-5 flex">
          <FilmCard
            movie={film_1}
            roleTag="FEATURE NO. 1"
            onMovieClick={onMovieClick}
            isReduced={isReduced}
          />
        </div>

        {/* Celluloid Film Sprocket Bridge */}
        <div className="md:col-span-2 flex flex-col items-center justify-center py-2 md:py-0">
          <div className="w-full flex md:flex-col items-center justify-center gap-2 select-none opacity-80">
            {/* Sprocket Holes */}
            <div className="flex md:flex-col gap-1.5 items-center">
              {[0, 1, 2, 3, 4].map((idx) => (
                <div
                  key={idx}
                  className="w-2.5 h-3.5 sm:w-3 sm:h-4 rounded-[2px] border border-primary/40 bg-foreground/5 dark:bg-background/40"
                  aria-hidden="true"
                />
              ))}
            </div>

            <div className="px-3 py-1.5 my-1 rounded-md border border-primary/40 bg-[#EDE7DA] dark:bg-[#151815] text-[10px] font-mono tracking-widest text-foreground font-bold text-center whitespace-nowrap uppercase shadow-xs">
              DOUBLE BILL
            </div>

            <div className="flex md:flex-col gap-1.5 items-center">
              {[0, 1, 2, 3, 4].map((idx) => (
                <div
                  key={idx}
                  className="w-2.5 h-3.5 sm:w-3 sm:h-4 rounded-[2px] border border-primary/40 bg-foreground/5 dark:bg-background/40"
                  aria-hidden="true"
                />
              ))}
            </div>
          </div>
        </div>

        {/* Film 2 Card */}
        <div className="md:col-span-5 flex">
          <FilmCard
            movie={film_2}
            roleTag="FEATURE NO. 2"
            onMovieClick={onMovieClick}
            isReduced={isReduced}
          />
        </div>
      </div>

      {/* Action Suite: Screen Double Feature & Save Both */}
      <div className="relative z-10 pt-5 border-t border-[#E6E1D5] dark:border-[#2C322B] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        
        {/* Watchlist Feedback message if error */}
        {watchlistError && (
          <p className="text-xs text-destructive font-mono order-3 sm:order-1">
            {watchlistError}
          </p>
        )}

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 w-full sm:w-auto ml-auto">
          {/* Secondary Action: Save Both to Watchlist */}
          <button
            type="button"
            onClick={handleSaveBothToWatchlist}
            disabled={isSavingWatchlist || bothSaved || watchlistSaveSuccess}
            className={`min-h-[44px] px-5 py-2.5 rounded-xl border text-xs font-mono uppercase tracking-wider font-semibold transition-all duration-200 inline-flex items-center justify-center gap-2 ${
              bothSaved || watchlistSaveSuccess
                ? "border-primary/50 bg-primary/10 text-primary cursor-default"
                : "border-[#C9C0AF] dark:border-[#3E463C] bg-white dark:bg-[#252B24] text-foreground hover:bg-[#F2ECE1] dark:hover:bg-[#2D342C] active:scale-[0.98]"
            }`}
          >
            {isSavingWatchlist ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <span>Saving Both Titles...</span>
              </>
            ) : bothSaved || watchlistSaveSuccess ? (
              <>
                <span className="material-symbols-outlined text-[16px] text-primary">
                  bookmark_added
                </span>
                <span>Both Saved in Watchlist</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">
                  bookmark_add
                </span>
                <span>Save Both to Watchlist</span>
              </>
            )}
          </button>

          {/* Primary Action: Screen Double Feature */}
          <button
            type="button"
            onClick={handleScreenDoubleFeature}
            className="min-h-[44px] px-6 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-mono uppercase tracking-wider font-bold shadow-md hover:opacity-95 active:scale-[0.98] transition-all duration-200 inline-flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">
              theaters
            </span>
            <span>Screen Double Feature</span>
          </button>
        </div>
      </div>
    </section>
  );
}

/* =========================================================================
   Individual Film Card Component
   ========================================================================= */
interface FilmCardProps {
  movie: Movie;
  roleTag: string;
  onMovieClick: (m: Movie) => void;
  isReduced: boolean;
}

function FilmCard({ movie, roleTag, onMovieClick, isReduced }: FilmCardProps) {
  const ratingNum = movie.rating != null ? Number(movie.rating) : null;
  const ratingDisplay = ratingNum != null ? ratingNum.toFixed(1) : null;
  const yearDisplay = movie.release_year || (movie.release_date ? new Date(movie.release_date).getFullYear() : null);

  return (
    <article
      onClick={() => onMovieClick(movie)}
      tabIndex={0}
      role="button"
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onMovieClick(movie);
        }
      }}
      aria-label={`Inspect film: ${movie.title}`}
      className="w-full group cursor-pointer rounded-2xl border border-[#DDD5C5] dark:border-[#333A31] bg-white dark:bg-[#232822] p-4 flex flex-col justify-between shadow-xs hover:shadow-md hover:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/40 transition-all duration-200"
    >
      <div>
        {/* Role Tag & Rating Header */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <span className="text-[10px] font-mono uppercase tracking-widest text-primary font-bold">
            {roleTag}
          </span>
          {ratingDisplay && (
            <span className="inline-flex items-center gap-1 text-[11px] font-mono font-bold text-foreground bg-[#F0EBE1] dark:bg-[#1A1D1A] px-2 py-0.5 rounded-md border border-[#D5CEBE]/50 dark:border-[#2E352C]">
              <span className="material-symbols-outlined text-[13px] text-amber-500 fill-current">
                star
              </span>
              <span>{ratingDisplay}</span>
            </span>
          )}
        </div>

        {/* Poster & Title Layout */}
        <div className="flex gap-3.5 sm:gap-4 items-start">
          {/* Poster Frame */}
          <div className="relative w-20 sm:w-24 shrink-0 aspect-[2/3] rounded-lg overflow-hidden border border-black/10 dark:border-white/10 bg-[#E8E4DA] dark:bg-[#171A17] shadow-xs">
            {movie.poster_url ? (
              <img
                src={movie.poster_url}
                alt={`${movie.title} poster`}
                loading="lazy"
                className={`w-full h-full object-cover transition-transform duration-300 ${
                  isReduced ? "" : "group-hover:scale-105"
                }`}
              />
            ) : (
              <div className="w-full h-full flex flex-col items-center justify-center p-2 text-center text-foreground-secondary">
                <span className="material-symbols-outlined text-xl">theaters</span>
                <span className="text-[9px] font-mono mt-1">NO REEL</span>
              </div>
            )}
          </div>

          {/* Details */}
          <div className="flex-1 min-w-0">
            <h3 className="font-editorial text-lg sm:text-xl font-bold text-foreground leading-tight truncate group-hover:text-primary transition-colors">
              {movie.title}
            </h3>

            <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-foreground-secondary font-mono">
              {yearDisplay && <span>{yearDisplay}</span>}
              {movie.genres && movie.genres.length > 0 && (
                <>
                  <span>·</span>
                  <span className="truncate">{movie.genres.slice(0, 2).join(", ")}</span>
                </>
              )}
            </div>

            {/* Overview Snippet */}
            {movie.overview && (
              <p className="mt-2 text-xs text-foreground-secondary line-clamp-2 leading-relaxed">
                {movie.overview}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Card Footer: Streaming Availability & Examine Trigger */}
      <div className="mt-3 pt-3 border-t border-[#EAE4D7] dark:border-[#2C322B] flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5 overflow-hidden">
          {movie.streaming_providers && movie.streaming_providers.length > 0 ? (
            <span className="inline-flex items-center gap-1 text-[11px] font-mono text-foreground-secondary">
              <span className="material-symbols-outlined text-[13px] text-primary">
                stream
              </span>
              <span className="truncate max-w-[120px] sm:max-w-[150px]">
                {movie.streaming_providers[0].name}
              </span>
            </span>
          ) : (
            <span className="text-[11px] font-mono text-foreground-secondary">
              Check availability
            </span>
          )}
        </div>

        <span className="inline-flex items-center gap-0.5 text-primary text-[11px] font-mono font-semibold uppercase tracking-wider group-hover:translate-x-0.5 transition-transform">
          <span>Examine</span>
          <span className="material-symbols-outlined text-[13px]">arrow_forward</span>
        </span>
      </div>
    </article>
  );
}
