import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { apiRequest, ApiError } from "../lib/api";
import { identifyUser, resetAnalyticsIdentity, trackEvent } from "../lib/analytics";
import { isGuest, isLoggedIn } from "../lib/auth";
import { hasSeenTour, markTourFinished, type TourIdentityInput } from "../lib/tutorial";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";
import SpotlightTour, { type SpotlightTourStep } from "../components/SpotlightTour";
import CinemaAdmissionTicket from "../components/CinemaAdmissionTicket";
import CinemaSalonPass from "../components/CinemaSalonPass";
import CuratorsDoubleFeature from "../components/CuratorsDoubleFeature";
import { MovieDetailSheet, type Movie } from "./DiscoverPage";
import { ActionButton } from "../components/motion/ActionButton";
import { IconTransition } from "../components/motion/IconTransition";
import { useKeyedActionStatus, useActionStatus } from "../lib/motion";
import { usePrefersReducedMotion } from "../lib/motion";

const homeStaggerContainer: Variants = {
  initial: {},
  animate: {
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.02,
    },
  },
};

const homeSectionItem: Variants = {
  initial: { opacity: 0, y: 12 },
  animate: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.28,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

const HOME_TOUR_STEPS: SpotlightTourStep[] = [
  {
    id: "welcome",
    title: "Welcome to Flick",
    description:
      "Discover hand-picked films solo or launch a live screening room to swipe and find mutual matches with a partner.",
    icon: "theaters",
    placement: "center",
    nextLabel: "Start Tour",
  },
  {
    id: "launch-deck",
    target: '[data-tour="home-launch-deck"]',
    title: "Launch a Screening Deck",
    description:
      "Pick your cinema tradition, languages, and genres, then share the room code or invite link to screen together.",
    icon: "confirmation_number",
  },
  {
    id: "join-room",
    target: '[data-tour="home-join-code"]',
    title: "Join with a Room Code",
    description:
      "Have a 6-character code from a partner? Enter it here to jump straight into their live screening deck.",
    icon: "meeting_room",
  },
  {
    id: "curator-archive",
    target: [
      '[data-tour="home-curator-feature"]',
      '[data-tour="home-curator"]',
      '[data-tour="home-explore-catalogue"]',
    ],
    title: "Curator's Selection & Catalogue",
    description:
      "Browse hand-picked spotlights, inspect film details or save to your watchlist, and explore the full archive.",
    icon: "auto_awesome",
  },
  {
    id: "navigation",
    target: ['[data-tour="nav-mobile"]', '[data-tour="nav-desktop"]'],
    title: "Navigate the App",
    description:
      "Jump between Screenings (rooms & history), Archive (browse & filter), Watchlist (saved titles), and Profile (taste & settings).",
    icon: "explore",
    nextLabel: "Finish",
  },
];

function safeStorageGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeStorageSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Ignore restricted/unavailable storage errors
  }
}

function safeIsLoggedIn(): boolean {
  try {
    return isLoggedIn();
  } catch {
    return false;
  }
}

function safeIsGuest(): boolean {
  try {
    return isGuest();
  } catch {
    return false;
  }
}

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
  const userDisplayName = safeStorageGet("display_name") || safeStorageGet("username") || "";

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
  const [curatorError, setCuratorError] = useState(false);
  const [spotlightImgError, setSpotlightImgError] = useState(false);
  const curatorFetchInFlightRef = useRef(false);
  const [selectedMovie, setSelectedMovie] = useState<Movie | null>(null);
  const [watchlistIds, setWatchlistIds] = useState<Set<number>>(new Set());
  const [stampedMovieId, setStampedMovieId] = useState<number | null>(null);
  const stampedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const watchlistAction = useKeyedActionStatus<number>({ errorDurationMs: 0 });
  const pendingWatchlistRef = useRef<Set<number>>(new Set());
  useEffect(() => {
    return () => {
      if (stampedTimerRef.current !== null) {
        clearTimeout(stampedTimerRef.current);
      }
    };
  }, []);

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
  const [profileResolved, setProfileResolved] = useState<boolean>(() => !safeIsLoggedIn());
  const [homeTourOpen, setHomeTourOpen] = useState(false);
  const homeTourDismissedRef = useRef(false);
  const homeTourStepRef = useRef<{ index: number; id: string }>({ index: 0, id: "welcome" });
  const [showActivationModal, setShowActivationModal] = useState(false);
  const activationCopy = useActionStatus();
  const [resendingVerification, setResendingVerification] = useState(false);
  const [verificationSent, setVerificationSent] = useState(false);

  /* ── Load user profile for activation status & canonical tour identity ── */
  useEffect(() => {
    let active = true;
    if (!safeIsLoggedIn()) {
      setProfileResolved(true);
      return;
    }
    apiRequest("/api/users/profile/")
      .then((res: { success?: boolean; user?: typeof profileUser }) => {
        if (!active) return;
        if (res?.success && res.user) {
          setProfileUser(res.user);
          if (res.user.id !== undefined && res.user.id !== null) {
            safeStorageSet("user_id", String(res.user.id));
            identifyUser(res.user.id, {
              is_guest: Boolean(res.user.is_guest),
              username: res.user.username,
            });
          }
          if (res.user.is_guest === false) {
            safeStorageSet("is_guest", "false");
          }
        }
      })
      .catch(() => {})
      .finally(() => {
        if (active) {
          setProfileResolved(true);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const tourIdentity: TourIdentityInput = useMemo(
    () => ({
      userId: profileUser?.id,
      username: profileUser?.username,
    }),
    [profileUser?.id, profileUser?.username]
  );

  useEffect(() => {
    if (!profileResolved || homeTourDismissedRef.current) return;
    if (!hasSeenTour("home", tourIdentity)) {
      setHomeTourOpen(true);
    }
  }, [profileResolved, tourIdentity]);

  const handleCompleteHomeTour = () => {
    homeTourDismissedRef.current = true;
    markTourFinished("home", "completed", tourIdentity);
    trackEvent("tutorial_completed", { tour: "home" });
    setHomeTourOpen(false);
  };

  const handleSkipHomeTour = () => {
    homeTourDismissedRef.current = true;
    markTourFinished("home", "skipped", tourIdentity);
    trackEvent("tutorial_skipped", {
      tour: "home",
      step_id: homeTourStepRef.current.id,
      step_index: homeTourStepRef.current.index,
    });
    setHomeTourOpen(false);
  };

  // An account is unactivated ONLY if it is an unconverted guest account.
  // When profile is fetched from backend, profileUser.is_guest is authoritative.
  const isGuestAccount = profileUser ? Boolean(profileUser.is_guest) : safeIsGuest();
  const isAccountUnactivated = safeIsLoggedIn() && isGuestAccount;

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
  const loadCuratorSelection = useCallback(async () => {
    if (curatorFetchInFlightRef.current) return;
    curatorFetchInFlightRef.current = true;
    setCuratorLoading(true);
    setCuratorError(false);
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
        } else {
          setCuratorMovie(null);
          setCuratorShelf([]);
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
        } else {
          setCuratorMovie(null);
          setCuratorShelf([]);
        }
      } catch (errFallback) {
        console.error("[HomePage] Error loading curator fallback:", errFallback);
        setCuratorMovie(null);
        setCuratorShelf([]);
        setCuratorError(true);
      }
    } finally {
      curatorFetchInFlightRef.current = false;
      setCuratorLoading(false);
    }
  }, []);

  useEffect(() => {
    loadCuratorSelection();
  }, [loadCuratorSelection]);

  /* ── Watchlist Toggle with Post-Confirmation Stamp Feedback ── */
  const handleToggleWatchlist = async (movie: Movie) => {
    const targetId = movie.id || movie.tmdb_id;
    if (pendingWatchlistRef.current.has(targetId)) return;
    const inList = watchlistIds.has(targetId);
    pendingWatchlistRef.current.add(targetId);
    watchlistAction.setPending(targetId);

    if (inList) {
      try {
        await apiRequest(`/api/watchlist/${targetId}/`, { method: "DELETE" });
        setWatchlistIds((prev) => {
          const next = new Set(prev);
          next.delete(targetId);
          return next;
        });
        watchlistAction.setConfirmed(targetId);
        trackEvent("watchlist_removed", { movie_id: targetId, source: "home" });
      } catch {
        watchlistAction.setError(targetId, "Couldn't update watchlist. Please try again.");
      } finally {
        pendingWatchlistRef.current.delete(targetId);
      }
    } else {
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
        setWatchlistIds((prev) => new Set(prev).add(targetId));
        watchlistAction.setConfirmed(targetId);
        // Trigger ticket-stamp visual feedback only after server confirmation
        if (stampedTimerRef.current !== null) {
          clearTimeout(stampedTimerRef.current);
        }
        setStampedMovieId(targetId);
        stampedTimerRef.current = setTimeout(() => {
          setStampedMovieId(null);
          stampedTimerRef.current = null;
        }, 1600);
        trackEvent("watchlist_added", { movie_id: targetId, source: "home" });
      } catch {
        watchlistAction.setError(targetId, "Couldn't save film to watchlist. Please try again.");
      } finally {
        pendingWatchlistRef.current.delete(targetId);
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
      trackEvent("session_join_failed", { source: "home_code", reason: message });
    } finally {
      setJoinLoading(false);
    }
  }

  function handleLogout() {
    try {
      ["auth_token", "username", "display_name", "email", "user_id"].forEach((k) =>
        localStorage.removeItem(k)
      );
    } catch {
      // Ignore storage errors
    }
    resetAnalyticsIdentity();
    navigate("/", { replace: true });
  }

  const isReduced = usePrefersReducedMotion();

  /* ============================
     RENDER
  ============================ */

  return (
    <div className="bg-background font-sans text-foreground min-h-screen min-h-[100dvh] flex flex-col antialiased selection:bg-primary/20 selection:text-foreground">
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
              <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary shrink-0 mt-0.5">
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
                className="min-h-11 sm:min-h-9 w-full sm:w-auto px-4 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider transition-colors shadow-2xs flex items-center justify-center gap-1.5 touch-manipulation"
              >
                <span>Complete Activation</span>
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
            </div>
          </div>
        </aside>
      )}

      {/* ── Main Content Container ── */}
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 md:py-12 pb-[calc(6.5rem+env(safe-area-inset-bottom,0px))] md:pb-16">
        <motion.div
          variants={isReduced ? undefined : homeStaggerContainer}
          initial={isReduced ? false : "initial"}
          animate="animate"
          className="space-y-11 sm:space-y-14 md:space-y-20"
        >
          {/* ══════════════════════════════════════════════════════
              SECTION A — THE INTERACTIVE SALON ENTRANCE
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
            <section aria-labelledby="salon-entrance-heading" className="space-y-8 lg:space-y-10">
              {/* Grand Narrative Broadside Header */}
              <div className="space-y-4 max-w-3xl">
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
                <p className="text-foreground-secondary text-sm sm:text-base leading-relaxed max-w-2xl">
                  Find something genuinely worth watching—or find someone to watch it with. Step beyond generic algorithms into an independent cinema library built for curious cinephiles.
                </p>
              </div>

              {/* Two Physical Cinema Entrance Artifacts (Matched Height & Alignment) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-stretch">
                {/* Left: The Admission Ticket (Primary Route) */}
                <div className="lg:col-span-7 flex">
                  <CinemaAdmissionTicket
                    onLaunch={() => navigate("/session/create")}
                    onExplore={() => navigate("/discover?view=catalogue")}
                    className="w-full h-full"
                  />
                </div>

                {/* Right: The Salon Entry Pass (Room Code Route) */}
                <div className="lg:col-span-5 relative flex">
                  <CinemaSalonPass
                    joinCode={joinCode}
                    setJoinCode={setJoinCode}
                    onJoin={handleJoinSession}
                    loading={joinLoading}
                    error={joinError}
                    className="w-full h-full"
                  />
                </div>
              </div>
            </section>
          </motion.div>

          {/* ══════════════════════════════════════════════════════
              SECTION B — THE CURATOR'S SELECTION
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
            <section aria-labelledby="curator-heading" className="space-y-6">
          <div
            data-tour="home-curator"
            className="flex items-end justify-between gap-3 border-b border-border/60 pb-3"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mb-1">
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
              <h2 id="curator-heading" className="font-editorial text-2xl sm:text-3xl font-semibold text-foreground leading-tight">
                The Curator's Selection
              </h2>
            </div>
            <button
              type="button"
              onClick={() => navigate("/discover?view=catalogue")}
              className="shrink-0 whitespace-nowrap min-h-11 sm:min-h-9 inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-primary hover:underline group touch-manipulation"
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
              
              {/* Primary Feature Card with Smooth Crossfade */}
              <div className="lg:col-span-8 relative">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={curatorMovie.id || curatorMovie.tmdb_id || curatorMovie.title}
                    initial={isReduced ? { opacity: 0 } : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={isReduced ? { opacity: 0 } : { opacity: 0, y: -8 }}
                    transition={{
                      duration: 0.22,
                      ease: [0.16, 1, 0.3, 1],
                    }}
                    data-tour="home-curator-feature"
                    className="rounded-2xl border border-border/80 bg-surface shadow-sm overflow-hidden flex flex-col md:flex-row relative group h-full"
                  >
                
                {/* Poster / Cinematic Still */}
                <div className="md:w-5/12 bg-surface-secondary relative aspect-[2/3] md:aspect-auto overflow-hidden">
                  {!spotlightImgError && curatorMovie.poster_url ? (
                    <img
                      src={curatorMovie.poster_url}
                      alt={curatorMovie.title}
                      className={`w-full h-full object-cover object-center transition-transform duration-500 ease-out ${
                        isReduced ? "" : "group-hover:scale-[1.02]"
                      }`}
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
                      <div className="border-l-2 border-primary/50 pl-3.5 py-0.5 text-xs text-foreground-secondary leading-relaxed flex items-start gap-2.5">
                        <span className="material-symbols-outlined text-[18px] text-primary shrink-0 mt-0.5">verified</span>
                        <div>
                          <p className="font-semibold text-foreground text-xs">Editorial Selection: Highly rated in the Flick collection</p>
                          <p className="text-[11px] text-foreground-secondary mt-0.5">
                            Personalized recommendations adapt as you rate and review films.
                          </p>
                        </div>
                      </div>
                    ) : curatorMovie.explanation?.reason ? (
                      <div className="border-l-2 border-primary/50 pl-3.5 py-0.5 text-xs text-foreground leading-relaxed space-y-1.5">
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
                      <div className="border-l-2 border-border pl-3.5 py-0.5 text-[11px] text-foreground-secondary leading-relaxed italic">
                        "A distinguished piece of cinema preserved in our collection that rewards patient contemplation."
                      </div>
                    )}

                    {/* Matched Signals Tags */}
                    {curatorMovie.explanation?.matched_signals && curatorMovie.explanation.matched_signals.length > 0 && (
                      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 pt-0.5">
                        <span className="text-[10px] font-mono uppercase tracking-wider text-foreground-secondary/70">Matched Signals:</span>
                        {curatorMovie.explanation.matched_signals.map((signal, idx) => (
                          <span
                            key={idx}
                            className="text-primary text-[10px] font-mono font-medium"
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
                      type="button"
                      onClick={() => setSelectedMovie(curatorMovie)}
                      className="h-10 px-4 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors flex items-center gap-1.5 active:scale-95 shadow-2xs"
                    >
                      <span className="material-symbols-outlined text-[16px]">info</span>
                      Examine Details
                    </button>

                    <ActionButton
                      status={watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id)}
                      onClick={() => handleToggleWatchlist(curatorMovie)}
                      confirmedClassName="ring-1 ring-primary/40"
                      errorClassName="border-error/60 bg-error/10 text-error"
                      className={`min-h-11 sm:min-h-10 px-4 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-colors flex items-center gap-1.5 cursor-pointer ${
                        watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id)
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border hover:border-primary/40 bg-surface text-foreground"
                      }`}
                    >
                      <IconTransition
                        iconKey={`${watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id)}-${watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id)}`}
                        sizeClassName="size-4"
                      >
                        {watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id) === "pending" ? (
                          <span className="size-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                        ) : (
                          <span className="material-symbols-outlined text-[16px]">
                            {watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id) === "error"
                              ? "error_outline"
                              : watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id)
                              ? "bookmark_added"
                              : "bookmark"}
                          </span>
                        )}
                      </IconTransition>
                      <span>
                        {watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id) === "pending"
                          ? "Saving…"
                          : watchlistAction.getStatus(curatorMovie.id || curatorMovie.tmdb_id) === "error"
                          ? "Retry"
                          : watchlistIds.has(curatorMovie.id || curatorMovie.tmdb_id)
                          ? "In Watchlist"
                          : "Save to Watchlist"}
                      </span>
                    </ActionButton>

                    <button
                      type="button"
                      onClick={() =>
                        navigate("/session/create", {
                          state: { preseedMovie: curatorMovie },
                        })
                      }
                      className="min-h-11 sm:min-h-10 px-3.5 rounded-xl border border-border hover:border-primary/40 text-foreground-secondary hover:text-foreground text-xs font-semibold uppercase tracking-wider transition-colors flex items-center gap-1.5 cursor-pointer active:scale-95 shadow-2xs"
                      title="Start a collaborative matching session with this title"
                    >
                      <span className="material-symbols-outlined text-[16px]">groups</span>
                      Match with Partner
                    </button>
                  </div>
                  {watchlistAction.errorState?.key === (curatorMovie.id || curatorMovie.tmdb_id) && (
                    <p role="alert" className="text-xs font-medium text-error">
                      {watchlistAction.errorState.message}
                    </p>
                  )}

                </div>
              </motion.div>
            </AnimatePresence>
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
                      const isSelected = curatorMovie && (curatorMovie.id || curatorMovie.tmdb_id) === id;
                      return (
                        <button
                          key={id}
                          type="button"
                          onClick={() => {
                            setSpotlightImgError(false);
                            setCuratorMovie(m);
                          }}
                          className={`w-full text-left flex items-center gap-3 p-2 rounded-xl border transition-all cursor-pointer group ${
                            isSelected
                              ? "border-primary/70 bg-primary/10 shadow-2xs"
                              : "border-border/60 hover:border-primary/50 bg-surface-secondary/40 hover:bg-surface-secondary"
                          }`}
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
                        </button>
                      );
                    }))}
                  </div>
                </div>

                <div className="pt-2 border-t border-border/40 text-center">
                  <button
                    type="button"
                    onClick={() => navigate("/discover?view=catalogue")}
                    className="text-[11px] font-semibold uppercase tracking-wider text-primary hover:underline"
                  >
                    Browse Complete Catalogue →
                  </button>
                </div>
              </div>

            </div>
          ) : (
            <div
              data-testid="curator-fallback-card"
              data-state={curatorError ? "error" : "empty"}
              className="rounded-2xl border border-border bg-surface p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-5 shadow-2xs"
            >
              <div className="flex items-start gap-4">
                <div className="size-11 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-center text-primary shrink-0">
                  <span className="material-symbols-outlined text-[22px]">movie_filter</span>
                </div>
                <div className="space-y-1">
                  <h3 className="font-editorial text-lg sm:text-xl font-semibold text-foreground">
                    Today's selection is temporarily unavailable
                  </h3>
                  <p className="text-xs sm:text-sm text-foreground-secondary leading-relaxed max-w-lg">
                    We couldn't load a featured spotlight right now. You can retry loading it or browse the full film archive.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                <button
                  type="button"
                  onClick={() => loadCuratorSelection()}
                  disabled={curatorLoading}
                  className="min-h-11 sm:min-h-10 px-4 rounded-xl bg-primary hover:bg-primary-hover text-primary-foreground text-xs font-semibold uppercase tracking-wider transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-[16px]">refresh</span>
                  <span>{curatorLoading ? "Retrying…" : "Retry"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => navigate("/discover?view=catalogue")}
                  className="min-h-11 sm:min-h-10 px-4 rounded-xl border border-border bg-surface-secondary/70 hover:bg-surface-secondary text-foreground text-xs font-semibold uppercase tracking-wider transition-colors flex items-center gap-1.5 cursor-pointer"
                >
                  <span>Full Archive</span>
                  <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                </button>
              </div>
            </div>
          )}
            </section>
          </motion.div>

          {/* ══════════════════════════════════════════════════════
              SECTION C — THE CINEMATIC LIBRARY
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
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
              <button
                key={shelf.id}
                type="button"
                onClick={() => navigate(shelf.path)}
                className="w-full text-left group relative rounded-2xl border border-border/80 hover:border-primary/60 bg-surface hover:bg-surface-secondary/40 p-5 sm:p-6 transition-all duration-300 cursor-pointer flex flex-col justify-between shadow-2xs hover:shadow-md"
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
              </button>
            ))}
          </div>
            </section>
          </motion.div>

          {/* ══════════════════════════════════════════════════════
              SECTION D — THE CURATOR'S DOUBLE FEATURE
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
            <CuratorsDoubleFeature
              onMovieClick={(movie) => setSelectedMovie(movie)}
              onScreenDoubleFeature={(m1, m2) => {
                const id1 = m1.id || m1.tmdb_id;
                const id2 = m2.id || m2.tmdb_id;
                navigate("/session/create", {
                  state: {
                    prioritizedMovieIds: [id1, id2],
                    preseedMovies: [m1, m2],
                  },
                });
              }}
              watchlistIds={watchlistIds}
              onWatchlistUpdated={(addedIds) => {
                setWatchlistIds((prev) => {
                  const next = new Set(prev);
                  addedIds.forEach((id) => next.add(id));
                  return next;
                });
              }}
            />
          </motion.div>

          {/* ══════════════════════════════════════════════════════
              SECTION E — THE SCREENING ROOM INVITATION
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
            <section aria-labelledby="screening-invitation-heading">
          <div
            data-testid="collaborative-screening-card"
            className="rounded-3xl border border-primary/25 bg-surface text-foreground p-6 sm:p-10 shadow-xl relative overflow-hidden"
          >
            
            {/* Theatrical Vignette Ambient Gradient & Breathing Glow */}
            {!isReduced ? (
              <motion.div
                animate={{
                  opacity: [0.18, 0.35, 0.18],
                  scale: [0.99, 1.02, 0.99],
                }}
                transition={{
                  duration: 4.8,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
                className="absolute inset-0 bg-radial from-primary/20 via-primary/5 to-transparent pointer-events-none"
              />
            ) : null}
            <div className="absolute inset-0 bg-radial from-primary/10 via-transparent to-surface-secondary/60 pointer-events-none" />

            <div className="relative z-10 grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
              
              <div className="lg:col-span-7 space-y-4">
                <span className="text-[10px] font-mono tracking-widest uppercase text-primary font-semibold">
                  COLLABORATIVE SCREENING
                </span>
                <h2
                  id="screening-invitation-heading"
                  className="font-editorial text-2xl sm:text-3xl md:text-4xl font-semibold tracking-tight leading-snug text-foreground"
                >
                  The best films are better shared.
                </h2>
                <p className="text-foreground-secondary text-xs sm:text-sm leading-relaxed max-w-lg">
                  Gather your co-viewer. Step into the Screening Room to privately rate curated titles and let Flick discover your mutual cinema matches.
                </p>

                <div className="pt-3 flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => navigate("/session/create")}
                    className="h-12 px-6 rounded-xl bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-xs uppercase tracking-wider transition-all active:scale-95 shadow-md flex items-center gap-2 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">style</span>
                    Start New Screening Deck
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate("/sessions")}
                    className="h-12 px-5 rounded-xl border border-border bg-surface-secondary/70 hover:bg-surface-secondary text-foreground font-semibold text-xs uppercase tracking-wider transition-colors flex items-center gap-2 cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[18px]">history</span>
                    View Session Archives
                  </button>
                </div>
              </div>

              {/* Recent Activity List Inside The Screening Room */}
              <div className="lg:col-span-5 bg-surface-secondary/60 rounded-2xl border border-border/80 p-5 space-y-3.5">
                <div className="flex items-center justify-between">
                  <h3 className="font-editorial text-sm font-semibold text-foreground">Recent Screenings</h3>
                  {recentSessions.length > 0 && (
                    <span className="text-[10px] font-mono text-foreground-secondary">
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
                        className="p-3 rounded-xl bg-surface border border-border hover:border-primary/50 transition-colors cursor-pointer flex items-center justify-between"
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
                            <p className="font-editorial text-xs font-semibold text-foreground truncate">{s.name}</p>
                            <div className="flex items-center gap-2 mt-1 text-[10px] text-foreground-secondary">
                              <span>{s.date}</span>
                              <span>·</span>
                              <span className="text-primary font-medium">{s.matches} Consensus Matches</span>
                            </div>
                          </div>
                        </div>
                        <span className="material-symbols-outlined text-foreground-secondary text-sm">
                          {s.ended ? "check_circle" : "arrow_forward"}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-6 text-center text-xs text-foreground-secondary">
                    No active screenings yet. Launch your first deck above.
                  </div>
                )}
              </div>

            </div>
          </div>
            </section>
          </motion.div>

          {/* ══════════════════════════════════════════════════════
              SECTION F — CLOSING NOTES
          ══════════════════════════════════════════════════════ */}
          <motion.div variants={isReduced ? undefined : homeSectionItem}>
            <footer className="pt-8 border-t border-border/60 text-center space-y-3">
              <p className="font-editorial text-xl sm:text-2xl text-foreground font-medium italic">
                "That's enough browsing. Time for a film."
              </p>
              <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-xs text-foreground-secondary pt-2">
                <button type="button" onClick={() => navigate("/discover?view=catalogue")} className="hover:text-foreground transition-colors">
                  Catalogue
                </button>
                <span>·</span>
                <button type="button" onClick={() => navigate("/watchlist")} className="hover:text-foreground transition-colors">
                  Watchlist
                </button>
                <span>·</span>
                <button type="button" onClick={() => navigate("/sessions")} className="hover:text-foreground transition-colors">
                  Screening Archives
                </button>
                <span>·</span>
                <button type="button" onClick={() => navigate("/profile")} className="hover:text-foreground transition-colors">
                  Salon Preferences
                </button>
                <span>·</span>
                <button type="button" onClick={handleLogout} className="text-error/80 hover:text-error transition-colors">
                  Sign Out
                </button>
              </div>
              <p className="text-[10px] text-foreground-secondary/50 font-mono pt-2">
                Flick Independent Cinema Club · Curated Celluloid & Collaborative Discovery
              </p>
            </footer>
          </motion.div>
        </motion.div>
      </main>

      {/* ── Movie Detail Sheet / Modal (Reused from DiscoverPage) ── */}
      {selectedMovie && (
        <MovieDetailSheet
          movie={selectedMovie}
          inWatchlist={watchlistIds.has(selectedMovie.id || selectedMovie.tmdb_id)}
          onWatchlist={handleToggleWatchlist}
          onClose={() => setSelectedMovie(null)}
          watchlistStatus={watchlistAction.getStatus(selectedMovie.id || selectedMovie.tmdb_id)}
          watchlistError={
            watchlistAction.errorState?.key === (selectedMovie.id || selectedMovie.tmdb_id)
              ? watchlistAction.errorState.message
              : null
          }
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
              type="button"
              onClick={() => setShowActivationModal(false)}
              aria-label="Close activation modal"
              className="absolute top-4 right-4 size-11 sm:size-9 rounded-full border border-border/80 flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[18px]">close</span>
            </button>

            {/* Header */}
            <div className="flex items-start gap-4 pr-10">
              <div className="size-12 rounded-2xl bg-primary/10 border border-primary/25 flex items-center justify-center text-primary shrink-0">
                <span className="material-symbols-outlined text-[28px]">
                  {isGuestAccount ? "workspace_premium" : "verified"}
                </span>
              </div>
              <div>
                <span className="text-xs font-mono uppercase tracking-widest text-primary font-semibold">
                  {isGuestAccount ? "Guest Session Activation" : "Email Verification Steps"}
                </span>
                <h2 className="font-editorial text-2xl font-bold text-foreground mt-0.5">
                  {isGuestAccount ? "Activate Your Flick Account" : "Activate Full Privileges"}
                </h2>
                <p className="text-sm text-foreground-secondary mt-1 leading-relaxed">
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
                    <ActionButton
                      type="button"
                      status={activationCopy.status}
                      onClick={async () => {
                        const code = profileUser?.recovery_code;
                        if (!code) return;
                        activationCopy.setPending();
                        try {
                          if (!navigator?.clipboard?.writeText) {
                            throw new Error("Clipboard unavailable");
                          }
                          await navigator.clipboard.writeText(code);
                          activationCopy.setConfirmed();
                        } catch {
                          activationCopy.setError("Couldn't copy code automatically — select to copy.");
                        }
                      }}
                      confirmedClassName="border-primary/50 bg-primary/10 text-primary"
                      errorClassName="border-error/60 bg-error/10 text-error"
                      className="min-h-11 sm:min-h-9 px-2.5 rounded-lg bg-surface-secondary hover:bg-primary hover:text-surface border border-border text-[11px] font-semibold flex items-center gap-1 transition-colors shrink-0 cursor-pointer"
                    >
                      <IconTransition iconKey={activationCopy.status} sizeClassName="size-3.5">
                        <span className="material-symbols-outlined text-[14px]">
                          {activationCopy.status === "confirmed"
                            ? "check"
                            : activationCopy.status === "error"
                            ? "error_outline"
                            : "content_copy"}
                        </span>
                      </IconTransition>
                      <span>
                        {activationCopy.status === "confirmed"
                          ? "Copied"
                          : activationCopy.status === "error"
                          ? "Failed"
                          : "Copy"}
                      </span>
                    </ActionButton>
                  </div>
                  {activationCopy.errorMessage && (
                    <p role="alert" className="ml-8.5 text-[11px] font-medium text-error">
                      {activationCopy.errorMessage}
                    </p>
                  )}
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
                      } catch (err) {
                        console.debug("[HomePage] Resend error:", err);
                      }
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

      {/* ── First-Visit Homepage Spotlight Tour ── */}
      <SpotlightTour
        isOpen={homeTourOpen && !showActivationModal && !selectedMovie}
        steps={HOME_TOUR_STEPS}
        ariaLabel="Flick homepage tour"
        onStepChange={(index, step) => {
          homeTourStepRef.current = { index, id: step.id };
        }}
        onComplete={handleCompleteHomeTour}
        onSkip={handleSkipHomeTour}
      />

      {/* ── Mobile Navigation Bar ── */}
      <BottomNav current="home" />
    </div>
  );
}
