import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { apiRequest, ApiError } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { isGuest, isLoggedIn } from "../lib/auth";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";
import { MovieDetailSheet, type Movie } from "./DiscoverPage";
import { prefersReducedMotion } from "../lib/motion";

/* ============================
   TYPES
============================ */

type ApiErrorResponse = {
  error?: string;
  errors?: { detail?: string; non_field_errors?: string[] };
};

type RecentSession = {
  id: number;
  name: string;
  date: string;
  matches: number;
  ended: boolean;
  participants: { avatar?: string; initials: string }[];
};

type DiscoverApiResponse = {
  movies?: Movie[];
  results?: Movie[];
};

/* ============================
   HELPERS & SUB-COMPONENTS
============================ */

function AvatarPlaceholder({ initials }: { initials: string }) {
  return (
    <div className="size-7 rounded-full border border-border bg-surface-secondary flex items-center justify-center text-[10px] font-bold text-foreground">
      {initials}
    </div>
  );
}

/* ============================
   MAIN HOMEPAGE
============================ */

export default function HomePage() {
  const navigate = useNavigate();
  const userDisplayName = localStorage.getItem("display_name") || localStorage.getItem("username") || "";

  // Session & Join State
  const [joinCode, setJoinCode] = useState("");
  const [joinLoading, setJoinLoading] = useState(false);
  const [joinError, setJoinError] = useState("");
  const [recentSessions, setRecentSessions] = useState<RecentSession[]>([]);

  // Curator's Selection State
  const [curatorMovie, setCuratorMovie] = useState<Movie | null>(null);
  const [curatorShelf, setCuratorShelf] = useState<Movie[]>([]);
  const [curatorLoading, setCuratorLoading] = useState(true);
  const [curatorConfidence, setCuratorConfidence] = useState<string | null>(null);
  const [spotlightImgError, setSpotlightImgError] = useState(false);
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [watchlistIds, setWatchlistIds] = useState<Set<number>>(new Set());
  const [stampedMovieId, setStampedMovieId] = useState<number | null>(null);

  // Account Activation State
  const [profileUser, setProfileUser] = useState<{
    id?: number;
    username?: string;
    display_name?: string;
    email?: string;
    email_verified?: boolean;
    is_guest?: boolean;
    recovery_code?: string;
  } | null>(null);
  const [showActivationModal, setShowActivationModal] = useState(false);
  const [copiedActivationCode, setCopiedActivationCode] = useState(false);
  const [resendingVerification, setResendingVerification] = useState(false);
  const [verificationSent, setVerificationSent] = useState(false);

  /* ── Load user profile for activation status ── */
  useEffect(() => {
    if (isLoggedIn()) {
      apiRequest("/api/users/profile/")
        .then((res: { success?: boolean; user?: typeof profileUser }) => {
          if (res?.success && res.user) {
            setProfileUser(res.user);
            if (res.user.is_guest === false) {
              localStorage.setItem("is_guest", "false");
            }
          }
        })
        .catch(() => {});
    }
  }, []);

  // An account is unactivated ONLY if it is an unconverted guest account.
  // When profile is fetched from backend, profileUser.is_guest is authoritative.
  const isGuestAccount = profileUser ? Boolean(profileUser.is_guest) : isGuest();
  const isAccountUnactivated = isLoggedIn() && isGuestAccount;

  /* ── Load recent sessions ── */
  useEffect(() => {
    apiRequest("/api/sessions/recent/")
      .then((data: { sessions?: RecentSession[] }) => {
        if (Array.isArray(data.sessions)) {
          setRecentSessions(data.sessions);
        }
      })
      .catch(() => {});
  }, []);

  /* ── Load user watchlist for status checks ── */
  const loadWatchlist = () => {
    apiRequest("/api/watchlist/")
      .then((data: { watchlist?: { movie_id: number; tmdb_id?: number }[] }) => {
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
  };

  useEffect(() => {
    loadWatchlist();
  }, []);

  /* ── Load Curator's Selection from Curators Selection API ── */
  useEffect(() => {
    async function loadCuratorSelection() {
      setCuratorLoading(true);
      try {
        const data = await apiRequest("/api/curators-selection/");
        const list: Movie[] = Array.isArray(data?.movies)
          ? data.movies
          : Array.isArray(data?.results)
          ? data.results
          : Array.isArray(data)
          ? data
          : [];
        const confidence = data?.confidence || list[0]?.explanation?.confidence || null;
        setCuratorConfidence(confidence);

        if (list.length > 0) {
          const spotlight = list[0];
          setCuratorMovie(spotlight);
          setSpotlightImgError(false);
          setCuratorShelf(
            list.filter((m: Movie) => (m.id || m.tmdb_id) !== (spotlight.id || spotlight.tmdb_id)).slice(0, 5)
          );
        } else {
          // If empty list, fallback to discover top_rated with cold start status
          const fallback: DiscoverApiResponse = await apiRequest("/api/discover/?category=top_rated&page=1");
          const fallbackList = Array.isArray(fallback?.movies) ? fallback.movies : [];
          setCuratorConfidence("COLD_START");
          if (fallbackList.length > 0) {
            setCuratorMovie(fallbackList[0]);
            setCuratorShelf(fallbackList.slice(1, 6));
          }
        }
      } catch (err) {
        console.error("[HomePage] Error loading curators selection, falling back to top_rated:", err);
        try {
          const fallback: DiscoverApiResponse = await apiRequest("/api/discover/?category=top_rated&page=1");
          const list = Array.isArray(fallback?.movies) ? fallback.movies : [];
          setCuratorConfidence("COLD_START");
          if (list.length > 0) {
            setCuratorMovie(list[0]);
            setCuratorShelf(list.slice(1, 6));
          }
        } catch (errFallback) {
          console.error("[HomePage] Error loading curator fallback:", errFallback);
        }
      } finally {
        setCuratorLoading(false);
      }
    }

    loadCuratorSelection();
  }, []);

  /* ── Watchlist Toggle with Ticket Stamp Feedback ── */
  const handleToggleWatchlist = async (movie: Movie) => {
    const targetId = movie.id || movie.tmdb_id;
    const inList = watchlistIds.has(targetId);

    if (inList) {
      setWatchlistIds((prev) => {
        const next = new Set(prev);
        next.delete(targetId);
        return next;
      });
      try {
        await apiRequest(`/api/watchlist/${targetId}/`, { method: "DELETE" });
      } catch {
        loadWatchlist();
      }
    } else {
      setWatchlistIds((prev) => new Set(prev).add(targetId));
      // Trigger ticket-stamp visual feedback
      setStampedMovieId(targetId);
      setTimeout(() => setStampedMovieId(null), 1600);

      try {
        await apiRequest("/api/watchlist/", {
          method: "POST",
          body: JSON.stringify({
            tmdb_id: movie.tmdb_id,
            title: movie.title,
            poster_url: movie.poster_url,
            release_year: movie.release_year,
            rating: movie.rating,
          }),
        });
      } catch {
        loadWatchlist();
      }
    }
  };

  /* ── Join Session Handler ── */
  async function handleJoinSession() {
    const code = joinCode.trim().toUpperCase();
    if (!code) { setJoinError("Please enter a 6-character code"); return; }
    if (code.length !== 6) { setJoinError("Session codes are 6 characters"); return; }
    setJoinError("");
    setJoinLoading(true);
    try {
      const data = await apiRequest("/api/sessions/join/", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      trackEvent("session_joined", { session_id: data.session_id });
      if (data.user_preferences_set) {
        navigate(`/session/${data.session_id}`);
      } else {
        navigate(`/session/${data.session_id}/preferences`);
      }
    } catch (err: unknown) {
      let message = "Unable to join session";
      if (err instanceof ApiError) {
        message = err.message;
      } else if (err instanceof Error) {
        message = err.message;
      } else if (typeof err === "object" && err !== null) {
        const apiError = err as ApiErrorResponse;
        if (apiError.error) {
          message = apiError.error;
        } else if (Array.isArray(apiError.errors?.non_field_errors)) {
          message = apiError.errors.non_field_errors[0] || message;
        }
      }
      setJoinError(message);
    } finally {
      setJoinLoading(false);
    }
  }

  function handleLogout() {
    ["auth_token", "username", "display_name", "email", "user_id"].forEach((k) =>
      localStorage.removeItem(k)
    );
    navigate("/", { replace: true });
  }

  const isReduced = prefersReducedMotion();

  /* ============================
     RENDER
  ============================ */

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased selection:bg-primary/20 selection:text-foreground">
      {/* ── Top Editorial Navigation ── */}
      <CinemaHeader current="home" />

      {/* ── Account Activation Reminder Banner ── */}
      {isAccountUnactivated && (
        <aside
          aria-label="Account Activation Notice"
          onClick={() => setShowActivationModal(true)}
          className="w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 sm:pt-6 cursor-pointer group"
        >
          <div className="w-full rounded-2xl border border-primary/35 bg-surface/90 hover:bg-surface border-l-4 border-l-primary backdrop-blur-md p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 transition-all duration-200 shadow-sm hover:shadow-md">
            <div className="flex items-start gap-3.5">
              <div className="size-10 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-center text-primary shrink-0 mt-0.5">
                <span className="material-symbols-outlined text-[22px]">
                  shield_lock
                </span>
              </div>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-block size-2 rounded-full bg-primary animate-pulse" />
                  <span className="text-[10px] font-mono uppercase tracking-widest font-semibold text-primary">
                    Guest Session · Action Required
                  </span>
                </div>
                <h2 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                  Your Flick account is not activated
                </h2>
                <p className="text-xs text-foreground-secondary mt-0.5 leading-relaxed">
                  You are browsing on a temporary guest session. Activate your account to permanently save your watchlist, matches, and taste profile across devices.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:self-center shrink-0">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowActivationModal(true);
                }}
                className="h-9 px-4 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider transition-colors shadow-2xs flex items-center gap-1.5"
              >
                <span>Complete Activation</span>
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* ── Main Content Container ── */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12 pb-28 md:pb-16 space-y-16 md:space-y-24">
        
        {/* ══════════════════════════════════════════════════════
            SECTION A — THE INTERACTIVE SALON ENTRANCE
        ══════════════════════════════════════════════════════ */}
        <section aria-labelledby="salon-entrance-heading" className="relative">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            
            {/* Left Narrative Broadside */}
            <div className="lg:col-span-7 space-y-6">
              
              {/* Salon Eyebrow */}
              <div className="flex items-center gap-2.5">
                <span className="inline-block size-2 rounded-full bg-primary animate-pulse" />
                <span className="text-[11px] font-semibold uppercase tracking-widest text-primary font-mono">
                  {userDisplayName ? `Salon No. 4 · Welcome, ${userDisplayName}` : "Salon No. 4 · Private Cinema Society"}
                </span>
                <span className="text-[10px] text-foreground-secondary/50 font-mono hidden sm:inline">
                  — Est. 2026
                </span>
              </div>

              {/* Main Headline */}
              <h1
                id="salon-entrance-heading"
                className="font-editorial text-3xl sm:text-4xl md:text-5xl lg:text-[3.25rem] font-semibold text-foreground tracking-tight leading-[1.12]"
              >
                Good films. Unexpected discoveries. <span className="italic font-normal text-primary">Better company.</span>
              </h1>

              {/* Supporting Lead Copy */}
              <p className="text-foreground-secondary text-sm sm:text-base leading-relaxed max-w-xl">
                Find something genuinely worth watching—or find someone to watch it with. Step beyond generic algorithms into an independent cinema library built for curious cinephiles.
              </p>

              {/* Editorial Annotations (Restrained & Playful) */}
              <div className="flex flex-wrap items-center gap-3 pt-1">
                {[
                  "Your seat is waiting",
                  "No spoilers · Only discoveries",
                  "Let the stories find you"
                ].map((note, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-border/80 bg-surface/70 text-[11px] font-medium text-foreground-secondary/90 shadow-2xs"
                  >
                    <span className="material-symbols-outlined text-[13px] text-primary">grain</span>
                    {note}
                  </span>
                ))}
              </div>

              {/* Primary Action Hub: Launch Screening & Join Code */}
              <div className="pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-3.5 max-w-xl">
                <button
                  onClick={() => navigate("/session/create")}
                  className="flex items-center justify-center gap-2.5 rounded-xl h-12 px-6 bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider shadow-sm transition-all active:scale-[0.98] group"
                >
                  <span className="material-symbols-outlined text-[18px] group-hover:rotate-12 transition-transform">
                    confirmation_number
                  </span>
                  Launch Screening Deck
                </button>

                <button
                  onClick={() => navigate("/discover?view=catalogue")}
                  className="flex items-center justify-center gap-2 rounded-xl h-12 px-5 border border-border hover:border-primary/50 bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs uppercase tracking-wider transition-all active:scale-[0.98]"
                >
                  <span className="material-symbols-outlined text-[18px] text-foreground-secondary">
                    explore
                  </span>
                  Explore Catalogue
                </button>
              </div>

            </div>

            {/* Right Interactive Ticket & Entrance Composition */}
            <div className="lg:col-span-5 relative">
              <div className="relative mx-auto max-w-md rounded-2xl border border-border/90 bg-surface p-6 sm:p-7 shadow-lg overflow-hidden">
                
                {/* Decorative Celluloid Perforation Top */}
                <div className="absolute top-0 inset-x-0 h-2 flex justify-between px-3 gap-1 overflow-hidden opacity-30">
                  {Array.from({ length: 24 }).map((_, i) => (
                    <div key={i} className="size-1 rounded-full bg-foreground" />
                  ))}
                </div>

                <div className="flex items-center justify-between mb-4 pt-1">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-primary text-[20px]">meeting_room</span>
                    <h2 className="font-editorial text-lg font-semibold text-foreground">Direct Salon Entry</h2>
                  </div>
                  <span className="text-[10px] font-mono tracking-widest uppercase text-foreground-secondary/60">
                    ROOM INVITATION
                  </span>
                </div>

                <p className="text-xs text-foreground-secondary mb-4 leading-relaxed">
                  Have a 6-character room passcode from a co-viewer? Enter below to join their active screening deck immediately.
                </p>

                {joinError && (
                  <div className="mb-3 p-2.5 bg-error/10 border border-error/20 rounded-xl text-center">
                    <p className="text-xs text-error font-medium">{joinError}</p>
                  </div>
                )}

                <div className="flex w-full items-stretch rounded-xl shadow-xs border border-border bg-surface focus-within:ring-2 focus-within:ring-primary/40 focus-within:border-primary transition-all">
                  <input
                    value={joinCode}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setJoinCode(e.target.value.toUpperCase())}
                    onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => e.key === "Enter" && handleJoinSession()}
                    placeholder="ENTER 6-DIGIT CODE"
                    maxLength={6}
                    className="flex-1 bg-transparent text-foreground placeholder:text-foreground-secondary/40 px-4 text-sm font-mono font-semibold tracking-widest uppercase focus:outline-none h-12"
                  />
                  <button
                    onClick={handleJoinSession}
                    disabled={joinLoading}
                    className="flex items-center justify-center px-5 bg-surface-secondary border-l border-border hover:bg-primary hover:text-surface disabled:opacity-50 transition-colors text-foreground font-semibold text-xs tracking-wider"
                    aria-label="Enter session"
                  >
                    {joinLoading ? (
                      <span className="size-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    )}
                  </button>
                </div>

                {/* Sub-note */}
                <div className="mt-4 pt-4 border-t border-border/50 flex items-center justify-between text-[11px] text-foreground-secondary">
                  <span>No account needed for guests</span>
                  <span className="font-mono text-primary flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-primary inline-block" /> Synced Live
                  </span>
                </div>
              </div>
            </div>

          </div>
        </section>

        {/* ══════════════════════════════════════════════════════
            SECTION B — THE CURATOR'S SELECTION
        ══════════════════════════════════════════════════════ */}
        <section aria-labelledby="curator-heading" className="space-y-6">
          <div className="flex items-end justify-between border-b border-border/60 pb-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase tracking-widest text-primary font-semibold">
                  {curatorConfidence === "COLD_START" || curatorMovie?.explanation?.confidence === "COLD_START"
                    ? "EDITORIAL SELECTION"
                    : "CURATORIAL ESSENTIAL"}
                </span>
                <span className="text-[10px] text-foreground-secondary">
                  {curatorConfidence === "COLD_START" || curatorMovie?.explanation?.confidence === "COLD_START"
                    ? "· Highly rated in the Flick collection"
                    : "· Editorial Spotlight"}
                </span>
              </div>
              <h2 id="curator-heading" className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground">
                The Curator's Selection
              </h2>
            </div>
            <button
              onClick={() => navigate("/discover?view=catalogue")}
              className="text-xs font-semibold uppercase tracking-wider text-primary hover:underline flex items-center gap-1 group"
            >
              Full Archive
              <span className="material-symbols-outlined text-[16px] group-hover:translate-x-0.5 transition-transform">
                arrow_forward
              </span>
            </button>
          </div>

          {curatorLoading ? (
            <div className="rounded-2xl border border-border bg-surface p-8 animate-pulse h-80 flex items-center justify-center">
              <span className="text-xs text-foreground-secondary font-mono tracking-widest uppercase">
                Consulting the Archive Index...
              </span>
            </div>
          ) : curatorMovie ? (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
              
              {/* Primary Feature Card */}
              <div className="lg:col-span-8 rounded-2xl border border-border/80 bg-surface shadow-sm overflow-hidden flex flex-col md:flex-row relative group">
                
                {/* Poster / Cinematic Still */}
                <div className="md:w-5/12 bg-surface-secondary relative aspect-[2/3] md:aspect-auto overflow-hidden">
                  {!spotlightImgError && curatorMovie.poster_url ? (
                    <img
                      src={curatorMovie.poster_url}
                      alt={curatorMovie.title}
                      className="w-full h-full object-cover object-center group-hover:scale-[1.02] transition-transform duration-500 ease-out"
                      onError={() => setSpotlightImgError(true)}
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center bg-surface-secondary text-foreground-secondary p-4 text-center">
                      <span className="material-symbols-outlined text-4xl mb-1">movie</span>
                      <span className="text-xs font-editorial font-semibold text-foreground/80 line-clamp-2">{curatorMovie.title}</span>
                    </div>
                  )}
                  {/* Subtle Grain Overlay */}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent md:hidden" />
                </div>

                {/* Feature Editorial Details */}
                <div className="md:w-7/12 p-6 sm:p-8 flex flex-col justify-between space-y-5 relative">
                  
                  {/* Ticket Stamp Feedback Animation */}
                  <AnimatePresence>
                    {stampedMovieId === (curatorMovie.id || curatorMovie.tmdb_id) && (
                      <motion.div
                        initial={isReduced ? { opacity: 0 } : { scale: 1.8, opacity: 0, rotate: -15 }}
                        animate={isReduced ? { opacity: 1 } : { scale: 1, opacity: 1, rotate: -4 }}
                        exit={{ opacity: 0, transition: { duration: 0.25 } }}
                        className="absolute top-4 right-4 z-20 px-3 py-1.5 rounded border-2 border-primary bg-surface/95 text-primary font-mono text-[11px] font-bold tracking-widest uppercase shadow-md flex items-center gap-1.5"
                      >
                        <span className="material-symbols-outlined text-[14px]">bookmark_added</span>
                        STAMPED · WATCHLIST
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      {curatorMovie.release_year && (
                        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-secondary text-foreground-secondary border border-border">
                          {curatorMovie.release_year}
                        </span>
                      )}
                      {curatorMovie.rating && (
                        <span className="text-[11px] font-mono font-medium text-primary flex items-center gap-1">
                          <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>
                            star
                          </span>
                          {curatorMovie.rating.toFixed(1)}
                        </span>
                      )}
                      {curatorMovie.original_language && (
                        <span className="text-[11px] font-mono uppercase text-foreground-secondary/70">
                          [{curatorMovie.original_language}]
                        </span>
                      )}
                    </div>

                    <h3 className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground tracking-tight leading-snug">
                      {curatorMovie.title}
                    </h3>

                    {/* Grounded Curatorial Explanation or Honest Cold-Start Label */}
                    {curatorConfidence === "COLD_START" || curatorMovie.explanation?.confidence === "COLD_START" ? (
                      <div className="p-3.5 rounded-xl bg-surface-secondary/80 border border-border/70 text-xs text-foreground-secondary leading-relaxed flex items-start gap-2.5">
                        <span className="material-symbols-outlined text-[18px] text-primary shrink-0 mt-0.5">verified</span>
                        <div>
                          <p className="font-semibold text-foreground text-xs">Editorial Selection: Highly rated in the Flick collection</p>
                          <p className="text-[11px] text-foreground-secondary mt-0.5">
                            Personalized recommendations adapt as you rate and review films.
                          </p>
                        </div>
                      </div>
                    ) : curatorMovie.explanation?.reason ? (
                      <div className="p-3.5 rounded-xl bg-surface-secondary/80 border border-primary/20 text-xs text-foreground leading-relaxed space-y-1.5">
                        <div className="flex items-start gap-2">
                          <span className="material-symbols-outlined text-[16px] text-primary shrink-0 mt-0.5" style={{ fontVariationSettings: "'FILL' 1" }}>
                            auto_awesome
                          </span>
                          <p className="italic text-foreground font-serif leading-snug">
                            "{curatorMovie.explanation.reason}"
                          </p>
                        </div>
                        {curatorMovie.explanation.confidence && curatorMovie.explanation.confidence !== "COLD_START" && (
                          <div className="flex items-center gap-1.5 text-[10px] font-mono text-primary font-semibold uppercase tracking-wider pl-6">
                            <span className="size-1.5 rounded-full bg-primary inline-block" />
                            <span>Curator Match · {curatorMovie.explanation.confidence} Confidence</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="p-3 rounded-xl bg-surface-secondary/70 border border-border/50 text-[11px] text-foreground-secondary leading-relaxed italic">
                        "A distinguished piece of cinema preserved in our collection that rewards patient contemplation."
                      </div>
                    )}

                    {/* Matched Signals Tags */}
                    {curatorMovie.explanation?.matched_signals && curatorMovie.explanation.matched_signals.length > 0 && (
                      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-foreground-secondary/70">Matched Signals:</span>
                        {curatorMovie.explanation.matched_signals.map((signal, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-0.5 rounded-full bg-primary/10 border border-primary/25 text-primary text-[10px] font-mono font-medium"
                          >
                            #{signal}
                          </span>
                        ))}
                      </div>
                    )}

                    <p className="text-xs text-foreground-secondary line-clamp-3 leading-relaxed">
                      {curatorMovie.overview || "An exceptional narrative crafted with deliberate framing and profound resonance."}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="pt-2 flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => setSelectedMovie(curatorMovie)}
                      className="h-10 px-4 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors flex items-center gap-1.5 active:scale-95 shadow-2xs"
                    >
                      <span className="material-symbols-outlined text-[16px]">info</span>
                      Examine Details
                    </button>

                    <button
                      onClick={() => handleToggleWatchlist(curatorMovie)}
                      className={`h-10 px-4 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all flex items-center gap-1.5 active:scale-95 ${
                        watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id)
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border hover:border-primary/40 bg-surface text-foreground"
                      }`}
                    >
                      <span className="material-symbols-outlined text-[16px]">
                        {watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id) ? "bookmark_added" : "bookmark"}
                      </span>
                      {watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id) ? "In Watchlist" : "Save to Watchlist"}
                    </button>

                    <button
                      onClick={() => navigate("/session/create")}
                      className="h-10 px-3 rounded-xl border border-border hover:border-primary/40 text-foreground-secondary hover:text-foreground text-xs font-semibold uppercase tracking-wider transition-colors flex items-center gap-1"
                      title="Screen with partner"
                    >
                      <span className="material-symbols-outlined text-[16px]">style</span>
                      Screen This
                    </button>
                  </div>

                </div>
              </div>

              {/* Secondary Shelf / Curator's Notebook */}
              <div className="lg:col-span-4 rounded-2xl border border-border/80 bg-surface p-5 flex flex-col justify-between space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="font-editorial text-base font-semibold text-foreground">Curator's Notebook</h4>
                    <span className="text-[10px] font-mono text-foreground-secondary/70 uppercase">Alternate Picks</span>
                  </div>
                  <p className="text-[11px] text-foreground-secondary mb-3 leading-relaxed">
                    Other distinguished titles currently under active review in the salon.
                  </p>

                  <div className="space-y-2.5">
                    {curatorShelf.length === 0 ? (
                      <div className="py-6 px-3 rounded-xl border border-dashed border-border text-center space-y-1">
                        <span className="material-symbols-outlined text-lg text-foreground-secondary/60">movie_edit</span>
                        <p className="text-[11px] text-foreground-secondary font-medium">
                          No alternate selections currently queued.
                        </p>
                      </div>
                    ) : (
                      curatorShelf.map((m) => {
                      const id = m.id || m.tmdb_id;
                      return (
                        <div
                          key={id}
                          onClick={() => setCuratorMovie(m)}
                          className="flex items-center gap-3 p-2 rounded-xl border border-border/60 hover:border-primary/50 bg-surface-secondary/40 hover:bg-surface-secondary transition-all cursor-pointer group"
                        >
                          <div className="size-12 rounded-lg bg-surface-secondary overflow-hidden shrink-0 border border-border">
                            {m.poster_url ? (
                              <img src={m.poster_url} alt={m.title} className="w-full h-full object-cover" />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center text-foreground-secondary text-xs">
                                🎬
                              </div>
                            )}
                          </div>
                          <div className="flex-1 min-w-0">
                            <h5 className="font-editorial text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                              {m.title}
                            </h5>
                            <div className="flex items-center gap-2 mt-0.5 text-[10px] text-foreground-secondary">
                              <span>{m.release_year || "Film"}</span>
                              {m.rating && (
                                <span className="text-primary font-mono">★ {m.rating.toFixed(1)}</span>
                              )}
                              {m.explanation?.matched_signals && m.explanation.matched_signals.length > 0 && (
                                <span className="text-primary font-mono truncate max-w-[110px]">
                                  · #{m.explanation.matched_signals[0]}
                                </span>
                              )}
                            </div>
                          </div>
                          <span className="material-symbols-outlined text-[16px] text-foreground-secondary group-hover:text-primary transition-colors">
                            swap_horiz
                          </span>
                        </div>
                      );
                    }))}
                  </div>
                </div>

                <div className="pt-2 border-t border-border/40 text-center">
                  <button
                    onClick={() => navigate("/discover?view=catalogue")}
                    className="text-[11px] font-semibold uppercase tracking-wider text-primary hover:underline"
                  >
                    Browse Complete Catalogue →
                  </button>
                </div>
              </div>

            </div>
          ) : null}
        </section>

        {/* ══════════════════════════════════════════════════════
            SECTION C — THE CINEMATIC LIBRARY
        ══════════════════════════════════════════════════════ */}
        <section aria-labelledby="library-heading" className="space-y-6">
          <div className="flex items-end justify-between border-b border-border/60 pb-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase tracking-widest text-primary font-semibold">
                  ORGANIZED ARCHIVE
                </span>
                <span className="text-[10px] text-foreground-secondary">· Filtered Collections</span>
              </div>
              <h2 id="library-heading" className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground">
                The Cinematic Library
              </h2>
            </div>
            <p className="text-xs text-foreground-secondary hidden sm:block max-w-xs text-right">
              Curated archive shelves mapped directly into our discovery engine.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
            {[
              {
                id: "classic",
                tag: "CAT. CLASSIC",
                title: "The Classic Vault",
                description: "Timeless celluloid preserved across golden eras prior to 1990.",
                icon: "history_edu",
                path: "/discover?era=classic&min_rating=7.5",
                badge: "Pre-1990 Archive",
              },
              {
                id: "nineties",
                tag: "CAT. 1990S",
                title: "The Nineties Wave",
                description: "Independent film rebellion, auteur voices, and era-defining narratives.",
                icon: "movie_filter",
                path: "/discover?era=90s",
                badge: "Indie Resurgence",
              },
              {
                id: "international",
                tag: "CAT. INTL",
                title: "World Cinema",
                description: "Stories that travelled further than their borders. Subtitled mastery.",
                icon: "public",
                path: "/discover?category=top_rated",
                badge: "Global Voices",
              },
              {
                id: "noir",
                tag: "CAT. NOIR",
                title: "Noir & Mystery",
                description: "Shadows, trenchcoats, high-stakes puzzles, and psychological ambiguity.",
                icon: "visibility",
                path: "/discover?genre=9648",
                badge: "Atmospheric",
              },
            ].map((shelf) => (
              <div
                key={shelf.id}
                onClick={() => navigate(shelf.path)}
                className="group relative rounded-2xl border border-border/80 hover:border-primary/60 bg-surface hover:bg-surface-secondary/40 p-5 sm:p-6 transition-all duration-300 cursor-pointer flex flex-col justify-between shadow-2xs hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <span className="text-[10px] font-mono font-semibold tracking-widest text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                      {shelf.tag}
                    </span>
                    <span className="material-symbols-outlined text-[20px] text-foreground-secondary group-hover:text-primary transition-colors">
                      {shelf.icon}
                    </span>
                  </div>

                  <h3 className="font-editorial text-lg font-semibold text-foreground group-hover:text-primary transition-colors mb-2">
                    {shelf.title}
                  </h3>

                  <p className="text-xs text-foreground-secondary leading-relaxed mb-4">
                    {shelf.description}
                  </p>
                </div>

                <div className="pt-3 border-t border-border/40 flex items-center justify-between text-[11px] font-medium text-foreground-secondary">
                  <span>{shelf.badge}</span>
                  <span className="material-symbols-outlined text-[16px] group-hover:translate-x-1 transition-transform text-primary">
                    arrow_forward
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════
            SECTION D — THE CONVERSATION CORNER
        ══════════════════════════════════════════════════════ */}
        <section aria-labelledby="conversation-heading" className="space-y-6">
          <div className="flex items-end justify-between border-b border-border/60 pb-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono uppercase tracking-widest text-primary font-semibold">
                  SALON DIALOGUES
                </span>
                <span className="text-[10px] text-foreground-secondary">· Cinephile Prompts</span>
              </div>
              <h2 id="conversation-heading" className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground">
                The Conversation Corner
              </h2>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              {
                quote: "A film you wish you could watch for the very first time again.",
                reflection: "That lightning-bolt revelation where every plot beat was completely unknown.",
                cta: "Top Rated Essentials →",
                path: "/discover?category=top_rated",
              },
              {
                quote: "Beautifully strange films that refuse to fit into any neat box.",
                reflection: "Dream logic, psychological labyrinths, and visionary authorial stamps.",
                cta: "Mystery & Mind-Bending →",
                path: "/discover?genre=9648",
              },
              {
                quote: "The single movie you recommend to absolutely everyone.",
                reflection: "The undisputed consensus choice that never leaves anyone disappointed.",
                cta: "High-Consensus Picks →",
                path: "/discover?min_rating=8",
              },
            ].map((prompt, i) => (
              <div
                key={i}
                className="rounded-2xl border border-border/70 bg-surface/80 p-6 flex flex-col justify-between space-y-4 relative overflow-hidden"
              >
                <div className="space-y-3">
                  <span className="text-2xl text-primary/40 font-serif leading-none block select-none">“</span>
                  <p className="font-editorial text-base font-semibold text-foreground leading-snug">
                    {prompt.quote}
                  </p>
                  <p className="text-xs text-foreground-secondary leading-relaxed">
                    {prompt.reflection}
                  </p>
                </div>

                <div className="pt-2">
                  <button
                    onClick={() => navigate(prompt.path)}
                    className="text-xs font-semibold text-primary hover:underline uppercase tracking-wider inline-flex items-center gap-1"
                  >
                    {prompt.cta}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════
            SECTION E — THE SCREENING ROOM INVITATION
        ══════════════════════════════════════════════════════ */}
        <section aria-labelledby="screening-invitation-heading">
          <div className="rounded-3xl border border-primary/30 bg-[#141614] text-[#E8E6E1] p-6 sm:p-10 shadow-xl relative overflow-hidden">
            
            {/* Theatrical Vignette Ambient Gradient */}
            <div className="absolute inset-0 bg-radial from-primary/10 via-transparent to-black/60 pointer-events-none" />

            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              
              <div className="lg:col-span-7 space-y-4">
                <span className="text-[10px] font-mono tracking-widest uppercase text-primary font-semibold">
                  COLLABORATIVE SCREENING
                </span>
                <h2
                  id="screening-invitation-heading"
                  className="font-editorial text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight leading-snug text-white"
                >
                  The best films are better shared.
                </h2>
                <p className="text-stone-300 text-xs sm:text-sm leading-relaxed max-w-lg">
                  Gather your co-viewer. Step into the Screening Room to privately rate curated titles and let Flick discover your mutual cinema matches.
                </p>

                <div className="pt-3 flex flex-wrap items-center gap-3">
                  <button
                    onClick={() => navigate("/session/create")}
                    className="h-12 px-6 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-all active:scale-95 shadow-md flex items-center gap-2"
                  >
                    <span className="material-symbols-outlined text-[18px]">style</span>
                    Start New Screening Deck
                  </button>
                  <button
                    onClick={() => navigate("/sessions")}
                    className="h-12 px-5 rounded-xl border border-stone-700 bg-stone-900/60 hover:bg-stone-800 text-stone-200 font-semibold text-xs uppercase tracking-wider transition-colors flex items-center gap-2"
                  >
                    <span className="material-symbols-outlined text-[18px]">history</span>
                    View Session Archives
                  </button>
                </div>
              </div>

              {/* Recent Activity List Inside The Screening Room */}
              <div className="lg:col-span-5 bg-black/40 rounded-2xl border border-stone-800/80 p-5 space-y-3.5">
                <div className="flex items-center justify-between">
                  <h3 className="font-editorial text-sm font-semibold text-white">Recent Screenings</h3>
                  {recentSessions.length > 0 && (
                    <span className="text-[10px] font-mono text-stone-400">
                      {recentSessions.length} recorded
                    </span>
                  )}
                </div>

                {recentSessions.length > 0 ? (
                  <div className="space-y-2">
                    {recentSessions.slice(0, 3).map((s) => (
                      <div
                        key={s.id}
                        onClick={() => navigate(s.ended ? `/sessions` : `/session/${s.id}`)}
                        className="p-3 rounded-xl bg-stone-900/70 border border-stone-800 hover:border-primary/50 transition-colors cursor-pointer flex items-center justify-between"
                      >
                        <div className="flex items-center gap-3 min-w-0 pr-3">
                          {s.participants && s.participants.length > 0 && (
                            <div className="flex -space-x-1.5 shrink-0">
                              {s.participants.slice(0, 2).map((p, i) => (
                                <AvatarPlaceholder key={i} initials={p.initials} />
                              ))}
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="font-editorial text-xs font-semibold text-stone-200 truncate">{s.name}</p>
                            <div className="flex items-center gap-2 mt-1 text-[10px] text-stone-400">
                              <span>{s.date}</span>
                              <span>·</span>
                              <span className="text-primary font-medium">{s.matches} Consensus Matches</span>
                            </div>
                          </div>
                        </div>
                        <span className="material-symbols-outlined text-stone-500 text-sm">
                          {s.ended ? "check_circle" : "arrow_forward"}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-xs text-stone-400">
                    No active screenings yet. Launch your first deck above.
                  </div>
                )}
              </div>

            </div>
          </div>
        </section>

        {/* ══════════════════════════════════════════════════════
            SECTION F — CLOSING NOTES
        ══════════════════════════════════════════════════════ */}
        <footer className="pt-8 border-t border-border/60 text-center space-y-3">
          <p className="font-editorial text-xl sm:text-2xl text-foreground font-medium italic">
            "That's enough browsing. Time for a film."
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-xs text-foreground-secondary pt-2">
            <button onClick={() => navigate("/discover?view=catalogue")} className="hover:text-foreground transition-colors">
              Catalogue
            </button>
            <span>·</span>
            <button onClick={() => navigate("/watchlist")} className="hover:text-foreground transition-colors">
              Watchlist
            </button>
            <span>·</span>
            <button onClick={() => navigate("/sessions")} className="hover:text-foreground transition-colors">
              Screening Archives
            </button>
            <span>·</span>
            <button onClick={() => navigate("/profile")} className="hover:text-foreground transition-colors">
              Salon Preferences
            </button>
            <span>·</span>
            <button onClick={handleLogout} className="text-error/80 hover:text-error transition-colors">
              Sign Out
            </button>
          </div>
          <p className="text-[10px] text-foreground-secondary/50 font-mono pt-2">
            Flick Independent Cinema Club · Curated Celluloid & Collaborative Discovery
          </p>
        </footer>

      </main>

      {/* ── Movie Detail Sheet / Modal (Reused from DiscoverPage) ── */}
      {selectedMovie && (
        <MovieDetailSheet
          movie={selectedMovie}
          inWatchlist={watchlistIds.has(selectedMovie.id || selectedMovie.tmdb_id)}
          onWatchlist={handleToggleWatchlist}
          onClose={() => setSelectedMovie(null)}
        />
      )}

      {/* ── Activation Steps Modal ── */}
      {showActivationModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-xs animate-in fade-in duration-200"
          onClick={() => setShowActivationModal(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="relative w-full max-w-lg bg-surface border border-border rounded-3xl p-6 sm:p-8 flex flex-col gap-6 shadow-2xl text-foreground max-h-[90vh] overflow-y-auto"
          >
            {/* Close button */}
            <button
              onClick={() => setShowActivationModal(false)}
              className="absolute top-5 right-5 size-8 rounded-full border border-border/80 flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>

            {/* Header */}
            <div className="flex items-start gap-4 pr-8">
              <div className="size-12 rounded-2xl bg-primary/10 border border-primary/25 flex items-center justify-center text-primary shrink-0">
                <span className="material-symbols-outlined text-[28px]">
                  {isGuestAccount ? "workspace_premium" : "verified"}
                </span>
              </div>
              <div>
                <span className="text-[10px] font-mono uppercase tracking-widest text-primary font-semibold">
                  {isGuestAccount ? "Guest Session Activation" : "Email Verification Steps"}
                </span>
                <h2 className="font-editorial text-2xl font-bold text-foreground mt-0.5">
                  {isGuestAccount ? "Activate Your Flick Account" : "Activate Full Privileges"}
                </h2>
                <p className="text-xs text-foreground-secondary mt-1 leading-relaxed">
                  {isGuestAccount
                    ? "Follow these 3 simple steps to make your account permanent without losing any movies or matches."
                    : "Verify your email to secure your account and recover it anytime."}
                </p>
              </div>
            </div>

            {isGuestAccount ? (
              <div className="space-y-4">
                {/* Step 1 */}
                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2.5">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">1</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Save Your Master Recovery Code</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    This 16-character code is currently the only key to this session. Store it safely before clearing your browser cookies.
                  </p>
                  {/* Recovery Code Display */}
                  <div className="ml-8.5 p-3 rounded-xl bg-surface border border-border flex items-center justify-between gap-2">
                    <span className="font-mono text-xs sm:text-sm font-semibold tracking-wider text-foreground select-all break-all">
                      {profileUser?.recovery_code || "Loading code…"}
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        const code = profileUser?.recovery_code;
                        if (code && navigator?.clipboard?.writeText) {
                          navigator.clipboard.writeText(code);
                          setCopiedActivationCode(true);
                          setTimeout(() => setCopiedActivationCode(false), 2000);
                        }
                      }}
                      className="h-7 px-2.5 rounded-lg bg-surface-secondary hover:bg-primary hover:text-surface border border-border text-[11px] font-semibold flex items-center gap-1 transition-colors shrink-0"
                    >
                      <span className="material-symbols-outlined text-[14px]">
                        {copiedActivationCode ? "check" : "content_copy"}
                      </span>
                      <span>{copiedActivationCode ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                </div>

                {/* Step 2 */}
                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">2</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Add Your Email & Password</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    Link your email and choose a password. All your existing movie swipes, watchlist entries, and taste signals will be 100% preserved.
                  </p>
                </div>

                {/* Step 3 */}
                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">3</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Sign In from Any Device</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    Once activated, log into Flick on your phone, tablet, or smart TV with your email anytime.
                  </p>
                </div>

                {/* Modal Actions */}
                <div className="pt-2 flex flex-col sm:flex-row gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      setShowActivationModal(false);
                      navigate("/convert");
                    }}
                    className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 shadow-xs transition-colors"
                  >
                    <span>Activate Account Now</span>
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowActivationModal(false);
                      navigate("/account-settings");
                    }}
                    className="h-11 px-4 rounded-xl border border-border text-foreground hover:bg-surface-secondary text-xs font-semibold transition-colors"
                  >
                    View in Settings
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {/* Email Verification Steps */}
                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">1</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Check Your Email Inbox</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    We sent a verification link to <strong className="text-foreground">{profileUser?.email}</strong>.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">2</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Click the Verification Link</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    Tap the button in the email to instantly confirm your email and activate your account.
                  </p>
                </div>

                <div className="p-4 rounded-2xl bg-surface-secondary/60 border border-border/70 space-y-2">
                  <div className="flex items-center gap-2.5">
                    <span className="size-6 rounded-full bg-primary text-surface text-xs font-bold flex items-center justify-center">3</span>
                    <h3 className="text-xs font-bold uppercase tracking-wider text-foreground">Didn't Receive the Email?</h3>
                  </div>
                  <p className="text-[11px] text-foreground-secondary leading-relaxed pl-8.5">
                    Check your spam/promotions folder or click the button below to send a new verification link.
                  </p>
                </div>

                {verificationSent && (
                  <p className="text-xs text-primary font-semibold text-center">✓ Verification email sent! Please check your inbox.</p>
                )}

                <div className="pt-2 flex flex-col sm:flex-row gap-3">
                  <button
                    type="button"
                    onClick={async () => {
                      setResendingVerification(true);
                      try {
                        await apiRequest("/api/auth/send-verification/", { method: "POST" });
                        setVerificationSent(true);
                        setTimeout(() => setVerificationSent(false), 4000);
                      } catch {}
                      finally { setResendingVerification(false); }
                    }}
                    disabled={resendingVerification}
                    className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider flex items-center justify-center gap-2 shadow-xs transition-colors disabled:opacity-50"
                  >
                    <span>{resendingVerification ? "Sending…" : "Resend Verification Email"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setShowActivationModal(false);
                      navigate("/verify-email");
                    }}
                    className="h-11 px-4 rounded-xl border border-border text-foreground hover:bg-surface-secondary text-xs font-semibold transition-colors"
                  >
                    Verify Page
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Mobile Navigation Bar ── */}
      <BottomNav current="home" />
    </div>
  );
}
