import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";

type HistoryItem = {
  session_id: number;
  session_code: string;
  partner_username: string;
  genres: string[];
  match_count: number;
  swipe_count: number;
  top_match: {
    movie_id: number;
    movie_title: string;
    poster_url: string | null;
  } | null;
  ended_at: string | null;
  created_at: string;
};

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`;
  return `${Math.floor(diffDays / 365)}y ago`;
}

export default function SessionHistoryPage() {
  const navigate = useNavigate();
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiRequest("/api/sessions/history/");
        setHistory(data.history || []);
      } catch {
        setError("Failed to load session history.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col max-w-lg mx-auto border-x border-border/40">

      {/* ── Header ── */}
      <header className="flex items-center px-4 py-3 sticky top-0 bg-background/95 backdrop-blur-md z-10 border-b border-border/60">
        <button
          onClick={() => navigate(-1)}
          className="size-9 rounded-full bg-surface border border-border flex items-center justify-center text-foreground-secondary hover:text-foreground transition-colors shrink-0"
          aria-label="Back"
        >
          <span className="material-symbols-outlined text-[18px]">arrow_back</span>
        </button>
        <h1 className="font-editorial text-lg font-bold flex-1 text-center">Screening History</h1>
        <div className="size-9" />
      </header>

      {/* ── Content ── */}
      <main className="flex-1 overflow-y-auto pb-8 px-6 pt-3">
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="size-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {error && (
          <div className="my-4 p-4 rounded-xl bg-error/10 border border-error/20 text-error text-xs text-center">
            {error}
          </div>
        )}

        {!loading && !error && history.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-24 text-center">
            <span className="material-symbols-outlined text-foreground-secondary text-4xl">movie</span>
            <h2 className="font-editorial text-lg font-bold">No Historical Screenings</h2>
            <p className="text-xs text-foreground-secondary leading-relaxed max-w-xs">
              Conclude a screening session with your partner and records will appear here.
            </p>
            <button
              onClick={() => navigate("/")}
              className="mt-2 px-5 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-xs"
            >
              Start Screening
            </button>
          </div>
        )}

        {!loading && history.map((item) => (
          <div
            key={item.session_id}
            className="my-3 rounded-xl bg-surface border border-border overflow-hidden hover:border-primary/40 transition-colors shadow-xs"
          >
            <div className="flex gap-3.5 p-4">
              {/* Top match poster */}
              <div className="shrink-0 w-14 aspect-[2/3] rounded-lg overflow-hidden bg-surface-secondary border border-border shadow-xs">
                {item.top_match?.poster_url ? (
                  <img
                    src={item.top_match.poster_url}
                    alt={item.top_match.movie_title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-foreground-secondary">
                    <span className="material-symbols-outlined text-[20px]">movie</span>
                  </div>
                )}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className="material-symbols-outlined text-[14px] text-primary">person</span>
                    <span className="text-xs font-semibold text-foreground truncate">{item.partner_username}</span>
                  </div>
                  <span className="text-[10px] text-foreground-secondary shrink-0 ml-2">
                    {item.ended_at ? timeAgo(item.ended_at) : timeAgo(item.created_at)}
                  </span>
                </div>

                {item.genres.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-2">
                    {item.genres.slice(0, 3).map((g) => (
                      <span key={g} className="text-[10px] font-medium px-2 py-0.5 rounded bg-surface-secondary text-foreground-secondary border border-border">
                        {g}
                      </span>
                    ))}
                  </div>
                )}

                {item.top_match && (
                  <p className="text-[11px] text-foreground-secondary leading-tight mb-2 line-clamp-1">
                    Spotlight: <span className="font-editorial text-foreground font-semibold">{item.top_match.movie_title}</span>
                  </p>
                )}

                <div className="flex items-center gap-3 text-xs">
                  <div className="flex items-center gap-1 text-primary">
                    <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>favorite</span>
                    <span className="text-xs font-bold">{item.match_count}</span>
                    <span className="text-[10px] text-foreground-secondary">agreed</span>
                  </div>
                  <div className="w-px h-3 bg-border" />
                  <div className="flex items-center gap-1 text-foreground-secondary">
                    <span className="material-symbols-outlined text-[13px]">swipe</span>
                    <span className="text-xs font-medium text-foreground">{item.swipe_count}</span>
                    <span className="text-[10px]">reviewed</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </main>
    </div>
  );
}
