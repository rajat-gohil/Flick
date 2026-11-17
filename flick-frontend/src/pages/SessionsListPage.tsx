import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiRequest } from "../lib/api";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type RecentSession = {
  id: number;
  code: string;
  name: string;
  date: string;
  matches: number;
  ended: boolean;
  /** Backend-computed status: "active" | "completed" | "ended_by_host" */
  status?: string;
  /** True when the current user is the session host */
  is_host?: boolean;
  /** "host" | "guest" */
  user_role?: string;
  participants: { initials: string; username: string }[];
};

function AvatarStack({ participants }: { participants: RecentSession["participants"] }) {
  return (
    <div className="flex -space-x-1.5">
      {participants.slice(0, 3).map((p, i) => (
        <div
          key={i}
          className="size-7 rounded-full border border-border bg-surface-secondary flex items-center justify-center text-[10px] font-bold text-foreground shadow-xs"
        >
          {p.initials}
        </div>
      ))}
      {participants.length > 3 && (
        <div className="size-7 rounded-full border border-border bg-surface-secondary flex items-center justify-center text-[10px] font-bold text-foreground-secondary">
          +{participants.length - 3}
        </div>
      )}
    </div>
  );
}

export default function SessionsListPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get("tab");
  const [filter, setFilter] = useState<"all" | "active" | "history">(
    tabParam === "history" ? "history" : tabParam === "active" ? "active" : "all"
  );
  const [sessions, setSessions] = useState<RecentSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [endingSessionId, setEndingSessionId] = useState<number | null>(null);
  const [confirmEndId, setConfirmEndId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    const tab = searchParams.get("tab");
    if (tab === "history") setFilter("history");
    else if (tab === "active") setFilter("active");
    else if (!tab) setFilter("all");
  }, [searchParams]);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiRequest("/api/sessions/recent/");
      if (Array.isArray(data.sessions)) {
        setSessions(data.sessions);
      }
    } catch {
      // Keep existing sessions if already loaded
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  const handleTabChange = (nextTab: "all" | "active" | "history") => {
    setFilter(nextTab);
    const newParams = new URLSearchParams(searchParams);
    if (nextTab === "all") {
      newParams.delete("tab");
    } else {
      newParams.set("tab", nextTab);
    }
    setSearchParams(newParams, { replace: true });
  };

  const handleEndSession = async (sessionId: number) => {
    if (endingSessionId !== null) return;
    setEndingSessionId(sessionId);
    setActionError(null);
    try {
      const res = await apiRequest("/api/sessions/end/", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
      if (res && res.success === false) {
        throw new Error(res.error || "Failed to end screening");
      }
      // Optimistically update session status in current view
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? { ...s, ended: true, status: "ended_by_host" }
            : s
        )
      );
      setConfirmEndId(null);
      // Re-fetch directory to sync authoritative backend metadata
      try {
        const data = await apiRequest("/api/sessions/recent/");
        if (Array.isArray(data.sessions)) {
          setSessions(
            data.sessions.map((s: RecentSession) =>
              s.id === sessionId
                ? { ...s, ended: true, status: s.status === "completed" ? "completed" : "ended_by_host" }
                : s
            )
          );
        }
      } catch {
        // Optimistic state remains
      }
    } catch (err: any) {
      const msg = err?.message || err?.error || "Failed to end screening. Please try again.";
      setActionError(msg);
      setConfirmEndId(null);
    } finally {
      setEndingSessionId(null);
    }
  };

  const isSessionActive = (s: RecentSession) => {
    if (s.ended) return false;
    if (s.status === "ended_by_host" || s.status === "completed" || s.status === "ended") return false;
    return s.status === "active" || !s.ended;
  };

  const active  = sessions.filter(isSessionActive);
  const history = sessions.filter((s) => !isSessionActive(s));

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* ── Header ── */}
      <CinemaHeader
        current="sessions"
        title="Screening Directory"
        subtitle={
          filter === "history"
            ? `${history.length} archived session${history.length !== 1 ? "s" : ""}`
            : active.length > 0
            ? `${active.length} active session${active.length !== 1 ? "s" : ""}`
            : undefined
        }
        onBack={() => navigate("/home")}
      />

      <div className="w-full max-w-5xl mx-auto flex-1 flex flex-col px-4 sm:px-6 lg:px-8 py-4 pb-24 md:pb-12">
        <main className="flex-1 overflow-y-auto">

          {/* ── Filter Tabs ── */}
          <div className="flex gap-2 max-w-md mx-auto w-full pt-1 pb-6">
            {([
              { id: "all", label: "All Screenings" },
              { id: "active", label: "Live", count: active.length },
              { id: "history", label: "Archived", count: history.length },
            ] as { id: "all" | "active" | "history"; label: string; count?: number }[]).map((t) => (
              <button
                key={t.id}
                onClick={() => handleTabChange(t.id)}
                className={`flex-1 h-8 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all border flex items-center justify-center gap-1.5 ${
                  filter === t.id
                    ? "bg-primary border-primary text-surface shadow-xs"
                    : "bg-surface border-border text-foreground-secondary hover:text-foreground"
                }`}
              >
                <span>{t.label}</span>
                {t.count !== undefined && !loading && (
                  <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                    filter === t.id ? "bg-surface/20 text-surface" : "bg-surface-secondary text-foreground-secondary"
                  }`}>
                    {t.count}
                  </span>
                )}
              </button>
            ))}
          </div>

          {/* ── Error Banner ── */}
          {actionError && (
            <div
              data-testid="directory-action-error"
              className="mb-4 p-3.5 rounded-xl bg-error/10 border border-error/30 text-error text-xs flex items-center justify-between gap-3 animate-fade-in"
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="material-symbols-outlined text-base shrink-0">error</span>
                <span className="truncate">{actionError}</span>
              </div>
              <button
                onClick={() => setActionError(null)}
                className="text-error hover:text-error/80 shrink-0 p-1"
                aria-label="Dismiss error"
              >
                <span className="material-symbols-outlined text-sm">close</span>
              </button>
            </div>
          )}

          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="size-7 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && sessions.length === 0 && (
            <div className="flex flex-col items-center gap-3 py-20 text-center">
              <span className="material-symbols-outlined text-foreground-secondary text-4xl">movie</span>
              <div>
                <h2 className="font-editorial text-lg font-bold mb-1">No Active Screenings</h2>
                <p className="text-xs text-foreground-secondary max-w-xs">
                  Launch a collaborative session with a friend to review movies together.
                </p>
              </div>
              <button
                onClick={() => navigate("/session/create")}
                className="mt-2 h-10 px-5 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-xs flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[16px]">add</span>
                Begin Screening
              </button>
            </div>
          )}

          {/* ── Active Sessions Section ── */}
          {!loading && (filter === "all" || filter === "active") && active.length > 0 && (
            <section className="mb-8">
              <div className="flex items-center gap-2 mb-3">
                <span className="size-2 rounded-full bg-primary animate-pulse" />
                <h2 className="text-[10px] font-semibold uppercase tracking-widest text-primary">Live Screenings</h2>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {active.map((s) => (
                  <SessionCard
                    key={s.id}
                    session={s}
                    onClick={() => navigate(`/session/${s.id}`)}
                    onEndRoom={() => setConfirmEndId(s.id)}
                    endingId={endingSessionId}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Empty active state when filter is active */}
          {!loading && filter === "active" && active.length === 0 && sessions.length > 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <span className="material-symbols-outlined text-foreground-secondary text-3xl">play_circle</span>
              <h3 className="font-editorial text-base font-semibold">No Live Sessions</h3>
              <p className="text-xs text-foreground-secondary max-w-xs">
                You do not currently have any uncompleted screening decks.
              </p>
              <button
                onClick={() => navigate("/session/create")}
                className="mt-2 h-9 px-4 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-colors shadow-xs"
              >
                Launch New Session
              </button>
            </div>
          )}

          {/* ── Past Sessions Section ── */}
          {!loading && (filter === "all" || filter === "history") && history.length > 0 && (
            <section>
              <h2 className="text-[10px] font-semibold uppercase tracking-widest text-foreground-secondary mb-3">Archived Screenings</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                {history.map((s) => (
                  <SessionCard key={s.id} session={s} onClick={() => navigate(`/session/${s.id}`)} />
                ))}
              </div>
            </section>
          )}

          {/* Empty history state when filter is history */}
          {!loading && filter === "history" && history.length === 0 && sessions.length > 0 && (
            <div className="flex flex-col items-center gap-3 py-16 text-center">
              <span className="material-symbols-outlined text-foreground-secondary text-3xl">history</span>
              <h3 className="font-editorial text-base font-semibold">No Archived Sessions</h3>
              <p className="text-xs text-foreground-secondary max-w-xs">
                Concluded screening sessions will be catalogued here for review.
              </p>
            </div>
          )}
        </main>
      </div>

      {/* ── Bottom Nav ── */}
      <BottomNav current="sessions" />

      {/* ── End Room Confirmation Modal (accessible to both host and guest) ── */}
      {confirmEndId !== null && (
        <div
          data-testid="archive-end-confirm-modal"
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
          onClick={(e) => {
            if (e.target === e.currentTarget && endingSessionId === null) {
              setConfirmEndId(null);
            }
          }}
        >
          <div className="w-full max-w-sm bg-surface border border-border rounded-2xl shadow-xl p-6 flex flex-col gap-4">
            <div className="flex flex-col gap-1.5 text-center">
              <span className="material-symbols-outlined text-rose-500 text-[36px] mx-auto">stop_circle</span>
              <h2 className="font-editorial text-lg font-semibold tracking-tight text-foreground">End this screening?</h2>
              <p className="text-xs text-foreground-secondary leading-relaxed">
                Ending this room will terminate the screening for both participants. This action cannot be undone.
              </p>
            </div>
            <div className="flex flex-col gap-2.5 pt-1">
              <button
                onClick={() => handleEndSession(confirmEndId)}
                disabled={endingSessionId !== null}
                data-testid="archive-end-confirm-proceed-btn"
                className="w-full h-11 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-60"
              >
                {endingSessionId !== null ? (
                  <span className="size-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                ) : (
                  <>
                    <span className="material-symbols-outlined text-[16px]">stop_circle</span>
                    End Room
                  </>
                )}
              </button>
              <button
                onClick={() => setConfirmEndId(null)}
                disabled={endingSessionId !== null}
                className="w-full h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-semibold text-xs tracking-wider uppercase transition-colors disabled:opacity-60"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Session Card ── */
function SessionCard({
  session,
  onClick,
  onEndRoom,
  endingId,
}: {
  session: RecentSession;
  onClick: () => void;
  onEndRoom?: () => void;
  endingId?: number | null;
}) {
  const isActive = !session.ended && session.status !== "ended_by_host" && session.status !== "ended" && session.status !== "completed";
  const canEnd = isActive && Boolean(onEndRoom);

  const statusLabel = (() => {
    if (isActive) return { label: "Active", cls: "text-primary bg-primary/10 border border-primary/20" };
    if (session.status === "ended_by_host") return { label: "Ended by host", cls: "text-foreground-secondary bg-surface-secondary" };
    if (session.status === "completed") return { label: "Completed", cls: "text-foreground-secondary bg-surface-secondary" };
    return { label: "Ended", cls: "text-foreground-secondary bg-surface-secondary" };
  })();

  return (
    <div className="w-full rounded-xl bg-surface border border-border shadow-xs overflow-hidden flex flex-col justify-between">
      <button
        onClick={onClick}
        className="w-full flex items-center gap-3.5 p-3.5 text-left hover:border-primary/50 transition-colors"
      >
        {/* Icon */}
        <div className={`size-11 rounded-lg flex items-center justify-center shrink-0 ${
          isActive ? "bg-primary/10 border border-primary/30 text-primary" : "bg-surface-secondary text-foreground-secondary"
        }`}>
          <span className="material-symbols-outlined text-[22px]"
            style={isActive ? { fontVariationSettings: "'FILL' 1" } : undefined}>
            {isActive ? "play_circle" : "movie"}
          </span>
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <h3 className="font-editorial text-sm font-semibold text-foreground truncate flex-1">{session.name}</h3>
            <span
              data-testid={`session-status-badge-${session.id}`}
              className={`text-[9px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded shrink-0 ${statusLabel.cls}`}
            >
              {statusLabel.label}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <AvatarStack participants={session.participants} />
            <span className="text-[11px] text-foreground-secondary">{session.date}</span>
          </div>
        </div>

        {/* Match count */}
        <div className="flex flex-col items-center shrink-0">
          <div className="flex items-center gap-1 text-primary">
            <span className="material-symbols-outlined text-[13px]" style={{ fontVariationSettings: "'FILL' 1" }}>favorite</span>
            <span className="text-xs font-bold">{session.matches}</span>
          </div>
          <span className="text-[9px] text-foreground-secondary uppercase tracking-wider">
            Consensus
          </span>
        </div>

        <span className="material-symbols-outlined text-foreground-secondary text-[16px] shrink-0">chevron_right</span>
      </button>

      {/* End Room action — visible to both host and guest on active rooms */}
      {canEnd && (
        <div className="border-t border-border/60 px-3.5 py-2.5 flex items-center justify-between bg-surface-secondary/30">
          <div className="flex items-center gap-1.5 text-[10px] text-foreground-secondary font-mono">
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Active Room</span>
          </div>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onEndRoom?.();
            }}
            disabled={endingId === session.id}
            data-testid={`end-room-btn-${session.id}`}
            data-end-btn={`end-screening-btn-${session.id}`}
            aria-label={`End screening room ${session.name}`}
            className="h-7 px-3 rounded-lg border border-rose-500/40 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 hover:text-rose-400 text-[10px] font-semibold uppercase tracking-wider transition-colors disabled:opacity-50 flex items-center gap-1.5 shadow-xs"
          >
            {endingId === session.id ? (
              <span className="size-3 border border-rose-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <span className="material-symbols-outlined text-[14px]">stop_circle</span>
            )}
            <span>End Room</span>
          </button>
        </div>
      )}
    </div>
  );
}
