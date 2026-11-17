import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { trackEvent } from "../lib/analytics";

/* ============================
   TYPES
============================ */

type QuestionOption = {
  value: string;
  label: string;
  icon: { type: "material" | "emoji"; value: string };
  subtitle?: string;
};

type Question = {
  id: string;
  title: string;
  subtitle: string;
  layout: "grid" | "list";
  multiSelect: boolean;
  options: QuestionOption[];
};

/* ============================
   QUESTIONNAIRE — 7 steps
   1. Tone       — what feeling do you want to leave with?
   2. Intensity  — how heavy do you want to go?
   3. Narrative  — what kind of story?
   4. Setting    — where does it take place?
   5. Themes     — what topics resonate?
   6. Era        — what time period?
   7. Quality    — minimum rating?
============================ */

const QUESTIONS: Question[] = [
  {
    id: "tone",
    title: "What feeling do you want to leave with?",
    subtitle: "This shapes the entire mood of your session",
    layout: "grid",
    multiSelect: true,
    options: [
      { value: "uplifted",  label: "Uplifted & Warm",    icon: { type: "material", value: "light_mode" }, subtitle: "Feel-good, hopeful, heartwarming" },
      { value: "thrilled",  label: "Thrilled & Pumped",  icon: { type: "material", value: "bolt" },       subtitle: "Adrenaline, action, spectacle" },
      { value: "moved",     label: "Moved & Reflective", icon: { type: "material", value: "water_drop" },  subtitle: "Emotional, poignant, meaningful" },
      { value: "unsettled", label: "Unsettled & Haunted",icon: { type: "material", value: "dark_mode" },   subtitle: "Dark, disturbing, intense" },
      { value: "amused",    label: "Laughing & Light",   icon: { type: "material", value: "theater_comedy" }, subtitle: "Comedy, fun, witty humour" },
      { value: "mindblown", label: "Mind-Blown",         icon: { type: "material", value: "psychology" },  subtitle: "Twists, puzzles, reality-bending" },
    ],
  },
  {
    id: "intensity",
    title: "How heavy do you want to go?",
    subtitle: "Be honest — nobody wants the wrong film at the wrong time",
    layout: "list",
    multiSelect: false,
    options: [
      { value: "light",  label: "Keep it light",         icon: { type: "material", value: "spa" },                   subtitle: "Easy watch, nothing too heavy or stressful" },
      { value: "medium", label: "Balanced — some depth", icon: { type: "material", value: "balance" },               subtitle: "Engaging but not exhausting" },
      { value: "heavy",  label: "Full commitment",       icon: { type: "material", value: "local_fire_department" }, subtitle: "Prepared to feel everything" },
      { value: "any",    label: "Doesn't matter",        icon: { type: "material", value: "casino" },                subtitle: "Surprise us" },
    ],
  },
  {
    id: "narrative",
    title: "What kind of story are you in the mood for?",
    subtitle: "Select all that apply",
    layout: "grid",
    multiSelect: true,
    options: [
      { value: "character", label: "Character-driven", icon: { type: "material", value: "person" },           subtitle: "Deep focus on one person's journey" },
      { value: "plot",      label: "Plot-driven",      icon: { type: "material", value: "timeline" },         subtitle: "Twists, stakes, constant momentum" },
      { value: "ensemble",  label: "Ensemble cast",    icon: { type: "material", value: "group" },            subtitle: "Multiple characters, interwoven stories" },
      { value: "world",     label: "World-building",   icon: { type: "material", value: "public" },           subtitle: "Immersive universe, mythology, lore" },
    ],
  },
  {
    id: "setting",
    title: "Where do you want to be taken?",
    subtitle: "Select all that apply",
    layout: "grid",
    multiSelect: true,
    options: [
      { value: "real_world",    label: "Real world",      icon: { type: "material", value: "apartment" },       subtitle: "Grounded, contemporary, recognisable" },
      { value: "historical",    label: "Historical",      icon: { type: "material", value: "account_balance" }, subtitle: "Past eras, period drama, biography" },
      { value: "fantasy_world", label: "Fantasy / Sci-Fi",icon: { type: "material", value: "rocket_launch" },   subtitle: "Otherworldly, futuristic, magical" },
      { value: "anywhere",      label: "Anywhere",        icon: { type: "material", value: "public" },          subtitle: "Setting doesn't matter to us" },
    ],
  },
  {
    id: "themes",
    title: "Which themes resonate right now?",
    subtitle: "Pick up to 3 — these guide the recommendation engine",
    layout: "grid",
    multiSelect: true,
    options: [
      { value: "love_relationships", label: "Love & Relationships", icon: { type: "material", value: "favorite" } },
      { value: "identity_growth",    label: "Identity & Growth",    icon: { type: "material", value: "self_improvement" } },
      { value: "power_corruption",   label: "Power & Corruption",   icon: { type: "material", value: "gavel" } },
      { value: "survival",           label: "Survival",             icon: { type: "material", value: "emergency" } },
      { value: "family_belonging",   label: "Family & Belonging",   icon: { type: "material", value: "family_restroom" } },
      { value: "justice_revenge",    label: "Justice & Revenge",    icon: { type: "material", value: "balance" } },
      { value: "mystery_truth",      label: "Mystery & Truth",      icon: { type: "material", value: "search" } },
      { value: "friendship",         label: "Friendship & Loyalty", icon: { type: "material", value: "handshake" } },
    ],
  },
  {
    id: "era",
    title: "What era do you prefer?",
    subtitle: "Select all that apply — or pick any",
    layout: "list",
    multiSelect: true,
    options: [
      { value: "before_1990", label: "Before 1990",                  icon: { type: "material", value: "history" },      subtitle: "Golden age, new wave, and pre-1990 cinema" },
      { value: "classic",     label: "Classic cinema (Before 2000)", icon: { type: "material", value: "theaters" },     subtitle: "Timeless films, golden & silver age" },
      { value: "2000s",       label: "2000s",                        icon: { type: "material", value: "album" },        subtitle: "Y2K era, peak blockbusters" },
      { value: "2010s",       label: "2010s",                        icon: { type: "material", value: "devices" },      subtitle: "Streaming era, franchise peak" },
      { value: "recent",      label: "Recent (2020+)",               icon: { type: "material", value: "new_releases" }, subtitle: "Latest releases" },
      { value: "any",         label: "Any era",                      icon: { type: "material", value: "movie" },        subtitle: "Doesn't matter when it was made" },
    ],
  },
  {
    id: "min_rating",
    title: "Minimum rating?",
    subtitle: "TMDB score — higher means fewer but better-rated films",
    layout: "list",
    multiSelect: true,
    options: [
      { value: "any", label: "Any",           icon: { type: "material", value: "casino" },       subtitle: "No filter — hidden gems welcome" },
      { value: "0+",  label: "0.0+",          icon: { type: "material", value: "sentiment_very_dissatisfied" }, subtitle: "Literally everything" },
      { value: "4+",  label: "4.0+",          icon: { type: "material", value: "sentiment_dissatisfied" },      subtitle: "Cuts out the unwatchable" },
      { value: "5+",  label: "5.0+",          icon: { type: "material", value: "sentiment_neutral" },           subtitle: "Decent — worth a watch" },
      { value: "6+",  label: "6.0+",          icon: { type: "material", value: "sentiment_satisfied" },         subtitle: "Generally well-received" },
      { value: "7+",  label: "7.0+",          icon: { type: "material", value: "sentiment_very_satisfied" },    subtitle: "Crowd-pleasing, critic-approved" },
      { value: "8+",  label: "8.0+",          icon: { type: "material", value: "star" },                        subtitle: "Top-tier films only" },
    ],
  },
];

/* ============================
   THEME → KEYWORD MAPPING
============================ */

const THEME_KEYWORDS: Record<string, string[]> = {
  love_relationships:  ["romance", "love", "relationship", "heartbreak", "marriage", "affair"],
  identity_growth:     ["coming of age", "self-discovery", "identity", "redemption", "transformation", "bildungsroman"],
  power_corruption:    ["political", "corruption", "power", "greed", "manipulation", "betrayal"],
  survival:            ["survival", "life or death", "wilderness", "escape", "catastrophe", "disaster"],
  family_belonging:    ["family", "belonging", "home", "parent", "sibling", "domestic"],
  justice_revenge:     ["revenge", "justice", "vengeance", "vigilante", "crime", "payback"],
  mystery_truth:       ["mystery", "secret", "conspiracy", "investigation", "truth", "revelation"],
  friendship:          ["friendship", "loyalty", "trust", "camaraderie", "brotherhood", "sisterhood"],
};

const SETTING_KEYWORDS: Record<string, string[]> = {
  real_world:     ["contemporary", "urban", "realistic", "modern day", "city life"],
  historical:     ["historical", "period", "biography", "based on true", "19th century", "medieval", "ancient"],
  fantasy_world:  ["fantasy", "sci-fi", "science fiction", "space", "magic", "futuristic", "alien", "post-apocalyptic"],
  anywhere:       [],
};

const TONE_TO_MOOD: Record<string, string> = {
  uplifted:   "happy",
  thrilled:   "exciting",
  moved:      "emotional",
  unsettled:  "intense",
  amused:     "happy",
  mindblown:  "intense",
};

const TONE_TO_VIBE: Record<string, string> = {
  uplifted:   "feel-good",
  thrilled:   "escapist",
  moved:      "realistic",
  unsettled:  "mind-bending",
  amused:     "feel-good",
  mindblown:  "mind-bending",
};

/* ============================
   ICON HELPER
============================ */

function OptionIcon({ icon, selected }: { icon: QuestionOption["icon"]; selected: boolean }) {
  const colorClass = selected ? "text-primary" : "text-foreground-secondary";
  if (icon.type === "material") {
    return (
      <span className={`material-symbols-outlined text-[24px] ${colorClass}`}>
        {icon.value}
      </span>
    );
  }
  return <span className="text-[24px] leading-none">{icon.value}</span>;
}

/* ============================
   COMPONENT
============================ */

export default function PreferencesPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string[]>>({
    tone: [], intensity: [], narrative: [], setting: [],
    themes: [], era: [], min_rating: [],
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [error, setError] = useState("");
  const [compatibilityMessage, setCompatibilityMessage] = useState("");
  const [compatibilityScore, setCompatibilityScore] = useState<number | null>(null);
  const [partnerStatus, setPartnerStatus] = useState<"waiting" | "ready">("waiting");

  const question = QUESTIONS[currentQuestion];
  const isLastQuestion = currentQuestion === QUESTIONS.length - 1;
  const progressPct = ((currentQuestion + 1) / QUESTIONS.length) * 100;
  const currentAnswers = answers[question.id] || [];

  /* ── Authoritative State Restoration ── */
  useEffect(() => {
    let isMounted = true;

    async function loadAuthoritativeState() {
      if (!id) return;
      try {
        const response = await apiRequest(`/api/sessions/${id}/`);
        if (!isMounted) return;
        const s = response.session;
        if (s) {
          // Both ready -> go straight to screening deck
          if (s.preferences_set) {
            navigate(`/session/${id}`, { replace: true });
            return;
          }

          // User already completed preferences -> restore submitted state
          if (s.user_preferences_set) {
            setHasSubmitted(true);
            if (s.user_preferences) {
              const up = s.user_preferences;
              setAnswers({
                tone: Array.isArray(up.tone) ? up.tone : [],
                intensity: up.intensity ? [up.intensity] : [],
                narrative: Array.isArray(up.narrative) ? up.narrative : [],
                setting: Array.isArray(up.setting) ? up.setting : [],
                themes: Array.isArray(up.themes) ? up.themes : [],
                era: Array.isArray(up.era) ? up.era : [],
                min_rating: Array.isArray(up.min_rating) ? up.min_rating : [],
              });
            }
          } else {
            // Restore in-progress draft from localStorage if present
            try {
              const draftStr = localStorage.getItem(`flick_draft_prefs_${id}`);
              if (draftStr) {
                const draft = JSON.parse(draftStr);
                if (draft.answers && typeof draft.answers === "object") {
                  setAnswers((prev) => ({ ...prev, ...draft.answers }));
                }
                if (
                  typeof draft.currentQuestion === "number" &&
                  draft.currentQuestion >= 0 &&
                  draft.currentQuestion < QUESTIONS.length
                ) {
                  setCurrentQuestion(draft.currentQuestion);
                }
              }
            } catch {
              // ignore invalid draft
            }
          }
        }
      } catch (err) {
        console.error("Failed to restore session preferences state:", err);
      } finally {
        if (isMounted) setLoadingInitial(false);
      }
    }

    loadAuthoritativeState();

    return () => {
      isMounted = false;
    };
  }, [id, navigate]);

  /* ── Persist in-progress draft to localStorage ── */
  useEffect(() => {
    if (!hasSubmitted && !loadingInitial && id) {
      try {
        localStorage.setItem(
          `flick_draft_prefs_${id}`,
          JSON.stringify({ currentQuestion, answers })
        );
      } catch {}
    }
  }, [answers, currentQuestion, hasSubmitted, loadingInitial, id]);

  /* ── Poll for partner ── */
  useEffect(() => {
    let intervalId: number;
    let redirected = false;

    async function checkSessionState() {
      try {
        const response = await apiRequest(`/api/sessions/${id}/`);
        const s = response.session;
        if (!s) return;

        // Authoritatively sync user_preferences_set
        if (s.user_preferences_set && !hasSubmitted) {
          setHasSubmitted(true);
        }

        if (s.preferences_set && !redirected) {
          redirected = true;
          if (intervalId) window.clearInterval(intervalId);
          try { localStorage.removeItem(`flick_draft_prefs_${id}`); } catch {}
          setPartnerStatus("ready");
          setTimeout(() => navigate(`/session/${id}`, { replace: true }), 1200);
        }
      } catch (_err: unknown) {}
    }

    intervalId = window.setInterval(checkSessionState, hasSubmitted ? 2000 : 3000);

    return () => {
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [hasSubmitted, id, navigate]);

  /* ── Select handler ── */
  function handleSelect(value: string) {
    if (hasSubmitted) return;
    const qId = question.id;
    const current = answers[qId] || [];

    // Themes: cap at 3
    if (qId === "themes" && !current.includes(value) && current.length >= 3) {
      setError("Pick up to 3 themes");
      return;
    }

    // Single-select
    if (!question.multiSelect) {
      setAnswers({ ...answers, [qId]: [value] });
      setError("");
      return;
    }

    // Era / Setting "any" exclusivity
    if ((qId === "era" || qId === "setting") && value === "any") {
      setAnswers({ ...answers, [qId]: ["any"] });
      setError("");
      return;
    }
    if ((qId === "era" || qId === "setting") && current.includes("any")) {
      setAnswers({ ...answers, [qId]: [value] });
      setError("");
      return;
    }

    setAnswers({
      ...answers,
      [qId]: current.includes(value)
        ? current.filter((v) => v !== value)
        : [...current, value],
    });
    setError("");
  }

  /* ── Build backend preferences from rich answers ── */
  function buildPreferences() {
    const tones = answers.tone || [];
    const intensity = answers.intensity?.[0] || "any";
    const themes = answers.themes || [];
    const settings = answers.setting || [];

    const mood = [...new Set(tones.map(t => TONE_TO_MOOD[t]).filter(Boolean))];
    const vibe = [...new Set(tones.map(t => TONE_TO_VIBE[t]).filter(Boolean))];

    const pace: string[] = [];
    if (intensity === "light") { pace.push("slow"); pace.push("balanced"); }
    else if (intensity === "medium") pace.push("balanced");
    else if (intensity === "heavy") { pace.push("fast"); pace.push("slow"); }
    else pace.push("balanced");

    const themeKeywords = themes.flatMap(t => THEME_KEYWORDS[t] || []);
    const settingKeywords = settings.filter(s => s !== "anywhere").flatMap(s => SETTING_KEYWORDS[s] || []);

    return {
      mood,
      pace,
      vibe,
      era: answers.era || [],
      min_rating: answers.min_rating || [],
      tone: tones,
      intensity,
      themes,
      theme_keywords: themeKeywords,
      setting: settings,
      setting_keywords: settingKeywords,
      narrative: answers.narrative || [],
    };
  }

  /* ── Navigation ── */
  async function handleNext() {
    if (hasSubmitted) return;
    if (currentAnswers.length === 0) {
      setError("Please select at least one option");
      return;
    }
    setError("");
    if (isLastQuestion) await handleSubmit();
    else setCurrentQuestion((prev) => prev + 1);
  }

  function handleBack() {
    if (hasSubmitted || currentQuestion === 0) return;
    setCurrentQuestion((prev) => prev - 1);
    setError("");
  }

  async function handleSubmit() {
    if (hasSubmitted) return;
    setIsSubmitting(true);
    setError("");
    try {
      const preferences = buildPreferences();
      const response = await apiRequest("/api/sessions/preferences/", {
        method: "POST",
        body: JSON.stringify({ session_id: Number(id), preferences }),
      });
      trackEvent("preferences_submitted", { session_id: Number(id), answers });
      try { localStorage.removeItem(`flick_draft_prefs_${id}`); } catch {}
      setHasSubmitted(true);
      setIsSubmitting(false);

      if (response.both_ready) {
        setPartnerStatus("ready");
        const score = response.overlap_score ?? 100;
        setCompatibilityScore(score);
        let message = "";
        if (score >= 70)      message = "Remarkable synergy. Your cinematic appetites are intimately aligned.";
        else if (score >= 50) message = `Strong mutual resonance (${score}% alignment). A harmonious viewing ahead.`;
        else if (score >= 30) message = `Complementary tastes (${score}% alignment). Shared ground exists in the subtleties.`;
        else                  message = `Distinct curiosities (${score}% alignment). Contrast often unearths the most enduring discoveries.`;
        setCompatibilityMessage(message);
        setTimeout(() => navigate(`/session/${id}`, { replace: true }), 1500);
      }
    } catch {
      setError("Failed to save preferences. Please try again.");
      setIsSubmitting(false);
    }
  }

  if (loadingInitial) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="flex flex-col items-center gap-3">
          <div className="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-foreground-secondary uppercase tracking-widest font-medium">
            Loading taste questionnaire…
          </span>
        </div>
      </div>
    );
  }

  /* ============================
     WAITING SCREEN
  ============================ */

  if (hasSubmitted) {
    const isReady = partnerStatus === "ready";
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-md flex flex-col items-center text-center gap-6 p-8 rounded-2xl border border-border bg-surface shadow-sm">
          <div className={`size-24 rounded-full flex items-center justify-center border transition-all duration-500 ${
            isReady ? "bg-primary/10 border-primary text-primary" : "bg-surface-secondary border-border text-foreground-secondary"
          }`}>
            <span className="material-symbols-outlined text-[42px]">
              {isReady ? "movie" : "hourglass_empty"}
            </span>
          </div>

          <div>
            <span className="text-[11px] font-semibold uppercase tracking-widest text-primary mb-1 block">
              Curatorial Alignment
            </span>
            <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-2">
              {isReady ? "Tastes Aligned" : "Awaiting Partner"}
            </h1>
            <p className="text-foreground-secondary text-xs leading-relaxed max-w-xs mx-auto">
              {isReady
                ? "Your collaborator has completed their questionnaire. Preparing your screening deck..."
                : "Waiting for your companion to submit their aesthetic preferences..."}
            </p>
          </div>

          {compatibilityMessage && (
            <div className="w-full bg-surface-secondary/60 border border-primary/20 rounded-xl p-5 text-left relative">
              {compatibilityScore !== null && (
                <div className="flex items-baseline gap-3 mb-2">
                  <div className="font-editorial text-3xl font-bold text-primary">{compatibilityScore}%</div>
                  <div className="text-[11px] uppercase tracking-wider text-foreground-secondary font-medium">Taste Alignment</div>
                </div>
              )}
              <p className="text-xs text-foreground leading-relaxed">{compatibilityMessage}</p>
            </div>
          )}

          {isReady ? (
            <div className="flex items-center gap-2 text-xs text-primary font-medium tracking-wide">
              <span className="size-2 rounded-full bg-primary animate-pulse" />
              Opening session deck...
            </div>
          ) : (
            <div className="flex gap-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="size-2 rounded-full bg-primary/40 animate-pulse"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ============================
     QUESTIONNAIRE SCREEN
  ============================ */

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col max-w-lg mx-auto border-x border-border/40">

      {/* ── App Bar ── */}
      <div className="flex items-center px-4 py-3 justify-between sticky top-0 bg-background/95 backdrop-blur-md border-b border-border/60 z-10">
        <button
          onClick={handleBack}
          disabled={currentQuestion === 0}
          className="flex size-10 shrink-0 items-center justify-center text-foreground-secondary hover:text-foreground disabled:opacity-20 transition-colors rounded-full hover:bg-surface-secondary"
          aria-label="Previous question"
        >
          <span className="material-symbols-outlined text-[20px]">arrow_back</span>
        </button>

        <div className="flex flex-col items-center">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-primary">
            Step {currentQuestion + 1} of {QUESTIONS.length}
          </span>
          {question.id === "themes" && (
            <p className="text-[10px] text-foreground-secondary mt-0.5">{currentAnswers.length}/3 selected</p>
          )}
          {question.multiSelect && question.id !== "themes" && (
            <p className="text-[10px] text-foreground-secondary mt-0.5">Select all that apply</p>
          )}
        </div>

        <div className="size-10" />
      </div>

      {/* ── Progress Bar ── */}
      <div className="px-6 pt-3 pb-2">
        <div className="h-1 w-full rounded-full bg-surface-secondary overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* ── Question Heading ── */}
      <div className="px-6 py-4 text-center">
        <h1 className="font-editorial text-2xl md:text-3xl font-semibold tracking-tight text-foreground mb-1.5 leading-snug">
          {question.title}
        </h1>
        <p className="text-xs text-foreground-secondary max-w-sm mx-auto">{question.subtitle}</p>
      </div>

      {/* ── Options ── */}
      <div className="flex-1 overflow-y-auto px-6 pb-6">

        {question.layout === "grid" && (
          <div className="grid grid-cols-2 gap-3">
            {question.options.map((option) => {
              const isSelected = currentAnswers.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  disabled={hasSubmitted}
                  className={`flex flex-col gap-2 rounded-xl border p-4 items-center justify-center transition-all active:scale-[0.98] relative overflow-hidden min-h-[112px] text-left focus:outline-none focus:ring-1 focus:ring-primary ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-sm"
                      : "border-border bg-surface hover:border-primary/40 hover:bg-surface-secondary/40"
                  }`}
                >
                  <div className={`flex items-center justify-center size-10 rounded-full transition-colors ${
                    isSelected ? "bg-primary/20 text-primary" : "bg-surface-secondary text-foreground-secondary"
                  }`}>
                    <OptionIcon icon={option.icon} selected={isSelected} />
                  </div>
                  <div className="text-center w-full">
                    <p className={`text-xs font-semibold leading-tight ${isSelected ? "text-foreground" : "text-foreground"}`}>
                      {option.label}
                    </p>
                    {option.subtitle && (
                      <p className="text-[10px] text-foreground-secondary mt-0.5 leading-tight line-clamp-2">
                        {option.subtitle}
                      </p>
                    )}
                  </div>
                  {isSelected && (
                    <div className="absolute top-2.5 right-2.5">
                      <span className="material-symbols-outlined text-primary text-[15px]"
                        style={{ fontVariationSettings: "'FILL' 1" }}>check_circle</span>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        )}

        {question.layout === "list" && (
          <div className="flex flex-col gap-2.5">
            {question.options.map((option) => {
              const isSelected = currentAnswers.includes(option.value);
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option.value)}
                  disabled={hasSubmitted}
                  className={`flex items-center gap-3.5 rounded-xl border p-3.5 text-left w-full transition-all active:scale-[0.98] focus:outline-none focus:ring-1 focus:ring-primary ${
                    isSelected
                      ? "border-primary bg-primary/10 shadow-sm"
                      : "border-border bg-surface hover:border-primary/40 hover:bg-surface-secondary/40"
                  }`}
                >
                  <div className={`flex size-10 shrink-0 items-center justify-center rounded-full transition-colors ${
                    isSelected ? "bg-primary/20 text-primary" : "bg-surface-secondary text-foreground-secondary"
                  }`}>
                    <OptionIcon icon={option.icon} selected={isSelected} />
                  </div>
                  <div className="flex grow flex-col">
                    <p className={`text-xs ${isSelected ? "font-semibold text-foreground" : "font-medium text-foreground"}`}>
                      {option.label}
                    </p>
                    {option.subtitle && (
                      <p className="text-[11px] text-foreground-secondary mt-0.5">{option.subtitle}</p>
                    )}
                  </div>
                  <span
                    className={`material-symbols-outlined text-[18px] shrink-0 ${isSelected ? "text-primary" : "text-transparent"}`}
                    style={{ fontVariationSettings: isSelected ? "'FILL' 1" : undefined }}
                  >
                    check_circle
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Error ── */}
      {error && (
        <div className="mx-6 mb-3 p-3 bg-error/10 border border-error/20 rounded-xl">
          <p className="text-xs text-error text-center">{error}</p>
        </div>
      )}

      {/* ── Bottom Navigation ── */}
      <div className="sticky bottom-0 bg-background/95 backdrop-blur-md border-t border-border/60 py-4 px-6">
        <div className="flex gap-3">
          {currentQuestion > 0 && (
            <button
              type="button"
              onClick={handleBack}
              disabled={isSubmitting || hasSubmitted}
              className="flex-1 py-3.5 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98] disabled:opacity-50"
            >
              Back
            </button>
          )}
          <button
            type="button"
            onClick={handleNext}
            disabled={isSubmitting || hasSubmitted}
            className={`py-3.5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-all active:scale-[0.98] shadow-sm disabled:opacity-50 flex items-center justify-center gap-2 ${
              currentQuestion > 0 ? "flex-1" : "w-full"
            }`}
          >
            {isSubmitting ? (
              <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
            ) : isLastQuestion ? (
              <>
                <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
                Generate Screening Deck
              </>
            ) : (
              <>
                Continue
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
