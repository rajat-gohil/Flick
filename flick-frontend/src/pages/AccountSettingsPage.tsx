import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { isGuest } from "../lib/auth";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type UserProfile = {
  username: string;
  email: string;
  date_joined?: string;
  email_verified?: boolean;
};

function SectionHeader({ title }: { title: string }) {
  return (
    <p className="text-[10px] font-semibold text-primary uppercase tracking-widest px-1 mb-2.5 mt-6 first:mt-1">
      {title}
    </p>
  );
}

function Row({
  icon, label, value, onClick, danger = false,
}: {
  icon: string; label: string; value?: string; onClick?: () => void; danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`flex items-center gap-3.5 w-full px-4 sm:px-5 py-3.5 border-b border-border/60 last:border-0 transition-colors text-left ${
        danger ? "hover:bg-error/5" : onClick ? "hover:bg-surface-secondary/40" : "cursor-default"
      }`}
    >
      <span className={`material-symbols-outlined text-[18px] shrink-0 ${danger ? "text-error" : "text-foreground-secondary"}`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-semibold ${danger ? "text-error" : "text-foreground"}`}>{label}</p>
        {value && <p className="text-[11px] text-foreground-secondary mt-0.5 truncate">{value}</p>}
      </div>
      {onClick && (
        <span className={`material-symbols-outlined text-[18px] shrink-0 ${danger ? "text-error/50" : "text-foreground-secondary"}`}>
          chevron_right
        </span>
      )}
    </button>
  );
}

export default function AccountSettingsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  /* ── Change password state ── */
  const [showChangePw, setShowChangePw]     = useState(false);
  const [currentPw, setCurrentPw]           = useState("");
  const [newPw, setNewPw]                   = useState("");
  const [confirmPw, setConfirmPw]           = useState("");
  const [pwError, setPwError]               = useState("");
  const [pwSuccess, setPwSuccess]           = useState(false);
  const [pwLoading, setPwLoading]           = useState(false);

  /* ── Change email state ── */
  const [showChangeEmail, setShowChangeEmail] = useState(false);
  const [newEmail, setNewEmail]               = useState("");
  const [emailError, setEmailError]           = useState("");
  const [emailSuccess, setEmailSuccess]       = useState(false);
  const [emailLoading, setEmailLoading]       = useState(false);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await apiRequest("/api/users/profile/");
      if (res.success) setUser(res.user);
    } catch (_err: unknown) {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  async function handleChangePassword() {
    if (!currentPw) { setPwError("Enter your current password."); return; }
    if (newPw.length < 8) { setPwError("New password must be at least 8 characters."); return; }
    if (newPw !== confirmPw) { setPwError("Passwords do not match."); return; }
    setPwLoading(true); setPwError("");
    try {
      const res = await apiRequest("/api/users/change-password/", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPw, new_password: newPw }),
      });
      if (res.success) {
        if (res.token) {
          localStorage.setItem("auth_token", res.token);
        }
        setPwSuccess(true);
        setTimeout(() => { setShowChangePw(false); setPwSuccess(false); setCurrentPw(""); setNewPw(""); setConfirmPw(""); }, 1500);
      } else {
        setPwError(res.error || "Failed to update password.");
      }
    } catch (_err: unknown) {
      setPwError("Something went wrong. Please try again.");
    } finally {
      setPwLoading(false);
    }
  }

  async function handleChangeEmail() {
    if (!newEmail.includes("@")) { setEmailError("Enter a valid email address."); return; }
    setEmailLoading(true); setEmailError("");
    try {
      const res = await apiRequest("/api/users/change-email/", {
        method: "POST",
        body: JSON.stringify({ new_email: newEmail }),
      });
      if (res.success) {
        setEmailSuccess(true);
        setTimeout(() => { setShowChangeEmail(false); setEmailSuccess(false); setNewEmail(""); fetchProfile(); }, 1800);
      } else {
        setEmailError(res.error || "Failed to update email.");
      }
    } catch (_err: unknown) {
      setEmailError("Something went wrong. Please try again.");
    } finally {
      setEmailLoading(false);
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
        title="Account Security"
        subtitle="Access & Credentials"
        onBack={() => navigate(-1)}
      />

      <div className="w-full max-w-2xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-6 pb-24 md:pb-12">
        <main className="flex-1 overflow-y-auto">
        <SectionHeader title="Access Credentials" />
        <div className="rounded-xl border border-border bg-surface overflow-hidden divide-y divide-border/60 shadow-xs">
          <Row
            icon="alternate_email"
            label="Account Handle"
            value={user?.username}
            onClick={() => navigate("/profile")}
          />
          {isGuest() ? (
            <Row
              icon="workspace_premium"
              label="Account Tier: Persistent Guest"
              value="Tap to upgrade to permanent account"
              onClick={() => navigate("/convert")}
            />
          ) : (
            <>
              <Row
                icon="mail"
                label="Email Address"
                value={user?.email}
                onClick={() => setShowChangeEmail(true)}
              />
              <Row
                icon="key"
                label="Password"
                value="••••••••"
                onClick={() => setShowChangePw(true)}
              />
            </>
          )}
        </div>

        <SectionHeader title="Security Status" />
        <div className="rounded-xl border border-border bg-surface overflow-hidden divide-y divide-border/60 shadow-xs">
          <Row
            icon={user?.email_verified ? "verified_user" : "gpp_maybe"}
            label="Email Verification"
            value={user?.email_verified ? "Verified and secured" : "Action required"}
            onClick={user?.email_verified ? undefined : () => navigate("/verify-email")}
          />
        </div>

        {/* Change Password Modal */}
        {showChangePw && (
          <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowChangePw(false)}>
            <div className="w-full max-w-sm bg-surface border border-border rounded-3xl p-6 flex flex-col gap-4 shadow-2xl" onClick={e => e.stopPropagation()}>
              <h2 className="font-editorial text-xl font-bold text-foreground">Update Password</h2>

              {pwSuccess ? (
                <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 text-primary text-xs font-semibold text-center">
                  Password updated successfully.
                </div>
              ) : (
                <>
                  <input
                    type="password"
                    placeholder="Current password"
                    value={currentPw}
                    onChange={e => setCurrentPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground px-3.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <input
                    type="password"
                    placeholder="New password (min. 8 characters)"
                    value={newPw}
                    onChange={e => setNewPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground px-3.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <input
                    type="password"
                    placeholder="Confirm new password"
                    value={confirmPw}
                    onChange={e => setConfirmPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground px-3.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />

                  {pwError && <p className="text-xs text-error">{pwError}</p>}

                  <div className="flex gap-2.5 mt-1">
                    <button
                      onClick={() => setShowChangePw(false)}
                      className="flex-1 h-11 rounded-xl border border-border text-foreground text-xs font-semibold hover:bg-surface-secondary transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleChangePassword}
                      disabled={pwLoading}
                      className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
                    >
                      {pwLoading ? <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" /> : "Save"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Change Email Modal */}
        {showChangeEmail && (
          <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowChangeEmail(false)}>
            <div className="w-full max-w-sm bg-surface border border-border rounded-3xl p-6 flex flex-col gap-4 shadow-2xl" onClick={e => e.stopPropagation()}>
              <h2 className="font-editorial text-xl font-bold text-foreground">Update Email Address</h2>

              {emailSuccess ? (
                <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 text-primary text-xs font-semibold text-center">
                  Email updated successfully.
                </div>
              ) : (
                <>
                  <input
                    type="email"
                    placeholder="New email address"
                    value={newEmail}
                    onChange={e => setNewEmail(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground px-3.5 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />

                  {emailError && <p className="text-xs text-error">{emailError}</p>}

                  <div className="flex gap-2.5 mt-1">
                    <button
                      onClick={() => setShowChangeEmail(false)}
                      className="flex-1 h-11 rounded-xl border border-border text-foreground text-xs font-semibold hover:bg-surface-secondary transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleChangeEmail}
                      disabled={emailLoading}
                      className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
                    >
                      {emailLoading ? <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" /> : "Update"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </main>
      </div>

      <BottomNav current="profile" />
    </div>
  );
}
