import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { trackEvent } from "../lib/analytics";
import { useTheme } from "../context/ThemeContext";
import AnimatedFlickLogo from "../components/AnimatedFlickLogo";

/* ============================
   MOVIE FACTS
============================ */

const MOVIE_FACTS = [
  "The velociraptors in Jurassic Park were voiced using acoustic recordings of mating tortoises.",
  "The iconic shower sequence in Psycho (1960) used chocolate syrup for blood to achieve high contrast in black and white.",
  "Toy Story (1995) was the first feature-length film realized entirely through digital CGI animation.",
  "The Lord of the Rings trilogy was filmed entirely across New Zealand over 438 shooting days.",
  "Heath Ledger improvised the pencil sequence in The Dark Knight — it wasn't scripted.",
  "The roar of the T-Rex in Jurassic Park is an acoustic composite of a baby elephant, an alligator, and a tiger.",
  "Approximately 90% of all silent films produced prior to 1929 are irrevocably lost due to nitrate decomposition.",
  "Morgan Freeman did not appear in a major feature film until the age of 52.",
  "The Wilhelm Scream is a stock archival sound effect deployed in hundreds of films since 1951.",
  "The production budget for Star Wars (1977) was $11 million against a worldwide return of $775 million.",
  "Clueless (1995) is a contemporary adaptation of Jane Austen's Emma set in Southern California.",
  "James Cameron trained in deep-sea technical diving specifically to direct The Abyss.",
  "Marlon Brando contoured his cheeks with dental cotton wool to portray Don Corleone in The Godfather.",
  "The lightsaber hum was created by pairing an idling projector motor with an unshielded cathode television set.",
  "Parasite (2019) made cinema history as the first non-English language film to win the Academy Award for Best Picture.",
];

export default function AutoJoin() {
  const navigate = useNavigate();
  const { logoFull } = useTheme();
  const [error, setError] = useState<string | null>(null);

  const [factIndex, setFactIndex] = useState(() =>
    Math.floor(Math.random() * MOVIE_FACTS.length)
  );
  const [factVisible, setFactVisible] = useState(true);
  const [dotPhase, setDotPhase] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setFactVisible(false);
      setTimeout(() => {
        setFactIndex((prev) => (prev + 1) % MOVIE_FACTS.length);
        setFactVisible(true);
      }, 400);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setDotPhase((prev) => (prev + 1) % 3);
    }, 500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    async function join() {
      const rawCode = localStorage.getItem("pendingSessionCode");
      const sessionCode = rawCode ? rawCode.trim().toUpperCase() : null;

      if (!sessionCode) {
        navigate("/", { replace: true });
        return;
      }

      try {
        const data = await apiRequest("/api/sessions/join/", {
          method: "POST",
          body: JSON.stringify({ code: sessionCode }),
        });

        localStorage.removeItem("pendingSessionCode");
        trackEvent("session_joined", {
          session_id: data.session_id,
          source: "invite_link",
        });
        if (data.user_preferences_set) {
          navigate(`/session/${data.session_id}`, { replace: true });
        } else {
          navigate(`/session/${data.session_id}/preferences`, { replace: true });
        }
      } catch (err: unknown) {
        localStorage.removeItem("pendingSessionCode");
        trackEvent("session_join_failed", {
          source: "invite_link",
          reason: err instanceof Error ? err.message : "invalid_or_ended",
        });
        setError("This invite link is invalid or the screening session has concluded.");
      }
    }

    join();
  }, [navigate]);

  if (error) {
    return (
      <div className="relative min-h-screen bg-background font-sans text-foreground flex items-center justify-center p-6">
        <div className="text-center max-w-sm p-8 rounded-2xl bg-surface border border-border shadow-sm">
          <div className="size-14 bg-error/10 text-error rounded-full flex items-center justify-center mx-auto mb-3">
            <span className="material-symbols-outlined text-[28px]">error</span>
          </div>
          <p className="text-error text-xs font-medium leading-relaxed mb-5">
            {error}
          </p>
          <button
            onClick={() => navigate("/", { replace: true })}
            className="px-5 h-10 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-xs"
          >
            Return to Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-background font-sans text-foreground flex flex-col justify-between p-6 max-w-lg mx-auto border-x border-border/40">

      {/* Top Header */}
      <div className="flex items-center justify-between pb-4">
        <button
          type="button"
          onClick={() => navigate("/")}
          className="size-11 sm:size-9 rounded-full bg-surface border border-border flex items-center justify-center text-foreground-secondary hover:text-foreground transition-colors cursor-pointer"
          aria-label="Cancel"
        >
          <span className="material-symbols-outlined text-[18px]">close</span>
        </button>
        <img src={logoFull} alt="Flick" className="h-6 w-auto object-contain" />
        <div className="size-11 sm:size-9" aria-hidden="true" />
      </div>

      {/* Center animation */}
      <div className="flex flex-col items-center gap-6 py-8">
        <div className="relative size-28 rounded-full border border-primary/30 bg-primary/10 flex items-center justify-center shadow-sm">
          <AnimatedFlickLogo variant="badge" loop decorative className="size-20 rounded-2xl shadow-sm relative z-10" />
          <div className="absolute inset-0 rounded-full border border-primary/40 animate-ping" style={{ animationDuration: "2.5s" }} />
        </div>

        <div className="text-center">
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-1 block">
            Screening Room
          </span>
          <h1 className="font-editorial text-2xl font-bold tracking-tight text-foreground mb-1">
            Entering Screening Deck
            <span className="inline-flex gap-1 ml-1.5 align-middle">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="size-1 rounded-full bg-primary transition-all duration-300"
                  style={{
                    opacity: dotPhase === i ? 1 : 0.3,
                  }}
                />
              ))}
            </span>
          </h1>
          <p className="text-sm text-foreground-secondary max-w-xs mx-auto">
            Syncing the film lineup with your partner.
          </p>
        </div>
      </div>

      {/* Archival Note */}
      <div className="my-auto pb-8">
        <div
          className="bg-surface border border-border rounded-xl p-5 shadow-xs transition-all duration-400"
          style={{
            opacity: factVisible ? 1 : 0,
            transform: factVisible ? "translateY(0)" : "translateY(6px)",
            transition: "opacity 0.4s ease, transform 0.4s ease",
          }}
        >
          <span className="text-xs font-semibold text-primary uppercase tracking-widest mb-1.5 block">
            Cinema Note
          </span>
          <p className="text-sm text-foreground leading-relaxed">
            {MOVIE_FACTS[factIndex]}
          </p>
        </div>
      </div>

      <div className="text-center pb-4">
        <p className="text-xs uppercase tracking-widest text-foreground-secondary">
          Secured Session
        </p>
      </div>
    </div>
  );
}
