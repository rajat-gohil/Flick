import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, useMotionValue, useTransform, type PanInfo } from "framer-motion";
import { useTheme } from "../context/ThemeContext";
import { usePrefersReducedMotion } from "../lib/motion";
import AnimatedFlickLogo from "../components/AnimatedFlickLogo";
import { ApiError } from "../lib/api";
import { coordinateGuestProvisioning } from "../services/guestProvisionCoordinator";
import RecoveryCodeModal from "../components/RecoveryCodeModal";

/* ============================
   VERIFIED FILM DATASET (FROM FLICK DB / TMDB)
   Used only as illustrative sample cards for the landing demonstration.
============================ */

type SampleFilm = {
  id: number;
  title: string;
  year: number;
  rating: string;
  genres: string[];
  posterUrl: string;
  backdropUrl: string;
  synopsis: string;
  fallbackTone: string;
};

const SAMPLE_DECK: SampleFilm[] = [
  {
    id: 157336,
    title: "Interstellar",
    year: 2014,
    rating: "8.5",
    genres: ["Adventure", "Drama", "Sci-Fi"],
    posterUrl: "https://image.tmdb.org/t/p/w780/yQvGrMoipbRoddT0ZR8tPoR7NfX.jpg",
    backdropUrl: "https://image.tmdb.org/t/p/w1280/8sNiAPPYU14PUepFNeSNGUTiHW.jpg",
    synopsis:
      "Explorers travel through a wormhole in space in an attempt to ensure humanity's survival.",
    fallbackTone: "from-slate-900 via-amber-950/70 to-zinc-950",
  },
  {
    id: 155,
    title: "The Dark Knight",
    year: 2008,
    rating: "8.5",
    genres: ["Action", "Crime", "Thriller"],
    posterUrl: "https://image.tmdb.org/t/p/w780/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
    backdropUrl: "https://image.tmdb.org/t/p/w1280/cfT29Im5VDvjE0RpyKOSdCKZal7.jpg",
    synopsis:
      "Batman faces the Joker, a criminal mastermind testing the limits of order and chaos in Gotham.",
    fallbackTone: "from-zinc-900 via-sky-950/70 to-neutral-950",
  },
  {
    id: 27205,
    title: "Inception",
    year: 2010,
    rating: "8.4",
    genres: ["Action", "Crime", "Sci-Fi"],
    posterUrl: "https://image.tmdb.org/t/p/w780/xlaY2zyzMfkhk0HSC5VUwzoZPU1.jpg",
    backdropUrl: "https://image.tmdb.org/t/p/w1280/8ZTVqvKDQ8emSGUEMjsS4yHAwrp.jpg",
    synopsis:
      "A thief who steals corporate secrets through dream-sharing technology takes on an inverse mission.",
    fallbackTone: "from-stone-900 via-orange-950/60 to-zinc-950",
  },
];

const SHAWSHANK_STILL: SampleFilm = {
  id: 278,
  title: "The Shawshank Redemption",
  year: 1994,
  rating: "8.7",
  genres: ["Crime", "Drama"],
  posterUrl: "https://image.tmdb.org/t/p/w780/9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg",
  backdropUrl: "https://image.tmdb.org/t/p/w1280/pNjh59JSxChQktamG3LMp9ZoQzp.jpg",
  synopsis: "Two imprisoned men bond over a number of years, finding solace and eventual redemption.",
  fallbackTone: "from-zinc-900 via-amber-950/50 to-neutral-950",
};

type WorkflowStep = {
  number: string;
  title: string;
  summary: string;
};

const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    number: "01",
    title: "Create a Screening Room",
    summary:
      "Choose Hollywood, Indian, or World Cinema, along with languages and genres to shape the deck for tonight.",
  },
  {
    number: "02",
    title: "Share the 6-letter room code",
    summary:
      "Send the invite link or room code to your partner. They join in any browser without installing an app.",
  },
  {
    number: "03",
    title: "Swipe independently",
    summary:
      "Browse the same film lineup on your own screens. Passes stay private so nobody steers the vote.",
  },
  {
    number: "04",
    title: "See only what you both chose",
    summary:
      "When both viewers recommend the same film, Flick unlocks the match with details, watchlist saving, and regional streaming info where available.",
  },
];

const FAQ_ITEMS = [
  {
    q: "Do we both need accounts to use Flick?",
    a: "No. Tap Start a Movie Night to open a guest session without entering an email or password. Your partner can join from your room link in seconds.",
  },
  {
    q: "Does Flick stream or play movies?",
    a: "No. Flick helps two people agree on what to watch. When you match on a film, Flick displays its overview, rating, and streaming providers via TMDB/JustWatch data where available for your region.",
  },
  {
    q: "How does my partner join my Screening Room?",
    a: "When you create a session, Flick gives you a 6-character room code and an invite URL. Send either one so your partner can open the same room and set their own preferences.",
  },
  {
    q: "What is the 16-character recovery key?",
    a: "Guest sessions issue a private 16-character key so you can restore your matches and watchlist on another browser or device, or convert your guest session into a permanent email account later.",
  },
];

function PosterArtwork({
  film,
  imgFailed,
  onImgError,
  className = "",
}: {
  film: SampleFilm;
  imgFailed: boolean;
  onImgError: () => void;
  className?: string;
}) {
  if (!imgFailed) {
    return (
      <img
        src={film.posterUrl}
        alt={`${film.title} (${film.year}) film poster`}
        className={`w-full h-full object-cover ${className}`}
        onError={onImgError}
      />
    );
  }
  return (
    <div
      className={`w-full h-full bg-gradient-to-br ${film.fallbackTone} flex flex-col justify-between p-5 text-white`}
    >
      <div className="flex items-center justify-between text-xs text-white/70 font-medium">
        <span>{film.year}</span>
        <span>★ {film.rating}</span>
      </div>
      <div>
        <p className="font-display text-2xl font-bold leading-tight text-white">{film.title}</p>
        <p className="text-xs text-white/75 mt-1.5">{film.genres.join(" · ")}</p>
      </div>
    </div>
  );
}

export default function EntryPage() {
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const shouldReduceMotion = usePrefersReducedMotion();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);

  // Interactive hero sample deck state
  const [deckIndex, setDeckIndex] = useState(0);
  const [sampleHistory, setSampleHistory] = useState<number[]>([]);
  const [matchedSampleFilm, setMatchedSampleFilm] = useState<SampleFilm | null>(null);
  const dragX = useMotionValue(0);
  const cardRotate = useTransform(dragX, [-180, 0, 180], [-10, 0, 10]);
  const likeBadgeOpacity = useTransform(dragX, [24, 95], [0, 1]);
  const passBadgeOpacity = useTransform(dragX, [-95, -24], [1, 0]);
  const [failedImages, setFailedImages] = useState<Record<number, boolean>>({});
  const [failedBackdrops, setFailedBackdrops] = useState<Record<number, boolean>>({});

  // Interactive 4-stage workflow showcase state
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (localStorage.getItem("auth_token")) {
      navigate("/home", { replace: true });
    }
  }, [navigate]);

  const handleStartExploring = async () => {
    setError("");
    setLoading(true);

    try {
      const data = await coordinateGuestProvisioning();
      if (data && data.token) {
        if (data.recovery_code) {
          setRecoveryCode(data.recovery_code);
        }
        navigate("/home", { replace: true });
      } else {
        setError("Unable to initialize guest discovery. Please try again.");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message || "Failed to initialize guest account.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Network error initializing session. Check your internet connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleModalConfirm = () => {
    setShowModal(false);
    navigate("/home", { replace: true });
  };

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  const activeFilm = SAMPLE_DECK[deckIndex % SAMPLE_DECK.length];
  const nextFilm = SAMPLE_DECK[(deckIndex + 1) % SAMPLE_DECK.length];

  const handleSampleDecision = (action: "pass" | "like") => {
    dragX.set(0);
    if (action === "pass") {
      setSampleHistory((prev) => [...prev, deckIndex]);
      setMatchedSampleFilm(null);
      setDeckIndex((prev) => (prev + 1) % SAMPLE_DECK.length);
    } else {
      setSampleHistory((prev) => [...prev, deckIndex]);
      setMatchedSampleFilm(activeFilm);
    }
  };

  const handleUndoSampleSwipe = () => {
    dragX.set(0);
    if (matchedSampleFilm) {
      setMatchedSampleFilm(null);
      setSampleHistory((prev) => prev.slice(0, -1));
      return;
    }
    if (sampleHistory.length === 0) return;
    const prevIndex = sampleHistory[sampleHistory.length - 1];
    setSampleHistory((prev) => prev.slice(0, -1));
    setDeckIndex(prevIndex);
  };

  const handleSampleDragEnd = (_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
    if (matchedSampleFilm) return;
    if (info.offset.x > 75 || info.velocity.x > 380) {
      handleSampleDecision("like");
    } else if (info.offset.x < -75 || info.velocity.x < -380) {
      handleSampleDecision("pass");
    }
  };

  const handleResetSampleDeck = () => {
    setMatchedSampleFilm(null);
    setDeckIndex((prev) => (prev + 1) % SAMPLE_DECK.length);
  };

  const markImageFailed = (id: number) => {
    setFailedImages((prev) => ({ ...prev, [id]: true }));
  };

  const markBackdropFailed = (id: number) => {
    setFailedBackdrops((prev) => ({ ...prev, [id]: true }));
  };

  return (
    <>
      <div
        data-landing="true"
        className="relative bg-background text-foreground font-sans antialiased min-h-screen min-h-[100dvh] flex flex-col justify-between overflow-x-clip transition-colors duration-200"
      >
        {/* Subtle diffused ambient poster atmosphere in the top viewport */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-[760px] overflow-hidden select-none"
        >
          {!failedBackdrops[activeFilm.id] && (
            <img
              src={activeFilm.backdropUrl}
              alt=""
              onError={() => markBackdropFailed(activeFilm.id)}
              className="w-full h-full object-cover object-top scale-105 opacity-[0.16] dark:opacity-[0.22] blur-3xl transition-opacity duration-500"
            />
          )}
          <div className="absolute inset-0 bg-gradient-to-b from-background/50 via-background/85 to-background" />
          <div className="absolute inset-0 bg-gradient-to-r from-background via-background/60 to-transparent" />
        </div>

        {/* ── Top Bar ── */}
        <header className="relative z-10 flex items-center justify-between w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 sm:h-18">
          <a
            href="#top"
            onClick={(e) => {
              e.preventDefault();
              window.scrollTo({ top: 0, behavior: "smooth" });
            }}
            className="flex items-center gap-2.5 group focus:outline-none focus-visible:ring-2 focus-visible:ring-focus rounded-lg py-1"
          >
            <AnimatedFlickLogo
              variant="mark"
              decorative
              className="size-8 shrink-0 rounded-lg ring-1 ring-border shadow-2xs transition-transform duration-150 group-hover:scale-105"
            />
            <span className="font-display text-lg font-bold tracking-tight text-foreground">
              Flick
            </span>
          </a>

          <nav aria-label="Landing navigation" className="flex items-center gap-1 sm:gap-2">
            <button
              type="button"
              onClick={() => scrollToSection("screening-flow")}
              className="min-h-11 sm:min-h-9 inline-flex items-center text-xs sm:text-[13px] font-medium text-foreground-secondary hover:text-foreground transition-colors px-2.5 sm:px-3 rounded-lg cursor-pointer whitespace-nowrap"
            >
              How it works
            </button>

            <button
              type="button"
              onClick={() => navigate("/register")}
              className="hidden sm:inline-flex min-h-9 items-center text-[13px] font-medium text-foreground-secondary hover:text-foreground transition-colors px-3 rounded-lg cursor-pointer whitespace-nowrap"
            >
              Sign Up
            </button>

            <button
              type="button"
              onClick={() => navigate("/login")}
              className="min-h-11 sm:min-h-9 inline-flex items-center text-xs sm:text-[13px] font-semibold text-foreground hover:text-primary transition-colors px-3.5 rounded-full border border-border bg-surface/70 hover:bg-surface-secondary active:scale-[0.99] cursor-pointer whitespace-nowrap"
            >
              Sign In
            </button>

            <button
              type="button"
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              className="size-11 sm:size-9 rounded-full border border-border bg-surface/70 flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary active:scale-[0.99] transition-colors cursor-pointer shrink-0"
            >
              <span className="material-symbols-outlined text-[18px]">
                {theme === "dark" ? "light_mode" : "dark_mode"}
              </span>
            </button>
          </nav>
        </header>

        {/* ── Hero Section ── */}
        <main
          id="top"
          className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-4 pb-10 sm:pt-10 sm:pb-16 lg:min-h-[calc(100svh-4.5rem)] flex items-center"
        >
          <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 sm:gap-10 lg:gap-12 items-center">
            {/* Left Column: Direct Headline, Product Value, Clear Actions */}
            <div className="lg:col-span-6 flex flex-col items-start text-left">
              <h1 className="font-display text-[2rem] sm:text-5xl lg:text-[3.35rem] font-extrabold leading-[1.08] tracking-[-0.03em] text-foreground max-w-xl">
                Find the movie you both want to watch.
              </h1>

              <p className="mt-3 sm:mt-5 text-foreground-secondary text-sm sm:text-lg max-w-lg leading-relaxed">
                Open a Screening Room, send the invite code, and swipe through the same film deck on your own screens. Flick reveals only the titles you both choose.
              </p>

              {/* Error Banner if Provisioning Failed */}
              {error && (
                <div
                  role="alert"
                  className="mt-4 w-full max-w-md p-3.5 bg-error/10 border border-error/25 rounded-xl flex items-start gap-2.5 text-left"
                >
                  <span className="material-symbols-outlined text-error text-[18px] shrink-0 mt-0.5">
                    error
                  </span>
                  <p className="text-xs text-error font-medium leading-relaxed">{error}</p>
                </div>
              )}

              {/* Primary & Secondary Action Pair */}
              <div className="mt-5 sm:mt-7 w-full sm:w-auto flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3">
                <button
                  type="button"
                  onClick={handleStartExploring}
                  disabled={loading}
                  className="min-h-11 h-11 sm:h-12 px-7 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-all duration-150 active:scale-[0.99] flex items-center justify-center gap-2 shadow-sm cursor-pointer disabled:opacity-60 whitespace-nowrap"
                >
                  {loading ? (
                    <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>Start a Movie Night</span>
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </>
                  )}
                </button>

                <button
                  type="button"
                  onClick={() => navigate("/login")}
                  disabled={loading}
                  className="min-h-11 h-11 sm:h-12 px-6 rounded-full bg-surface hover:bg-surface-secondary border border-border text-foreground font-semibold text-sm transition-colors duration-150 active:scale-[0.99] flex items-center justify-center cursor-pointer whitespace-nowrap"
                >
                  Sign In
                </button>
              </div>

              {/* Clean inline access reassurance (no bordered pill, no clutter) */}
              <div className="mt-3 sm:mt-4 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs text-foreground-secondary">
                <span>No email needed to start.</span>
                <span aria-hidden="true" className="text-foreground-secondary/50">·</span>
                <button
                  type="button"
                  onClick={() => navigate("/recover")}
                  className="font-medium text-foreground hover:text-primary underline underline-offset-4 transition-colors cursor-pointer py-0.5"
                  title="Restore a guest session with your 16-character recovery key"
                >
                  Restore key
                </button>
                <span aria-hidden="true" className="sm:hidden text-foreground-secondary/50">·</span>
                <button
                  type="button"
                  onClick={() => navigate("/register")}
                  className="sm:hidden font-medium text-foreground hover:text-primary underline underline-offset-4 transition-colors cursor-pointer py-0.5"
                >
                  Sign Up
                </button>
              </div>
            </div>

            {/* Right Column: Live-UI Swipe Deck Demonstration (No outer box wrapper) */}
            <div className="lg:col-span-6 flex flex-col items-center">
              <div className="w-full max-w-[300px] sm:max-w-[330px]">
                {/* Card Stack Wrapper (isolated height so background card never bleeds onto controls) */}
                <div className="relative w-full aspect-[4/5]">
                  {/* Stacked next film card peeking beneath */}
                  {!matchedSampleFilm && (
                    <div
                      aria-hidden="true"
                      className="absolute inset-0 translate-x-3 translate-y-2 rotate-[2.5deg] scale-[0.96] rounded-2xl overflow-hidden border border-white/10 bg-zinc-900 opacity-55 pointer-events-none"
                    >
                      <PosterArtwork
                        film={nextFilm}
                        imgFailed={Boolean(failedImages[nextFilm.id])}
                        onImgError={() => markImageFailed(nextFilm.id)}
                      />
                      <div className="absolute inset-0 bg-black/55" />
                    </div>
                  )}

                  {/* Active Interactive Sample Deck Card or Mutual Match View */}
                  <motion.div
                    aria-label="Sample screening card preview"
                    drag={matchedSampleFilm ? false : "x"}
                    dragConstraints={{ left: 0, right: 0 }}
                    dragElastic={0.45}
                    onDragEnd={handleSampleDragEnd}
                    style={
                      matchedSampleFilm || shouldReduceMotion
                        ? undefined
                        : { x: dragX, rotate: cardRotate }
                    }
                    className={`relative z-10 w-full h-full rounded-2xl overflow-hidden border border-white/15 bg-zinc-950 shadow-2xl ${
                      matchedSampleFilm ? "" : "touch-pan-y cursor-grab active:cursor-grabbing select-none"
                    }`}
                  >
                    {matchedSampleFilm ? (
                      <div className="relative w-full h-full flex flex-col justify-between p-4 sm:p-5 text-white">
                        {!failedBackdrops[matchedSampleFilm.id] && (
                          <img
                            src={matchedSampleFilm.backdropUrl}
                            alt=""
                            onError={() => markBackdropFailed(matchedSampleFilm.id)}
                            className="absolute inset-0 w-full h-full object-cover opacity-35"
                          />
                        )}
                        <div className="absolute inset-0 bg-gradient-to-b from-black/75 via-black/70 to-black/95" />

                        <div className="relative z-10 flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300 bg-emerald-500/20 border border-emerald-400/35 px-2.5 py-1 rounded-full">
                            <span
                              className="material-symbols-outlined text-[14px]"
                              style={{ fontVariationSettings: "'FILL' 1" }}
                            >
                              verified
                            </span>
                            Mutual Match Example
                          </span>
                          <button
                            type="button"
                            onClick={handleResetSampleDeck}
                            className="text-xs font-medium text-white/80 hover:text-white underline underline-offset-4 cursor-pointer"
                          >
                            Next film
                          </button>
                        </div>

                        <div className="relative z-10 flex items-center gap-3 sm:gap-3.5 my-auto py-2.5 sm:py-3">
                          <div className="w-20 sm:w-24 aspect-[2/3] rounded-lg overflow-hidden border border-white/20 shrink-0 shadow-lg">
                            <PosterArtwork
                              film={matchedSampleFilm}
                              imgFailed={Boolean(failedImages[matchedSampleFilm.id])}
                              onImgError={() => markImageFailed(matchedSampleFilm.id)}
                            />
                          </div>
                          <div className="min-w-0">
                            <h3 className="font-display text-xl font-bold text-white leading-tight">
                              {matchedSampleFilm.title}
                            </h3>
                            <p className="text-xs text-white/75 mt-1">
                              {matchedSampleFilm.year} · ★ {matchedSampleFilm.rating}
                            </p>
                            <p className="text-xs text-white/70 mt-2 leading-relaxed">
                              Both viewers recommended this film. Unlocked in shared matches with watchlist & provider info.
                            </p>
                          </div>
                        </div>

                        <div className="relative z-10 pt-3 border-t border-white/15 flex items-center justify-between gap-3">
                          <span className="text-xs text-white/85">
                            Sample interaction preview
                          </span>
                          <button
                            type="button"
                            onClick={handleResetSampleDeck}
                            className="px-3.5 py-1.5 rounded-full bg-white text-zinc-950 text-xs font-semibold hover:bg-white/90 transition-colors cursor-pointer"
                          >
                            Try another card
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <PosterArtwork
                          film={activeFilm}
                          imgFailed={Boolean(failedImages[activeFilm.id])}
                          onImgError={() => markImageFailed(activeFilm.id)}
                        />
                        {/* Top subtle vignette & heavy bottom scrim so poster footer text never clashes */}
                        <div className="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-black/55 to-transparent pointer-events-none" />
                        <div className="absolute inset-x-0 bottom-0 h-[56%] bg-gradient-to-t from-[#090A0D] via-[#090A0D]/92 via-[42%] to-transparent pointer-events-none" />

                        {!shouldReduceMotion && (
                          <>
                            <motion.span
                              style={{ opacity: likeBadgeOpacity }}
                              className="pointer-events-none absolute top-14 left-4 z-20 px-3 py-1 rounded-lg border-2 border-emerald-400 bg-emerald-950/75 text-emerald-300 font-bold text-xs uppercase tracking-widest -rotate-12"
                            >
                              Recommend
                            </motion.span>
                            <motion.span
                              style={{ opacity: passBadgeOpacity }}
                              className="pointer-events-none absolute top-14 right-4 z-20 px-3 py-1 rounded-lg border-2 border-rose-400 bg-rose-950/75 text-rose-300 font-bold text-xs uppercase tracking-widest rotate-12"
                            >
                              Pass
                            </motion.span>
                          </>
                        )}

                        {/* Top Metadata Row */}
                        <div className="absolute top-3.5 inset-x-3.5 flex items-center justify-between gap-2">
                          <span className="text-[11px] font-medium text-white/90 bg-black/60 backdrop-blur-sm px-2.5 py-1 rounded-full border border-white/15">
                            Sample deck · {deckIndex + 1} of {SAMPLE_DECK.length}
                          </span>
                          <span className="inline-flex items-center gap-1 text-xs font-semibold text-amber-300 bg-black/65 backdrop-blur-sm px-2.5 py-1 rounded-full border border-white/15">
                            <span
                              className="material-symbols-outlined text-[13px]"
                              style={{ fontVariationSettings: "'FILL' 1" }}
                            >
                              star
                            </span>
                            {activeFilm.rating}
                          </span>
                        </div>

                        {/* Bottom Film Title & Metadata (Matches SessionPage card layout) */}
                        <div className="absolute bottom-0 inset-x-0 p-4 sm:p-5 text-white">
                          <div className="flex items-center gap-2 text-xs text-white/80 mb-1">
                            <span>{activeFilm.year}</span>
                            <span aria-hidden="true">·</span>
                            <span className="truncate">{activeFilm.genres.join(" · ")}</span>
                          </div>
                          <h2 className="font-display text-xl sm:text-2xl font-bold text-white leading-tight">
                            {activeFilm.title}
                          </h2>
                          <p className="text-xs text-white/80 line-clamp-2 mt-1.5 leading-relaxed">
                            {activeFilm.synopsis}
                          </p>
                        </div>
                      </>
                    )}
                  </motion.div>
                </div>

                {/* Real Swipe Controls below deck (Pass, Recommend, Undo) */}
                <div className="mt-4 flex items-center justify-center gap-5">
                  <button
                    type="button"
                    onClick={() => handleSampleDecision("pass")}
                    aria-label="Preview pass film"
                    title="Pass"
                    className="size-12 rounded-full border border-border bg-surface text-foreground-secondary hover:text-rose-500 hover:border-rose-500/60 shadow-xs transition-all active:scale-95 flex items-center justify-center cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[22px]">close</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleSampleDecision("like")}
                    aria-label="Preview recommend film"
                    title="Recommend"
                    className="size-14 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground shadow-md transition-all active:scale-95 flex items-center justify-center cursor-pointer"
                  >
                    <span
                      className="material-symbols-outlined text-[26px]"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      favorite
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={handleUndoSampleSwipe}
                    disabled={sampleHistory.length === 0 && !matchedSampleFilm}
                    aria-label="Preview undo last swipe"
                    title="Undo"
                    className="size-12 rounded-full border border-border bg-surface text-foreground-secondary hover:text-primary hover:border-primary/60 shadow-xs transition-all active:scale-95 flex items-center justify-center cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100"
                  >
                    <span className="material-symbols-outlined text-[21px]">
                      undo
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* ── Section 2: Interactive 4-Step Product Walkthrough (Asymmetric Split) ── */}
        <section
          id="screening-flow"
          className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24 border-t border-border/70"
        >
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
            {/* Left Column: Heading & Unboxed Hairline-Divided Interactive Steps */}
            <div className="lg:col-span-5">
              <h2 className="font-display text-2xl sm:text-3xl font-bold text-foreground tracking-tight">
                How a Screening Room works
              </h2>
              <p className="mt-3 text-sm sm:text-base text-foreground-secondary leading-relaxed">
                Select any step to see the actual flow from room setup to mutual match.
              </p>

              <div className="mt-8 border-t border-border">
                {WORKFLOW_STEPS.map((step, idx) => {
                  const isSelected = activeStep === idx;
                  return (
                    <button
                      key={step.number}
                      type="button"
                      onClick={() => setActiveStep(idx)}
                      aria-pressed={isSelected}
                      className={`w-full text-left py-4 sm:py-5 border-b border-border transition-all cursor-pointer flex items-start gap-4 group ${
                        isSelected
                          ? "border-l-2 border-l-primary pl-3.5 text-foreground"
                          : "pl-1 text-foreground-secondary hover:text-foreground"
                      }`}
                    >
                      <span
                        className={`text-xs font-bold tabular-nums pt-1 transition-colors ${
                          isSelected ? "text-primary" : "text-foreground-secondary/70 group-hover:text-foreground"
                        }`}
                      >
                        {step.number}
                      </span>
                      <div className="min-w-0 flex-1">
                        <h3 className="font-display text-base sm:text-lg font-bold leading-snug">
                          {step.title}
                        </h3>
                        <p
                          className={`mt-1.5 text-sm leading-relaxed transition-colors ${
                            isSelected ? "text-foreground-secondary" : "text-foreground-secondary/80"
                          }`}
                        >
                          {step.summary}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Right Column: Dynamic Authentic Product Screen Representation */}
            <div className="lg:col-span-7">
              <div className="relative rounded-2xl border border-border bg-surface overflow-hidden shadow-lg">
                {/* Ambient Cinema Header Strip inside Preview */}
                <div className="px-5 py-3.5 border-b border-border bg-surface-secondary/50 flex items-center justify-between text-xs">
                  <span className="font-semibold text-foreground">
                    {WORKFLOW_STEPS[activeStep].number} · {WORKFLOW_STEPS[activeStep].title}
                  </span>
                  <span className="text-foreground-secondary">Example screening UI</span>
                </div>

                {/* Stage 1: Room Configuration (Matches CreateSessionPage) */}
                {activeStep === 0 && (
                  <div className="p-6 sm:p-8 space-y-6">
                    <div>
                      <p className="text-xs font-semibold text-foreground-secondary mb-3">
                        Cinema tradition
                      </p>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                        {[
                          { label: "Hollywood & Global", active: true },
                          { label: "Indian Cinema", active: false },
                          { label: "World & Festivals", active: false },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className={`rounded-xl px-3.5 py-3 border text-xs font-semibold ${
                              item.active
                                ? "border-primary bg-primary/10 text-foreground"
                                : "border-border bg-surface-secondary/40 text-foreground-secondary"
                            }`}
                          >
                            {item.label}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="text-xs font-semibold text-foreground-secondary mb-3">
                        Genres for tonight
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {[
                          { name: "Thriller", selected: true },
                          { name: "Science Fiction", selected: true },
                          { name: "Drama", selected: false },
                          { name: "Comedy", selected: false },
                          { name: "Mystery", selected: true },
                          { name: "Crime", selected: false },
                        ].map((g) => (
                          <span
                            key={g.name}
                            className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
                              g.selected
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-background text-foreground-secondary"
                            }`}
                          >
                            {g.name}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="pt-4 border-t border-border/70 flex items-center justify-between text-xs text-foreground-secondary">
                      <span>Shared deck generated from TMDB catalogue</span>
                      <span className="font-semibold text-primary">Create Room →</span>
                    </div>
                  </div>
                )}

                {/* Stage 2: Partner Join via Code or Link */}
                {activeStep === 1 && (
                  <div className="p-6 sm:p-8 space-y-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 items-center">
                      <div className="space-y-4">
                        <div>
                          <p className="text-xs font-semibold text-foreground-secondary">
                            Example 6-letter room code
                          </p>
                          <div className="mt-2 inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-surface-secondary border border-border text-2xl font-display font-extrabold tracking-[0.22em] text-foreground">
                            CINE24
                          </div>
                        </div>
                        <p className="text-xs text-foreground-secondary leading-relaxed">
                          Your partner enters the code on the Home screen or taps the shared link to enter the room directly.
                        </p>
                        <div className="rounded-xl bg-background border border-border px-3.5 py-2.5 text-xs text-foreground-secondary flex items-center justify-between gap-2">
                          <span className="truncate">flick.app/join/CINE24</span>
                          <span className="font-semibold text-primary shrink-0">Copy link</span>
                        </div>
                      </div>

                      <div className="relative aspect-[4/3] rounded-xl overflow-hidden border border-border">
                        {!failedBackdrops[SAMPLE_DECK[1].id] ? (
                          <img
                            src={SAMPLE_DECK[1].backdropUrl}
                            alt={`${SAMPLE_DECK[1].title} film backdrop`}
                            onError={() => markBackdropFailed(SAMPLE_DECK[1].id)}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full bg-surface-secondary" />
                        )}
                        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/30 to-transparent" />
                        <div className="absolute bottom-3 left-3 right-3 text-white text-xs">
                          <p className="font-semibold">2 seats per Screening Room</p>
                          <p className="text-white/75 mt-0.5">Host & partner join with independent taste controls</p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Stage 3: Independent Swiping */}
                {activeStep === 2 && (
                  <div className="p-6 sm:p-8 space-y-5">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="rounded-xl border border-border bg-background p-4 space-y-3">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-foreground">Viewer A screen</span>
                          <span className="text-primary font-semibold">Recommended ♥</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-12 aspect-[2/3] rounded-md overflow-hidden border border-border shrink-0">
                            <PosterArtwork
                              film={SHAWSHANK_STILL}
                              imgFailed={Boolean(failedImages[SHAWSHANK_STILL.id])}
                              onImgError={() => markImageFailed(SHAWSHANK_STILL.id)}
                            />
                          </div>
                          <div>
                            <p className="font-display font-bold text-sm text-foreground">
                              {SHAWSHANK_STILL.title}
                            </p>
                            <p className="text-xs text-foreground-secondary">
                              {SHAWSHANK_STILL.year} · ★ {SHAWSHANK_STILL.rating}
                            </p>
                          </div>
                        </div>
                      </div>

                      <div className="rounded-xl border border-border bg-background p-4 space-y-3">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-semibold text-foreground">Viewer B screen</span>
                          <span className="text-foreground-secondary font-medium">Swiping independently</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-12 aspect-[2/3] rounded-md overflow-hidden border border-border shrink-0">
                            <PosterArtwork
                              film={SHAWSHANK_STILL}
                              imgFailed={Boolean(failedImages[SHAWSHANK_STILL.id])}
                              onImgError={() => markImageFailed(SHAWSHANK_STILL.id)}
                            />
                          </div>
                          <div>
                            <p className="font-display font-bold text-sm text-foreground">
                              {SHAWSHANK_STILL.title}
                            </p>
                            <p className="text-xs text-foreground-secondary">
                              Passes remain private to each person
                            </p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-foreground-secondary leading-relaxed">
                      Swipes are submitted independently on each device. You can also Super-Like a top pick or use Undo to recall your previous swipe.
                    </p>
                  </div>
                )}

                {/* Stage 4: Mutual Match Reveal */}
                {activeStep === 3 && (
                  <div className="relative p-6 sm:p-8 text-white overflow-hidden bg-zinc-950">
                    {!failedBackdrops[SAMPLE_DECK[0].id] && (
                      <img
                        src={SAMPLE_DECK[0].backdropUrl}
                        alt=""
                        onError={() => markBackdropFailed(SAMPLE_DECK[0].id)}
                        className="absolute inset-0 w-full h-full object-cover opacity-30"
                      />
                    )}
                    <div className="relative z-10 flex flex-col sm:flex-row gap-5 items-start sm:items-center">
                      <div className="w-28 aspect-[2/3] rounded-xl overflow-hidden border border-white/20 shrink-0 shadow-xl">
                        <PosterArtwork
                          film={SAMPLE_DECK[0]}
                          imgFailed={Boolean(failedImages[SAMPLE_DECK[0].id])}
                          onImgError={() => markImageFailed(SAMPLE_DECK[0].id)}
                        />
                      </div>
                      <div className="space-y-2.5">
                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-300">
                          <span
                            className="material-symbols-outlined text-[16px]"
                            style={{ fontVariationSettings: "'FILL' 1" }}
                          >
                            verified
                          </span>
                          Mutual Match
                        </span>
                        <h3 className="font-display text-2xl font-bold text-white">
                          {SAMPLE_DECK[0].title}
                        </h3>
                        <p className="text-xs text-white/80">
                          {SAMPLE_DECK[0].year} · ★ {SAMPLE_DECK[0].rating} · {SAMPLE_DECK[0].genres.join(" · ")}
                        </p>
                        <p className="text-xs text-white/75 leading-relaxed max-w-md">
                          {SAMPLE_DECK[0].synopsis}
                        </p>
                        <p className="text-xs text-white/85 pt-1">
                          Save to shared Watchlist or check regional watch options.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* ── Section 3: Account Flexibility (Tonal Ground Band, Zero Pricing Card Grid) ── */}
        <section className="relative z-10 w-full bg-surface/55 border-y border-border/70">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20 grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-start">
            <div className="lg:col-span-5">
              <h2 className="font-display text-2xl sm:text-3xl font-bold text-foreground tracking-tight">
                Start right away, or save across devices
              </h2>
              <p className="mt-3 text-sm sm:text-base text-foreground-secondary leading-relaxed">
                Guest sessions unlock every Screening Room feature without signup. Convert to an email account only when you want permanent multi-device sync.
              </p>
            </div>

            <div className="lg:col-span-7 divide-y divide-border">
              <div className="pb-7 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
                <div className="max-w-md">
                  <h3 className="font-display text-lg font-bold text-foreground">
                    Instant guest access
                  </h3>
                  <p className="mt-1.5 text-sm text-foreground-secondary leading-relaxed">
                    Launch a room in one tap and receive a 16-character recovery key to bring your history to another browser anytime.
                  </p>
                </div>
                <div className="flex flex-wrap sm:flex-col items-start sm:items-end gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleStartExploring}
                    disabled={loading}
                    className="text-sm font-semibold text-primary hover:underline inline-flex items-center gap-1 cursor-pointer whitespace-nowrap"
                  >
                    <span>Start a Movie Night</span>
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate("/recover")}
                    className="text-xs font-medium text-foreground-secondary hover:text-foreground underline underline-offset-4 cursor-pointer whitespace-nowrap"
                  >
                    Restore with recovery key
                  </button>
                </div>
              </div>

              <div className="pt-7 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
                <div className="max-w-md">
                  <h3 className="font-display text-lg font-bold text-foreground">
                    Permanent email account
                  </h3>
                  <p className="mt-1.5 text-sm text-foreground-secondary leading-relaxed">
                    Keep your watchlist, taste profile, and past matches available from any phone or laptop with standard sign-in.
                  </p>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <button
                    type="button"
                    onClick={() => navigate("/register")}
                    className="text-sm font-semibold text-foreground hover:text-primary underline underline-offset-4 cursor-pointer whitespace-nowrap"
                  >
                    Sign Up
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate("/login")}
                    className="text-sm font-semibold text-foreground hover:text-primary underline underline-offset-4 cursor-pointer whitespace-nowrap"
                  >
                    Sign In
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ── Section 4: Questions (Open Hairline List, Asymmetric Layout) ── */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-20">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-14 items-start">
            <div className="lg:col-span-4">
              <h2 className="font-display text-2xl sm:text-3xl font-bold text-foreground tracking-tight">
                Common questions
              </h2>
            </div>

            <div className="lg:col-span-8 border-t border-border">
              {FAQ_ITEMS.map((faq, index) => {
                const isOpen = activeFaq === index;
                return (
                  <div key={faq.q} className="border-b border-border">
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      onClick={() => setActiveFaq(isOpen ? null : index)}
                      className="w-full py-5 text-left flex items-center justify-between gap-4 cursor-pointer group"
                    >
                      <span className="text-sm sm:text-base font-semibold text-foreground group-hover:text-primary transition-colors">
                        {faq.q}
                      </span>
                      <span
                        className="material-symbols-outlined text-[20px] text-foreground-secondary shrink-0 transition-transform duration-200"
                        style={{ transform: isOpen ? "rotate(180deg)" : "rotate(0deg)" }}
                      >
                        keyboard_arrow_down
                      </span>
                    </button>
                    {isOpen && (
                      <div className="pb-5 pr-8 text-sm text-foreground-secondary leading-relaxed">
                        {faq.a}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── Section 5: Unboxed Open Closing CTA + Footer ── */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 pt-12 pb-16 border-t border-border/70">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8">
            <div className="max-w-lg">
              <h2 className="font-display text-2xl sm:text-4xl font-bold text-foreground tracking-tight">
                Ready to pick tonight&apos;s film?
              </h2>
              <p className="mt-3 text-sm sm:text-base text-foreground-secondary leading-relaxed">
                Open a Screening Room now as a guest, or create an account to save your list.
              </p>
            </div>

            <div className="flex flex-col sm:flex-row gap-3 shrink-0">
              <button
                type="button"
                onClick={handleStartExploring}
                disabled={loading}
                className="min-h-12 h-12 px-7 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-2 cursor-pointer shadow-xs disabled:opacity-60 whitespace-nowrap"
              >
                <span>Start a Movie Night</span>
                <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
              </button>
              <button
                type="button"
                onClick={() => navigate("/register")}
                className="min-h-12 h-12 px-6 rounded-full bg-surface hover:bg-surface-secondary border border-border text-foreground font-semibold text-sm transition-colors active:scale-[0.99] flex items-center justify-center cursor-pointer whitespace-nowrap"
              >
                Create Account
              </button>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 border-t border-border/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-foreground-secondary">
          <p>© Flick · Collaborative Movie Discovery</p>
          <div className="flex flex-wrap items-center gap-6">
            <button
              type="button"
              onClick={() => navigate("/discover")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Browse Movies
            </button>
            <button
              type="button"
              onClick={() => navigate("/terms")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Terms
            </button>
            <button
              type="button"
              onClick={() => navigate("/privacy")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Privacy
            </button>
            <a
              href="mailto:discoverflick@gmail.com"
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Contact
            </a>
          </div>
        </footer>
      </div>

      {/* Recovery Code Presentation Modal */}
      {recoveryCode && (
        <RecoveryCodeModal
          isOpen={showModal}
          recoveryCode={recoveryCode}
          onConfirm={handleModalConfirm}
        />
      )}
    </>
  );
}
