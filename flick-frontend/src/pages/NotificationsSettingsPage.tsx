import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type NotifPrefs = {
  session_invites: boolean;
  match_alerts: boolean;
  partner_joined: boolean;
  weekly_digest: boolean;
  push_enabled: boolean;
};

const DEFAULT_PREFS: NotifPrefs = {
  session_invites: true,
  match_alerts: true,
  partner_joined: true,
  weekly_digest: false,
  push_enabled: false,
};

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label || "Toggle notification preference"}
      onClick={() => onChange(!on)}
      className="min-h-[44px] min-w-[44px] -my-2 flex items-center justify-end shrink-0 cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-full p-1"
    >
      <span
        className={`relative inline-block w-10 h-5 rounded-full transition-colors ${on ? "bg-primary" : "bg-surface-secondary border border-border"}`}
      >
        <span
          className={`absolute top-0.5 size-4 rounded-full bg-surface shadow-xs transition-transform block ${on ? "translate-x-5" : "translate-x-0.5"}`}
        />
      </span>
    </button>
  );
}

function NotifRow({
  icon, title, subtitle, value, onChange,
}: {
  icon: string; title: string; subtitle: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-3.5 px-5 py-3.5 border-b border-border/60 last:border-0">
      <span className="material-symbols-outlined text-[18px] text-foreground-secondary shrink-0">{icon}</span>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-foreground">{title}</p>
        <p className="text-[11px] text-foreground-secondary mt-0.5 leading-snug">{subtitle}</p>
      </div>
      <Toggle on={value} onChange={onChange} label={`Toggle ${title}`} />
    </div>
  );
}

export default function NotificationsSettingsPage() {
  const navigate = useNavigate();
  const [prefs, setPrefs] = useState<NotifPrefs>(DEFAULT_PREFS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [pushStatus, setPushStatus] = useState<"unsupported" | "denied" | "granted" | "default">("default");

  useEffect(() => {
    apiRequest("/api/users/notification-preferences/")
      .then((res: unknown) => {
        const r = res as { success?: boolean; preferences?: Partial<NotifPrefs> };
        if (r.success && r.preferences) setPrefs(p => ({ ...p, ...r.preferences }));
      })
      .catch((_err: unknown) => {})
      .finally(() => setLoading(false));

    if (!("Notification" in window)) {
      setPushStatus("unsupported");
    } else {
      setPushStatus(Notification.permission as "denied" | "granted" | "default");
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    const t = setTimeout(() => {
      setSaving(true);
      apiRequest("/api/users/notification-preferences/", {
        method: "POST",
        body: JSON.stringify(prefs),
      })
        .then((_res: unknown) => {
          setSaved(true);
          setTimeout(() => setSaved(false), 1500);
        })
        .catch((_err: unknown) => {})
        .finally(() => setSaving(false));
    }, 600);
    return () => clearTimeout(t);
  }, [prefs]);

  function update(key: keyof NotifPrefs, value: boolean) {
    setPrefs(p => ({ ...p, [key]: value }));
  }

  async function requestPushPermission() {
    if (!("Notification" in window)) return;
    const result = await Notification.requestPermission();
    setPushStatus(result);
    if (result === "granted") {
      update("push_enabled", true);
    }
  }

  if (loading) {
    return (
      <div className="bg-background min-h-screen flex items-center justify-center font-sans">
        <div className="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* Header */}
      <CinemaHeader
        current="profile"
        title="Notification Preferences"
        subtitle="Web & Dispatch Alerts"
        onBack={() => {
          if (window.history.length > 1) navigate(-1);
          else navigate("/profile");
        }}
        rightAction={
          (saving || saved) ? (
            <span className={`text-xs font-semibold tracking-wide transition-colors ${saved ? "text-primary" : "text-foreground-secondary"} px-2 py-1`}>
              {saved ? "✓ Synchronized" : "Updating…"}
            </span>
          ) : undefined
        }
      />

      <div className="w-full max-w-2xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-6 pb-24 md:pb-12">
        <main className="flex-1 overflow-y-auto">
          {pushStatus !== "granted" && pushStatus !== "unsupported" && (
            <div className="mb-5 p-4 rounded-xl bg-primary/10 border border-primary/20 flex items-start gap-3">
              <span className="material-symbols-outlined text-primary text-[20px] shrink-0 mt-0.5">notifications_active</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-foreground">Enable Web Dispatch Notifications</p>
                <p className="text-[11px] text-foreground-secondary mt-0.5 leading-snug">
                  {pushStatus === "denied"
                    ? "Notifications are disallowed by your browser settings."
                    : "Receive instant match cues when a co-viewer makes a selection."}
                </p>
              </div>
              {pushStatus === "default" && (
                <button
                  onClick={requestPushPermission}
                  className="shrink-0 text-xs font-semibold uppercase tracking-wider text-surface bg-primary px-3 py-1.5 rounded-lg"
                >
                  Allow
                </button>
              )}
            </div>
          )}

          <p className="text-[10px] font-semibold text-primary uppercase tracking-widest px-1 mb-2 mt-2">
            In-App Screening Alerts
          </p>
          <div className="rounded-xl bg-surface border border-border overflow-hidden divide-y divide-border/60 shadow-xs mb-5">
            <NotifRow
              icon="group_add"
              title="Session Invitations"
              subtitle="When an invite passcode is directed to your attention"
              value={prefs.session_invites}
              onChange={(v) => update("session_invites", v)}
            />
            <NotifRow
              icon="favorite"
              title="Consensus Matches"
              subtitle="When mutual selection is recorded on a title"
              value={prefs.match_alerts}
              onChange={(v) => update("match_alerts", v)}
            />
            <NotifRow
              icon="person_add"
              title="Partner Presence"
              subtitle="When your partner enters a shared screening room"
              value={prefs.partner_joined}
              onChange={(v) => update("partner_joined", v)}
            />
          </div>

          <p className="text-[10px] font-semibold text-primary uppercase tracking-widest px-1 mb-2">
            Editorial Correspondence
          </p>
          <div className="rounded-xl bg-surface border border-border overflow-hidden shadow-xs mb-5">
            <NotifRow
              icon="mail"
              title="Weekly Dispatch"
              subtitle="Curated digest of matched titles and cinema releases"
              value={prefs.weekly_digest}
              onChange={(v) => update("weekly_digest", v)}
            />
          </div>

          <p className="text-[10px] font-semibold text-primary uppercase tracking-widest px-1 mb-2">
            Push Notifications
          </p>
          <div className="rounded-xl bg-surface border border-border overflow-hidden shadow-xs mb-6">
            <NotifRow
              icon="notifications"
              title="Direct Push Notifications"
              subtitle={
                pushStatus === "denied"
                  ? "Blocked in browser permissions"
                  : pushStatus === "unsupported"
                  ? "Not supported in this environment"
                  : "Receive alerts when the app is backgrounded"
              }
              value={prefs.push_enabled && pushStatus === "granted"}
              onChange={(v) => {
                if (v && pushStatus !== "granted") {
                  requestPushPermission();
                } else {
                  update("push_enabled", v);
                }
              }}
            />
          </div>

          <p className="text-[11px] text-foreground-secondary text-center px-4 leading-relaxed">
            Preferences save automatically to your member profile.
          </p>
        </main>
      </div>

      <BottomNav current="profile" />
    </div>
  );
}
