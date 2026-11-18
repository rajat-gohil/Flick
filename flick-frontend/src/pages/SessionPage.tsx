import { useEffect, useState, useCallback, useRef, useMemo, forwardRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiRequest, getWsUrl } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import confetti from "canvas-confetti";
import { motion, AnimatePresence, useMotionValue, useTransform, animate, type Variants } from "framer-motion";
import StreamingOptions from "../components/StreamingOptions";
import CinematicLoader from "../components/CinematicLoader";
import { DeckCardSkeleton, MatchItemSkeleton, StreamingItemSkeleton } from "../components/Skeleton";
import { bottomSheetVariants, backdropVariants, prefersReducedMotion } from "../lib/motion";
import { ConstraintExhaustionNoticeModal } from "../components/session/ConstraintExhaustionNoticeModal";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { hasSeenTour, markTourFinished, type TourIdentityInput } from "../lib/tutorial";
import SpotlightTour, { type SpotlightTourStep } from "../components/SpotlightTour";

/* ============================
   TYPES (MATCH BACKEND)
============================ */

type Movie = {
  id: number;
  title: string;
  overview: string;
  poster_url: string;
  rating?: number;
  vote_count?: number;
  release_year?: number;
  trailer_url?: string;
  metadataStatus?: "pending" | "success" | "failed";
  superlike_attribution?: "none" | "host" | "guest" | "mutual";
  match_type?: "ordinary" | "superlike" | "mutual_superlike";
};

type Match = {
  session_id: number;
  movie_id: number;
  movie_title: string;
  matched_at?: string;
  poster_url?: string;
  tmdb_id?: number;
  rating?: number;
  vote_count?: number;
  release_year?: number;
  overview?: string;
  genres?: string[];
  original_language?: string;
  superlike_attribution?: "none" | "host" | "guest" | "mutual";
  match_type?: "ordinary" | "superlike" | "mutual_superlike";
};

type Session = {
  id: number;
  code: string;
  host_joined: boolean;
  guest_joined: boolean;
  ended: boolean;
  preferences_set: boolean;
  user_preferences_set?: boolean;
  host_preferences_set?: boolean;
  guest_preferences_set?: boolean;
  user_role?: "host" | "guest" | null;
  host_id?: string | number | null;
  guest_id?: string | number | null;
  host_display_name?: string;
  guest_display_name?: string;
  is_legacy?: boolean;
  reviewed_count?: number;
  matched_count?: number;
  affinity_percent?: number;
  status?: string;
};

const SESSION_TOUR_STEPS: SpotlightTourStep[] = [
  {
    id: "like",
    target: '[data-tour="session-like"]',
    title: "Swipe Right to Like",
    description:
      "Drag a film card right or tap the heart button to like a film. Mutual likes create an instant match.",
    icon: "favorite",
    shortcutHint: "→",
    shortcutLabel: "Like",
    gestureHint: "swipe-right",
  },
  {
    id: "pass",
    target: '[data-tour="session-pass"]',
    title: "Swipe Left to Pass",
    description:
      "Drag left or tap × to skip a film for this screening and move on to the next title.",
    icon: "close",
    shortcutHint: "←",
    shortcutLabel: "Pass",
    gestureHint: "swipe-left",
  },
  {
    id: "superlike",
    target: '[data-tour="session-superlike"]',
    title: "Super-Like Your Top Pick",
    description:
      "Tap ★ to flag a must-watch film with a priority highlight when you match.",
    icon: "star",
    shortcutHint: "↑",
    shortcutLabel: "Super-like",
    gestureHint: "superlike",
  },
  {
    id: "info-undo",
    target: '[data-tour="session-card"]',
    title: "Film Info & Undo",
    description:
      "Tap the movie card's info button for full synopsis and ratings. After swiping, Undo unlocks to recall your last choice.",
    icon: "info",
    shortcutHint: "Space",
    shortcutLabel: "Film details",
    gestureHint: "info-undo",
  },
  {
    id: "live-matches",
    target: '[data-tour="session-header"]',
    title: "Live Matches & Progress",
    description:
      "Track your partner's live status, adjust taste parameters, and see mutual matches appear in real time.",
    icon: "sync",
    nextLabel: "Start Swiping",
  },
];

// Module-level connection registry to prevent duplicate WebSocket instances for the same session in a single tab
const activeSessionSockets = new Map<string, WebSocket>();

/* ============================
   SWIPE CARD MOTION VARIANTS & COMPONENT
============================ */

const cardVariants: Variants = {
  enter: {
    opacity: 0,
    scale: 0.96,
  },
  center: {
    opacity: 1,
    scale: 1,
    x: 0,
    y: 0,
    rotate: 0,
    transition: {
      duration: prefersReducedMotion() ? 0.08 : 0.2,
      ease: [0.16, 1, 0.3, 1],
    },
  },
  exit: (direction: "like" | "dislike" | "superlike") => {
    if (prefersReducedMotion()) {
      return {
        opacity: 0,
        pointerEvents: "none",
        transition: { duration: 0.1 },
      };
    }
    if (direction === "like") {
      return {
        opacity: 0,
        x: 600,
        rotate: 15,
        pointerEvents: "none",
        transition: {
          duration: 0.22,
          ease: [0.16, 1, 0.3, 1],
        },
      };
    }
    if (direction === "dislike") {
      return {
        opacity: 0,
        x: -600,
        rotate: -15,
        pointerEvents: "none",
        transition: {
          duration: 0.22,
          ease: [0.16, 1, 0.3, 1],
        },
      };
    }
    if (direction === "superlike") {
      return {
        opacity: 0,
        y: -600,
        scale: 1.05,
        pointerEvents: "none",
        transition: {
          duration: 0.25,
          ease: [0.16, 1, 0.3, 1],
        },
      };
    }
    return {
      opacity: 0,
      scale: 0.95,
      pointerEvents: "none",
      transition: { duration: 0.2 },
    };
  },
};

function normalizeDeckCard(card: any): Movie {
  const posterUrl = card.poster_path
    ? (card.poster_path.startsWith("http")
        ? card.poster_path
        : `https://image.tmdb.org/t/p/w780${card.poster_path}`)
    : "";
  const releaseYear = card.release_date
    ? parseInt(String(card.release_date).slice(0, 4), 10)
    : undefined;

  return {
    id: card.movie_id,
    title: card.title || "Film Selection",
    overview: card.overview || "",
    poster_url: posterUrl,
    rating: typeof card.rating === "number" ? card.rating : undefined,
    vote_count: typeof card.vote_count === "number" ? card.vote_count : undefined,
    release_year: releaseYear,
    metadataStatus: "success",
  };
}

interface MovieSwipeCardProps {
  movie: Movie;
  onSwipe: (reaction: "like" | "dislike") => void;
  onInfoClick: () => void;
  posterLoaded: boolean;
  onPosterLoad: () => void;
  custom?: "like" | "dislike" | "superlike";
  disabled?: boolean;
}

export const MovieSwipeCard = forwardRef<HTMLDivElement, MovieSwipeCardProps>(
  function MovieSwipeCard(
    { movie, onSwipe, onInfoClick, posterLoaded, onPosterLoad, custom, disabled },
    ref
  ) {
    // Fluid responsive motion values: continuous 1:1 finger tracking with proportional subtle rotation
    const dragX = useMotionValue(0);
    const cardRotate = useTransform(dragX, [-280, 0, 280], [-10, 0, 10]);
    const considerOpacity = useTransform(dragX, [30, 90], [0, 1]);
    const passOpacity = useTransform(dragX, [-30, -90], [0, 1]);
    const cardScale = useTransform(dragX, [-280, 0, 280], [1.02, 1, 1.02]);
    const hasSwipedRef = useRef(false);

    const handleDragEnd = (
      _: unknown,
      info: { offset: { x: number; y: number }; velocity: { x: number; y: number } }
    ) => {
      if (disabled || hasSwipedRef.current) return;

      const offsetX = info.offset.x;
      const velocityX = info.velocity.x;

      // Responsive commit threshold (displacement or swipe flick velocity)
      if (offsetX > 100 || velocityX > 400) {
        hasSwipedRef.current = true;
        onSwipe("like");
      } else if (offsetX < -100 || velocityX < -400) {
        hasSwipedRef.current = true;
        onSwipe("dislike");
      } else {
        // Smooth responsive spring return to center on uncommitted gesture
        animate(dragX, 0, {
          type: "spring",
          stiffness: 420,
          damping: 30,
          mass: 0.75,
        });
      }
    };

    return (
      <motion.div
        ref={ref}
        data-tour="session-card"
        custom={custom}
        style={{ x: dragX, rotate: cardRotate, scale: cardScale }}
        drag={disabled ? undefined : "x"}
        onDragEnd={handleDragEnd}
        variants={cardVariants}
        initial="enter"
        animate="center"
        exit="exit"
        className={`relative w-full max-w-sm h-[63vh] rounded-2xl overflow-hidden border border-border shadow-lg bg-surface z-10 touch-pan-y will-change-transform select-none ${
          disabled ? "pointer-events-none opacity-90 cursor-not-allowed" : "cursor-grab active:cursor-grabbing"
        }`}
      >
        {/* CONSIDER stamp */}
        <motion.div
          style={{ opacity: considerOpacity }}
          className="absolute top-6 left-6 z-30 pointer-events-none px-4 py-1.5 rounded-lg border-2 border-emerald-500 bg-emerald-950/80 text-emerald-400 font-editorial font-bold text-lg uppercase tracking-wider -rotate-12 shadow-lg backdrop-blur-xs"
        >
          Consider
        </motion.div>

        {/* PASS stamp */}
        <motion.div
          style={{ opacity: passOpacity }}
          className="absolute top-6 right-6 z-30 pointer-events-none px-4 py-1.5 rounded-lg border-2 border-rose-500 bg-rose-950/80 text-rose-400 font-editorial font-bold text-lg uppercase tracking-wider rotate-12 shadow-lg backdrop-blur-xs"
        >
          Pass
        </motion.div>

        {/* Shimmer skeleton (underneath poster) */}
        {movie.poster_url && !posterLoaded && (
          <div className="absolute inset-0 bg-surface-secondary z-0 flex items-center justify-center">
            <span className="material-symbols-outlined text-foreground-secondary text-[36px] animate-pulse">movie</span>
          </div>
        )}

        {/* Poster image */}
        {movie.poster_url ? (
          <img
            src={movie.poster_url}
            alt={movie.title}
            loading="eager"
            onLoad={onPosterLoad}
            className="absolute inset-0 w-full h-full object-cover z-0"
          />
        ) : (
          <div className="absolute inset-0 bg-surface-secondary flex items-center justify-center p-6 text-center">
            <span className="material-symbols-outlined text-foreground-secondary text-[48px]">movie</span>
          </div>
        )}

        {/* Cinema Gradient overlay: natural fade focused only on bottom text area */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/95 via-black/40 to-transparent from-0% via-30% to-65% pointer-events-none z-10" />

        {/* Drag cues */}
        <div className="absolute inset-x-0 top-3 flex justify-center pointer-events-none z-20">
          <span className="bg-black/50 backdrop-blur-md rounded-full px-3 py-1 text-[10px] uppercase tracking-widest text-white/80 font-medium">
            ← Pass · Consider →
          </span>
        </div>

        {/* Bottom metadata banner */}
        <div className="absolute bottom-0 left-0 right-0 p-5 flex justify-between items-end z-20">
          <div className="flex-1 min-w-0 pr-3">
            <h1 className="font-editorial text-2xl font-bold text-white leading-tight drop-shadow-sm truncate mb-0.5">
              {movie.title}
            </h1>
            <div className="flex items-center gap-2 text-xs text-white/80 font-medium">
              <span>{movie.release_year ?? new Date().getFullYear()}</span>
              {movie.rating != null && (
                <>
                  <span>·</span>
                  <span className="flex items-center gap-0.5 text-primary">
                    <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                    <span className="text-white font-semibold">{movie.rating.toFixed(1)}</span>
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Info button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onInfoClick();
            }}
            className="size-9 rounded-full bg-white/15 hover:bg-white/25 text-white flex items-center justify-center transition-all active:scale-90 shrink-0"
            aria-label="View film details"
          >
            <span className="material-symbols-outlined text-[18px]">info</span>
          </button>
        </div>
      </motion.div>
    );
  }
);

/* ============================
   COMPONENT
============================ */

function SessionPageInner() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  /* ----------------------------
     STATE
  ---------------------------- */

  const [session, setSession] = useState<Session | null>(null);
  const sessionRef = useRef<Session | null>(null);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const [movies, setMovies] = useState<Movie[]>([]);
  const moviesRef = useRef<Movie[]>([]);
  useEffect(() => {
    moviesRef.current = movies;
  }, [movies]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [moviesLoaded, setMoviesLoaded] = useState(false);
  const [summaryLoaded, setSummaryLoaded] = useState(false);

  // Phase 3 Collaborative Manifest Deck State
  const [isManifestDeck, setIsManifestDeck] = useState(false);
  const [currentDeckCard, setCurrentDeckCard] = useState<any>(null);
  const currentDeckCardRef = useRef<any>(null);
  const [deckCardIndex, setDeckCardIndex] = useState(0);
  const [totalDeckCards, setTotalDeckCards] = useState(40);
  const [waitingForPartner, setWaitingForPartner] = useState(false);
  const waitingForPartnerRef = useRef(false);
  useEffect(() => {
    waitingForPartnerRef.current = waitingForPartner;
  }, [waitingForPartner]);

  const [isDeckCompleted, setIsDeckCompleted] = useState(false);
  const [deckError, setDeckError] = useState<string | null>(null);
  const [isCandidateExhausted, setIsCandidateExhausted] = useState(false);
  const [lastSwipedCard, setLastSwipedCard] = useState<{
    card_index: number;
    movie_id: number;
    movie: Movie;
  } | null>(null);

  const [showMatch, setShowMatch] = useState(false);
  const [matchedMovie, setMatchedMovie] = useState<Movie | null>(null);

  const [matches, setMatches] = useState<Match[]>([]);
  const [loadingMatches, setLoadingMatches] = useState(false);

  const [error, setError] = useState("");
  const [swipeToast, setSwipeToast] = useState("");

  const [sessionLocked, setSessionLocked] = useState(false);
  const [partnerDisconnected, setPartnerDisconnected] = useState(false);
  const [swipeDirection, setSwipeDirection] = useState<"like" | "dislike" | "superlike">("like");
  const [partnerStatus, setPartnerStatus] = useState<"online" | "offline" | "swiping">("online");
  const [swipeCount, setSwipeCount] = useState(0);
  const recommendationsFetchedRef = useRef(false);
  const swipedMovieIdsRef = useRef(new Set<number>());
  const [checkingMore, setCheckingMore] = useState(false);
  const preferencesRedirectedRef = useRef(false);
  const isMountedRef = useRef(true);
  const isEndingRef = useRef(false);
  const isSwipePendingRef = useRef(false);
  const [isSwiping, setIsSwiping] = useState(false);
  const isSessionTerminatedRef = useRef(false);
  const [endSessionLoading, setEndSessionLoading] = useState(false);
  const [matchQueue, setMatchQueue] = useState<Movie[]>([]);
  const [partnerJoinedToast, setPartnerJoinedToast] = useState(false);
  const [partnerJoinedToastMsg, setPartnerJoinedToastMsg] = useState("");
  const [partnerDisplayName, setPartnerDisplayName] = useState<string>("");
  const [selectedMatchDetail, setSelectedMatchDetail] = useState<Match | null>(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Preload upcoming movie posters for buttery smooth card transitions
  useEffect(() => {
    if (!movies || movies.length === 0) return;
    for (let i = 1; i <= 3; i++) {
      const next = movies[currentIndex + i];
      if (next?.poster_url) {
        const img = new Image();
        img.src = next.poster_url;
      }
    }
  }, [currentIndex, movies]);

  const userDisplayName = localStorage.getItem("display_name") || localStorage.getItem("username") || "";
  const effectivePartnerName = partnerDisplayName || (
    session?.host_display_name && session.host_display_name !== userDisplayName
      ? session.host_display_name
      : session?.guest_display_name && session.guest_display_name !== userDisplayName
      ? session.guest_display_name
      : ""
  );

  /* ── Info bottom sheet ── */
  const [showInfoSheet, setShowInfoSheet] = useState(false);

  /* ── Streaming bottom sheet ── */
  const [showStreamingSheet, setShowStreamingSheet] = useState(false);
  const [streamingProviders, setStreamingProviders] = useState<{name:string;logo_url:string;url:string;type:string}[]>([]);
  const [streamingLoading, setStreamingLoading] = useState(false);
  const [streamingMovieId, setStreamingMovieId] = useState<number|null>(null);
  const [streamingMovieTitle, setStreamingMovieTitle] = useState<string>("");

  /* ── Watchlist ── */
  const [watchlistedIds, setWatchlistedIds] = useState<Set<number>>(new Set());
  const [watchlistLoading, setWatchlistLoading] = useState<number | null>(null);

  /* ── Re-questionnaire ── */
  const [showReQuestionnaire, setShowReQuestionnaire] = useState(false);

  /* ── Poster loaded tracking ── */
  const [posterLoaded, setPosterLoaded] = useState<Record<number, boolean>>({});

  /* ── Undo ── */
  const [lastSwiped, setLastSwiped] = useState<{movieId:number;index:number}|null>(null);
  const [undoLoading, setUndoLoading] = useState(false);

  // Waiting screen state
  const [codeCopied, setCodeCopied] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);

  /* ── Slice D: partner waiting overlay (non-blocking) ── */
  const [partnerLeftSession, setPartnerLeftSession] = useState(false);

  /* ── Slice E: role-aware end/leave controls ── */
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [leaveSessionLoading, setLeaveSessionLoading] = useState(false);

  /* ── Super-like ── */
  const [superLikeLoading, setSuperLikeLoading] = useState(false);
  const [showSuperLikeBurst, setShowSuperLikeBurst] = useState(false);

  /* ── Summary search ── */
  const [matchSearch, setMatchSearch] = useState("");

  /* ── Session Spotlight Tutorial ── */
  const [showSessionTour, setShowSessionTour] = useState(false);
  const [sessionTourDismissed, setSessionTourDismissed] = useState(false);

  const sessionUserId =
    session?.user_role === "guest" ? session?.guest_id : session?.host_id;
  const tourIdentity: TourIdentityInput = useMemo(
    () => ({ userId: sessionUserId }),
    [sessionUserId]
  );

  const activeCardMovie = movies[currentIndex];

  const isDeckReadyForTour = Boolean(
    (!error || error === "Swipe action could not be recorded.") &&
    Boolean(session) &&
    !session?.ended &&
    !sessionLocked &&
    !isSessionTerminatedRef.current &&
    Boolean(session?.host_joined && session?.guest_joined) &&
    moviesLoaded &&
    !waitingForPartner &&
    !showMatch &&
    !showReQuestionnaire &&
    !selectedMatchDetail &&
    !showStreamingSheet &&
    !showInfoSheet &&
    !showEndConfirm &&
    Boolean(activeCardMovie) &&
    (isManifestDeck
      ? Boolean(currentDeckCard) && !isDeckCompleted && !isCandidateExhausted
      : currentIndex < movies.length)
  );

  const isSessionTourLocked =
    showSessionTour ||
    (isDeckReadyForTour &&
      !sessionTourDismissed &&
      !hasSeenTour("session", tourIdentity));

  useEffect(() => {
    if (!isDeckReadyForTour || sessionTourDismissed) return;
    if (!hasSeenTour("session", tourIdentity)) {
      setShowSessionTour(true);
    }
  }, [isDeckReadyForTour, sessionTourDismissed, tourIdentity]);

  useEffect(() => {
    if (showSessionTour && (session?.ended || sessionLocked || showMatch)) {
      setShowSessionTour(false);
    }
  }, [showSessionTour, session?.ended, sessionLocked, showMatch]);

  const handleSessionTourComplete = useCallback(() => {
    setSessionTourDismissed(true);
    markTourFinished("session", "completed", tourIdentity);
    setShowSessionTour(false);
  }, [tourIdentity]);

  const handleSessionTourSkip = useCallback(() => {
    setSessionTourDismissed(true);
    markTourFinished("session", "skipped", tourIdentity);
    setShowSessionTour(false);
  }, [tourIdentity]);

  /* ── Component-scoped swipe eligibility gate ── */
  const canSwipe = Boolean(
    (!error || error === "Swipe action could not be recorded.") &&
    session &&
    !session.ended &&
    !sessionLocked &&
    !isSessionTerminatedRef.current &&
    session.host_joined &&
    session.guest_joined &&
    moviesLoaded &&
    !superLikeLoading &&
    !isSwiping &&
    !isSwipePendingRef.current &&
    !waitingForPartner &&
    !showMatch &&
    !showReQuestionnaire &&
    !selectedMatchDetail &&
    !showStreamingSheet &&
    !showInfoSheet &&
    !isSessionTourLocked &&
    (isManifestDeck ? Boolean(currentDeckCard) && !isDeckCompleted && !isCandidateExhausted : currentIndex < movies.length)
  );

  /* ============================
     LOAD MATCH HISTORY
  ============================ */

  const loadMatchHistory = useCallback(async () => {
    try {
      setLoadingMatches(true);
      const data = await apiRequest(`/api/matches/?session_id=${id}`);
      if (Array.isArray(data.matches)) {
        setMatches(data.matches);
      } else {
        setMatches([]);
      }
      const matchCount = Array.isArray(data.matches) ? data.matches.length : (typeof data.matched_count === "number" ? data.matched_count : 0);
      const incomingReviewed = typeof data.reviewed_count === "number" ? Math.max(data.reviewed_count, matchCount) : matchCount;
      if (incomingReviewed > 0) {
        setSwipeCount((prev) => Math.max(prev, incomingReviewed));
      }
      if (typeof data.matched_count === "number" || typeof data.affinity_percent === "number" || typeof data.reviewed_count === "number") {
        setSession((prev) => {
          if (!prev) return prev;
          const finalMatched = typeof data.matched_count === "number" ? data.matched_count : (prev.matched_count ?? matchCount);
          const candidateReviewed = typeof data.reviewed_count === "number" ? data.reviewed_count : (prev.reviewed_count ?? incomingReviewed);
          const finalReviewed = Math.max(candidateReviewed, finalMatched);
          const finalAffinity = (typeof data.affinity_percent === "number" && (typeof data.reviewed_count !== "number" || data.reviewed_count >= finalMatched))
            ? data.affinity_percent
            : (finalReviewed > 0 ? Math.min(100, Math.max(0, Math.round((finalMatched / finalReviewed) * 100))) : 0);
          return {
            ...prev,
            reviewed_count: finalReviewed,
            matched_count: finalMatched,
            affinity_percent: finalAffinity,
          };
        });
      }
    } catch (_e) {
      setMatches([]);
    } finally {
      setLoadingMatches(false);
    }
  }, [id]);

  /* ── Load watchlist IDs ── */
  const loadWatchlist = useCallback(async () => {
    try {
      const data = await apiRequest("/api/watchlist/");
      const ids = new Set<number>((data.watchlist || []).map((item: {movie_id: number}) => item.movie_id));
      setWatchlistedIds(ids);
    } catch { /* ignored */ }
  }, []);

  const toggleWatchlist = async (movieId: number, sessionId?: number) => {
    setWatchlistLoading(movieId);
    try {
      if (watchlistedIds.has(movieId)) {
        await apiRequest(`/api/watchlist/${movieId}/`, { method: "DELETE" });
        setWatchlistedIds(prev => { const s = new Set(prev); s.delete(movieId); return s; });
      } else {
        await apiRequest("/api/watchlist/", {
          method: "POST",
          body: JSON.stringify({ movie_id: movieId, session_id: sessionId }),
        });
        setWatchlistedIds(prev => new Set([...prev, movieId]));
      }
    } catch { /* ignored */ }
    setWatchlistLoading(null);
  };

  /* ============================
     METADATA RETRIEVAL & RECOVERY
  ============================ */

  const fetchMetadata = useCallback(async (movieId: number, fallbackTitle: string) => {
    try {
      const movieData = await apiRequest(`/api/movies/${movieId}/`);
      if (!isMountedRef.current) return;
      setMatchQueue((prev) =>
        prev.map((m) =>
          m.id === movieId
            ? {
                id: movieData.id,
                title: movieData.title || m.title || fallbackTitle,
                overview: movieData.overview || "",
                poster_url: movieData.poster_url || "",
                rating: movieData.rating ?? undefined,
                vote_count: movieData.vote_count ?? undefined,
                release_year: movieData.release_year ?? undefined,
                trailer_url: movieData.trailer_url ?? undefined,
                metadataStatus: "success",
              }
            : m
        )
      );
      setMatchedMovie((current) => {
        if (current && current.id === movieId) {
          return {
            ...current,
            title: movieData.title || current.title || fallbackTitle,
            overview: movieData.overview || current.overview,
            poster_url: movieData.poster_url || current.poster_url,
            rating: movieData.rating ?? current.rating,
            vote_count: movieData.vote_count ?? current.vote_count,
            release_year: movieData.release_year ?? current.release_year,
            trailer_url: movieData.trailer_url ?? current.trailer_url,
            metadataStatus: "success",
          };
        }
        return current;
      });
    } catch (_err) {
      if (!isMountedRef.current) return;
      setMatchQueue((prev) =>
        prev.map((m) =>
          m.id === movieId
            ? {
                ...m,
                metadataStatus: "failed",
              }
            : m
        )
      );
      setMatchedMovie((current) => {
        if (current && current.id === movieId) {
          return { ...current, metadataStatus: "failed" };
        }
        return current;
      });
    }
  }, []);

  /* ============================
     PHASE 3: DECK RETRIEVAL (SAFE FALLBACK)
  ============================ */

  const fetchDeckCard = useCallback(async (sessionId: string | number) => {
    try {
      const data = await apiRequest(`/api/sessions/${sessionId}/deck/card/`);
      if (data && data.is_legacy) {
        return { status: "legacy" as const };
      }
      if (data && data.transient_error) {
        setIsManifestDeck(true);
        setIsCandidateExhausted(false);
        const errStr = data.error || "Temporary movie service connection error. Tap retry to reconnect.";
        setDeckError(errStr);
        return { status: "retryable_error" as const, error: errStr };
      }
      if (data && data.replenishing) {
        setIsManifestDeck(true);
        setIsCandidateExhausted(false);
        setDeckError(null);
        setTimeout(() => {
          if (isMountedRef.current && sessionId) {
            fetchDeckCard(sessionId);
          }
        }, 1500);
        return { status: "replenishing" as const };
      }
      if (data && (data.exhausted || data.proposal_required)) {
        setIsManifestDeck(true);
        setIsCandidateExhausted(true);
        const errStr = data.error || "Eligible candidate pool exhausted (< 16).";
        setDeckError(errStr);
        return { status: "exhausted" as const, error: errStr };
      }
      if (data && data.success) {
        setIsManifestDeck(true);
        setDeckError(null);
        setIsCandidateExhausted(false);
        setDeckCardIndex(data.card_index ?? 0);
        setTotalDeckCards(data.total_cards || 40);
        setWaitingForPartner(Boolean(data.waiting_for_partner));
        setIsDeckCompleted(Boolean(data.is_completed));

        if (data.card) {
          const normalized = normalizeDeckCard(data.card);
          setCurrentDeckCard(data.card);
          currentDeckCardRef.current = data.card;
          setMovies([normalized]);
          moviesRef.current = [normalized];
          setCurrentIndex(0);
          setMoviesLoaded(true);
        } else if (data.is_completed) {
          setCurrentDeckCard(null);
          currentDeckCardRef.current = null;
          setMoviesLoaded(true);
        } else if (data.waiting_for_partner) {
          // No new card yet — partner hasn't caught up. Keep existing card visible
          // and set moviesLoaded so the compact waiting banner renders in the swiping UI.
          setMoviesLoaded(true);
        }
        return { status: "success" as const };
      }
      const errStr = data?.error || "Deck delivery returned unsuccessful";
      setDeckError(errStr);
      return { status: "retryable_error" as const, error: errStr };
    } catch (err: unknown) {
      console.warn("[fetchDeckCard] Collaborative deck retrieval error:", err);
      if (typeof err === "object" && err !== null) {
        const errorObj = err as { status?: number; data?: any; message?: string };
        if (errorObj.data?.is_legacy) {
          return { status: "legacy" as const };
        }
        if (errorObj.data?.exhausted || errorObj.data?.proposal_required) {
          setIsManifestDeck(true);
          setIsCandidateExhausted(true);
          const errStr = errorObj.data?.error || "Eligible candidate pool exhausted (< 16).";
          setDeckError(errStr);
          return { status: "exhausted" as const, error: errStr };
        }
        if (errorObj.status === 401 || errorObj.status === 403) {
          const errStr = errorObj.data?.error || errorObj.message || "Authentication error";
          setDeckError(errStr);
          return { status: "auth_error" as const, error: errStr, statusCode: errorObj.status };
        }
        const errStr = errorObj.data?.error || errorObj.message || "Screening deck connection error. Tap retry to reconnect.";
        setDeckError(errStr);
        return { status: "retryable_error" as const, error: errStr, statusCode: errorObj.status };
      }
      const genericError = "Screening deck connection error. Tap retry to reconnect.";
      setDeckError(genericError);
      return { status: "retryable_error" as const, error: genericError };
    }
  }, []);

  /* ============================
     SESSION POLLING DEFINITION
  ============================ */

  const pollSession = useCallback(async () => {
    if (!id) return;
    try {
      const data = await apiRequest(`/api/sessions/${id}/`);
      const s: Session = data.session;
      if (s) {
        const sMatched = typeof s.matched_count === "number" ? s.matched_count : 0;
        const sReviewed = typeof s.reviewed_count === "number" ? Math.max(s.reviewed_count, sMatched) : sMatched;
        const sAffinity = (typeof s.affinity_percent === "number" && (typeof s.reviewed_count !== "number" || s.reviewed_count >= sMatched))
          ? s.affinity_percent
          : (sReviewed > 0 ? Math.min(100, Math.max(0, Math.round((sMatched / sReviewed) * 100))) : 0);

        const normalizedSession: Session = {
          ...s,
          reviewed_count: sReviewed,
          matched_count: sMatched,
          affinity_percent: sAffinity,
        };
        setSession(normalizedSession);

        if (sReviewed > 0) {
          setSwipeCount((prev) => Math.max(prev, sReviewed));
        }

        if (s.ended) {
          isSessionTerminatedRef.current = true;
          setSessionLocked(true);
          if (sReviewed > 0) {
            setSwipeCount(sReviewed);
          }
          if (!summaryLoaded) {
            loadMatchHistory();
            loadWatchlist();
            setSummaryLoaded(true);
            trackEvent("session_summary_loaded", { session_id: s.id });
          }
          return;
        }
      }

      if (
        s.host_joined &&
        s.guest_joined &&
        s.user_preferences_set === false &&
        !s.preferences_set
      ) {
        navigate(`/session/${id}/preferences`, { replace: true });
        return;
      }

      if (s.preferences_set) {
        preferencesRedirectedRef.current = false;
      }

      if (moviesLoaded) return;

      if (
        s.host_joined &&
        s.guest_joined &&
        s.preferences_set &&
        !recommendationsFetchedRef.current
      ) {
        recommendationsFetchedRef.current = true;

        if (s.is_legacy) {
          try {
            const recos = await apiRequest(`/api/recommendations/?session_id=${id}`);
            setMovies(Array.isArray(recos.movies) ? recos.movies : []);
            setCurrentIndex(0);
            setMoviesLoaded(true);
            setIsManifestDeck(false);
            trackEvent("movies_loaded", { count: recos.movies?.length || 0 });
          } catch (err: unknown) {
            console.error("Failed to load recommendations:", err);
            setError("Failed to load movies. Please refresh.");
            recommendationsFetchedRef.current = false;
          }
          return;
        }

        const deckRes = await fetchDeckCard(id);
        if (deckRes.status === "success") {
          trackEvent("manifest_deck_loaded", { session_id: s.id });
        } else if (deckRes.status === "legacy") {
          try {
            const recos = await apiRequest(`/api/recommendations/?session_id=${id}`);
            setMovies(Array.isArray(recos.movies) ? recos.movies : []);
            setCurrentIndex(0);
            setMoviesLoaded(true);
            setIsManifestDeck(false);
            trackEvent("movies_loaded", { count: recos.movies?.length || 0 });
          } catch (err: unknown) {
            console.error("Failed to load recommendations:", err);
            setError("Failed to load movies. Please refresh.");
            recommendationsFetchedRef.current = false;
          }
        } else if (deckRes.status === "exhausted") {
          setIsCandidateExhausted(true);
        } else {
          // Retryable error / transient network or 500 error
          // Do NOT load legacy recommendations. Reset ref so user or retry button can re-attempt.
          recommendationsFetchedRef.current = false;
        }
      }
    } catch (_e) {
      if (!sessionRef.current && !moviesLoaded) {
        setError("Failed to load session");
      } else {
        console.warn("[pollSession] Background poll failed transiently, active session preserved");
      }
    }
  }, [id, moviesLoaded, summaryLoaded, loadMatchHistory, loadWatchlist, navigate, fetchDeckCard]);

  const pollSessionRef = useRef(pollSession);
  useEffect(() => {
    pollSessionRef.current = pollSession;
  }, [pollSession]);

  const fetchDeckCardRef = useRef(fetchDeckCard);
  useEffect(() => {
    fetchDeckCardRef.current = fetchDeckCard;
  }, [fetchDeckCard]);

  /* ============================
     WEBSOCKET (REAL-TIME STATE SYNCHRONIZATION & LIFECYCLE)
  ============================ */

  useEffect(() => {
    if (!id) return;

    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let fallbackPollTimer: number | null = null;
    let retryCount = 0;
    let isDisposed = false;
    let hadConnectedOnce = false;
    const sessionKey = String(id);

    // Initial REST fetch on mount to ensure immediate state hydration
    pollSessionRef.current();

    function stopFallbackPolling() {
      if (fallbackPollTimer !== null) {
        clearInterval(fallbackPollTimer);
        fallbackPollTimer = null;
      }
    }

    function startFallbackPolling() {
      if (isDisposed || isSessionTerminatedRef.current || fallbackPollTimer !== null) return;
      fallbackPollTimer = window.setInterval(() => {
        if (!isDisposed && !isSessionTerminatedRef.current) {
          pollSessionRef.current();
        }
      }, 6000);
    }

    function cleanupSocket(code = 1000) {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (socket) {
        const existing = activeSessionSockets.get(sessionKey);
        if (existing === socket) {
          activeSessionSockets.delete(sessionKey);
        }
        try {
          if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
            socket.close(code, "Session unmounted or terminated");
          }
        } catch {
          // ignore
        }
        socket = null;
      }
    }

    function connect() {
      if (isDisposed || isSessionTerminatedRef.current) return;

      // Tab-level deduplication: reuse active socket or prevent concurrent instances for the same session
      const existing = activeSessionSockets.get(sessionKey);
      if (existing && (existing.readyState === WebSocket.OPEN || existing.readyState === WebSocket.CONNECTING)) {
        socket = existing;
        return;
      }

      const wsUrl = getWsUrl(id!);
      const token = localStorage.getItem("auth_token");
      try {
        socket = new WebSocket(wsUrl, token ? ["token", token] : []);
        activeSessionSockets.set(sessionKey, socket);
      } catch (err) {
        console.warn("[Flick WS] Socket instantiation error:", err);
        startFallbackPolling();
        return;
      }

      socket.onopen = () => {
        retryCount = 0;
        setPartnerDisconnected(false);
        stopFallbackPolling();

        if (hadConnectedOnce) {
          // Resynchronize state after reconnection
          pollSessionRef.current();
          if (id) {
            fetchDeckCardRef.current(id);
          }
        }
        hadConnectedOnce = true;
      };

      socket.onerror = (err) => {
        console.warn("[Flick WS] Socket encountered error:", err);
      };

      socket.onclose = (event) => {
        if (activeSessionSockets.get(sessionKey) === socket) {
          activeSessionSockets.delete(sessionKey);
        }
        if (isDisposed || isSessionTerminatedRef.current) return;

        // Terminal close codes: 1000 (normal), 4000 (session terminated), 4001 (unauthorized), 4003 (forbidden), 4004 (not found)
        if (event.code === 1000 || event.code === 4000 || event.code === 4001 || event.code === 4003 || event.code === 4004) {
          console.warn(`[Flick WS] Connection closed terminally (${event.code}): ${event.reason}`);
          if (event.code === 1000 || event.code === 4000) {
            isSessionTerminatedRef.current = true;
            setSessionLocked(true);
            setPartnerStatus("offline");
            setSession((prev) => (prev ? { ...prev, ended: true } : prev));
          }
          stopFallbackPolling();
          return;
        }

        // Temporary interruption: activate controlled 6-second fallback polling while reconnecting
        startFallbackPolling();

        // Resilient reconnect with exponential backoff + full random jitter capped at 10s
        const backoffMs = Math.min(1000 * Math.pow(1.5, retryCount), 10000) + Math.random() * 500;
        retryCount++;
        reconnectTimer = window.setTimeout(connect, backoffMs);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === "partner_disconnected") {
            setPartnerDisconnected(true);
            trackEvent("partner_disconnected", { session_id: Number(id) });
          }

          if (data.type === "partner_swiping") {
            setPartnerStatus("swiping");
            if (waitingForPartnerRef.current && id) {
              fetchDeckCard(id);
            }
            setTimeout(() => {
              setPartnerStatus((prev) => (prev === "swiping" ? "online" : prev));
            }, 1500);
          }

          if (data.type === "presence") {
            if (data.user_id !== undefined) {
              setPartnerStatus(data.status);
            }
          }

          if (data.type === "partner_joined") {
            if (data.display_name) {
              setPartnerDisplayName(data.display_name);
            }
            const name = data.display_name || "Collaborator";
            setPartnerJoinedToastMsg(`${name} connected`);
            setPartnerJoinedToast(true);
            setTimeout(() => setPartnerJoinedToast(false), 3500);
            setSession((prev) => (prev ? { ...prev, guest_joined: true } : prev));
          }

          if (data.type === "match_event") {
            const incomingMovieId = Number(data.movie_id);
            const fallbackTitle = data.movie_title || "Discovered Film";
            const deckMovie = moviesRef.current.find((m) => m.id === incomingMovieId);
            const incomingPosterUrl = data.poster_url || deckMovie?.poster_url || "";
            const incomingRating = data.rating ?? deckMovie?.rating;
            const incomingYear = data.release_year ?? deckMovie?.release_year;
            const incomingSuperlikeAttr = data.superlike_attribution || "none";
            const incomingMatchType = data.match_type || (incomingSuperlikeAttr === "mutual" ? "mutual_superlike" : incomingSuperlikeAttr !== "none" ? "superlike" : "ordinary");
            let shouldFetch = false;

            setMatchQueue((prev) => {
              const existing = prev.find((m) => m.id === incomingMovieId);
              const isCurrent = matchedMovie && matchedMovie.id === incomingMovieId;

              // If already retrieved successfully, ignore duplicate event
              if ((isCurrent && matchedMovie.metadataStatus === "success") || (existing && existing.metadataStatus === "success")) {
                return prev;
              }

              // If currently fetching, do not launch concurrent duplicate request
              if (existing && existing.metadataStatus === "pending") {
                return prev;
              }

              // If failed earlier, safely retry recovery!
              if (existing && existing.metadataStatus === "failed") {
                shouldFetch = !incomingPosterUrl;
                return prev.map((m) => m.id === incomingMovieId ? {
                  ...m,
                  poster_url: incomingPosterUrl || m.poster_url,
                  rating: incomingRating ?? m.rating,
                  release_year: incomingYear ?? m.release_year,
                  superlike_attribution: incomingSuperlikeAttr,
                  match_type: incomingMatchType,
                  metadataStatus: incomingPosterUrl ? "success" : "pending",
                } : m);
              }

              // If poster_url is already available from websocket or in-memory deck, mark success immediately!
              if (incomingPosterUrl) {
                return [
                  ...prev,
                  {
                    id: incomingMovieId,
                    title: fallbackTitle,
                    overview: deckMovie?.overview || "",
                    poster_url: incomingPosterUrl,
                    rating: incomingRating,
                    release_year: incomingYear,
                    trailer_url: deckMovie?.trailer_url,
                    superlike_attribution: incomingSuperlikeAttr,
                    match_type: incomingMatchType,
                    metadataStatus: "success",
                  },
                ];
              }

              // Fresh placeholder inserted immediately to prevent concurrent duplicates
              shouldFetch = true;
              return [
                ...prev,
                {
                  id: incomingMovieId,
                  title: fallbackTitle,
                  overview: "",
                  poster_url: "",
                  superlike_attribution: incomingSuperlikeAttr,
                  match_type: incomingMatchType,
                  metadataStatus: "pending",
                },
              ];
            });

            if (shouldFetch) {
              fetchMetadata(incomingMovieId, fallbackTitle);
            }

            if (!prefersReducedMotion()) {
              confetti({
                particleCount: 80,
                spread: 60,
                scalar: 0.8,
                colors: ["#42634A", "#86A58A", "#D9D3C6", "#20221E"],
              });
            }

            trackEvent("match_queued", {
              session_id: Number(id),
              movie_id: incomingMovieId,
              source: "websocket",
            });
          }

          if (data.type === "session_ended" || data.type === "session_state_changed") {
            if (data.type === "session_ended" || (data.session && (data.session.ended || data.session.status === "ended")) || data.status === "ended" || data.ended) {
              isSessionTerminatedRef.current = true;
              setSessionLocked(true);
              setPartnerStatus("offline");
              setSession((prev) => (prev ? { ...prev, ended: true } : prev));
              trackEvent("session_ended_ws", { session_id: Number(id) });
              stopFallbackPolling();
              cleanupSocket(1000);
              loadMatchHistory();
              loadWatchlist();
              setSummaryLoaded(true);
              pollSessionRef.current();
              return;
            }
            if (data.type === "session_state_changed" && data.session) {
              setSession((prev) => (prev ? { ...prev, ...data.session } : data.session));
            }
          }

          if (data.type === "partner_left") {
            // Guest left voluntarily — session remains active for host
            setPartnerStatus("offline");
            setPartnerLeftSession(true);
            trackEvent("partner_left_session", { session_id: Number(id), role: data.role });
          }

          if (data.type === "preferences_updated") {
            setSession((prev) => {
              if (!prev) return prev;
              const isHost = prev.user_role === "host";
              const isGuest = prev.user_role === "guest";
              const myPrefsSet = isHost
                ? Boolean(data.host_preferences_set)
                : isGuest
                ? Boolean(data.guest_preferences_set)
                : prev.user_preferences_set;
              return {
                ...prev,
                preferences_set: Boolean(data.preferences_set),
                host_preferences_set: Boolean(data.host_preferences_set),
                guest_preferences_set: Boolean(data.guest_preferences_set),
                user_preferences_set: myPrefsSet,
              };
            });
            if (data.preferences_set) {
              recommendationsFetchedRef.current = false;
              setMoviesLoaded(false);
              setIsCandidateExhausted(false);
              setDeckError(null);
              setMovies([]);
              setCurrentIndex(0);
              if (id) {
                fetchDeckCardRef.current(id);
              }
            } else {
              recommendationsFetchedRef.current = false;
              setMoviesLoaded(false);
            }
          }

          if (data.type === "proposal_event") {
            if (data.event === "constraints_updated") {
              setIsCandidateExhausted(false);
              setDeckError(null);
              if (id) fetchDeckCardRef.current(id);
            } else if (data.event === "replenishment_exhausted") {
              setDeckError("Constraint replenishment exhausted (< 16 matching titles).");
            }
          }
        } catch (_e) {
          void _e;
        }
      };
    }

    connect();

    return () => {
      isDisposed = true;
      stopFallbackPolling();
      cleanupSocket(1000);
    };
  }, [id]);

  // Process match queue sequentially
  useEffect(() => {
    if (!showMatch && matchQueue.length > 0) {
      const timer = setTimeout(() => {
        const nextMatch = matchQueue[0];
        setMatchedMovie(nextMatch);
        setShowMatch(true);

        // Optional progressive haptic feedback on devices that support Vibration API
        if (typeof navigator !== "undefined" && "vibrate" in navigator) {
          try {
            const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
            if (!prefersReduced) {
              navigator.vibrate([40, 60, 40]);
            }
          } catch (_e) {
            // Graceful fallback for environments with restricted permissions
          }
        }
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [showMatch, matchQueue]);

  /* ============================
     SWIPE HANDLER
  ============================ */

  async function handleSwipe(reaction: "like" | "dislike" | "superlike") {
    if (!canSwipe || isSwiping || isSwipePendingRef.current) return;
    setIsSwiping(true);
    isSwipePendingRef.current = true;

    if (isManifestDeck) {
      const card = currentDeckCardRef.current;
      if (!card) {
        setIsSwiping(false);
        isSwipePendingRef.current = false;
        return;
      }

      try {
        setSwipeDirection(reaction);
        const currentMovie = movies[0] || normalizeDeckCard(card);
        setLastSwipedCard({
          card_index: card.card_index,
          movie_id: card.movie_id,
          movie: currentMovie,
        });
        setLastSwiped({ movieId: card.movie_id, index: card.card_index });

        trackEvent(
          reaction === "like" ? "swipe_like" : reaction === "superlike" ? "swipe_superlike" : "swipe_dislike",
          { movie_id: card.movie_id, card_index: card.card_index }
        );

        setSwipeCount((prev) => prev + 1);

        const idempotencyKey = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `${id}-${card.movie_id}-${card.card_index}-${Date.now()}`;

        const res = await apiRequest(`/api/sessions/${id}/deck/swipe/`, {
          method: "POST",
          headers: {
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            card_index: card.card_index,
            movie_id: card.movie_id,
            reaction,
          }),
        });

        if (res && res.success) {
          if (res.match_formed) {
            const posterUrl = card.poster_path
              ? (card.poster_path.startsWith("http")
                  ? card.poster_path
                  : `https://image.tmdb.org/t/p/w780${card.poster_path}`)
              : "";
            const releaseYear = card.release_date
              ? parseInt(String(card.release_date).slice(0, 4), 10)
              : undefined;

            const matched: Movie = {
              id: card.movie_id,
              title: card.title || "Film Selection",
              overview: card.overview || "",
              poster_url: posterUrl,
              rating: typeof card.rating === "number" ? card.rating : undefined,
              vote_count: typeof card.vote_count === "number" ? card.vote_count : undefined,
              release_year: releaseYear,
              superlike_attribution: res.superlike_attribution || (reaction === "superlike" ? (session?.user_role || "host") : "none"),
              match_type: res.match_type || (reaction === "superlike" ? "superlike" : "ordinary"),
              metadataStatus: "success",
            };
            setMatchedMovie(matched);
            setShowMatch(true);
            if (!prefersReducedMotion()) {
              confetti({
                particleCount: 80,
                spread: 60,
                scalar: 0.8,
                colors: ["#42634A", "#86A58A", "#D9D3C6", "#20221E"],
              });
            }
          }

          if (res.waiting_for_partner) {
            setWaitingForPartner(true);
          } else if (res.is_completed) {
            setIsDeckCompleted(true);
            setCurrentDeckCard(null);
            currentDeckCardRef.current = null;
          } else {
            await fetchDeckCard(id!);
          }
        }
      } catch (err: unknown) {
        console.error("[SessionPage] Manifest deck swipe error:", err);
        let resynced = false;
        let isEnded = false;

        if (typeof err === "object" && err !== null && "status" in err) {
          const errorObj = err as { status: number; data?: { error?: string; detail?: string; resync_required?: boolean } };
          const errMsg = errorObj.data?.error || errorObj.data?.detail || "";
          if (
            errMsg.toLowerCase().includes("ended") ||
            errorObj.status === 410
          ) {
            isEnded = true;
            isSessionTerminatedRef.current = true;
            setSessionLocked(true);
            setSession((prev) => (prev ? { ...prev, ended: true } : prev));
            return;
          }

          if (
            errorObj.status === 409 ||
            errorObj.status === 400 ||
            errorObj.data?.resync_required ||
            errMsg.toLowerCase().includes("expected card_index") ||
            errMsg.toLowerCase().includes("does not match manifest")
          ) {
            try {
              await fetchDeckCard(id!);
              resynced = true;
            } catch (syncErr) {
              console.warn("[SessionPage] Failed to fetch current deck card after swipe error:", syncErr);
            }
          }
        }

        if (!isEnded && !resynced) {
          try {
            await fetchDeckCard(id!);
            resynced = true;
          } catch (syncErr) {
            console.warn("[SessionPage] Fallback fetchDeckCard failed:", syncErr);
          }
        }

        setLastSwipedCard(null);
        setLastSwiped(null);

        if (!isEnded) {
          setSwipeToast(resynced ? "Deck updated. Please swipe again." : "Swipe could not be recorded. Please retry.");
          setTimeout(() => {
            if (isMountedRef.current) setSwipeToast("");
          }, 3500);
        }
      } finally {
        setIsSwiping(false);
        isSwipePendingRef.current = false;
      }
      return;
    }

    const movie = movies[currentIndex];
    if (!movie) {
      setIsSwiping(false);
      isSwipePendingRef.current = false;
      return;
    }

    // Strict client-side idempotency lock per movie ID
    if (swipedMovieIdsRef.current.has(movie.id)) {
      setIsSwiping(false);
      isSwipePendingRef.current = false;
      return;
    }
    swipedMovieIdsRef.current.add(movie.id);

    try {
      // Direction is set for the exiting card and preserved throughout transition
      setSwipeDirection(reaction);
      setCurrentIndex((prev) => prev + 1);
      setLastSwiped({ movieId: movie.id, index: currentIndex });
      setTimeout(() => setLastSwiped(null), 10000);

      trackEvent(
        reaction === "like" ? "swipe_like" : reaction === "superlike" ? "swipe_superlike" : "swipe_dislike",
        { movie_id: movie.id }
      );

      setSwipeCount((prev) => prev + 1);

      const idempotencyKey = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${id}-${movie.id}-${currentIndex}-${Date.now()}`;

      // Decoupled asynchronous API submission — never blocks the swipe deck
      await apiRequest("/api/swipes/", {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          session: Number(id),
          movie: movie.id,
          reaction,
          idempotency_key: idempotencyKey,
        }),
      });
    } catch (err: unknown) {
      console.error("[SessionPage] Legacy swipe error:", err);
      let sessionEnded = false;
      if (typeof err === "object" && err !== null && "status" in err) {
        const errorObj = err as { status: number; data?: { error?: string; detail?: string } };
        const errMsg = errorObj.data?.error || errorObj.data?.detail || "";
        if (errorObj.status === 409 || errMsg.toLowerCase().includes("ended")) {
          sessionEnded = true;
        }
      }
      if (sessionEnded) {
        return;
      }
      // Revert optimistic client state so the movie is preserved and user can retry
      swipedMovieIdsRef.current.delete(movie.id);
      setCurrentIndex((prev) => Math.max(0, prev - 1));
      setSwipeCount((prev) => Math.max(0, prev - 1));
      setLastSwiped(null);

      setSwipeToast("Swipe could not be recorded. Please retry.");
      setTimeout(() => {
        if (isMountedRef.current) setSwipeToast("");
      }, 4000);
    } finally {
      setIsSwiping(false);
      isSwipePendingRef.current = false;
    }
  }

  /* ============================
     END SESSION HELPER
  ============================ */

  async function endSession() {
    if (sessionLocked || session?.ended || isEndingRef.current) return;
    isEndingRef.current = true;
    setEndSessionLoading(true);
    setShowEndConfirm(false);
    try {
      const res = await apiRequest("/api/sessions/end/", {
        method: "POST",
        body: JSON.stringify({ session_id: Number(id) }),
      });
      if (isMountedRef.current) {
        isSessionTerminatedRef.current = true;
        setSessionLocked(true);
        if (Array.isArray(res?.matches)) {
          setMatches(res.matches);
        }
        const resMatched = typeof res?.matched_count === "number"
          ? res.matched_count
          : (Array.isArray(res?.matches) ? res.matches.length : 0);
        const resReviewed = typeof res?.reviewed_count === "number"
          ? Math.max(res.reviewed_count, resMatched)
          : resMatched;
        const resAffinity = (typeof res?.affinity_percent === "number" && (typeof res?.reviewed_count !== "number" || res.reviewed_count >= resMatched))
          ? res.affinity_percent
          : (resReviewed > 0 ? Math.min(100, Math.max(0, Math.round((resMatched / resReviewed) * 100))) : 0);

        if (resReviewed > 0) {
          setSwipeCount(resReviewed);
        }
        setSession((prev) => (prev ? {
          ...prev,
          ended: true,
          reviewed_count: resReviewed,
          matched_count: resMatched,
          affinity_percent: resAffinity,
        } : prev));
        const active = activeSessionSockets.get(String(id));
        if (active) {
          try { active.close(1000, "Session ended by user"); } catch {}
          activeSessionSockets.delete(String(id));
        }
        loadMatchHistory();
        loadWatchlist();
        setSummaryLoaded(true);
      }
    } catch (err: unknown) {
      console.error("[endSession] API error:", err);
      if (isMountedRef.current) {
        // Unlock on failure so temporary network interruptions allow retry
        isEndingRef.current = false;
        setEndSessionLoading(false);
        setError("Unable to conclude session. Please check your connection and retry.");
        setTimeout(() => {
          if (isMountedRef.current) setError("");
        }, 4000);
      }
      return;
    } finally {
      if (isMountedRef.current) {
        setEndSessionLoading(false);
      }
    }
  }

  /* ============================
     LEAVE SESSION HELPER (guest only)
  ============================ */

  async function leaveSession() {
    if (leaveSessionLoading || session?.ended) return;
    setLeaveSessionLoading(true);
    try {
      await apiRequest("/api/sessions/leave/", {
        method: "POST",
        body: JSON.stringify({ session_id: Number(id) }),
      });
      if (isMountedRef.current) {
        isSessionTerminatedRef.current = true;
        setSessionLocked(true);
        setSession((prev) => (prev ? { ...prev, ended: true } : prev));
        const active = activeSessionSockets.get(String(id));
        if (active) {
          try { active.close(1000, "Session left by user"); } catch {}
          activeSessionSockets.delete(String(id));
        }
      }
    } catch (err: unknown) {
      console.error("[leaveSession] API error:", err);
      if (isMountedRef.current) {
        setError("Unable to leave session. Please check your connection and retry.");
        setTimeout(() => {
          if (isMountedRef.current) setError("");
        }, 4000);
      }
    } finally {
      if (isMountedRef.current) setLeaveSessionLoading(false);
    }
  }

  /* ============================
     UNDO HANDLER
  ============================ */

  async function handleUndo() {
    if (isSessionTourLocked) return;
    if (isManifestDeck) {
      if (!lastSwipedCard || !session || undoLoading || isSwipePendingRef.current) return;
      setUndoLoading(true);
      try {
        await apiRequest(`/api/sessions/${id}/deck/undo/`, {
          method: "POST",
          body: JSON.stringify({
            card_index: lastSwipedCard.card_index,
            movie_id: lastSwipedCard.movie_id,
          }),
        });
        setLastSwipedCard(null);
        setLastSwiped(null);
        setWaitingForPartner(false);
        setIsDeckCompleted(false);
        await fetchDeckCard(id!);
        trackEvent("deck_swipe_undo", { movie_id: lastSwipedCard.movie_id, card_index: lastSwipedCard.card_index });
      } catch (err: unknown) {
        if (typeof err === "object" && err !== null && "status" in err) {
          const e = err as { status: number };
          if (e.status === 400 || e.status === 403) setLastSwipedCard(null);
        }
        setSwipeToast("Undo could not be completed.");
        setTimeout(() => {
          if (isMountedRef.current) setSwipeToast("");
        }, 4000);
      } finally {
        setUndoLoading(false);
      }
      return;
    }

    if (!lastSwiped || !session || undoLoading || isSwipePendingRef.current) return;
    setUndoLoading(true);
    try {
      await apiRequest("/api/swipes/undo/", {
        method: "DELETE",
        body: JSON.stringify({
          session_id: Number(id),
          movie_id: lastSwiped.movieId,
        }),
      });
      swipedMovieIdsRef.current.delete(lastSwiped.movieId);
      setCurrentIndex(lastSwiped.index);
      setLastSwiped(null);
      trackEvent("swipe_undo", { movie_id: lastSwiped.movieId });
    } catch (err: unknown) {
      if (typeof err === "object" && err !== null && "status" in err) {
        const e = err as { status: number };
        if (e.status === 403) setLastSwiped(null);
      }
    } finally {
      setUndoLoading(false);
    }
  }

  /* ============================
     SUPER-LIKE HANDLER
  ============================ */

  async function handleSuperLike() {
    if (!canSwipe || isSessionTourLocked || !session || superLikeLoading || isSwipePendingRef.current || showMatch || sessionLocked || session.ended) return;
    const movie = movies[currentIndex];
    if (!movie || !moviesLoaded) return;
    if (swipedMovieIdsRef.current.has(movie.id)) return;

    setSuperLikeLoading(true);
    setShowSuperLikeBurst(true);
    setTimeout(() => setShowSuperLikeBurst(false), 900);

    try {
      await handleSwipe("superlike");
    } finally {
      setSuperLikeLoading(false);
    }
  }

  /* ============================
     STREAMING SHEET HANDLER
  ============================ */

  async function openStreamingSheet(movieId: number, movieTitle?: string) {
    if (streamingMovieId === movieId) {
      setShowStreamingSheet(true);
      return;
    }
    setStreamingLoading(true);
    setShowStreamingSheet(true);
    setStreamingMovieId(movieId);
    if (movieTitle) setStreamingMovieTitle(movieTitle);
    try {
      const data = await apiRequest(`/api/movies/${movieId}/streaming-options/`);
      setStreamingProviders(Array.isArray(data.providers) ? data.providers : []);
    } catch (_e) {
      setStreamingProviders([]);
    } finally {
      setStreamingLoading(false);
    }
  }

  /* ============================
     KEYBOARD SHORTCUTS & DISMISSAL LISTENER
  ============================ */

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (isSessionTourLocked) return;
      const target = e.target as HTMLElement | null;
      const isTextInput = target && (
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable
      );
      const isInteractive = target && (
        isTextInput ||
        target.tagName === "SELECT" ||
        target.tagName === "BUTTON" ||
        target.tagName === "A" ||
        target.getAttribute("role") === "button"
      );

      // Escape key handling
      if (e.key === "Escape") {
        if (isTextInput && !showStreamingSheet && !showInfoSheet && !showReQuestionnaire && !selectedMatchDetail && !showMatch) {
          target.blur();
          return;
        }

        // Strict topmost dismissal order (one sheet/modal at a time)
        if (showStreamingSheet) {
          e.preventDefault();
          setShowStreamingSheet(false);
          return;
        }
        if (showInfoSheet) {
          e.preventDefault();
          setShowInfoSheet(false);
          return;
        }
        if (showReQuestionnaire) {
          e.preventDefault();
          setShowReQuestionnaire(false);
          return;
        }
        if (selectedMatchDetail) {
          e.preventDefault();
          setSelectedMatchDetail(null);
          return;
        }
        if (showMatch) {
          e.preventDefault();
          trackEvent("match_continue");
          setShowMatch(false);
          setMatchedMovie(null);
          setMatchQueue((prev) => prev.slice(1));
          return;
        }
        return;
      }

      // Ignore all other shortcuts when focus is inside an interactive control
      if (isInteractive) return;

      // Prevent duplicate triggers from holding down a key
      if (e.repeat) return;

      // Toggle movie info sheet: Space or I/KeyI
      if (e.key === " " || e.key === "Spacebar" || e.key === "i" || e.key === "I") {
        const canToggleInfo = (
          session &&
          !session.ended &&
          !sessionLocked &&
          moviesLoaded &&
          currentIndex < movies.length &&
          !showMatch &&
          !showReQuestionnaire &&
          !selectedMatchDetail &&
          !showStreamingSheet
        );
        if (canToggleInfo) {
          e.preventDefault();
          setShowInfoSheet((prev) => !prev);
          return;
        }
      }

      // Screening deck swipe shortcuts: ArrowLeft (Pass), ArrowRight (Like), ArrowUp (Super-like)
      if (!canSwipe) return;

      if (e.key === "ArrowLeft") {
        e.preventDefault();
        handleSwipe("dislike");
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        handleSwipe("like");
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        handleSuperLike();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    canSwipe,
    isSessionTourLocked,
    showStreamingSheet,
    showInfoSheet,
    showReQuestionnaire,
    selectedMatchDetail,
    showMatch,
    session,
    sessionLocked,
    moviesLoaded,
    currentIndex,
    movies,
  ]);

  /* ============================
     UI STATES — LOADING / ERROR
  ============================ */

  if (error && !moviesLoaded) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6 gap-4">
        <span className="material-symbols-outlined text-error text-[44px]">error</span>
        <p className="text-error text-sm font-medium text-center">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="mt-2 h-11 px-6 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold tracking-wider uppercase transition-colors"
        >
          Refresh Session
        </button>
      </div>
    );
  }

  if (!session) {
    return (
      <CinematicLoader
        message="Entering Screening Room"
        submessage="Connecting to collaborative viewing room..."
        fullScreen={true}
      />
    );
  }

  /* ============================
     SESSION ENDED — RECAP
  ============================ */

  if (session.ended) {
    const filteredMatches = matches.filter((m) =>
      m.movie_title.toLowerCase().includes(matchSearch.toLowerCase())
    );
    const effectiveMatched = (session && typeof session.matched_count === "number" && session.ended)
      ? session.matched_count
      : matches.length;

    const rawReviewed = (session && typeof session.reviewed_count === "number" && session.reviewed_count > 0)
      ? session.reviewed_count
      : swipeCount;

    // Mathematical invariant: every mutual match was reviewed by both participants
    const effectiveReviewed = Math.max(rawReviewed, effectiveMatched);

    const effectiveAffinity = (session && typeof session.affinity_percent === "number" && session.ended && (typeof session.reviewed_count !== "number" || session.reviewed_count >= effectiveMatched))
      ? session.affinity_percent
      : (effectiveReviewed > 0 ? Math.min(100, Math.max(0, Math.round((effectiveMatched / effectiveReviewed) * 100))) : 0);

    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col max-w-lg mx-auto border-x border-border/40">

        {/* ── Recap hero ── */}
        <div className="relative px-6 pt-12 pb-8 text-center border-b border-border/60 bg-surface">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
            Screening Concluded
          </span>
          <h1 className="font-editorial text-3xl md:text-4xl font-semibold tracking-tight text-foreground mb-2">
            Curated Matches
          </h1>
          <p className="text-foreground-secondary text-xs leading-relaxed max-w-sm mx-auto mb-6">
            {matches.length === 0
              ? "No mutual selections this time. Diverse tastes make for the most expansive film conversations."
              : `You and your partner found consensus on ${matches.length} film${matches.length !== 1 ? "s" : ""}.`}
          </p>

          {/* Stats row */}
          <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
            <div className="rounded-xl bg-surface-secondary/70 border border-border p-3 flex flex-col items-center">
              <span data-testid="stat-reviewed-count" className="font-editorial text-2xl font-bold text-foreground">{effectiveReviewed}</span>
              <span className="text-[10px] uppercase tracking-wider text-foreground-secondary font-medium mt-0.5">Reviewed</span>
            </div>
            <div className="rounded-xl bg-primary/10 border border-primary/30 p-3 flex flex-col items-center">
              <span data-testid="stat-matched-count" className="font-editorial text-2xl font-bold text-primary">{effectiveMatched}</span>
              <span className="text-[10px] uppercase tracking-wider text-primary font-medium mt-0.5">Matched</span>
            </div>
            <div className="rounded-xl bg-surface-secondary/70 border border-border p-3 flex flex-col items-center">
              <span data-testid="stat-affinity-percent" className="font-editorial text-2xl font-bold text-foreground">{effectiveAffinity}%</span>
              <span className="text-[10px] uppercase tracking-wider text-foreground-secondary font-medium mt-0.5">Affinity</span>
            </div>
          </div>
        </div>

        {/* ── Match list header ── */}
        {matches.length > 0 && (
          <div className="px-6 pt-5 pb-3">
            <div className="flex w-full items-center rounded-xl h-11 bg-surface border border-border focus-within:border-primary transition-colors px-3 gap-2">
              <span className="material-symbols-outlined text-foreground-secondary text-[18px]">search</span>
              <input
                value={matchSearch}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMatchSearch(e.target.value)}
                placeholder="Filter agreed films..."
                className="w-full bg-transparent border-none text-foreground placeholder:text-foreground-secondary text-xs outline-none"
              />
            </div>
          </div>
        )}

        {/* ── Match list ── */}
        <main className="flex-1 overflow-y-auto px-6 pb-36 divide-y divide-border/60">
          {loadingMatches && (
            <div className="py-2 space-y-1">
              {Array.from({ length: 4 }).map((_, i) => (
                <MatchItemSkeleton key={i} />
              ))}
            </div>
          )}

          {!loadingMatches && filteredMatches.length === 0 && matches.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <span className="material-symbols-outlined text-foreground-secondary text-[40px]">movie</span>
              <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs">
                No matching titles found in this session. Start a new screening with varied mood and genre selections.
              </p>
            </div>
          )}

          {!loadingMatches && filteredMatches.map((m, index) => {
            const isWatchlisted = watchlistedIds.has(m.movie_id);
            return (
              <div
                key={`${m.movie_id}-${index}`}
                className="flex items-center gap-3.5 py-3 hover:bg-surface-secondary/40 transition-colors rounded-xl px-2 -mx-2"
              >
                {/* Poster thumbnail */}
                <div
                  className="shrink-0 w-12 aspect-[2/3] rounded-md overflow-hidden bg-surface-secondary border border-border shadow-sm cursor-pointer relative"
                  onClick={() => setSelectedMatchDetail(m)}
                >
                  {m.poster_url ? (
                    <img
                      src={m.poster_url}
                      alt={m.movie_title}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = "none";
                      }}
                    />
                  ) : null}
                  <div className="w-full h-full flex items-center justify-center text-foreground-secondary absolute inset-0 -z-0">
                    <span className="material-symbols-outlined text-[18px]">movie</span>
                  </div>
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setSelectedMatchDetail(m)}>
                  <div className="flex items-center gap-1.5">
                    <h3 className="font-editorial text-sm font-semibold text-foreground line-clamp-1">{m.movie_title}</h3>
                    {m.match_type === "mutual_superlike" && (
                      <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-500/15 text-amber-500 border border-amber-500/30">
                        <span className="material-symbols-outlined text-[10px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                        Mutual
                      </span>
                    )}
                    {m.match_type === "superlike" && (
                      <span className="shrink-0 inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-bold bg-primary/15 text-primary border border-primary/30">
                        <span className="material-symbols-outlined text-[10px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                        Super-Liked
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-[10px] text-foreground-secondary">
                    {m.rating != null && (
                      <span className="flex items-center gap-0.5 text-primary font-semibold">
                        <span className="material-symbols-outlined text-[11px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                        {m.rating.toFixed(1)}
                      </span>
                    )}
                    {m.release_year && <span>· {m.release_year}</span>}
                    {m.matched_at && (
                      <span className="hidden sm:inline">· Agreed {new Date(m.matched_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {/* Info button */}
                  <button
                    onClick={() => setSelectedMatchDetail(m)}
                    className="size-9 rounded-full flex items-center justify-center border border-border bg-surface text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-all"
                    title="Film details"
                    aria-label="Film details"
                  >
                    <span className="material-symbols-outlined text-[18px]">info</span>
                  </button>

                  {/* Watchlist button */}
                  <button
                    onClick={() => toggleWatchlist(m.movie_id, m.session_id)}
                    disabled={watchlistLoading === m.movie_id}
                    className={`size-9 rounded-full flex items-center justify-center border transition-all ${
                      isWatchlisted
                        ? "bg-primary/10 border-primary text-primary"
                        : "bg-surface border-border text-foreground-secondary hover:text-foreground hover:border-foreground-secondary"
                    }`}
                    aria-label={isWatchlisted ? "Saved in watchlist" : "Save to watchlist"}
                  >
                    {watchlistLoading === m.movie_id ? (
                      <span className="size-3.5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <span
                        className="material-symbols-outlined text-[18px]"
                        style={{ fontVariationSettings: isWatchlisted ? "'FILL' 1" : undefined }}
                      >
                        bookmark
                      </span>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </main>

        {/* ── Selected match detail sheet ── */}
        <AnimatePresence>
          {selectedMatchDetail && (
            <motion.div
              variants={backdropVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end sm:items-center sm:justify-center p-0 sm:p-4"
              onClick={() => setSelectedMatchDetail(null)}
            >
              <motion.div
                variants={bottomSheetVariants}
                initial="initial"
                animate="animate"
                exit="exit"
                className="w-full max-w-lg bg-surface rounded-t-3xl sm:rounded-2xl border-t sm:border border-border p-6 pb-[max(2.5rem,calc(1.5rem+env(safe-area-inset-bottom)))] max-h-[85vh] overflow-y-auto overscroll-contain shadow-2xl"
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
              >
                <div className="flex justify-center sm:hidden mb-4">
                  <div className="w-10 h-1 rounded-full bg-border" />
                </div>

                <div className="flex items-start justify-between gap-4 mb-4">
                  <div className="flex gap-4">
                    <div className="w-16 sm:w-20 aspect-[2/3] rounded-lg overflow-hidden bg-surface-secondary border border-border shrink-0">
                      {selectedMatchDetail.poster_url ? (
                        <img src={selectedMatchDetail.poster_url} alt={selectedMatchDetail.movie_title} className="w-full h-full object-cover" />
                      ) : (
                        <div className="w-full h-full flex items-center justify-center text-foreground-secondary">
                          <span className="material-symbols-outlined text-[24px]">movie</span>
                        </div>
                      )}
                    </div>
                    <div>
                      <h3 className="font-editorial text-xl font-bold text-foreground leading-tight">{selectedMatchDetail.movie_title}</h3>
                      <div className="flex items-center gap-2 mt-1 text-xs text-foreground-secondary flex-wrap">
                        {selectedMatchDetail.rating != null && (
                          <span className="flex items-center gap-0.5 text-primary font-semibold">
                            <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                            {selectedMatchDetail.rating.toFixed(1)}
                            {selectedMatchDetail.vote_count && <span className="text-foreground-secondary font-normal">({selectedMatchDetail.vote_count})</span>}
                          </span>
                        )}
                        {selectedMatchDetail.release_year && (
                          <span>· {selectedMatchDetail.release_year}</span>
                        )}
                        {selectedMatchDetail.original_language && (
                          <span className="uppercase text-[10px] px-1.5 py-0.5 bg-surface-secondary rounded border border-border">
                            {selectedMatchDetail.original_language}
                          </span>
                        )}
                      </div>
                      {Array.isArray(selectedMatchDetail.genres) && selectedMatchDetail.genres.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {selectedMatchDetail.genres.map((g, i) => (
                            <span key={i} className="text-[10px] font-medium bg-primary/10 text-primary px-2 py-0.5 rounded-full border border-primary/20">
                              {g}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedMatchDetail(null)}
                    className="size-8 rounded-full bg-surface-secondary flex items-center justify-center text-foreground-secondary hover:text-foreground shrink-0 transition-transform active:scale-90"
                  >
                    <span className="material-symbols-outlined text-[18px]">close</span>
                  </button>
                </div>

                {selectedMatchDetail.overview && (
                  <div className="mb-5">
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-1 block">Synopsis</span>
                    <p className="text-foreground text-xs leading-relaxed">{selectedMatchDetail.overview}</p>
                  </div>
                )}

                <div className="mb-5">
                  <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-2 block">Streaming Availability</span>
                  <StreamingOptions movieId={selectedMatchDetail.movie_id} movieTitle={selectedMatchDetail.movie_title} />
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => toggleWatchlist(selectedMatchDetail.movie_id, selectedMatchDetail.session_id)}
                    className={`flex-1 h-11 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 active:scale-[0.98] ${
                      watchlistedIds.has(selectedMatchDetail.movie_id)
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-surface hover:bg-surface-secondary text-foreground"
                    }`}
                  >
                    <span className="material-symbols-outlined text-[16px]" style={{ fontVariationSettings: watchlistedIds.has(selectedMatchDetail.movie_id) ? "'FILL' 1" : undefined }}>
                      bookmark
                    </span>
                    {watchlistedIds.has(selectedMatchDetail.movie_id) ? "Saved in Watchlist" : "Save to Watchlist"}
                  </button>
                  <button
                    onClick={() => setSelectedMatchDetail(null)}
                    className="h-11 px-5 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground text-xs font-semibold uppercase tracking-wider transition-colors active:scale-95"
                  >
                    Close
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Bottom CTAs ── */}
        <div className="fixed bottom-0 left-0 right-0 max-w-lg mx-auto bg-background/95 backdrop-blur-md border-t border-border/60 p-4 flex flex-col gap-2.5 z-20">
          <button
            onClick={() => { trackEvent("start_new_session_clicked"); navigate("/"); }}
            className="w-full h-12 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
          >
            <span className="material-symbols-outlined text-[18px]">add_circle</span>
            Begin New Screening
          </button>
          <button
            onClick={() => navigate("/sessions?tab=history")}
            className="w-full h-11 rounded-xl bg-surface border border-border hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2"
          >
            <span className="material-symbols-outlined text-[18px]">history</span>
            Screening Archives
          </button>
        </div>
      </div>
    );
  }

  /* ============================
     WAITING ROOM
  ============================ */

  const sessionLink = session ? `${window.location.origin}/join/${session.code}` : "";
  const copyCode = () => {
    if (session) navigator.clipboard?.writeText(session.code);
    setCodeCopied(true); setTimeout(() => setCodeCopied(false), 2000);
  };
  const copyLink = () => {
    navigator.clipboard?.writeText(sessionLink);
    setLinkCopied(true); setTimeout(() => setLinkCopied(false), 2000);
  };
  const shareLink = async () => {
    if (navigator.share) {
      await navigator.share({ title: "Join my Flick cinema session", url: sessionLink }).catch(() => {});
    } else {
      copyLink();
    }
  };

  if (!session.host_joined || !session.guest_joined) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        {partnerJoinedToast && (
          <div className="fixed top-6 left-1/2 -translate-x-1/2 z-50 bg-primary text-surface text-xs font-semibold px-4 py-2.5 rounded-full shadow-lg flex items-center gap-2 animate-fade-in-down uppercase tracking-wider">
            <span className="material-symbols-outlined text-[16px]">person_add</span>
            {partnerJoinedToastMsg || "Collaborator connected"}
          </div>
        )}

        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center">
          <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary relative">
            <span className="material-symbols-outlined text-[36px]">group</span>
            <div className="absolute inset-0 rounded-full border border-primary/30 animate-ping" style={{ animationDuration: "2.5s" }} />
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Collaborative Deck
            </span>
            <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5">
              Awaiting Second Viewer
            </h1>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              Share the invitation code below to synchronize your screening deck.
            </p>
          </div>

          {/* Session code card */}
          <div className="w-full bg-surface border border-border rounded-2xl p-6 flex flex-col items-center gap-3 shadow-sm">
            <span className="text-[10px] text-foreground-secondary uppercase tracking-widest font-semibold">Passcode</span>
            <div className="font-editorial text-4xl font-bold tracking-[0.25em] text-foreground">{session.code}</div>
            <button
              onClick={copyCode}
              className="flex items-center gap-1.5 text-xs text-foreground-secondary hover:text-foreground transition-colors font-medium mt-1"
            >
              <span className="material-symbols-outlined text-[15px]">{codeCopied ? "check" : "content_copy"}</span>
              {codeCopied ? "Copied" : "Copy code"}
            </button>
          </div>

          {/* Share options */}
          <div className="w-full flex gap-3">
            <button
              onClick={shareLink}
              className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <span className="material-symbols-outlined text-[16px]">share</span>
              Share Invite
            </button>
            <button
              onClick={copyLink}
              className="flex-1 h-11 rounded-xl bg-surface border border-border hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined text-[16px]">{linkCopied ? "check" : "link"}</span>
              {linkCopied ? "Copied" : "Copy Link"}
            </button>
          </div>

          {/* Pulsing indicator */}
          <div className="flex gap-2 pt-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="size-2 rounded-full bg-primary/40 animate-pulse"
                   style={{ animationDelay: `${i * 0.25}s` }} />
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* ============================
     MATCH POPUP MODAL
  ============================ */

  if (showMatch && matchedMovie) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.3 }}
        className="fixed inset-0 z-50 bg-background/95 backdrop-blur-md overflow-y-auto overscroll-contain p-3 sm:p-6 pb-4 sm:pb-8 flex flex-col items-center justify-center"
      >
        <div className="max-w-sm w-full flex-1 flex flex-col justify-between py-1 sm:py-3 my-auto max-h-full">

          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ delay: 0.1, duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            className="text-center pt-0 mb-0.5"
          >
            <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-0.5 block">
              {matchedMovie.match_type === "mutual_superlike"
                ? "★ Mutual Super-Like ★"
                : matchedMovie.match_type === "superlike"
                ? "★ Super-Liked Discovery ★"
                : "Consensus Reached"}
            </span>
            <h1 className="font-editorial text-xl sm:text-2xl md:text-3xl font-semibold text-foreground tracking-tight mb-0.5">
              {matchedMovie.match_type === "mutual_superlike"
                ? "Double Super-Like!"
                : matchedMovie.match_type === "superlike"
                ? "Mutual Selection"
                : "Film Selected"}
            </h1>
            <p className="text-foreground-secondary text-[11px] sm:text-xs">
              {matchedMovie.match_type === "mutual_superlike"
                ? "Both viewers sent a Super-Like for this film!"
                : matchedMovie.match_type === "superlike"
                ? "A Super-Like unlocked this film recommendation."
                : "Both viewers expressed interest in this film."}
            </p>
            {matchedMovie.superlike_attribution && matchedMovie.superlike_attribution !== "none" && (
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-primary/15 border border-primary/30 text-primary text-[11px] font-bold uppercase tracking-wider mt-1.5">
                <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                <span>
                  {matchedMovie.superlike_attribution === "mutual"
                    ? "Mutual Priority Interest"
                    : matchedMovie.superlike_attribution === "host"
                    ? session?.user_role === "host" ? "Priority Interest (Your Selection)" : "Priority Interest (Partner's Selection)"
                    : session?.user_role === "guest" ? "Priority Interest (Your Selection)" : "Priority Interest (Partner's Selection)"}
                </span>
              </div>
            )}
          </motion.div>

          {/* Stacked poster cards */}
          <motion.div
            initial={{ opacity: 0, scale: 0.84, rotateY: 15 }}
            animate={{ opacity: 1, scale: 1, rotateY: 0 }}
            transition={{ delay: 0.18, type: "spring", stiffness: 320, damping: 22 }}
            className="relative w-full max-w-[120px] sm:max-w-[160px] md:max-w-[190px] aspect-[2/3] mx-auto my-1.5 sm:my-3 shrink-0"
          >
            {/* Back rotated card */}
            <div className="absolute inset-0 -rotate-6 translate-x-2 -translate-y-2 rounded-2xl overflow-hidden shadow-lg border border-border bg-surface-secondary opacity-60">
              {matchedMovie.poster_url && (
                <img src={matchedMovie.poster_url} className="w-full h-full object-cover" alt="" />
              )}
            </div>

            {/* Front card */}
            <div className="absolute inset-0 rotate-2 rounded-2xl overflow-hidden shadow-2xl border-2 border-primary/40 bg-surface z-10">
              {matchedMovie.poster_url ? (
                <img src={matchedMovie.poster_url} className="w-full h-full object-cover" alt={matchedMovie.title} />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-surface-secondary p-4 text-center">
                  <span className="material-symbols-outlined text-foreground-secondary text-[40px]">movie</span>
                </div>
              )}
            </div>
          </motion.div>

          {/* Title & metadata */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.26, duration: 0.3 }}
            className="text-center mb-1.5"
          >
            <h2 className="font-editorial text-base sm:text-lg md:text-xl font-bold text-foreground leading-snug mb-0.5">
              {matchedMovie.title}
            </h2>
            <div className="flex items-center justify-center gap-2 text-xs text-foreground-secondary">
              {matchedMovie.rating && (
                <span className="flex items-center gap-1 font-semibold text-foreground">
                  <span className="material-symbols-outlined text-primary text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
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
                  onClick={() => fetchMetadata(matchedMovie.id, matchedMovie.title)}
                  className="inline-flex items-center gap-0.5 text-[10px] text-primary hover:underline font-semibold"
                >
                  <span className="material-symbols-outlined text-[13px]">refresh</span>
                  Retry details
                </button>
              </div>
            )}
          </motion.div>

          {/* Quick actions row */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.32, duration: 0.3 }}
            className="flex items-center justify-center gap-2 mb-2 w-full"
          >
            {matchedMovie.trailer_url && (
              <a
                href={matchedMovie.trailer_url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackEvent("match_trailer_clicked", { movie_id: matchedMovie.id })}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 sm:py-2 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground text-xs font-semibold uppercase tracking-wider transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-[16px]">play_circle</span>
                Trailer
              </a>
            )}

            <button
              onClick={() => toggleWatchlist(matchedMovie.id, Number(id))}
              disabled={watchlistLoading === matchedMovie.id}
              className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 sm:py-2 rounded-xl border text-xs font-semibold uppercase tracking-wider transition-all active:scale-95 ${
                watchlistedIds.has(matchedMovie.id)
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-surface hover:bg-surface-secondary text-foreground"
              }`}
            >
              <span className="material-symbols-outlined text-[16px]"
                style={{ fontVariationSettings: watchlistedIds.has(matchedMovie.id) ? "'FILL' 1" : undefined }}>
                bookmark
              </span>
              {watchlistedIds.has(matchedMovie.id) ? "Saved" : "Save"}
            </button>
          </motion.div>

          {/* Streaming options preview */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.36, duration: 0.3 }}
            className="w-full mb-2"
          >
            <StreamingOptions movieId={matchedMovie.id} movieTitle={matchedMovie.title} />
          </motion.div>

          {/* Action buttons */}
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4, duration: 0.3 }}
            className="flex flex-col gap-2 w-full mt-1"
          >
            <button
              onClick={() => {
                trackEvent("match_continue");
                setShowMatch(false);
                setMatchedMovie(null);
                setMatchQueue((prev) => prev.slice(1));
              }}
              className="w-full h-10 sm:h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98]"
            >
              Continue Screening Deck
            </button>
            <button
              onClick={async () => {
                trackEvent("match_end_session");
                await endSession();
              }}
              disabled={endSessionLoading || sessionLocked || session?.ended}
              className="w-full h-10 sm:h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-all shadow-sm active:scale-[0.98] disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {endSessionLoading ? (
                <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
              ) : (
                "Conclude & View All Matches"
              )}
            </button>
          </motion.div>
        </div>
      </motion.div>
    );
  }

  /* ============================
     AWAITING PARTNER PREFERENCES
  ============================ */

  if (
    session &&
    session.host_joined &&
    session.guest_joined &&
    session.user_preferences_set &&
    !session.preferences_set
  ) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
          <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary relative">
            <span className="material-symbols-outlined text-[36px]">tune</span>
            <div className="absolute inset-0 rounded-full border border-primary/30 animate-ping" style={{ animationDuration: "2.5s" }} />
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Curatorial Alignment
            </span>
            <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5">
              Awaiting Partner Preferences
            </h1>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              Your cinematic taste parameters are locked in. Waiting for your companion to submit their questionnaire.
            </p>
          </div>

          <div className="flex gap-2 pt-2">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="size-2 rounded-full bg-primary/40 animate-pulse"
                style={{ animationDelay: `${i * 0.25}s` }}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  /* ============================
     UNSET USER PREFERENCES FALLBACK
  ============================ */

  if (
    session &&
    session.host_joined &&
    session.guest_joined &&
    session.user_preferences_set === false &&
    !session.preferences_set
  ) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
          <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary relative">
            <span className="material-symbols-outlined text-[36px]">tune</span>
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Curatorial Alignment
            </span>
            <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5">
              Set Your Taste Parameters
            </h1>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              Please complete your questionnaire to curate the collaborative screening deck.
            </p>
          </div>

          <button
            onClick={() => navigate(`/session/${id}/preferences`)}
            className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
          >
            <span className="material-symbols-outlined text-[16px]">tune</span>
            Complete Questionnaire
          </button>
        </div>
      </div>
    );
  }

  /* ============================
     AWAITING PARTNER SYNCHRONY (BUFFER LIMIT)
     — no longer a full-screen takeover; now rendered as an inline overlay
       inside the main swiping UI further below.
  ============================ */

  /* ============================
     MANIFEST DECK CONCLUDED
  ============================ */

  if (isManifestDeck && isDeckCompleted && !showMatch && !session?.ended) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
          <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[36px]">auto_awesome</span>
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Curated Manifest Concluded
            </span>
            <h2 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5">
              Screening Deck Concluded
            </h2>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              Every curated film in this {totalDeckCards}-title manifest has been evaluated by participants. Proceed to the screening summary to see your joint selections.
            </p>
          </div>

          <div className="w-full flex flex-col gap-2.5">
            <button
              onClick={endSession}
              disabled={endSessionLoading || sessionLocked || session?.ended}
              className="w-full h-12 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              {endSessionLoading ? (
                <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">movie</span>
                  Conclude Screening & View Matches
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ============================
     LOADING MOVIES SKELETON & RETRY VIEW
  ============================ */

  if (!moviesLoaded && movies.length === 0) {
    if (deckError && !isCandidateExhausted) {
      return (
        <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
          <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
            <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-amber-500">
              <span className="material-symbols-outlined text-[36px]">wifi_off</span>
            </div>

            <div>
              <span className="text-[11px] font-semibold uppercase tracking-widest text-amber-500 mb-1 block">
                Connection Notice
              </span>
              <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5">
                Screening Deck Unavailable
              </h1>
              <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto" data-testid="deck-error-message">
                {deckError}
              </p>
            </div>

            <button
              onClick={() => {
                setDeckError(null);
                recommendationsFetchedRef.current = false;
                if (id) fetchDeckCard(id);
              }}
              data-testid="deck-retry-button"
              className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
            >
              <span className="material-symbols-outlined text-[16px]">refresh</span>
              Retry Screening Deck
            </button>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col justify-between overflow-hidden max-w-lg mx-auto border-x border-border/40 p-6 select-none relative">
        <div className="flex items-center justify-between py-3.5 border-b border-border/60">
          <div className="h-4 w-32 bg-surface-secondary rounded animate-pulse" />
          <div className="size-8 rounded-full bg-surface-secondary animate-pulse" />
        </div>
        <div className="flex-grow flex items-center justify-center py-6">
          <DeckCardSkeleton />
        </div>
        <div className="pb-8 pt-2 flex justify-around items-center max-w-sm mx-auto w-full">
          <div className="size-12 rounded-full bg-surface-secondary animate-pulse" />
          <div className="size-14 rounded-full bg-surface-secondary animate-pulse" />
          <div className="size-16 rounded-full bg-primary/20 animate-pulse" />
          <div className="size-12 rounded-full bg-surface-secondary animate-pulse" />
        </div>

        <ConstraintExhaustionNoticeModal
          isOpen={isCandidateExhausted}
          sessionId={id!}
          userRole={session?.user_role || (session?.host_joined ? "host" : "guest")}
          onClose={() => setIsCandidateExhausted(false)}
          onReplenished={() => {
            setIsCandidateExhausted(false);
            setDeckError(null);
            if (id) fetchDeckCard(id);
          }}
          onConcludeSession={endSession}
          onAdjustPreferences={() => {
            setIsCandidateExhausted(false);
            recommendationsFetchedRef.current = false;
            setMoviesLoaded(false);
            setDeckError(null);
            navigate(`/session/${id}/preferences`);
          }}
        />
      </div>
    );
  }

  /* ============================
     NO MORE MOVIES
  ============================ */

  if (currentIndex >= movies.length && !waitingForPartner) {
    const fetchMoreMovies = async () => {
      setCheckingMore(true);
      try {
        const recos = await apiRequest(`/api/recommendations/?session_id=${id}`);
        if (recos.exhausted || recos.movies.length === 0) {
          setError("All curated titles for these parameters have been reviewed.");
        } else {
          const newMovies = Array.isArray(recos.movies) ? recos.movies : [];
          setMovies(newMovies);
          setCurrentIndex(0);
          trackEvent("movies_refetched", { session_id: Number(id), count: newMovies.length });
        }
      } catch (_e) {
        setError("Failed to load more films");
      } finally {
        setCheckingMore(false);
      }
    };

    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-sm flex flex-col items-center gap-6 text-center p-8 rounded-2xl border border-border bg-surface shadow-sm">
          <div className="size-20 rounded-full bg-surface-secondary border border-border flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-[36px]">movie_filter</span>
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Deck Exhausted
            </span>
            <h2 className="font-editorial text-2xl font-semibold tracking-tight text-foreground mb-1.5">
              Batch Concluded
            </h2>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              You have reviewed all current film recommendations for this session.
            </p>
          </div>

          <div className="w-full flex flex-col gap-2.5">
            <button
              onClick={fetchMoreMovies}
              disabled={checkingMore}
              className="w-full h-12 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              {checkingMore ? (
                <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span className="material-symbols-outlined text-[18px]">refresh</span>
                  Load Extended Catalog
                </>
              )}
            </button>

            <button
              onClick={endSession}
              disabled={endSessionLoading || sessionLocked || session?.ended}
              className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {endSessionLoading ? (
                <span className="size-4 border-2 border-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                "Conclude Screening & View Matches"
              )}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ============================
     MAIN SWIPING UI
  ============================ */

  const movie = activeCardMovie;
  const nextMovie = movies[currentIndex + 1];

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col justify-between overflow-hidden max-w-lg mx-auto border-x border-border/40 select-none">

      {/* ── Partner status pill (top bar) ── */}
      <div
        data-tour="session-header"
        className="flex items-center justify-between px-6 py-3.5 bg-background/95 backdrop-blur-md border-b border-border/60 z-10 relative"
      >
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${
            partnerStatus === "online"  ? "bg-primary" :
            partnerStatus === "swiping" ? "bg-primary animate-pulse" :
                                          "bg-foreground-secondary/40"
          }`} />
          <span className="text-xs font-medium text-foreground-secondary tracking-wide">
            {partnerStatus === "online"  && (effectivePartnerName ? `${effectivePartnerName} connected` : "Partner connected")}
            {partnerStatus === "swiping" && (effectivePartnerName ? `${effectivePartnerName} reviewing…` : "Partner reviewing…")}
            {partnerStatus === "offline" && (effectivePartnerName ? `${effectivePartnerName} disconnected` : "Partner disconnected")}
          </span>
        </div>

        {/* End / Preferences top-right */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowReQuestionnaire(true)}
            className="size-8 rounded-full flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors"
            title="Adjust taste parameters"
            aria-label="Adjust taste parameters"
          >
            <span className="material-symbols-outlined text-[18px]">tune</span>
          </button>
          {session?.user_role === "guest" ? (
            <button
              onClick={leaveSession}
              disabled={leaveSessionLoading || sessionLocked || session?.ended}
              data-testid="leave-screening-btn"
              className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary hover:text-foreground transition-colors disabled:opacity-50"
            >
              {leaveSessionLoading ? "Leaving…" : "Leave"}
            </button>
          ) : (
            <button
              onClick={() => setShowEndConfirm(true)}
              disabled={endSessionLoading || sessionLocked || session?.ended}
              data-testid="conclude-screening-btn"
              className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary hover:text-foreground transition-colors disabled:opacity-50"
            >
              {endSessionLoading ? "Concluding…" : "Conclude"}
            </button>
          )}
        </div>
      </div>

      {/* ── Slot type badge (Collaborative Deck) ── */}
      {isManifestDeck && currentDeckCard?.slot_type && (
        <div className="flex justify-center pt-2 px-6 z-10">
          <span className="text-[10px] uppercase tracking-widest font-semibold px-2.5 py-0.5 rounded-full bg-primary/10 border border-primary/20 text-primary">
            {currentDeckCard.slot_type.replace(/_/g, " ")}
          </span>
        </div>
      )}

      {/* ── Boutique curatorial note (Phase 3 Section 8) ── */}
      {isManifestDeck && totalDeckCards < 40 && !isDeckCompleted && (
        <div className="flex justify-center pt-1.5 px-6 z-10" data-testid="boutique-selection-note">
          <span className="text-[11px] font-medium tracking-wide text-primary bg-primary/10 border border-primary/20 rounded-full px-3 py-0.5">
            Curated boutique selection of {totalDeckCards} matching films
          </span>
        </div>
      )}

      {/* ── In-deck retryable error banner (Phase 3 Safe Fallback) ── */}
      {deckError && (
        <div className="mx-6 mt-2 rounded-xl bg-amber-500/10 border border-amber-500/30 px-3.5 py-2.5 text-xs text-amber-700 dark:text-amber-300 flex items-center justify-between gap-2 z-10" data-testid="deck-error-banner">
          <span>{deckError}</span>
          <button
            onClick={() => {
              setDeckError(null);
              if (id) fetchDeckCard(id);
            }}
            className="px-2.5 py-1 text-[11px] font-semibold bg-amber-500/20 hover:bg-amber-500/30 rounded-lg transition-colors shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Partner disconnected notification ── */}
      {partnerDisconnected && (
        <div className="mx-6 mt-2 rounded-xl bg-amber-500/10 border border-amber-500/20 px-3.5 py-2 text-xs text-amber-700 dark:text-amber-300 text-center z-10">
          {effectivePartnerName ? `${effectivePartnerName} temporarily disconnected. Awaiting reconnection…` : "Partner temporarily disconnected. Awaiting reconnection…"}
        </div>
      )}

      {/* ── Partner left session notification (guest left voluntarily) ── */}
      {partnerLeftSession && (
        <div
          data-testid="partner-left-banner"
          className="mx-6 mt-2 rounded-xl bg-surface border border-border px-3.5 py-2 text-xs text-foreground-secondary text-center z-10 flex items-center justify-center gap-2"
        >
          <span className="material-symbols-outlined text-[14px]">person_remove</span>
          <span>{effectivePartnerName ? `${effectivePartnerName} has left the screening.` : "Your partner has left the screening."} Your session remains active.</span>
        </div>
      )}

      {/* ── Compact partner-synchrony waiting banner (Slice D) ── */}
      {isManifestDeck && waitingForPartner && !showMatch && !session?.ended && (
        <div
          data-testid="partner-waiting-banner"
          className="mx-6 mt-2 rounded-xl bg-primary/8 border border-primary/25 px-3.5 py-2.5 z-20 flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2 min-w-0">
            <div className="relative shrink-0">
              <span className="material-symbols-outlined text-primary text-[18px]">sync</span>
              <span className="absolute inset-0 rounded-full border border-primary/40 animate-ping" style={{ animationDuration: "2s" }} />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold text-primary uppercase tracking-wider leading-none mb-0.5">Partner catching up</p>
              <p className="text-[10px] text-foreground-secondary leading-tight truncate">
                {effectivePartnerName ? `Waiting for ${effectivePartnerName}…` : "Waiting for your partner…"}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            {lastSwipedCard && (
              <button
                onClick={handleUndo}
                disabled={undoLoading}
                data-testid="waiting-undo-btn"
                className="h-7 px-2.5 rounded-lg border border-border bg-surface text-foreground-secondary hover:text-foreground text-[10px] font-semibold uppercase tracking-wider transition-colors disabled:opacity-50 flex items-center gap-1"
              >
                <span className="material-symbols-outlined text-[13px]">undo</span>
                Undo
              </button>
            )}
            <button
              onClick={() => id && fetchDeckCard(id)}
              data-testid="check-partner-status-btn"
              className="h-7 px-2.5 rounded-lg bg-primary/15 hover:bg-primary/25 text-primary text-[10px] font-semibold uppercase tracking-wider transition-colors flex items-center gap-1"
            >
              <span className="material-symbols-outlined text-[13px]">refresh</span>
              Check
            </button>
            <button
              onClick={session?.user_role === "guest" ? leaveSession : () => setShowEndConfirm(true)}
              disabled={endSessionLoading || leaveSessionLoading || sessionLocked || session?.ended}
              data-testid="waiting-leave-btn"
              className="h-7 px-2 rounded-lg border border-border bg-surface text-foreground-secondary hover:text-foreground text-[10px] font-semibold uppercase tracking-wider transition-colors disabled:opacity-50"
              title={session?.user_role === "guest" ? "Leave screening" : "End screening"}
            >
              <span className="material-symbols-outlined text-[13px]">exit_to_app</span>
            </button>
          </div>
        </div>
      )}

      {/* ── Transient swipe error notification ── */}
      {swipeToast && (
        <div className="mx-6 mt-2 rounded-xl bg-red-500/10 border border-red-500/20 px-3.5 py-2 text-xs text-red-600 dark:text-red-400 text-center z-10 flex items-center justify-center gap-2">
          <span className="material-symbols-outlined text-[16px]">warning</span>
          <span>{swipeToast}</span>
        </div>
      )}

      {/* ── Movie card (Art-House aesthetic) ── */}
      <div className="flex-grow flex items-center justify-center px-4 py-3 z-0 relative">
        {/* Underneath Card (depth illusion) */}
        {nextMovie && (
          <div
            aria-hidden="true"
            className="absolute w-full max-w-sm h-[63vh] rounded-2xl overflow-hidden border border-border/60 bg-surface shadow-md pointer-events-none select-none scale-[0.95] translate-y-2 opacity-60 transition-transform duration-300"
          >
            {nextMovie.poster_url && (
              <img
                src={nextMovie.poster_url}
                alt=""
                className="w-full h-full object-cover"
              />
            )}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
            <div className="absolute bottom-0 left-0 right-0 p-5 bg-black/40 backdrop-blur-sm border-t border-white/10">
              <h2 className="font-editorial text-2xl font-bold text-white/90 leading-tight truncate">
                {nextMovie.title}
              </h2>
            </div>
          </div>
        )}

        <AnimatePresence custom={swipeDirection} mode="popLayout">
          {movie && (
            <MovieSwipeCard
              key={movie.id}
              custom={swipeDirection}
              movie={movie}
              disabled={!canSwipe}
              onSwipe={(reaction) => handleSwipe(reaction)}
              onInfoClick={() => !isSessionTourLocked && setShowInfoSheet(true)}
              posterLoaded={!!posterLoaded[movie.id]}
              onPosterLoad={() => setPosterLoaded((prev) => ({ ...prev, [movie.id]: true }))}
            />
          )}
        </AnimatePresence>
      </div>

      {/* ── Action buttons & counter ── */}
      <div className="pb-8 pt-2 px-6 z-10 relative">
        <div className="flex justify-around items-center max-w-sm mx-auto">

          {/* Undo */}
          <button
            data-tour="session-undo"
            onClick={handleUndo}
            disabled={!lastSwiped || undoLoading || isSessionTourLocked}
            className={`size-12 rounded-full border flex items-center justify-center transition-all active:scale-95 ${
              lastSwiped && !undoLoading && !isSessionTourLocked
                ? "border-border bg-surface text-foreground hover:bg-surface-secondary shadow-sm"
                : "border-border/40 bg-surface/40 text-foreground-secondary/30 cursor-not-allowed"
            }`}
            title="Recall last action"
            aria-label="Recall last action"
          >
            {undoLoading ? (
              <span className="size-4 border-2 border-foreground border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[20px]">undo</span>
            )}
          </button>

          {/* Dislike / Pass */}
          <button
            data-tour="session-pass"
            onClick={() => handleSwipe("dislike")}
            disabled={!canSwipe}
            className={`size-14 rounded-full border border-border bg-surface flex items-center justify-center shadow-sm transition-all ${
              canSwipe
                ? "hover:border-error hover:text-error text-foreground-secondary hover:scale-105 active:scale-95 cursor-pointer"
                : "opacity-40 cursor-not-allowed text-foreground-secondary/40"
            }`}
            title="Pass"
            aria-label="Pass"
          >
            <span className="material-symbols-outlined text-[26px]">close</span>
          </button>

          {/* Like / Primary CTA */}
          <button
            data-tour="session-like"
            onClick={() => handleSwipe("like")}
            disabled={!canSwipe}
            className={`size-16 rounded-full bg-primary text-surface flex items-center justify-center shadow-md transition-all ${
              canSwipe
                ? "hover:bg-primary-hover hover:scale-105 active:scale-95 cursor-pointer"
                : "opacity-40 cursor-not-allowed"
            }`}
            title="Recommend"
            aria-label="Recommend"
          >
            <span className="material-symbols-outlined text-[30px]" style={{ fontVariationSettings: "'FILL' 1" }}>
              favorite
            </span>
          </button>

          {/* Super-like */}
          <div className="relative">
            {showSuperLikeBurst && (
              <div className="absolute inset-0 rounded-full bg-primary/20 animate-ping pointer-events-none" />
            )}
            <button
              data-tour="session-superlike"
              onClick={handleSuperLike}
              disabled={!canSwipe}
              className={`size-12 rounded-full border border-primary/40 bg-primary/10 text-primary flex items-center justify-center shadow-sm transition-all ${
                canSwipe
                  ? "hover:bg-primary/20 hover:scale-105 active:scale-95 cursor-pointer"
                  : "opacity-40 cursor-not-allowed"
              }`}
              title="Priority interest"
              aria-label="Priority interest"
            >
              {superLikeLoading ? (
                <span className="size-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              ) : (
                <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
              )}
            </button>
          </div>
        </div>

        {/* Film counter */}
        <p
          data-tour="session-progress"
          className="text-center text-[10px] uppercase tracking-widest font-semibold text-foreground-secondary mt-4"
        >
          {isManifestDeck
            ? `Film ${deckCardIndex + 1} of ${totalDeckCards}`
            : `Film ${currentIndex + 1} of ${movies.length}`}
        </p>

        {/* Subtle desktop keyboard shortcuts */}
        <div className="hidden md:flex items-center justify-center gap-2.5 text-[11px] text-foreground-secondary/70 mt-3 select-none">
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded border border-border bg-surface-secondary font-mono text-[10px]">←</kbd>
            <span>Pass</span>
          </span>
          <span className="text-border">·</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded border border-border bg-surface-secondary font-mono text-[10px]">↑</kbd>
            <span>Super-like</span>
          </span>
          <span className="text-border">·</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded border border-border bg-surface-secondary font-mono text-[10px]">→</kbd>
            <span>Like</span>
          </span>
          <span className="text-border">·</span>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 rounded border border-border bg-surface-secondary font-mono text-[10px]">Space</kbd>
            <span>Info</span>
          </span>
        </div>
      </div>

      {/* ── INFO BOTTOM SHEET ── */}
      <AnimatePresence>
        {showInfoSheet && (
          <>
            <motion.div
              variants={backdropVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
              onClick={() => setShowInfoSheet(false)}
            />
            <motion.div
              variants={bottomSheetVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed bottom-0 left-0 right-0 max-w-lg mx-auto z-50 bg-surface border-t border-border rounded-t-3xl max-h-[85vh] overflow-y-auto overscroll-contain px-6 pt-3 pb-[max(2.5rem,calc(1.5rem+env(safe-area-inset-bottom)))] shadow-2xl"
            >
              <div className="flex justify-center mb-5">
                <div className="w-10 h-1 bg-border rounded-full cursor-pointer" onClick={() => setShowInfoSheet(false)} />
              </div>

              <div className="flex justify-between items-center mb-5">
                <h2 className="font-editorial text-2xl font-semibold text-foreground">Film Overview</h2>
                <button
                  onClick={() => setShowInfoSheet(false)}
                  className="size-8 flex items-center justify-center rounded-full bg-surface-secondary text-foreground-secondary hover:text-foreground transition-transform active:scale-90"
                >
                  <span className="material-symbols-outlined text-[18px]">close</span>
                </button>
              </div>

              {movie && (
                <div className="space-y-5">
                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-2 block">Synopsis</span>
                    <p className="text-foreground text-xs leading-relaxed">{movie.overview || "No synopsis available."}</p>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap">
                    {movie.rating && (
                      <span className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-surface-secondary border border-border text-xs font-semibold text-foreground">
                        <span className="material-symbols-outlined text-primary text-[14px]" style={{ fontVariationSettings: "'FILL' 1" }}>star</span>
                        {movie.rating.toFixed(1)}
                        {movie.vote_count && <span className="text-foreground-secondary font-normal">({movie.vote_count})</span>}
                      </span>
                    )}
                    {movie.release_year && (
                      <span className="px-3 py-1.5 rounded-lg bg-surface-secondary border border-border text-xs text-foreground-secondary font-medium">
                        {movie.release_year}
                      </span>
                    )}
                    {movie.trailer_url && (
                      <a
                        href={movie.trailer_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/30 text-primary text-xs font-semibold hover:bg-primary/20 transition-colors"
                      >
                        <span className="material-symbols-outlined text-[16px]">play_circle</span>
                        Trailer
                      </a>
                    )}
                  </div>

                  <div>
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-primary mb-2 block">Streaming Availability</span>
                    <button
                      onClick={() => { setShowInfoSheet(false); openStreamingSheet(movie.id, movie.title); }}
                      className="flex items-center gap-2 w-full px-4 py-3 rounded-xl border border-border bg-surface-secondary hover:bg-surface-secondary/70 transition-colors text-left"
                    >
                      <span className="material-symbols-outlined text-primary text-[18px]">play_circle</span>
                      <span className="text-xs font-semibold text-foreground">Streaming Availability</span>
                      <span className="material-symbols-outlined text-foreground-secondary text-[16px] ml-auto">chevron_right</span>
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── STREAMING BOTTOM SHEET ── */}
      <AnimatePresence>
        {showStreamingSheet && (
          <>
            <motion.div
              variants={backdropVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setShowStreamingSheet(false)}
            />
            <motion.div
              variants={bottomSheetVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-x-0 bottom-0 max-w-lg mx-auto z-50"
            >
              <div className="bg-surface rounded-t-3xl border-t border-border max-h-[70vh] flex flex-col px-6 pt-3 pb-[max(2rem,calc(1rem+env(safe-area-inset-bottom)))] shadow-2xl">
                <div className="flex justify-center mb-4">
                  <div className="w-10 h-1 rounded-full bg-border" />
                </div>

                <div className="flex items-center justify-between pb-3 border-b border-border/60 mb-4">
                  <div>
                    <h3 className="font-editorial text-xl font-semibold text-foreground">Streaming Availability</h3>
                    {streamingMovieTitle && <p className="text-xs text-foreground-secondary mt-0.5">{streamingMovieTitle}</p>}
                  </div>
                  <button onClick={() => setShowStreamingSheet(false)}
                    className="size-8 rounded-full bg-surface-secondary flex items-center justify-center text-foreground-secondary hover:text-foreground transition-transform active:scale-90">
                    <span className="material-symbols-outlined text-[18px]">close</span>
                  </button>
                </div>

                <div className="overflow-y-auto overscroll-contain flex-1">
                  {streamingLoading ? (
                    <div className="py-4 space-y-2">
                      <StreamingItemSkeleton />
                      <StreamingItemSkeleton />
                      <StreamingItemSkeleton />
                    </div>
                  ) : streamingProviders.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 gap-2 text-center">
                      <span className="material-symbols-outlined text-foreground-secondary text-[36px]">tv_off</span>
                      <p className="text-xs font-semibold text-foreground">No current streaming outlets verified</p>
                      <p className="text-[11px] text-foreground-secondary">Available via archival rental or regional theatrical platforms.</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-3">
                      {["flatrate", "rent", "buy"].map((type) => {
                        const group = streamingProviders.filter(p => p.type === type);
                        if (group.length === 0) return null;
                        const label = type === "flatrate" ? "Subscription" : type === "rent" ? "Digital Rental" : "Digital Purchase";
                        return (
                          <div key={type}>
                            <span className="text-[10px] font-semibold text-primary uppercase tracking-widest mb-1.5 block">{label}</span>
                            <div className="flex flex-col gap-1.5">
                              {group.map((p, i) => {
                                const item = (
                                  <div key={i} className="flex items-center gap-3 bg-surface-secondary/60 hover:bg-surface-secondary rounded-xl px-3 py-2 border border-border transition-colors">
                                    {p.logo_url ? (
                                      <img src={p.logo_url} alt={p.name} className="size-7 rounded-md object-contain bg-surface p-0.5 border border-border" />
                                    ) : (
                                      <div className="size-7 rounded-md bg-primary/10 flex items-center justify-center text-primary">
                                        <span className="material-symbols-outlined text-[16px]">smart_display</span>
                                      </div>
                                    )}
                                    <span className="text-xs font-medium text-foreground flex-1">{p.name}</span>
                                    {p.url && (
                                      <span className="material-symbols-outlined text-foreground-secondary text-[14px]">open_in_new</span>
                                    )}
                                  </div>
                                );
                                return p.url ? (
                                  <a key={i} href={p.url} target="_blank" rel="noopener noreferrer" className="block focus:outline-hidden">
                                    {item}
                                  </a>
                                ) : (
                                  item
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                      <div className="pt-2 text-[10px] text-foreground-secondary text-center font-sans">
                        Data provided by JustWatch via TMDB
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── RE-QUESTIONNAIRE SHEET ── */}
      <AnimatePresence>
        {showReQuestionnaire && (
          <>
            <motion.div
              variants={backdropVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end"
              onClick={() => setShowReQuestionnaire(false)}
            />
            <motion.div
              variants={bottomSheetVariants}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed bottom-0 inset-x-0 max-w-lg mx-auto z-50"
            >
              <div className="w-full bg-surface rounded-t-3xl border-t border-border p-6 pb-[max(2rem,calc(1rem+env(safe-area-inset-bottom)))] shadow-2xl" onClick={(e) => e.stopPropagation()}>
                <div className="flex justify-center mb-4">
                  <div className="w-10 h-1 rounded-full bg-border" />
                </div>
                <h3 className="font-editorial text-xl font-semibold text-foreground mb-1">Adjust Taste Parameters</h3>
                <p className="text-xs text-foreground-secondary mb-5 leading-relaxed">
                  Both viewers will re-align their mood and genre selections. Your existing match log remains preserved.
                </p>
                <div className="flex flex-col gap-2.5">
                  <button
                    onClick={async () => {
                      setShowReQuestionnaire(false);
                      recommendationsFetchedRef.current = false;
                      setMoviesLoaded(false);
                      setIsCandidateExhausted(false);
                      setDeckError(null);
                      try {
                        await apiRequest(`/api/sessions/${id}/reset-preferences/`, { method: "POST" });
                      } catch { /* ignored */ }
                      navigate(`/session/${id}/preferences`);
                    }}
                    className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
                  >
                    <span className="material-symbols-outlined text-[16px]">tune</span>
                    Reconfigure Taste Parameters
                  </button>
                  <button
                    onClick={() => setShowReQuestionnaire(false)}
                    className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98]"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* ── Constraint Exhaustion Notice Modal (Phase 3 Section 15) ── */}
      <ConstraintExhaustionNoticeModal
        isOpen={isCandidateExhausted}
        sessionId={id!}
        userRole={session?.user_role || (session?.host_joined ? "host" : "guest")}
        onClose={() => setIsCandidateExhausted(false)}
        onReplenished={() => {
          setIsCandidateExhausted(false);
          setDeckError(null);
          if (id) fetchDeckCard(id);
        }}
        onConcludeSession={endSession}
        onAdjustPreferences={() => {
          setIsCandidateExhausted(false);
          recommendationsFetchedRef.current = false;
          setMoviesLoaded(false);
          setDeckError(null);
          navigate(`/session/${id}/preferences`);
        }}
      />

      {/* ── End Screening Confirmation Modal (Slice E — host only) ── */}
      {showEndConfirm && (
        <div
          data-testid="end-confirm-modal"
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setShowEndConfirm(false); }}
        >
          <div className="w-full max-w-sm bg-surface border border-border rounded-2xl shadow-xl p-6 flex flex-col gap-4">
            <div className="flex flex-col gap-1 text-center">
              <span className="material-symbols-outlined text-primary text-[32px] mx-auto">stop_circle</span>
              <h2 className="font-editorial text-lg font-semibold tracking-tight text-foreground">End Screening?</h2>
              <p className="text-xs text-foreground-secondary leading-relaxed">
                This will end the screening for both participants. Your match history and screening archive will be preserved.
              </p>
            </div>
            <div className="flex flex-col gap-2.5">
              <button
                onClick={endSession}
                disabled={endSessionLoading}
                data-testid="end-confirm-proceed-btn"
                className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-60"
              >
                {endSessionLoading ? (
                  <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[16px]">stop_circle</span>
                    End Screening for Both
                  </>
                )}
              </button>
              <button
                onClick={() => setShowEndConfirm(false)}
                className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-colors"
              >
                Keep Screening
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Session Spotlight Tutorial ── */}
      <SpotlightTour
        isOpen={showSessionTour}
        steps={SESSION_TOUR_STEPS}
        ariaLabel="Screening room tutorial"
        onComplete={handleSessionTourComplete}
        onSkip={handleSessionTourSkip}
      />
    </div>
  );
}

export default function SessionPage() {
  return (
    <ErrorBoundary>
      <SessionPageInner />
    </ErrorBoundary>
  );
}
