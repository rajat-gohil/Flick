import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { apiRequest } from "../lib/api";
import { usePrefersReducedMotion } from "../lib/motion";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type WatchlistItem = {
  id: number;
  movie_id: number;
  movie_title: string;
  poster_url: string | null;
  rating: number | null;
  release_year: number | null;
  trailer_url: string | null;
  session_id: number | null;
  added_at: string;
  watched: boolean;
};

export default function WatchlistPage() {
  const navigate = useNavigate();
  const shouldReduceMotion = usePrefersReducedMotion();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"all" | "unwatched" | "watched">("all");
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const fetchWatchlist = useCallback(async () => {
    try {
      const data = await apiRequest("/api/watchlist/");
      setItems(data.watchlist ?? []);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const toggleWatched = async (movieId: number, current: boolean) => {
    setTogglingId(movieId);
    setItems(prev => prev.map(i => (i.movie_id === movieId ? { ...i, watched: !current } : i)));
    try {
      await apiRequest(`/api/watchlist/${movieId}/`, {
        method: "PATCH",
        body: JSON.stringify({ watched: !current }),
      });
    } catch {
      setItems(prev => prev.map(i => (i.movie_id === movieId ? { ...i, watched: current } : i)));
    } finally {
      setTogglingId(null);
    }
  };

  const removeItem = async (movieId: number) => {
    setRemovingId(movieId);
    setItems(prev => prev.filter(i => i.movie_id !== movieId));
    try {
      await apiRequest(`/api/watchlist/${movieId}/`, { method: "DELETE" });
    } catch {
      fetchWatchlist();
    } finally {
      setRemovingId(null);
    }
  };

  const filtered = items.filter(i => {
    if (filter === "watched") return i.watched;
    if (filter === "unwatched") return !i.watched;
    return true;
  });

  const unwatchedCount = items.filter(i => !i.watched).length;

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* Header */}
      <CinemaHeader
        current="watchlist"
        title="Personal Watchlist"
        subtitle={unwatchedCount > 0 ? `${unwatchedCount} pending viewings` : undefined}
        onBack={() => navigate(-1)}
      />

      <div className="w-full max-w-6xl mx-auto flex-1 flex flex-col px-4 sm:px-6 lg:px-8 py-4 pb-24 md:pb-12">

        {/* Filter tabs */}
        <div className="flex gap-2 max-w-md mx-auto w-full pt-1 pb-4">
          {(["all", "unwatched", "watched"] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex-1 min-h-11 sm:min-h-9 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all border relative overflow-hidden cursor-pointer ${
                filter === f
                  ? "border-primary text-surface shadow-xs"
                  : "bg-surface border-border text-foreground-secondary hover:text-foreground"
              }`}
            >
              {filter === f && (
                <motion.span
                  layoutId={shouldReduceMotion ? undefined : "watchlistFilterPill"}
                  className="absolute inset-0 bg-primary rounded-xl -z-0"
                  transition={
                    shouldReduceMotion
                      ? { duration: 0 }
                      : { type: "spring", stiffness: 420, damping: 34, mass: 0.8 }
                  }
                />
              )}
              <span className="relative z-10">{f === "all" ? "All" : f === "unwatched" ? "Pending" : "Viewed"}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <main className="flex-1 overflow-y-auto pt-1">
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="size-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && filtered.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-20 text-center">
              <span className="material-symbols-outlined text-foreground-secondary text-4xl">bookmark</span>
              <div>
                <p className="font-editorial text-lg font-bold text-foreground mb-1">
                  {filter === "watched" ? "No Viewings Logged" : filter === "unwatched" ? "All Caught Up" : "Watchlist Empty"}
                </p>
                <p className="text-xs text-foreground-secondary max-w-xs">
                  {filter === "all" ? "Films you save from discovery or mutual sessions appear here." : "Switch filter to view other selections."}
                </p>
              </div>
              {filter === "all" && (
                <button
                  onClick={() => navigate("/session/create")}
                  className="mt-2 h-10 px-5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-xs"
                >
                  Start a Screening
                </button>
              )}
            </div>
          )}

          {!loading && filtered.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
              <AnimatePresence mode="popLayout">
                {filtered.map(item => (
                  <motion.div
                    layout={!shouldReduceMotion}
                    key={item.id}
                    initial={shouldReduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.95, y: 10 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={
                      shouldReduceMotion
                        ? { opacity: 0 }
                        : { opacity: 0, scale: 0.9, y: -8, transition: { duration: 0.2 } }
                    }
                    transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                    className={`flex gap-3.5 rounded-xl border p-3.5 sm:p-4 transition-colors ${
                      item.watched
                        ? "bg-surface/80 border-border/70"
                        : "bg-surface border-border hover:border-primary/40 shadow-xs"
                    }`}
                  >
                    {/* Poster */}
                    <div className="shrink-0 w-16 sm:w-20 aspect-[2/3] rounded-lg overflow-hidden bg-surface-secondary border border-border shadow-xs">
                      {item.poster_url ? (
                        <img
                          src={item.poster_url}
                          alt={item.movie_title}
                          className={`w-full h-full object-cover transition-all ${item.watched ? "grayscale opacity-75" : ""}`}
                        />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-foreground-secondary">
                          <span className="material-symbols-outlined text-[20px]">movie</span>
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0 flex flex-col justify-between py-0.5">
                      <div>
                        <h3 className={`font-editorial text-sm sm:text-base font-semibold leading-tight line-clamp-2 mb-1.5 ${
                          item.watched ? "text-foreground-secondary" : "text-foreground"
                        }`}>
                          {item.movie_title}
                        </h3>
                        <div className="flex items-center gap-2 flex-wrap text-xs text-foreground-secondary">
                          {item.rating && (
                            <span className="flex items-center gap-0.5 text-primary font-semibold">
                              <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                              {item.rating.toFixed(1)}
                            </span>
                          )}
                          {item.release_year && <span>{item.release_year}</span>}
                          {item.watched && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-secondary text-foreground font-mono text-[10px] font-semibold uppercase tracking-wider">
                              <span className="material-symbols-outlined text-[12px] text-primary">check_circle</span>
                              Viewed
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-2 mt-3 flex-wrap">
                        {item.trailer_url && (
                          <a
                            href={item.trailer_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 min-h-11 sm:min-h-9 px-3.5 rounded-xl bg-surface-secondary border border-border text-foreground-secondary hover:text-foreground text-[11px] font-medium transition-all active:scale-95"
                          >
                            <span className="material-symbols-outlined text-[14px]">play_arrow</span>
                            Trailer
                          </a>
                        )}
                        <motion.button
                          whileTap={shouldReduceMotion ? undefined : { scale: 0.94 }}
                          onClick={() => toggleWatched(item.movie_id, item.watched)}
                          disabled={togglingId === item.movie_id}
                          className={`flex items-center gap-1.5 min-h-11 sm:min-h-9 px-3.5 rounded-xl text-[11px] font-semibold transition-colors border cursor-pointer ${
                            item.watched
                              ? "bg-surface-secondary border-border text-foreground hover:bg-surface"
                              : "bg-primary/10 border-primary/30 text-primary hover:bg-primary/20"
                          }`}
                        >
                          <motion.span
                            animate={
                              togglingId === item.movie_id && !shouldReduceMotion
                                ? { scale: [1, 1.3, 1], rotate: [0, 15, 0] }
                                : { scale: 1, rotate: 0 }
                            }
                            transition={{ duration: 0.28, type: "spring", stiffness: 400, damping: 16 }}
                            className="material-symbols-outlined text-[14px]"
                          >
                            {item.watched ? "replay" : "check_circle"}
                          </motion.span>
                          <span>{item.watched ? "Rewatch" : "Mark Viewed"}</span>
                        </motion.button>
                      </div>
                    </div>

                    {/* Remove Button with 44px Touch Target Area */}
                    <motion.button
                      whileTap={shouldReduceMotion ? undefined : { scale: 0.88 }}
                      onClick={() => removeItem(item.movie_id)}
                      disabled={removingId === item.movie_id}
                      className="shrink-0 size-11 flex items-center justify-center text-foreground-secondary hover:text-error hover:bg-surface-secondary transition-colors rounded-full self-start -mr-2 -mt-2 active:scale-90 cursor-pointer"
                      aria-label="Remove from watchlist"
                    >
                      <span className="material-symbols-outlined text-[18px]">close</span>
                    </motion.button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </main>
      </div>

      {/* Bottom Nav */}
      <BottomNav current="watchlist" />
    </div>
  );
}
