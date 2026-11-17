import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

/* ============================
   TYPES
============================ */

type Genre = {
  id: number;
  name: string;
};

type Industry = "bollywood" | "hollywood" | "mixed";

type LanguageOption = {
  code: string;
  name: string;
};

/* ============================
   LANGUAGE OPTIONS
============================ */

const LANGUAGE_OPTIONS: Record<Industry, LanguageOption[]> = {
  bollywood: [
    { code: "hi", name: "Hindi" },
    { code: "ta", name: "Tamil" },
    { code: "te", name: "Telugu" },
    { code: "bn", name: "Bengali" },
    { code: "mr", name: "Marathi" },
    { code: "gu", name: "Gujarati" },
    { code: "kn", name: "Kannada" },
    { code: "ml", name: "Malayalam" },
    { code: "pa", name: "Punjabi" },
  ],
  hollywood: [
    { code: "en", name: "English" },
  ],
  mixed: [
    { code: "hi", name: "Hindi" },
    { code: "ta", name: "Tamil" },
    { code: "te", name: "Telugu" },
    { code: "en", name: "English" },
    { code: "mr", name: "Marathi" },
    { code: "gu", name: "Gujarati" },
    { code: "es", name: "Spanish" },
    { code: "fr", name: "French" },
    { code: "ko", name: "Korean" },
    { code: "ja", name: "Japanese" },
  ],
};

/* ============================
   GENRE ICON HELPER
============================ */

function getGenreIcon(name: string): { type: "material" | "emoji"; value: string } {
  switch (name.toLowerCase()) {
    case "horror":      return { type: "material", value: "skull" };
    case "romance":     return { type: "material", value: "favorite" };
    case "action":      return { type: "material", value: "local_fire_department" };
    case "comedy":      return { type: "material", value: "theater_comedy" };
    case "drama":       return { type: "material", value: "masks" };
    case "sci-fi":
    case "science fiction": return { type: "material", value: "rocket_launch" };
    case "fantasy":     return { type: "material", value: "auto_awesome" };
    case "thriller":    return { type: "material", value: "warning" };
    case "family":      return { type: "material", value: "family_restroom" };
    case "documentary": return { type: "material", value: "movie" };
    case "animation":   return { type: "material", value: "animation" };
    default:            return { type: "material", value: "theaters" };
  }
}

/* ============================
   INDUSTRY OPTIONS
============================ */

const INDUSTRY_OPTIONS: {
  value: Industry;
  label: string;
  description: string;
  icon: string;
}[] = [
  {
    value: "hollywood",
    label: "Hollywood & Global English",
    description: "Features and studio releases in English",
    icon: "movie",
  },
  {
    value: "bollywood",
    label: "Indian Cinema",
    description: "Bollywood, South Indian, and regional languages",
    icon: "theater_comedy",
  },
  {
    value: "mixed",
    label: "World Cinema & Festivals",
    description: "Curated international titles across languages",
    icon: "public",
  },
];

const STREAMING_SERVICES = [
  { id: "8", name: "Netflix" },
  { id: "119", name: "Prime Video" },
  { id: "122", name: "Disney+ Hotstar" },
  { id: "350", name: "Apple TV+" },
  { id: "220", name: "JioCinema" },
  { id: "237", name: "SonyLIV" },
  { id: "232", name: "Zee5" },
];

/* ============================
   COMPONENT
============================ */

export default function CreateSessionPage() {
  const navigate = useNavigate();

  const [step, setStep] = useState<"industry" | "language" | "genre" | "created">("industry");
  const [industry, setIndustry] = useState<Industry | null>(null);
  const [selectedLanguages, setSelectedLanguages] = useState<string[]>([]);
  const [genres, setGenres] = useState<Genre[]>([]);
  const [selectedGenreIds, setSelectedGenreIds] = useState<number[]>([]);
  const [selectedProviders, setSelectedProviders] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessionCode, setSessionCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  /* ----------------------------
     FETCH GENRES WHEN INDUSTRY CHANGES
  ---------------------------- */
  const fetchGenres = useCallback(async (ind: Industry) => {
    setIsLoading(true);
    setError("");
    try {
      const data = await apiRequest(`/api/genres/?industry=${ind}`);
      const list = data.genres || [];
      setGenres(list);

      // Default to empty selection so user picks intended genre(s)
      setSelectedGenreIds([]);
    } catch {
      setError("Failed to load genres. Please retry.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (industry) {
      fetchGenres(industry);
      // Default to empty selection so user intentionally picks their preferred language(s)
      setSelectedLanguages([]);
    }
  }, [industry, fetchGenres]);

  /* ----------------------------
     CREATE SESSION ON BACKEND
  ---------------------------- */
  async function createSession() {
    if (!industry) { setError("Please select an industry"); return; }
    if (selectedLanguages.length === 0) { setError("Please select at least one language"); return; }
    if (selectedGenreIds.length === 0) { setError("Please select at least one genre"); return; }

    setIsLoading(true);
    setError("");
    try {
      const sessionData = await apiRequest("/api/sessions/create/", {
        method: "POST",
        body: JSON.stringify({}),
      });

      await apiRequest("/api/sessions/genre/", {
        method: "POST",
        body: JSON.stringify({
          genre_ids: selectedGenreIds,
          genre_id: selectedGenreIds[0],
          session_id: sessionData.id,
          industry: industry,
          languages: selectedLanguages,
          streaming_provider_ids: selectedProviders.map((p) => Number(p)),
        }),
      });

      setSessionId(sessionData.id);
      setSessionCode(sessionData.code);
      setStep("created");

      trackEvent("session_created", {
        industry,
        genres_count: selectedGenreIds.length,
        session_id: sessionData.id,
      });
    } catch {
      setError("Failed to create session. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  /* ----------------------------
     HANDLERS
  ---------------------------- */
  const toggleGenre = (id: number) => {
    setSelectedGenreIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleLanguage = (code: string) => {
    setSelectedLanguages((prev) =>
      prev.includes(code) ? prev.filter((x) => x !== code) : [...prev, code]
    );
  };

  const handleBack = () => {
    setError("");
    if (step === "language") setStep("industry");
    if (step === "genre") setStep("language");
  };

  const handleClear = () => {
    if (step === "genre") setSelectedGenreIds([]);
    if (step === "language") setSelectedLanguages([]);
  };

  const handleLanguageContinue = () => {
    if (selectedLanguages.length === 0) {
      setError("Please select at least one language");
      return;
    }
    setError("");
    setStep("genre");
  };

  const inviteLink = sessionCode
    ? `${window.location.origin}/join/${sessionCode}`
    : "";

  const handleCopyCode = async () => {
    if (!sessionCode) return;
    try {
      await navigator.clipboard.writeText(sessionCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleCopyLink = async () => {
    if (!inviteLink) return;
    try {
      await navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleShare = async () => {
    if (!sessionCode) return;
    const shareData = {
      title: "Join my film discovery session on Flick",
      text: `Join my film session with code ${sessionCode}!`,
      url: inviteLink,
    };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch {
        handleCopyLink();
      }
    } else {
      handleCopyLink();
    }
  };

  const progress =
    step === "industry" ? 33 : step === "language" ? 66 : 100;

  const STEP_TITLES: Record<typeof step, string> = {
    industry: "Industry Curation",
    language: "Language Distribution",
    genre: "Genre Selection",
    created: "Session Ready",
  };

  /* ============================
     RENDER
  ============================ */

  return (
    <div className="relative min-h-screen bg-background text-foreground font-sans flex flex-col antialiased transition-colors duration-200">

      {/* ── GLOBAL CINEMA HEADER ── */}
      <CinemaHeader
        current="sessions"
        title={STEP_TITLES[step]}
        onBack={step !== "industry" ? handleBack : () => navigate("/home")}
        rightAction={
          (step === "genre" || step === "language") ? (
            <button
              onClick={handleClear}
              className="text-primary hover:text-primary-hover text-xs font-semibold uppercase tracking-wider transition-colors px-2 py-1"
            >
              Clear
            </button>
          ) : undefined
        }
      />

      <div className="w-full max-w-xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-4 pb-44 md:pb-28">

        {/* ── DESKTOP STEP HEADING ── */}
        <div className="hidden md:flex items-center justify-between pb-3 mb-2 border-b border-border/40">
          <div>
            <h2 className="font-editorial text-2xl font-bold tracking-tight text-foreground">
              {STEP_TITLES[step]}
            </h2>
            <p className="text-xs text-foreground-secondary mt-0.5">
              {step === "industry" && "Step 1 of 3 · Choose your cinema catalogue scope"}
              {step === "language" && "Step 2 of 3 · Select preferred streaming languages"}
              {step === "genre" && "Step 3 of 3 · Choose genres for matching"}
              {step === "created" && "Session is configured and awaiting participants"}
            </p>
          </div>
          {(step === "genre" || step === "language") && (
            <button
              onClick={handleClear}
              className="text-primary hover:text-primary-hover text-xs font-semibold uppercase tracking-wider transition-colors px-3 py-1.5 rounded-lg border border-primary/30 hover:bg-primary/10"
            >
              Clear All
            </button>
          )}
        </div>

        {/* ── PROGRESS BAR (steps 2 & 3) ── */}
        {(step === "language" || step === "genre") && (
          <div className="flex flex-col gap-1.5 pt-1 pb-3">
            <div className="flex justify-between items-center text-xs text-foreground-secondary">
              <span>Step {step === "language" ? 2 : 3} of 3</span>
              <span className="font-mono">{progress}%</span>
            </div>
            <div className="rounded-full bg-surface-secondary overflow-hidden h-1.5 border border-border/50">
              <div
                className="h-full rounded-full bg-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* ── ERROR ── */}
        {error && (
          <div className="mb-3">
            <div className="p-3 bg-error/10 border border-error/20 rounded-xl">
              <p className="text-xs text-error text-center font-medium">{error}</p>
            </div>
          </div>
        )}

      {/* ══════════════════════════════════
          STEP 1 — INDUSTRY
      ══════════════════════════════════ */}
      {step === "industry" && (
        <main className="flex-1 overflow-y-auto pb-4">
          <div className="pt-2 pb-6 text-center">
            <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center mx-auto mb-4 shadow-xs">
              <span className="material-symbols-outlined text-primary text-[32px]">theaters</span>
            </div>
            <h1 className="font-editorial text-3xl font-normal leading-tight mb-1 text-foreground">
              What cinema tradition?
            </h1>
            <p className="text-foreground-secondary text-xs sm:text-sm">
              Select the catalogue scope for this matching session
            </p>
          </div>

          <div className="flex flex-col gap-3">
            {INDUSTRY_OPTIONS.map((opt) => {
              const isSelected = industry === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => { setIndustry(opt.value); setError(""); }}
                  className={`w-full flex items-center gap-4 p-4 rounded-xl border text-left transition-all ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-xs"
                      : "border-border bg-surface hover:border-primary/50"
                  }`}
                >
                  <div className={`flex size-12 shrink-0 items-center justify-center rounded-lg transition-colors ${
                    isSelected ? "bg-primary/20 text-primary" : "bg-surface-secondary text-foreground-secondary"
                  }`}>
                    <span className="material-symbols-outlined text-[24px]">{opt.icon}</span>
                  </div>

                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-semibold leading-tight mb-0.5 ${isSelected ? "text-foreground font-bold" : "text-foreground"}`}>
                      {opt.label}
                    </p>
                    <p className="text-xs text-foreground-secondary">{opt.description}</p>
                  </div>

                  <div className={`size-5 rounded-full border flex items-center justify-center shrink-0 transition-all ${
                    isSelected ? "border-primary bg-primary text-primary-foreground" : "border-border"
                  }`}>
                    {isSelected && (
                      <span className="material-symbols-outlined text-[14px]">check</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </main>
      )}

      {/* ══════════════════════════════════
          STEP 2 — LANGUAGE
      ══════════════════════════════════ */}
      {step === "language" && industry && (
        <div className="flex-1 overflow-y-auto pb-4">
          <div className="pt-2 pb-2">
            <h1 className="font-editorial text-3xl font-normal leading-tight text-foreground mb-1">
              Select Languages
            </h1>
            <p className="text-foreground-secondary text-xs sm:text-sm">
              Choose the languages you prefer to stream in
            </p>
          </div>

          {/* Select All toggle & count */}
          <div className="pt-2 pb-2 flex justify-between items-center text-xs">
            <span className="text-foreground-secondary">
              {selectedLanguages.length} of {LANGUAGE_OPTIONS[industry].length} selected
            </span>
            <button
              onClick={() => {
                const allSelected = LANGUAGE_OPTIONS[industry].every((lang) =>
                  selectedLanguages.includes(lang.code)
                );
                setSelectedLanguages(
                  allSelected ? [] : LANGUAGE_OPTIONS[industry].map((l) => l.code)
                );
              }}
              className="font-semibold text-primary uppercase tracking-wider hover:underline"
            >
              {LANGUAGE_OPTIONS[industry].every((lang) =>
                selectedLanguages.includes(lang.code)
              )
                ? "Deselect All"
                : "Select All"}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            {LANGUAGE_OPTIONS[industry].map((lang) => {
              const isSelected = selectedLanguages.includes(lang.code);
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => toggleLanguage(lang.code)}
                  className={`w-full flex items-center gap-3.5 rounded-xl border px-4 py-3 text-left transition-all ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-xs"
                      : "border-border bg-surface hover:border-primary/50"
                  }`}
                >
                  <span className={`size-7 rounded-md border text-[11px] font-bold flex items-center justify-center shrink-0 uppercase tracking-wider font-mono transition-colors ${
                    isSelected
                      ? "bg-primary/20 border-primary text-primary"
                      : "bg-surface-secondary border-border text-foreground-secondary"
                  }`}>
                    {lang.code}
                  </span>
                  <span
                    className={`text-sm flex-1 ${
                      isSelected ? "font-bold text-foreground" : "font-normal text-foreground-secondary"
                    }`}
                  >
                    {lang.name}
                  </span>
                  {isSelected && (
                    <span className="material-symbols-outlined text-primary text-[18px]">
                      check_circle
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════
          STEP 3 — GENRE
      ══════════════════════════════════ */}
      {step === "genre" && industry && (
        <div className="flex-1 overflow-y-auto pb-4">
          <div className="pt-2 pb-2">
            <h1 className="font-editorial text-3xl font-normal leading-tight text-foreground mb-1">
              Select Film Genres
            </h1>
            <p className="text-foreground-secondary text-xs sm:text-sm">
              Choose one or more — movies matching any category will appear in the deck
            </p>
          </div>

          {/* Select All */}
          <div className="pt-2 pb-2 flex justify-between items-center text-xs">
            <span className="text-foreground-secondary">
              {selectedGenreIds.length} of {genres.length} selected
            </span>
            <button
              onClick={() => {
                const allSelected = genres.every((g) => selectedGenreIds.includes(g.id));
                setSelectedGenreIds(allSelected ? [] : genres.map((g) => g.id));
              }}
              className="font-semibold text-primary uppercase tracking-wider hover:underline"
            >
              {genres.every((g) => selectedGenreIds.includes(g.id)) ? "Deselect All" : "Select All"}
            </button>
          </div>

          {isLoading ? (
            <div className="flex items-center justify-center py-16">
              <div className="size-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {genres.map((genre) => {
                const isSelected = selectedGenreIds.includes(genre.id);
                const icon = getGenreIcon(genre.name);
                return (
                  <button
                    key={genre.id}
                    type="button"
                    onClick={() => toggleGenre(genre.id)}
                    className={`flex h-12 w-full shrink-0 items-center justify-start gap-x-2.5 rounded-full px-3.5 transition-all text-left text-xs ${
                      isSelected
                        ? "bg-primary text-primary-foreground border border-primary font-semibold shadow-xs"
                        : "border border-border bg-surface text-foreground hover:border-primary/50"
                    }`}
                  >
                    {icon.type === "material" ? (
                      <span className="material-symbols-outlined text-[18px]">{icon.value}</span>
                    ) : (
                      <span className="text-base leading-none">{icon.value}</span>
                    )}
                    <span className="truncate">{genre.name}</span>
                  </button>
                );
              })}
            </div>
          )}

          {/* Optional Streaming Services */}
          <div className="pt-6 border-t border-border/60">
            <div className="flex items-center justify-between mb-2">
              <div>
                <span className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[15px] text-primary">live_tv</span>
                  Streaming Services (Optional)
                </span>
                <p className="text-[11px] text-foreground-secondary">
                  Only show movies available on platforms you both share
                </p>
              </div>
              {selectedProviders.length > 0 && (
                <button
                  type="button"
                  onClick={() => setSelectedProviders([])}
                  className="text-[11px] text-primary hover:underline font-medium"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2 pt-1">
              {STREAMING_SERVICES.map((provider) => {
                const isSelected = selectedProviders.includes(provider.id);
                return (
                  <button
                    key={provider.id}
                    type="button"
                    onClick={() => {
                      setSelectedProviders((prev) =>
                        prev.includes(provider.id)
                          ? prev.filter((p) => p !== provider.id)
                          : [...prev, provider.id]
                      );
                    }}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium transition-all border ${
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary font-semibold shadow-xs"
                        : "border-border bg-surface text-foreground hover:border-primary/50"
                    }`}
                  >
                    <span>{provider.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════
          STEP 4 — SESSION CREATED
      ══════════════════════════════════ */}
      {step === "created" && sessionId && sessionCode && (
        <main className="flex-1 overflow-y-auto pb-4 pt-2">
          <div className="text-center mb-6">
            <div className="size-16 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center mx-auto mb-3 text-primary">
              <span className="material-symbols-outlined text-[36px]">theaters</span>
            </div>
            <h1 className="font-editorial text-3xl font-normal text-foreground">Screening Ready</h1>
            <p className="text-xs text-foreground-secondary mt-1">
              Invite your partner using the code below
            </p>
          </div>

          {/* Code Card */}
          <div className="bg-surface border border-border rounded-2xl p-6 flex flex-col items-center text-center relative overflow-hidden mb-5 shadow-xs">
            <div className="h-1 w-full bg-primary/40 absolute top-0 left-0" />

            <p className="text-[11px] font-semibold text-foreground-secondary uppercase tracking-widest mb-3">
              Session Code
            </p>

            <button
              onClick={handleCopyCode}
              title="Click to copy code"
              className="text-4xl sm:text-5xl font-mono font-black tracking-[0.2em] text-foreground mb-4 bg-surface-secondary py-3 px-6 rounded-xl border border-border hover:border-primary/50 transition-colors"
            >
              {sessionCode}
            </button>

            <div className="flex gap-2.5 w-full">
              <button
                onClick={handleCopyCode}
                className="flex-1 h-11 bg-surface-secondary hover:bg-surface border border-border text-foreground font-semibold text-xs rounded-full flex items-center justify-center gap-1.5 transition-colors"
              >
                <span className="material-symbols-outlined text-[16px]">
                  {copied ? "check" : "content_copy"}
                </span>
                {copied ? "Copied!" : "Copy Code"}
              </button>
              <button
                onClick={handleShare}
                className="flex-1 h-11 bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-xs rounded-full flex items-center justify-center gap-1.5 transition-colors shadow-xs"
              >
                <span className="material-symbols-outlined text-[16px]">share</span>
                Share Link
              </button>
            </div>
          </div>

          {/* Invite link direct row */}
          <div className="mb-6">
            <p className="text-xs text-foreground-secondary text-center mb-2">Or send direct screening link:</p>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={inviteLink}
                className="flex-1 rounded-xl border border-border bg-surface px-3 py-2 text-xs text-foreground-secondary font-mono focus:outline-hidden"
              />
              <button
                type="button"
                onClick={handleCopyLink}
                className="rounded-xl border border-border bg-surface-secondary px-3.5 py-2 text-xs font-semibold hover:bg-surface text-foreground transition-colors"
              >
                {copied ? "✓" : "Copy"}
              </button>
            </div>
          </div>

          {/* Continue CTA */}
          <button
            onClick={() => navigate(`/session/${sessionId}`)}
            className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors flex items-center justify-center gap-2 shadow-xs"
          >
            <span>Enter Screening Deck</span>
            <span className="material-symbols-outlined text-[18px]">play_arrow</span>
          </button>
        </main>
      )}

      </div>

      {/* ══════════════════════════════════
          FIXED BOTTOM BUTTON (Steps 1-3)
      ══════════════════════════════════ */}
      {step !== "created" && (
        <div className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom,0px))] md:bottom-0 left-0 right-0 z-30 pointer-events-none">
          <div className="w-full max-w-xl mx-auto px-4 pb-4 pt-3 md:pb-6 bg-gradient-to-t from-background via-background/95 to-transparent pointer-events-auto">
            <button
              onClick={() => {
                if (step === "industry") {
                  if (!industry) { setError("Please select an industry to continue"); return; }
                  setError("");
                  setStep("language");
                }
                if (step === "language") handleLanguageContinue();
                if (step === "genre")    createSession();
              }}
              disabled={
                (step === "industry" && !industry) ||
                (step === "language" && selectedLanguages.length === 0) ||
                (step === "genre" && (selectedGenreIds.length === 0 || isLoading))
              }
              className={`flex w-full items-center justify-center rounded-full h-12 px-5 transition-colors text-sm font-semibold tracking-wide shadow-xs focus:outline-hidden ${
                (step === "industry" && !industry) ||
                (step === "language" && selectedLanguages.length === 0) ||
                (step === "genre" && (selectedGenreIds.length === 0 || isLoading))
                  ? "bg-surface-secondary text-foreground-secondary/50 border border-border cursor-not-allowed"
                  : "bg-primary hover:bg-primary-hover text-primary-foreground"
              }`}
            >
              {isLoading ? (
                <span className="flex items-center gap-2">
                  <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  Preparing Deck…
                </span>
              ) : (
                <span>
                  {step === "industry" && "Continue to Languages →"}
                  {step === "language" && (selectedLanguages.length > 0 ? `Continue to Genres · ${selectedLanguages.length} language${selectedLanguages.length > 1 ? "s" : ""} →` : "Select at least one language")}
                  {step === "genre"    && (selectedGenreIds.length > 0 ? `Create Session · ${selectedGenreIds.length} genre${selectedGenreIds.length > 1 ? "s" : ""}` : "Create Session")}
                </span>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ── GLOBAL BOTTOM NAV (Mobile) ── */}
      <BottomNav current="sessions" />
    </div>
  );
}
