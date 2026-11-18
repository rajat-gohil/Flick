import React, { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { apiRequest } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import StreamingOptions from "../components/StreamingOptions";
import { MovieCardSkeleton, ShelfSkeleton } from "../components/Skeleton";
import { bottomSheetVariants, backdropVariants } from "../lib/motion";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

/* ============================
   TYPES
============================ */

export type CuratorExplanation = {
  reason?: string;
  matched_signals?: string[];
  confidence?: "HIGH" | "MEDIUM" | "LOW" | "COLD_START" | string;
};

export type Movie = {
  id?: number | null;
  tmdb_id: number;
  title: string;
  overview: string;
  poster_url: string | null;
  backdrop_url?: string | null;
  rating?: number | null;
  vote_count?: number | null;
  release_year?: number | null;
  original_language?: string | null;
  trailer_url?: string | null;
  genres?: string[];
  is_in_watchlist?: boolean;
  explanation?: CuratorExplanation;
};

export type ArchiveShelf = {
  id: string;
  title: string;
  subtitle?: string;
  icon: string;
  anchor_movie?: Movie | null;
  movies: Movie[];
};

type Genre = { id: number; tmdb_id?: number; name: string };

export type Filters = {
  genre: string;
  language: string;
  era: string;
  min_rating: string;
  provider?: string;
};

export const STREAMING_PLATFORMS = [
  { id: "", label: "All Streaming", icon: "live_tv" },
  { id: "8", label: "Netflix", icon: "play_circle" },
  { id: "119", label: "Prime Video", icon: "play_arrow" },
  { id: "122", label: "Disney+ Hotstar", icon: "stars" },
  { id: "350", label: "Apple TV+", icon: "tv" },
  { id: "220", label: "JioCinema", icon: "movie" },
  { id: "237", label: "SonyLIV", icon: "ondemand_video" },
  { id: "232", label: "Zee5", icon: "smart_display" },
] as const;

export type CatalogueSort = "rating" | "popularity" | "release_date" | "title";

export type DiscoverView = "archive" | "catalogue";

type WatchlistResponse = {
  watchlist?: { id: number; movie_id: number; tmdb_id?: number }[];
};

type GenreResponse = { genres?: Genre[] };

/* ============================
   CONSTANTS
============================ */

export const CATEGORIES = [
  { id: "popular",     label: "Popular",     icon: "whatshot" },
  { id: "trending",    label: "Trending",    icon: "trending_up" },
  { id: "top_rated",   label: "Top Rated",   icon: "star" },
  { id: "now_playing", label: "In Theatres", icon: "movie" },
  { id: "upcoming",    label: "Upcoming",    icon: "event" },
] as const;

export type CategoryId = typeof CATEGORIES[number]["id"];

const SORT_OPTIONS: { value: CatalogueSort; label: string; icon: string }[] = [
  { value: "popularity", label: "Popularity", icon: "trending_up" },
  { value: "rating", label: "Rating", icon: "star" },
  { value: "release_date", label: "Release Date", icon: "calendar_today" },
  { value: "title", label: "Title (A–Z)", icon: "sort_by_alpha" },
];

const LANGUAGES = [
  { code: "",   label: "All"       },
  { code: "en", label: "English"   },
  { code: "hi", label: "Hindi"     },
  { code: "ta", label: "Tamil"     },
  { code: "te", label: "Telugu"    },
  { code: "ml", label: "Malayalam" },
  { code: "kn", label: "Kannada"   },
  { code: "mr", label: "Marathi"   },
  { code: "bn", label: "Bengali"   },
  { code: "ko", label: "Korean"    },
  { code: "ja", label: "Japanese"  },
  { code: "es", label: "Spanish"   },
  { code: "fr", label: "French"    },
  { code: "it", label: "Italian"   },
  { code: "de", label: "German"    },
  { code: "zh", label: "Chinese"   },
];

const ERAS = [
  { value: "any",         label: "Any Era"     },
  { value: "recent",      label: "2020s"       },
  { value: "2010s",       label: "2010s"       },
  { value: "2000s",       label: "2000s"       },
  { value: "90s",         label: "90s"         },
  { value: "before_1990", label: "Before 1990" },
  { value: "classic",     label: "Classic"     },
];

const RATINGS = [
  { value: "any", label: "Any"  },
  { value: "6",   label: "6.0+" },
  { value: "7",   label: "7.0+" },
  { value: "7.5", label: "7.5+" },
  { value: "8",   label: "8.0+" },
];

const MOODS = [
  { id: "comedy",    label: "Comedy",          icon: "theater_comedy", genre: "35",    language: "",   era: "any",     min_rating: "7"   },
  { id: "thriller",  label: "Thriller",        icon: "psychology",     genre: "53",    language: "",   era: "any",     min_rating: "7"   },
  { id: "romance",   label: "Romance",         icon: "favorite",       genre: "10749", language: "",   era: "any",     min_rating: "7"   },
  { id: "korean",    label: "Korean Cinema",   icon: "translate",      genre: "",      language: "ko", era: "any",     min_rating: "7.5" },
  { id: "hindi",     label: "Hindi Cinema",    icon: "movie",          genre: "",      language: "hi", era: "any",     min_rating: "7"   },
  { id: "top_picks", label: "Top Picks",       icon: "star",           genre: "",      language: "",   era: "any",     min_rating: "8"   },
  { id: "classic",   label: "Classic Archive", icon: "history_edu",    genre: "",      language: "",   era: "classic", min_rating: "7.5" },
];

const EMPTY_FILTERS: Filters = { genre: "", language: "", era: "any", min_rating: "any", provider: "" };

/* ============================
   CHIP COMPONENT
============================ */

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-all active:scale-95 border ${
        active
          ? "bg-primary border-primary text-surface font-semibold shadow-xs"
          : "bg-surface border-border text-foreground-secondary hover:border-primary/50 hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}

/* ============================
   NORMALIZER FOR ARCHIVE SHELVES
============================ */

function normalizeArchiveShelves(data: any): ArchiveShelf[] {
  const result: ArchiveShelf[] = [];
  if (!data || typeof data !== "object") return result;

  const rawShelves = data.shelves || data;

  const shelfDefs = [
    {
      id: "recommended_for_you",
      defaultTitle: "Recommended For You",
      defaultSubtitle: "Curated to match your unique taste profile",
      defaultIcon: "auto_awesome",
    },
    {
      id: "because_you_liked",
      defaultTitle: "Because You Liked",
      defaultSubtitle: "Nearest matches based on shared director, themes, and tone",
      defaultIcon: "recommend",
    },
    {
      id: "explore_your_genres",
      defaultTitle: "Explore Your Genres",
      defaultSubtitle: "Top-rated discoveries within your highest-affinity genres",
      defaultIcon: "category",
    },
    {
      id: "explore_by_era",
      defaultTitle: "Explore By Era",
      defaultSubtitle: "Iconic cinematic eras aligned with your watch history",
      defaultIcon: "history",
    },
    {
      id: "outside_your_comfort_zone",
      defaultTitle: "Outside Your Comfort Zone",
      defaultSubtitle: "High-quality serendipity selections beyond your usual preferences",
      defaultIcon: "explore",
    },
  ];

  if (Array.isArray(rawShelves)) {
    for (const item of rawShelves) {
      if (!item) continue;
      const id = item.id || item.slug || "shelf";
      const movies = Array.isArray(item.movies) ? item.movies : Array.isArray(item.results) ? item.results : [];
      if (movies.length > 0) {
        result.push({
          id,
          title: item.title || item.name || "Curated Shelf",
          subtitle: item.subtitle,
          icon: item.icon || "movie",
          anchor_movie: item.anchor_movie || null,
          movies,
        });
      }
    }
    return result;
  }

  for (const def of shelfDefs) {
    const val = rawShelves[def.id];
    if (!val) continue;

    let movies: Movie[] = [];
    let title = def.defaultTitle;
    let subtitle = def.defaultSubtitle;
    let anchor: Movie | null = null;

    if (Array.isArray(val)) {
      movies = val;
    } else if (typeof val === "object" && val !== null) {
      if (Array.isArray(val.movies)) movies = val.movies;
      else if (Array.isArray(val.results)) movies = val.results;
      if (val.title) title = val.title;
      if (val.subtitle) subtitle = val.subtitle;
      if (val.anchor_movie) {
        anchor = val.anchor_movie;
        if (!val.title && anchor?.title) {
          title = `Because You Liked ${anchor.title}`;
        }
      }
    }

    if (movies.length > 0) {
      result.push({
        id: def.id,
        title,
        subtitle,
        icon: def.defaultIcon,
        anchor_movie: anchor,
        movies,
      });
    }
  }

  for (const key of Object.keys(rawShelves)) {
    if (shelfDefs.some((d) => d.id === key) || key === "success" || key === "count" || key === "user_id") continue;
    const val = rawShelves[key];
    if (Array.isArray(val) && val.length > 0) {
      result.push({
        id: key,
        title: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        icon: "movie",
        movies: val,
      });
    }
  }

  return result;
}

/* ============================
   MOVIE DETAIL SHEET
============================ */

export function MovieDetailSheet({
  movie,
  inWatchlist,
  onWatchlist,
  onClose,
}: {
  movie: Movie;
  inWatchlist: boolean;
  onWatchlist: (m: Movie) => void;
  onClose: () => void;
}) {
  const targetId = movie.id || movie.tmdb_id;
  const dialogRef = useRef<HTMLDivElement>(null);

  // Background scroll lock
  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, []);

  // Keyboard escape, focus trapping, and focus restoration
  useEffect(() => {
    const prevActive = document.activeElement as HTMLElement | null;
    dialogRef.current?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (!dialogRef.current.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
          return;
        }

        if (e.shiftKey) {
          if (document.activeElement === first || document.activeElement === dialogRef.current) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      prevActive?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col justify-end md:justify-center md:items-center p-0 md:p-6"
      onClick={onClose}
    >
      <motion.div
        variants={backdropVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
      />
      <motion.div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="movie-detail-title"
        tabIndex={-1}
        variants={bottomSheetVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
        className="relative bg-surface border-t md:border border-border rounded-t-3xl md:rounded-2xl overflow-hidden z-50 max-h-[88vh] md:max-h-[85vh] flex flex-col shadow-2xl max-w-lg md:max-w-xl mx-auto w-full focus:outline-hidden"
        onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}
      >
        {/* Backdrop hero */}
        <div className="relative h-44 md:h-48 shrink-0 bg-surface-secondary overflow-hidden">
          {movie.backdrop_url ? (
            <img src={movie.backdrop_url} alt="" className="w-full h-full object-cover opacity-60" />
          ) : movie.poster_url ? (
            <img src={movie.poster_url} alt="" className="w-full h-full object-cover opacity-30 scale-110 blur-sm" />
          ) : null}
          <div className="absolute inset-0 bg-gradient-to-t from-surface via-surface/40 to-transparent" />

          {/* Close pill with 44x44px hitbox */}
          <button
            onClick={onClose}
            className="absolute top-3 right-3 size-11 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white hover:bg-black/70 transition-colors z-10 cursor-pointer"
            aria-label="Close details"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>

          {/* Poster + title overlay */}
          <div className="absolute bottom-3 left-4 right-4 flex items-end gap-3">
            <div className="w-16 rounded-xl overflow-hidden shrink-0 shadow-lg border border-border bg-surface-secondary" style={{ aspectRatio: "2/3" }}>
              {movie.poster_url ? (
                <img src={movie.poster_url} alt={movie.title} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-foreground-secondary">
                  <span className="material-symbols-outlined text-[20px]">movie</span>
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <h2
                id="movie-detail-title"
                className="font-editorial text-lg md:text-xl font-bold text-foreground leading-tight line-clamp-2"
              >
                {movie.title}
              </h2>
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                {movie.rating != null && (
                  <span className="flex items-center gap-0.5 text-xs font-semibold text-primary">
                    <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                    {movie.rating.toFixed(1)}
                  </span>
                )}
                {movie.release_year && <span className="text-xs text-foreground-secondary">{movie.release_year}</span>}
                {movie.original_language && (
                  <span className="text-[10px] font-semibold uppercase bg-surface-secondary px-1.5 py-0.5 rounded text-foreground-secondary border border-border">
                    {movie.original_language}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto overscroll-contain flex-1 px-5 py-4 space-y-5">
          {/* Curatorial explanation if available */}
          {movie.explanation?.reason && (
            <div className="p-3.5 rounded-xl bg-surface-secondary/80 border border-primary/25 space-y-1.5">
              <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold uppercase tracking-wider text-primary">
                <span className="material-symbols-outlined text-[15px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
                <span>Curatorial Recommendation</span>
                {movie.explanation.confidence && movie.explanation.confidence !== "COLD_START" && (
                  <span className="text-foreground-secondary font-normal">· {movie.explanation.confidence}</span>
                )}
              </div>
              <p className="text-xs italic text-foreground font-serif leading-relaxed">
                "{movie.explanation.reason}"
              </p>
              {movie.explanation.matched_signals && movie.explanation.matched_signals.length > 0 && (
                <div className="flex flex-wrap items-center gap-1 pt-1">
                  {movie.explanation.matched_signals.map((sig, i) => (
                    <span key={i} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                      #{sig}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {movie.overview && (
            <div>
              <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-1.5 block">Synopsis</span>
              <p className="text-xs text-foreground leading-relaxed">{movie.overview}</p>
            </div>
          )}

          <div>
            <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-2 block">Streaming Availability</span>
            <StreamingOptions movieId={targetId} movieTitle={movie.title} />
          </div>

          {movie.trailer_url && (
            <a
              href={movie.trailer_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-xs font-semibold text-primary hover:underline uppercase tracking-wider"
            >
              <span className="material-symbols-outlined text-[16px]">play_circle</span>
              Watch Trailer
            </a>
          )}
        </div>

        {/* Action bar */}
        <div className="px-5 pb-[max(1.5rem,calc(1rem+env(safe-area-inset-bottom)))] md:pb-4 pt-3 border-t border-border/60 shrink-0">
          <button
            onClick={() => onWatchlist(movie)}
            className={`w-full h-12 flex items-center justify-center gap-2 rounded-xl font-semibold text-xs uppercase tracking-wider transition-all cursor-pointer ${
              inWatchlist
                ? "bg-primary/10 border border-primary text-primary"
                : "bg-primary hover:bg-primary-hover text-surface shadow-sm"
            }`}
          >
            <span
              className="material-symbols-outlined text-[18px]"
              style={{ fontVariationSettings: inWatchlist ? "'FILL' 1" : "'FILL' 0" }}
            >
              bookmark
            </span>
            {inWatchlist ? "Saved in Watchlist" : "Save to Watchlist"}
          </button>
        </div>
      </motion.div>
    </div>
  );
}

/* ============================
   MOVIE CARD
============================ */

function MovieCard({
  movie,
  onWatchlist,
  inWatchlist,
  onTap,
}: {
  movie: Movie;
  onWatchlist: (m: Movie) => void;
  inWatchlist: boolean;
  onTap: (movie: Movie) => void;
}) {
  const [imgError, setImgError] = useState(false);

  function handleBookmark(e: React.MouseEvent<HTMLButtonElement>) {
    e.stopPropagation();
    onWatchlist(movie);
  }

  return (
    <div
      className="relative rounded-xl overflow-hidden bg-surface border border-border hover:border-primary/50 group flex flex-col cursor-pointer transition-all active:scale-[0.98] shadow-xs"
      onClick={() => onTap(movie)}
    >
      <div className="relative overflow-hidden bg-surface-secondary" style={{ aspectRatio: "2/3" }}>
        {!imgError && movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={movie.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-foreground-secondary">
            <span className="material-symbols-outlined text-4xl">movie</span>
          </div>
        )}

        <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/80 to-transparent pointer-events-none" />

        {movie.rating != null && (
          <div className="absolute top-2 left-2 flex items-center gap-0.5 bg-black/60 backdrop-blur-sm rounded px-1.5 py-0.5">
            <span className="material-symbols-outlined text-primary text-[10px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
            <span className="text-[10px] font-bold text-white">{movie.rating.toFixed(1)}</span>
          </div>
        )}

        <button
          onClick={handleBookmark}
          className="absolute top-1 right-1 size-11 flex items-center justify-center z-10 cursor-pointer"
          aria-label={inWatchlist ? "Remove from watchlist" : "Add to watchlist"}
        >
          <span
            className={`size-9 rounded-full flex items-center justify-center backdrop-blur-sm transition-all shadow-xs pointer-events-none ${
              inWatchlist
                ? "bg-primary text-surface"
                : "bg-black/50 text-white/80 hover:bg-black/70 hover:text-white"
            }`}
          >
            <span
              className="material-symbols-outlined text-[15px]"
              style={{ fontVariationSettings: inWatchlist ? "'FILL' 1" : "'FILL' 0" }}
            >
              bookmark
            </span>
          </span>
        </button>
      </div>

      <div className="p-2.5 sm:p-3 flex flex-col gap-0.5 flex-1">
        <p className="font-editorial text-xs sm:text-sm font-semibold text-foreground leading-snug line-clamp-1">{movie.title}</p>
        <p className="text-[10px] sm:text-xs text-foreground-secondary">
          {movie.release_year ?? ""}
          {movie.release_year && movie.original_language ? " · " : ""}
          {movie.original_language ? movie.original_language.toUpperCase() : ""}
        </p>
        {movie.explanation?.matched_signals && movie.explanation.matched_signals.length > 0 && (
          <div className="mt-1">
            <span className="inline-block text-[9px] font-mono text-primary truncate max-w-full">
              #{movie.explanation.matched_signals[0]}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/* ============================
   FEATURED HERO CARD
============================ */

function HeroCard({
  movie,
  inWatchlist,
  onWatchlist,
  onTap,
}: {
  movie: Movie;
  inWatchlist: boolean;
  onWatchlist: (m: Movie) => void;
  onTap: (movie: Movie) => void;
}) {
  const [imgError, setImgError] = useState(false);
  const imageUrl = movie.backdrop_url || movie.poster_url;

  return (
    <div
      className="relative mx-4 sm:mx-6 lg:mx-8 mb-6 sm:mb-8 rounded-2xl sm:rounded-3xl overflow-hidden cursor-pointer border border-border shadow-md h-52 sm:h-72 md:h-80 lg:h-96"
      onClick={() => onTap(movie)}
    >
      {!imgError && imageUrl ? (
        <img
          src={imageUrl}
          alt={movie.title}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      ) : (
        <div className="w-full h-full bg-surface-secondary flex items-center justify-center text-foreground-secondary">
          <span className="material-symbols-outlined text-5xl">movie</span>
        </div>
      )}
      <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-transparent" />

      {/* Featured badge */}
      <div className="absolute top-3 left-3 sm:top-4 sm:left-4 flex items-center gap-1 bg-primary text-surface rounded-md px-2.5 py-1">
        <span className="material-symbols-outlined text-[12px]" style={{ fontVariationSettings: "'FILL' 1" }}>auto_awesome</span>
        <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-wider">Spotlight Selection</span>
      </div>

      {/* Watchlist */}
      <button
        onClick={(e: React.MouseEvent<HTMLButtonElement>) => { e.stopPropagation(); onWatchlist(movie); }}
        className="absolute top-1.5 right-1.5 sm:top-2.5 sm:right-2.5 size-11 flex items-center justify-center z-10 cursor-pointer"
        aria-label="Save to watchlist"
      >
        <span
          className={`size-9 sm:size-10 rounded-full flex items-center justify-center backdrop-blur-sm transition-all pointer-events-none ${
            inWatchlist ? "bg-primary text-surface" : "bg-black/50 text-white hover:bg-black/70"
          }`}
        >
          <span className="material-symbols-outlined text-[18px]" style={{ fontVariationSettings: inWatchlist ? "'FILL' 1" : "'FILL' 0" }}>bookmark</span>
        </span>
      </button>

      {/* Info */}
      <div className="absolute bottom-0 left-0 right-0 p-4 sm:p-6 lg:p-8">
        <h3 className="font-editorial text-xl sm:text-2xl md:text-3xl font-bold text-white leading-tight line-clamp-1">{movie.title}</h3>
        <div className="flex items-center gap-2 mt-1 sm:mt-2 text-xs sm:text-sm text-white/80">
          {movie.rating != null && (
            <span className="flex items-center gap-0.5 text-primary font-semibold">
              <span className="material-symbols-outlined text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
              {movie.rating.toFixed(1)}
            </span>
          )}
          {movie.release_year && <span>{movie.release_year}</span>}
          {movie.overview && <span className="line-clamp-1 text-white/70 text-xs sm:text-sm flex-1">{movie.overview}</span>}
        </div>
      </div>
    </div>
  );
}

/* ============================
   ARCHIVE SHELF COMPONENT
============================ */

function ArchiveShelfSection({
  shelf,
  watchlistIds,
  onWatchlist,
  onTap,
}: {
  shelf: ArchiveShelf;
  watchlistIds: Set<number>;
  onWatchlist: (m: Movie) => void;
  onTap: (movie: Movie) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScroll = () => {
    if (scrollRef.current) {
      const { scrollLeft, scrollWidth, clientWidth } = scrollRef.current;
      setCanScrollLeft(scrollLeft > 10);
      setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 10);
    }
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener("resize", checkScroll);
    return () => window.removeEventListener("resize", checkScroll);
  }, [shelf.movies]);

  const scroll = (direction: "left" | "right") => {
    if (scrollRef.current) {
      const offset = direction === "left" ? -400 : 400;
      scrollRef.current.scrollBy({ left: offset, behavior: "smooth" });
      setTimeout(checkScroll, 350);
    }
  };

  if (shelf.movies.length === 0) return null;

  return (
    <div className="mb-8 sm:mb-10">
      <div className="flex items-end justify-between px-4 sm:px-6 lg:px-8 mb-3">
        <div>
          <div className="flex items-center gap-1.5 text-primary text-[10px] font-mono uppercase tracking-widest font-semibold mb-0.5">
            <span className="material-symbols-outlined text-[14px]">{shelf.icon}</span>
            <span>Personalized Archive Shelf</span>
          </div>
          <h3 className="font-editorial text-lg sm:text-xl font-semibold text-foreground tracking-tight">
            {shelf.title}
          </h3>
          {shelf.subtitle && (
            <p className="text-xs text-foreground-secondary mt-0.5">{shelf.subtitle}</p>
          )}
        </div>
        <div className="hidden md:flex items-center gap-1.5">
          <button
            onClick={() => scroll("left")}
            disabled={!canScrollLeft}
            aria-label="Scroll left"
            className="size-8 rounded-full border border-border bg-surface flex items-center justify-center text-foreground-secondary hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">chevron_left</span>
          </button>
          <button
            onClick={() => scroll("right")}
            disabled={!canScrollRight}
            aria-label="Scroll right"
            className="size-8 rounded-full border border-border bg-surface flex items-center justify-center text-foreground-secondary hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">chevron_right</span>
          </button>
        </div>
      </div>
      <div
        ref={scrollRef}
        onScroll={checkScroll}
        className="flex gap-3.5 sm:gap-4 px-4 sm:px-6 lg:px-8 overflow-x-auto hide-scrollbar pb-2 scroll-smooth"
      >
        {shelf.movies.map((movie, idx) => {
          const isMarked = watchlistIds.has(movie.tmdb_id) || (movie.id != null && watchlistIds.has(movie.id));
          return (
            <div key={`shelf-${shelf.id}-${movie.tmdb_id || movie.id || idx}`} className="shrink-0 w-28 sm:w-36 md:w-40 lg:w-44">
              <MovieCard
                movie={movie}
                inWatchlist={isMarked}
                onWatchlist={onWatchlist}
                onTap={onTap}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ============================
   SEARCH BAR
============================ */

function SearchBar({
  value,
  onChange,
  onClear,
}: {
  value: string;
  onChange: (v: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="relative mx-4 sm:mx-6 lg:mx-8 my-3">
      <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">search</span>
      <input
        value={value}
        onChange={(e: React.ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
        placeholder="Search full catalogue by title or keyword..."
        className="w-full h-11 bg-surface border border-border rounded-xl pl-10 pr-10 text-xs sm:text-sm text-foreground placeholder:text-foreground-secondary focus:outline-none focus:border-primary transition-colors"
      />
      {value && (
        <button onClick={onClear} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary hover:text-foreground transition-colors">
          <span className="material-symbols-outlined text-[18px]">close</span>
        </button>
      )}
    </div>
  );
}

/* ============================
   MAIN DISCOVER PAGE
============================ */

export default function DiscoverPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial query parameters
  const urlView = searchParams.get("view");
  const urlCategory = (searchParams.get("category") as CategoryId) || "popular";
  const urlGenre = searchParams.get("genre") || "";
  const urlLang = searchParams.get("language") || "";
  const urlEra = searchParams.get("era") || "any";
  const urlRating = searchParams.get("min_rating") || "any";
  const urlSearch = searchParams.get("search") || "";
  const urlSort = (searchParams.get("sort_by") as CatalogueSort) || "popularity";

  const initialFilters: Filters = {
    genre: urlGenre,
    language: urlLang,
    era: urlEra,
    min_rating: urlRating,
  };

  // Determine initial surface view:
  // If explicitly requested via ?view=archive or ?view=catalogue, honor it.
  // If filters or search query are set, default to "catalogue".
  // Otherwise, default to "archive" if authenticated, or "catalogue" if guest.
  const [activeView, setActiveView] = useState<DiscoverView>(() => {
    if (urlView === "archive" || urlView === "catalogue") return urlView;
    if (urlSearch || urlGenre || (urlLang && urlLang !== "all") || (urlEra && urlEra !== "any") || (urlRating && urlRating !== "any") || urlCategory !== "popular") {
      return "catalogue";
    }
    const token = localStorage.getItem("auth_token");
    return token ? "archive" : "catalogue";
  });

  // State: Your Archive (Personalized Shelves)
  const [archiveShelves, setArchiveShelves] = useState<ArchiveShelf[]>([]);
  const [archiveSpotlight, setArchiveSpotlight] = useState<Movie | null>(null);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [archiveLoaded, setArchiveLoaded] = useState(false);

  // State: Complete Catalogue (Unpersonalized Browsing)
  const [catalogueSort, setCatalogueSort] = useState<CatalogueSort>(urlSort);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);

  // Filter controls
  const [filters, setFilters] = useState<Filters>(initialFilters);
  const [pendingFilters, setPendingFilters] = useState<Filters>(initialFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [searchQuery, setSearchQuery] = useState(urlSearch);
  const [activeMood, setActiveMood] = useState<string | null>(null);

  // Detail Sheet & Watchlist
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [watchlistIds, setWatchlistIds] = useState<Set<number>>(new Set());

  const sentinelRef = useRef<HTMLDivElement>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevSearchRef = useRef(searchQuery);
  const activeReqIdRef = useRef(0);

  const isAuthenticated = Boolean(localStorage.getItem("auth_token"));

  const hasActiveFilters = Boolean(
    filters.genre ||
    (filters.language && filters.language !== "all") ||
    (filters.era && filters.era !== "any") ||
    (filters.min_rating && filters.min_rating !== "any") ||
    filters.provider
  );

  /* ── Load user watchlist ── */
  useEffect(() => {
    apiRequest("/api/watchlist/")
      .then((raw: unknown) => {
        const data = raw as WatchlistResponse;
        if (Array.isArray(data.watchlist)) {
          const ids = new Set<number>();
          data.watchlist.forEach((item) => {
            if (item.movie_id) ids.add(item.movie_id);
            if (item.tmdb_id) ids.add(item.tmdb_id);
          });
          setWatchlistIds(ids);
        }
      })
      .catch(() => {});
  }, []);

  /* ── Load genres on mount ── */
  useEffect(() => {
    apiRequest("/api/genres/?industry=mixed")
      .then((raw: unknown) => {
        const data = raw as GenreResponse;
        if (Array.isArray(data.genres)) setGenres(data.genres);
      })
      .catch(() => {});
  }, []);

  /* ── Load Your Archive Shelves (Personalized) ── */
  const loadYourArchive = useCallback(async () => {
    if (!isAuthenticated) return;
    setArchiveLoading(true);
    setArchiveError(null);
    try {
      const data = await apiRequest("/api/your-archive/");
      const parsed = normalizeArchiveShelves(data);
      setArchiveShelves(parsed);

      if (parsed.length > 0 && parsed[0].movies.length > 0) {
        setArchiveSpotlight(parsed[0].movies[0]);
      } else {
        setArchiveSpotlight(null);
      }
      setArchiveLoaded(true);
    } catch (err: unknown) {
      console.error("[DiscoverPage] Error loading /api/your-archive/:", err);
      setArchiveError("Unable to load personalized archive shelves. Please verify your connection.");
    } finally {
      setArchiveLoading(false);
    }
  }, [isAuthenticated]);

  /* ── Fetch Complete Catalogue (Unpersonalized) ── */
  const fetchCatalogueMovies = useCallback(
    async (
      f: Filters,
      p: number,
      append: boolean,
      q?: string,
      sort?: CatalogueSort
    ) => {
      const currentReqId = ++activeReqIdRef.current;
      if (append) setLoadingMore(true);
      else {
        setLoading(true);
        setCatalogueError(null);
      }

      try {
        const params = new URLSearchParams();
        params.set("page", String(p));
        params.set("page_size", "20");

        if (q) params.set("search", q);
        if (f.genre) params.set("genre", f.genre);
        if (f.language) params.set("language", f.language);
        if (f.era && f.era !== "any") params.set("era", f.era);
        if (f.min_rating && f.min_rating !== "any") params.set("min_rating", f.min_rating);
        if (f.provider) params.set("watch_provider_id", f.provider);
        if (sort) {
          const sortMap: Record<string, string> = {
            rating: "vote_average.desc",
            popularity: "popularity.desc",
            release_date: "primary_release_date.desc",
            title: "title.asc",
          };
          params.set("sort_by", sortMap[sort] || "popularity.desc");
        }

        let data: any = null;
        try {
          data = await apiRequest(`/api/discover/?${params.toString()}`);
        } catch (discErr) {
          // Fallback to local /api/catalogue/ if live TMDB endpoint is unreachable
          console.warn("[DiscoverPage] Live discovery unavailable, falling back to local catalogue:", discErr);
          data = await apiRequest(`/api/catalogue/?${params.toString()}`);
        }

        if (currentReqId !== activeReqIdRef.current) return;

        const incoming: Movie[] = Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data?.movies)
          ? data.movies
          : [];

        setMovies((prev) => {
          if (!append) return incoming;
          const existingIds = new Set(prev.map((m) => m.tmdb_id || m.id));
          const fresh = incoming.filter((m) => !existingIds.has(m.tmdb_id || m.id));
          return [...prev, ...fresh];
        });

        const totalCount = data?.count ?? data?.total_results ?? null;
        const hasMorePages = data?.has_more ?? (totalCount !== null ? p * 20 < totalCount : incoming.length >= 20);
        setHasMore(Boolean(hasMorePages));
      } catch (err: unknown) {
        console.error("[DiscoverPage] Failed to fetch catalogue movies:", err);
        if (!append) {
          setCatalogueError("Failed to load catalogue. Please retry.");
        }
      } finally {
        if (currentReqId === activeReqIdRef.current) {
          if (append) setLoadingMore(false);
          else setLoading(false);
        }
      }
    },
    []
  );

  /* ── Effect: Trigger appropriate fetch when view or filters change ── */
  useEffect(() => {
    if (activeView === "archive") {
      if (!archiveLoaded) {
        loadYourArchive();
      }
    } else {
      setPage(1);
      fetchCatalogueMovies(filters, 1, false, searchQuery, catalogueSort);
    }
  }, [activeView, archiveLoaded, loadYourArchive, fetchCatalogueMovies, filters, searchQuery, catalogueSort]);

  /* ── Debounced Search for Catalogue ── */
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);

    // Skip redundant fetch on initial mount when searchQuery is empty
    if (searchQuery === "" && prevSearchRef.current === "") return;
    prevSearchRef.current = searchQuery;

    searchTimer.current = setTimeout(() => {
      if (activeView !== "catalogue") {
        setActiveView("catalogue");
      }
      setPage(1);
      fetchCatalogueMovies(filters, 1, false, searchQuery, catalogueSort);
    }, 350);

    return () => {
      if (searchTimer.current) clearTimeout(searchTimer.current);
    };
  }, [searchQuery, activeView, filters, catalogueSort, fetchCatalogueMovies]);

  /* ── Infinite Scroll Observer for Catalogue ── */
  useEffect(() => {
    if (activeView !== "catalogue" || !hasMore || loading || loadingMore || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          const next = page + 1;
          setPage(next);
          fetchCatalogueMovies(filters, next, true, searchQuery, catalogueSort);
        }
      },
      { rootMargin: "250px" }
    );
    const el = sentinelRef.current;
    if (el) observer.observe(el);
    return () => {
      if (el) observer.unobserve(el);
    };
  }, [activeView, hasMore, loading, loadingMore, page, filters, searchQuery, catalogueSort, fetchCatalogueMovies]);

  /* ── Keyboard Dismissal ── */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        const target = e.target as HTMLElement | null;
        const isTextInput = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
        if (isTextInput && !selectedMovie && !showFilters) {
          target.blur();
          return;
        }

        if (selectedMovie) {
          e.preventDefault();
          setSelectedMovie(null);
          return;
        }
        if (showFilters) {
          e.preventDefault();
          setShowFilters(false);
          return;
        }
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedMovie, showFilters]);

  /* ── Watchlist Toggle ── */
  async function toggleWatchlist(movie: Movie) {
    const key = movie.tmdb_id || movie.id || 0;
    if (!key) return;

    const already = watchlistIds.has(key) || (movie.id != null && watchlistIds.has(movie.id));
    setWatchlistIds((prev) => {
      const next = new Set(prev);
      if (already) {
        next.delete(key);
        if (movie.id) next.delete(movie.id);
      } else {
        next.add(key);
        if (movie.id) next.add(movie.id);
      }
      return next;
    });

    try {
      if (already) {
        await apiRequest(`/api/watchlist/${key}/`, { method: "DELETE" });
        trackEvent("watchlist_removed", { movie_id: key, source: "discover" });
      } else {
        await apiRequest("/api/watchlist/", {
          method: "POST",
          body: JSON.stringify({ tmdb_id: movie.tmdb_id, movie_id: movie.id || movie.tmdb_id }),
        });
        trackEvent("watchlist_added", { movie_id: key, source: "discover" });
      }
    } catch {
      // Revert on failure
      setWatchlistIds((prev) => {
        const next = new Set(prev);
        if (already) {
          next.add(key);
          if (movie.id) next.add(movie.id);
        } else {
          next.delete(key);
          if (movie.id) next.delete(movie.id);
        }
        return next;
      });
    }
  }

  /* ── View Switcher ── */
  function handleViewChange(newView: DiscoverView) {
    setActiveView(newView);
    const newParams = new URLSearchParams(searchParams);
    newParams.set("view", newView);
    setSearchParams(newParams, { replace: true });
  }

  /* ── Filter Actions ── */
  function applyFilters() {
    setFilters(pendingFilters);
    setActiveMood(null);
    setShowFilters(false);
  }

  function clearFilters() {
    setPendingFilters(EMPTY_FILTERS);
    setFilters(EMPTY_FILTERS);
    setActiveMood(null);
    setSearchQuery("");
    setShowFilters(false);
  }

  function clearSearch() {
    setSearchQuery("");
  }

  function applyMood(mood: typeof MOODS[0]) {
    const isActive = activeMood === mood.label;
    if (isActive) {
      setActiveMood(null);
      setFilters(EMPTY_FILTERS);
    } else {
      setActiveMood(mood.label);
      setFilters({ genre: mood.genre, language: mood.language, era: mood.era, min_rating: mood.min_rating });
      if (activeView !== "catalogue") {
        setActiveView("catalogue");
      }
    }
    setSearchQuery("");
  }

  const activeFilterCount = [
    filters.genre,
    filters.language,
    filters.era !== "any" ? filters.era : "",
    filters.min_rating !== "any" ? filters.min_rating : "",
    filters.provider,
  ].filter(Boolean).length;

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">
      {/* ── Editorial Header ── */}
      <CinemaHeader
        current="discover"
        title={activeView === "archive" ? "Your Archive" : "Complete Catalogue"}
        subtitle={
          activeView === "archive"
            ? "Personalized shelves tailored to your cinematic taste"
            : "Unfiltered global catalogue with zero taste bias"
        }
        onBack={() => navigate(-1)}
        rightAction={
          activeView === "catalogue" ? (
            <button
              onClick={() => {
                setPendingFilters(filters);
                setShowFilters(true);
              }}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                activeFilterCount > 0
                  ? "bg-primary/10 border-primary text-primary"
                  : "bg-surface border-border text-foreground-secondary hover:text-foreground hover:border-foreground-secondary"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]">tune</span>
              <span className="hidden sm:inline">Filter</span>
              {activeFilterCount > 0 && (
                <span className="size-4 rounded-full bg-primary text-surface text-[10px] font-bold flex items-center justify-center ml-0.5">
                  {activeFilterCount}
                </span>
              )}
            </button>
          ) : undefined
        }
      />

      {/* ── Surface Navigation Tabs (Your Archive vs Complete Catalogue) ── */}
      <div className="w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-2 flex items-center justify-center shrink-0">
        <div className="inline-flex rounded-xl p-1 bg-surface border border-border shadow-xs">
          <button
            onClick={() => handleViewChange("archive")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs uppercase tracking-wider transition-all ${
              activeView === "archive"
                ? "bg-primary text-surface shadow-xs font-bold"
                : "text-foreground-secondary hover:text-foreground hover:bg-surface-secondary/60 font-semibold"
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">auto_awesome</span>
            Your Archive
          </button>
          <button
            onClick={() => handleViewChange("catalogue")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs uppercase tracking-wider transition-all ${
              activeView === "catalogue"
                ? "bg-primary text-surface shadow-xs font-bold"
                : "text-foreground-secondary hover:text-foreground hover:bg-surface-secondary/60 font-semibold"
            }`}
          >
            <span className="material-symbols-outlined text-[16px]">local_library</span>
            Live Catalogue
          </button>
        </div>
      </div>

      <div className="w-full max-w-7xl mx-auto flex-1 flex flex-col pb-20 md:pb-10">
        {/* =======================================================
            SURFACE 1: YOUR ARCHIVE (Personalized Shelves)
        ======================================================= */}
        {activeView === "archive" && (
          <main className="flex-1 pt-2 pb-8">
            {!isAuthenticated ? (
              <div className="mx-4 sm:mx-6 lg:mx-8 my-8 p-8 sm:p-10 rounded-3xl border border-border/80 bg-surface text-center space-y-4 max-w-2xl mx-auto shadow-sm">
                <div className="size-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto">
                  <span className="material-symbols-outlined text-2xl">lock_open</span>
                </div>
                <div className="space-y-1.5">
                  <h3 className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground">
                    Personalized Archive Requires Sign In
                  </h3>
                  <p className="text-xs sm:text-sm text-foreground-secondary max-w-md mx-auto leading-relaxed">
                    Sign in to Flick to generate your 5 personal cinematic shelves, tailored to your swipe and screening history.
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
                  <button
                    onClick={() => navigate("/login")}
                    className="h-10 px-5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-all shadow-xs"
                  >
                    Sign In
                  </button>
                  <button
                    onClick={() => handleViewChange("catalogue")}
                    className="h-10 px-5 rounded-xl border border-border hover:border-primary/50 bg-surface-secondary text-foreground font-semibold text-xs uppercase tracking-wider transition-all"
                  >
                    Browse Complete Catalogue
                  </button>
                </div>
              </div>
            ) : archiveLoading ? (
              <div className="px-4 sm:px-6 lg:px-8 space-y-8 pt-4">
                <div className="h-64 rounded-3xl bg-surface border border-border animate-pulse" />
                <ShelfSkeleton />
                <ShelfSkeleton />
                <ShelfSkeleton />
              </div>
            ) : archiveError ? (
              <div className="mx-4 sm:mx-6 lg:mx-8 my-8 p-8 rounded-2xl border border-error/30 bg-error/5 text-center space-y-3 max-w-lg mx-auto">
                <span className="material-symbols-outlined text-3xl text-error">error</span>
                <p className="text-sm text-foreground font-medium">{archiveError}</p>
                <button
                  onClick={() => loadYourArchive()}
                  className="px-4 py-2 rounded-xl bg-primary text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-2xs"
                >
                  Retry
                </button>
              </div>
            ) : archiveShelves.length === 0 ? (
              <div className="mx-4 sm:mx-6 lg:mx-8 my-8 p-8 sm:p-10 rounded-3xl border border-border/80 bg-surface text-center space-y-4 max-w-2xl mx-auto shadow-sm">
                <div className="size-12 rounded-2xl bg-primary/10 text-primary flex items-center justify-center mx-auto">
                  <span className="material-symbols-outlined text-2xl">auto_awesome</span>
                </div>
                <div className="space-y-1.5">
                  <h3 className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground">
                    Your Archive is Warming Up
                  </h3>
                  <p className="text-xs sm:text-sm text-foreground-secondary max-w-md mx-auto leading-relaxed">
                    We haven't recorded enough interactions yet to build your 5 personal shelves. Start a screening deck or explore the catalogue below to calibrate your taste profile!
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-center gap-3 pt-3">
                  <button
                    onClick={() => navigate("/session/create")}
                    className="h-10 px-5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-all shadow-xs"
                  >
                    Launch Screening Deck
                  </button>
                  <button
                    onClick={() => handleViewChange("catalogue")}
                    className="h-10 px-5 rounded-xl border border-border hover:border-primary/50 bg-surface-secondary text-foreground font-semibold text-xs uppercase tracking-wider transition-all"
                  >
                    Explore Complete Catalogue
                  </button>
                </div>
              </div>
            ) : (
              <div>
                {/* Spotlight Selection Hero */}
                {archiveSpotlight && (
                  <HeroCard
                    movie={archiveSpotlight}
                    inWatchlist={
                      watchlistIds.has(archiveSpotlight.tmdb_id) ||
                      (archiveSpotlight.id != null && watchlistIds.has(archiveSpotlight.id))
                    }
                    onWatchlist={toggleWatchlist}
                    onTap={setSelectedMovie}
                  />
                )}

                {/* The 5 Personalized Shelves */}
                {archiveShelves.map((shelf) => (
                  <ArchiveShelfSection
                    key={shelf.id}
                    shelf={shelf}
                    watchlistIds={watchlistIds}
                    onWatchlist={toggleWatchlist}
                    onTap={setSelectedMovie}
                  />
                ))}

                {/* Bottom link to Complete Catalogue */}
                <div className="mt-8 mb-4 text-center px-4">
                  <button
                    onClick={() => handleViewChange("catalogue")}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-xs uppercase font-semibold tracking-wider text-primary hover:underline transition-all shadow-2xs"
                  >
                    <span>Browse Unfiltered Complete Catalogue</span>
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </button>
                </div>
              </div>
            )}
          </main>
        )}

        {/* =======================================================
            SURFACE 2: COMPLETE CATALOGUE (Unpersonalized Browsing)
        ======================================================= */}
        {activeView === "catalogue" && (
          <main className="flex-1 pb-8">
            {/* Search Bar */}
            <SearchBar value={searchQuery} onChange={setSearchQuery} onClear={clearSearch} />

            {/* Live Streaming Platforms Filter Bar */}
            <div className="flex items-center gap-2 px-4 sm:px-6 lg:px-8 py-2.5 overflow-x-auto hide-scrollbar shrink-0 bg-surface/50 border-b border-border/40">
              <span className="text-[11px] font-mono uppercase tracking-wider text-foreground-secondary shrink-0 flex items-center gap-1 font-semibold pr-1">
                <span className="material-symbols-outlined text-[15px] text-primary">live_tv</span>
                Stream On:
              </span>
              {STREAMING_PLATFORMS.map((plat) => {
                const isActive = (filters.provider || "") === plat.id;
                return (
                  <button
                    key={plat.id || "__all__"}
                    onClick={() => {
                      setFilters((f) => ({ ...f, provider: isActive ? "" : plat.id }));
                      setActiveMood(null);
                    }}
                    className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all border ${
                      isActive
                        ? "bg-primary text-surface border-primary font-bold shadow-xs scale-105"
                        : "bg-surface border-border text-foreground-secondary hover:text-foreground hover:border-primary/50"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[14px]">{plat.icon}</span>
                    <span>{plat.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Sort & Quick Filter Bar */}
            <div className="px-4 sm:px-6 lg:px-8 py-2 flex flex-col gap-2.5 md:flex-row md:items-center md:justify-between shrink-0">
              {/* Mood Quick Picks */}
              <div className="flex items-center gap-2 overflow-x-auto hide-scrollbar pb-0.5">
                {MOODS.map((mood) => (
                  <button
                    key={mood.id}
                    onClick={() => applyMood(mood)}
                    className={`shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all border cursor-pointer ${
                      activeMood === mood.label
                        ? "bg-primary border-primary text-surface font-semibold shadow-xs"
                        : "bg-surface border-border text-foreground-secondary hover:text-foreground hover:border-primary/50"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[15px]">{mood.icon}</span>
                    <span>{mood.label}</span>
                  </button>
                ))}
              </div>

              {/* Sort Selector */}
              <div className="flex items-center gap-1.5 overflow-x-auto hide-scrollbar shrink-0 md:pl-2 md:border-l md:border-border/50">
                <span className="text-[10px] font-mono text-foreground-secondary uppercase tracking-wider shrink-0 font-semibold">Sort:</span>
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setCatalogueSort(opt.value)}
                    className={`shrink-0 px-2.5 py-1 rounded-md text-[11px] font-mono font-medium transition-all border cursor-pointer ${
                      catalogueSort === opt.value
                        ? "bg-primary/10 border-primary text-primary font-bold shadow-2xs"
                        : "bg-surface border-border text-foreground-secondary hover:text-foreground hover:border-primary/40"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Global Language Filter Pills */}
            <div className="flex gap-2 px-4 sm:px-6 lg:px-8 pb-3 overflow-x-auto hide-scrollbar shrink-0 border-b border-border/60">
              {LANGUAGES.map((lang) => (
                <Chip
                  key={lang.code === "" ? "__all__" : lang.code}
                  label={lang.label}
                  active={filters.language === lang.code}
                  onClick={() => {
                    setFilters((f) => ({ ...f, language: lang.code }));
                    setActiveMood(null);
                  }}
                />
              ))}
            </div>

            {/* Active Filters Display */}
            <div className="px-4 sm:px-6 lg:px-8 pt-4">
              <div className="flex items-center gap-2 mb-4 flex-wrap">
                {searchQuery && (
                  <span className="flex items-center gap-1 bg-surface-secondary border border-border text-foreground text-xs font-medium px-2.5 py-1 rounded-lg">
                    "{searchQuery}"
                    <button onClick={clearSearch} className="ml-1 text-foreground-secondary hover:text-foreground">
                      <span className="material-symbols-outlined text-[12px]">close</span>
                    </button>
                  </span>
                )}

                {activeMood && (
                  <span className="flex items-center gap-1.5 bg-primary/10 border border-primary/30 text-primary text-xs font-semibold px-2.5 py-1 rounded-lg">
                    {(() => {
                      const m = MOODS.find((item) => item.label === activeMood);
                      return m ? <span className="material-symbols-outlined text-[13px]">{m.icon}</span> : null;
                    })()}
                    <span>{activeMood}</span>
                    <button onClick={clearFilters} className="ml-1 text-primary hover:opacity-80">
                      <span className="material-symbols-outlined text-[12px]">close</span>
                    </button>
                  </span>
                )}

                {filters.provider && (
                  <span className="flex items-center gap-1.5 bg-primary/10 border border-primary/30 text-primary text-xs font-semibold px-2.5 py-1 rounded-lg">
                    <span className="material-symbols-outlined text-[13px]">live_tv</span>
                    <span>{STREAMING_PLATFORMS.find((p) => p.id === filters.provider)?.label || "Streaming"}</span>
                    <button
                      onClick={() => setFilters((f) => ({ ...f, provider: "" }))}
                      className="ml-1 text-primary hover:opacity-80"
                    >
                      <span className="material-symbols-outlined text-[12px]">close</span>
                    </button>
                  </span>
                )}

                {!searchQuery && !activeMood && hasActiveFilters && (
                  <span className="text-xs text-foreground-secondary">
                    Showing filtered catalogue results
                  </span>
                )}

                {(activeFilterCount > 0 || searchQuery) && (
                  <button onClick={clearFilters} className="text-xs text-foreground-secondary hover:text-foreground underline underline-offset-2">
                    Reset filters
                  </button>
                )}
              </div>

              {/* Error banner */}
              {catalogueError && (
                <div className="mb-6 p-4 rounded-xl border border-error/30 bg-error/5 text-center">
                  <p className="text-xs text-error font-medium">{catalogueError}</p>
                  <button
                    onClick={() => fetchCatalogueMovies(filters, 1, false, searchQuery, catalogueSort)}
                    className="mt-2 px-3 py-1 bg-primary text-surface rounded-lg text-xs font-semibold uppercase tracking-wider"
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Dynamic Grid / Loading / Empty States */}
              {loading ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3.5 sm:gap-4 md:gap-5">
                  {Array.from({ length: 12 }).map((_, i) => (
                    <MovieCardSkeleton key={i} />
                  ))}
                </div>
              ) : movies.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 gap-3 text-center px-6">
                  <span className="material-symbols-outlined text-foreground-secondary text-4xl">movie_filter</span>
                  <p className="font-editorial text-lg font-bold text-foreground">No Titles Matched</p>
                  <p className="text-xs text-foreground-secondary max-w-xs -mt-1 leading-relaxed">
                    Adjust your search keywords or broaden your filter parameters to discover films across the catalogue.
                  </p>
                  <button
                    onClick={clearFilters}
                    className="mt-2 px-4 py-2 rounded-xl bg-primary text-surface text-xs font-semibold uppercase tracking-wider shadow-sm"
                  >
                    Clear Filters
                  </button>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-3.5 sm:gap-4 md:gap-5">
                    {movies.map((movie, idx) => {
                      const isMarked = watchlistIds.has(movie.tmdb_id) || (movie.id != null && watchlistIds.has(movie.id));
                      return (
                        <MovieCard
                          key={`cat-${movie.tmdb_id || movie.id || idx}`}
                          movie={movie}
                          inWatchlist={isMarked}
                          onWatchlist={toggleWatchlist}
                          onTap={setSelectedMovie}
                        />
                      );
                    })}
                  </div>

                  <div ref={sentinelRef} className="h-10 mt-5 flex items-center justify-center">
                    {loadingMore && (
                      <div className="flex gap-1.5">
                        {[0, 1, 2].map((i) => (
                          <div
                            key={i}
                            className="w-1.5 h-1.5 rounded-full bg-primary/60 animate-pulse"
                            style={{ animationDelay: `${i * 0.15}s` }}
                          />
                        ))}
                      </div>
                    )}
                    {!hasMore && movies.length > 0 && (
                      <p className="text-[11px] text-foreground-secondary font-medium">End of available catalogue</p>
                    )}
                  </div>
                </>
              )}
            </div>
          </main>
        )}
      </div>

      {/* ── Mobile Navigation ── */}
      <BottomNav current="discover" />

      {/* ── Movie Detail Sheet ── */}
      <AnimatePresence>
        {selectedMovie && (
          <MovieDetailSheet
            movie={selectedMovie}
            inWatchlist={watchlistIds.has(selectedMovie.tmdb_id) || (selectedMovie.id != null && watchlistIds.has(selectedMovie.id))}
            onWatchlist={toggleWatchlist}
            onClose={() => setSelectedMovie(null)}
          />
        )}
      </AnimatePresence>

      {/* ── Filter Bottom Sheet ── */}
      <AnimatePresence>
        {showFilters && (
          <div
            className="fixed inset-0 z-50 flex flex-col justify-end md:justify-center md:items-center p-0 md:p-6"
            onClick={() => setShowFilters(false)}
          >
            <motion.div
              variants={backdropVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            />
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="catalogue-filters-title"
              variants={bottomSheetVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="relative bg-surface border-t md:border border-border rounded-t-3xl md:rounded-2xl z-50 max-h-[85vh] flex flex-col max-w-lg md:max-w-xl mx-auto w-full shadow-2xl overflow-hidden"
              onClick={(e: React.MouseEvent<HTMLDivElement>) => e.stopPropagation()}
            >
              <div className="w-10 h-1 rounded-full bg-border mx-auto mt-3 mb-1 md:hidden" />
              <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-primary text-xl">tune</span>
                  <h2 id="catalogue-filters-title" className="font-editorial text-xl font-bold text-foreground">
                    Catalogue Filters
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={clearFilters}
                    className="text-xs text-foreground-secondary hover:text-foreground transition-colors px-2 py-1 cursor-pointer"
                  >
                    Reset
                  </button>
                  <button
                    onClick={() => setShowFilters(false)}
                    className="size-9 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-foreground-secondary hover:text-foreground transition-colors cursor-pointer"
                    aria-label="Close filters"
                  >
                    <span className="material-symbols-outlined text-[18px]">close</span>
                  </button>
                </div>
              </div>

              <div className="overflow-y-auto overscroll-contain px-6 py-4 flex-1 space-y-5">
                <div>
                  <span className="text-[10px] font-semibold text-primary uppercase tracking-widest mb-2 block">Genre</span>
                  <div className="flex flex-wrap gap-2">
                    <Chip label="All Genres" active={pendingFilters.genre === ""} onClick={() => setPendingFilters((f) => ({ ...f, genre: "" }))} />
                    {genres.map((g) => {
                      const val = String(g.tmdb_id || g.id);
                      return (
                        <Chip
                          key={g.id}
                          label={g.name}
                          active={pendingFilters.genre === val}
                          onClick={() => setPendingFilters((f) => ({ ...f, genre: val }))}
                        />
                      );
                    })}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] font-semibold text-primary uppercase tracking-widest mb-2 block">Era</span>
                  <div className="flex flex-wrap gap-2">
                    {ERAS.map((e) => (
                      <Chip
                        key={e.value}
                        label={e.label}
                        active={pendingFilters.era === e.value}
                        onClick={() => setPendingFilters((f) => ({ ...f, era: e.value }))}
                      />
                    ))}
                  </div>
                </div>

                <div>
                  <span className="text-[10px] font-semibold text-primary uppercase tracking-widest mb-2 block">Minimum Rating</span>
                  <div className="flex gap-2">
                    {RATINGS.map((r) => (
                      <Chip
                        key={r.value}
                        label={r.label}
                        active={pendingFilters.min_rating === r.value}
                        onClick={() => setPendingFilters((f) => ({ ...f, min_rating: r.value }))}
                      />
                    ))}
                  </div>
                </div>
              </div>

              <div className="p-4 px-6 border-t border-border/60 bg-surface pb-[max(1.5rem,calc(1rem+env(safe-area-inset-bottom)))] shrink-0">
                <button
                  onClick={applyFilters}
                  className="w-full h-12 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider shadow-sm transition-all active:scale-[0.98] cursor-pointer"
                >
                  Apply Filter Parameters
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      <style>{`
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to   { transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
