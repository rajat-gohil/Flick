import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { isGuest } from "../lib/auth";
import { useAccessibleDialog } from "../lib/useAccessibleDialog";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type UserProfile = {
  username: string;
  email: string;
  date_joined?: string;
  email_verified?: boolean;
  is_guest?: boolean;
  recovery_code?: string;
};

function SectionHeader({ title }: { title: string }) {
  return (
    <p className="text-xs font-semibold text-primary uppercase tracking-widest px-1 mb-2.5 mt-6 first:mt-1">
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
      type="button"
      onClick={onClick}
      disabled={!onClick}
      className={`flex items-center gap-3.5 w-full min-h-11 px-4 sm:px-5 py-3.5 border-b border-border/60 last:border-0 transition-colors text-left ${
        danger ? "hover:bg-error/5" : onClick ? "hover:bg-surface-secondary/40" : "cursor-default"
      }`}
    >
      <span className={`material-symbols-outlined text-[18px] shrink-0 ${danger ? "text-error" : "text-foreground-secondary"}`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-semibold ${danger ? "text-error" : "text-foreground"}`}>{label}</p>
        {value && <p className="text-xs text-foreground-secondary mt-0.5 truncate">{value}</p>}
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
  const isGuestAccount = user ? Boolean(user.is_guest) : isGuest();
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

  /* ── Recovery code state for guests ── */
  const [recoveryCode, setRecoveryCode]       = useState("");
  const [showCode, setShowCode]               = useState(false);
  const [copiedCode, setCopiedCode]           = useState(false);
  const [rotatingCode, setRotatingCode]       = useState(false);
  const [rotateSuccess, setRotateSuccess]     = useState(false);
  const [rotateError, setRotateError]         = useState("");
  const [showRotateConfirm, setShowRotateConfirm] = useState(false);

  const changePwDialogRef = useRef<HTMLDivElement>(null);
  const changeEmailDialogRef = useRef<HTMLDivElement>(null);
  const rotateDialogRef = useRef<HTMLDivElement>(null);

  useAccessibleDialog(showChangePw, () => setShowChangePw(false), changePwDialogRef);
  useAccessibleDialog(showChangeEmail, () => setShowChangeEmail(false), changeEmailDialogRef);
  useAccessibleDialog(showRotateConfirm, () => !rotatingCode && setShowRotateConfirm(false), rotateDialogRef);

  const fetchProfile = useCallback(async () => {
    try {
      const res = await apiRequest("/api/users/profile/");
      if (res.success && res.user) {
        setUser(res.user);
        if (res.user.is_guest === false) {
          localStorage.setItem("is_guest", "false");
        }
        if (res.user.recovery_code) {
          setRecoveryCode(res.user.recovery_code);
        }
      }
    } catch {
      // ignore
    }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchProfile(); }, [fetchProfile]);

  async function handleCopyCode() {
    if (!recoveryCode) return;
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(recoveryCode);
        setCopiedCode(true);
        setTimeout(() => setCopiedCode(false), 2000);
      }
    } catch {
      // fallback
    }
  }

  async function handleRotateCode() {
    setRotatingCode(true);
    setRotateError("");
    try {
      const res = await apiRequest("/api/auth/guest-rotate-code/", { method: "POST" });
      if (res.success && res.recovery_code) {
        setRecoveryCode(res.recovery_code);
        setRotateSuccess(true);
        setShowCode(true);
        setShowRotateConfirm(false);
        setTimeout(() => setRotateSuccess(false), 3000);
      }
    } catch {
      // ignore
    } finally {
      setRotatingCode(false);
    }
  }

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
    } catch {
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
    } catch {
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

        {/* ── Guest Recovery Code Card ── */}
        {isGuestAccount && (
          <div className="mt-4 p-4 sm:p-5 rounded-xl border border-primary/25 bg-surface shadow-xs space-y-3.5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <span className="material-symbols-outlined text-[20px] text-primary">key</span>
                <div>
                  <p className="text-sm font-semibold text-foreground">Guest Recovery Code</p>
                  <p className="text-xs text-foreground-secondary mt-0.5">Save this code to restore your guest session on another device</p>
                </div>
              </div>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-primary/10 text-primary border border-primary/20 shrink-0">
                Active Key
              </span>
            </div>

            {/* Code display block */}
            <div className="flex items-center justify-between gap-2 p-3 rounded-lg bg-surface-secondary border border-border">
              <p className="font-mono text-sm font-semibold tracking-wider text-foreground select-all break-all">
                {recoveryCode ? (showCode ? recoveryCode : "•••• •••• •••• ••••") : "Generating / fetching code…"}
              </p>
              <div className="flex items-center gap-1.5 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowCode(!showCode)}
                  title={showCode ? "Hide code" : "Reveal code"}
                  aria-label={showCode ? "Hide recovery code" : "Reveal recovery code"}
                  className="size-11 sm:size-9 rounded-md hover:bg-surface border border-transparent hover:border-border flex items-center justify-center text-foreground-secondary transition-colors cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showCode ? "visibility_off" : "visibility"}
                  </span>
                </button>
                <button
                  type="button"
                  onClick={handleCopyCode}
                  title="Copy recovery code"
                  className="min-h-11 sm:min-h-9 px-3 rounded-md bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold flex items-center gap-1.5 transition-colors shadow-2xs cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px]">
                    {copiedCode ? "check" : "content_copy"}
                  </span>
                  <span>{copiedCode ? "Copied!" : "Copy"}</span>
                </button>
              </div>
            </div>

            {rotateSuccess && (
              <p className="text-xs text-primary font-medium">✓ New recovery code generated and saved to your device.</p>
            )}

            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-foreground-secondary pt-2 border-t border-border/50">
              <p className="leading-relaxed">
                Save this in a password manager to restore your session if you clear browser cache or change phones.
              </p>
              <button
                type="button"
                onClick={() => { setRotateError(""); setShowRotateConfirm(true); }}
                disabled={rotatingCode}
                className="min-h-11 sm:min-h-9 px-2 text-sm font-semibold text-primary hover:underline disabled:opacity-50 shrink-0 text-left sm:text-right cursor-pointer"
              >
                {rotatingCode ? "Generating…" : "Generate New Code"}
              </button>
            </div>
          </div>
        )}

        <SectionHeader title="Security Status" />
        <div className="rounded-xl border border-border bg-surface overflow-hidden divide-y divide-border/60 shadow-xs">
          <Row
            icon={isGuestAccount ? "gpp_maybe" : "verified_user"}
            label="Account Security"
            value={isGuestAccount ? "Guest session — add an email to save your account" : "Email & password verified"}
            onClick={isGuestAccount ? () => navigate("/convert") : undefined}
          />
        </div>

        {/* Rotate Recovery Code Confirmation Modal */}
        {showRotateConfirm && (
          <div
            className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4"
            onClick={() => !rotatingCode && setShowRotateConfirm(false)}
          >
            <div
              ref={rotateDialogRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="rotate-code-dialog-title"
              tabIndex={-1}
              className="w-full max-w-sm bg-surface border border-border rounded-3xl p-6 flex flex-col gap-4 shadow-2xl"
              onClick={e => e.stopPropagation()}
            >
              <h2 id="rotate-code-dialog-title" className="font-editorial text-xl font-bold text-foreground">
                Generate New Recovery Code?
              </h2>
              <p className="text-sm text-foreground-secondary leading-relaxed">
                Your previous recovery code will stop working immediately. Make sure to save the new code once it is generated.
              </p>
              {rotateError && <p role="alert" className="text-xs text-error">{rotateError}</p>}
              <div className="flex gap-2.5 mt-1">
                <button
                  type="button"
                  onClick={() => setShowRotateConfirm(false)}
                  disabled={rotatingCode}
                  className="flex-1 min-h-11 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleRotateCode}
                  disabled={rotatingCode}
                  className="flex-1 min-h-11 rounded-xl bg-error hover:bg-error/90 text-white text-sm font-semibold transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs cursor-pointer"
                >
                  {rotatingCode ? <span className="size-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : "Generate New Code"}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Change Password Modal */}
        {showChangePw && (
          <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowChangePw(false)}>
            <div
              ref={changePwDialogRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="change-pw-dialog-title"
              tabIndex={-1}
              className="w-full max-w-sm bg-surface border border-border rounded-3xl p-6 flex flex-col gap-4 shadow-2xl"
              onClick={e => e.stopPropagation()}
            >
              <h2 id="change-pw-dialog-title" className="font-editorial text-xl font-bold text-foreground">Update Password</h2>

              {pwSuccess ? (
                <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 text-primary text-sm font-semibold text-center">
                  Password updated successfully.
                </div>
              ) : (
                <>
                  <input
                    type="password"
                    aria-label="Current password"
                    placeholder="Current password"
                    value={currentPw}
                    onChange={e => setCurrentPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground placeholder:text-foreground-secondary/75 px-3.5 text-sm focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
                  />
                  <input
                    type="password"
                    aria-label="New password"
                    placeholder="New password (min. 8 characters)"
                    value={newPw}
                    onChange={e => setNewPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground placeholder:text-foreground-secondary/75 px-3.5 text-sm focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
                  />
                  <input
                    type="password"
                    aria-label="Confirm new password"
                    placeholder="Confirm new password"
                    value={confirmPw}
                    onChange={e => setConfirmPw(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground placeholder:text-foreground-secondary/75 px-3.5 text-sm focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
                  />

                  {pwError && <p role="alert" className="text-xs text-error">{pwError}</p>}

                  <div className="flex gap-2.5 mt-1">
                    <button
                      type="button"
                      onClick={() => setShowChangePw(false)}
                      className="flex-1 min-h-11 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleChangePassword}
                      disabled={pwLoading}
                      className="flex-1 min-h-11 rounded-xl bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs cursor-pointer"
                    >
                      {pwLoading ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Save"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Change Email Modal */}
        {showChangeEmail && (
          <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowChangeEmail(false)}>
            <div
              ref={changeEmailDialogRef}
              role="dialog"
              aria-modal="true"
              aria-labelledby="change-email-dialog-title"
              tabIndex={-1}
              className="w-full max-w-sm bg-surface border border-border rounded-3xl p-6 flex flex-col gap-4 shadow-2xl"
              onClick={e => e.stopPropagation()}
            >
              <h2 id="change-email-dialog-title" className="font-editorial text-xl font-bold text-foreground">Update Email Address</h2>

              {emailSuccess ? (
                <div className="p-4 rounded-xl bg-primary/10 border border-primary/30 text-primary text-sm font-semibold text-center">
                  Email updated successfully.
                </div>
              ) : (
                <>
                  <input
                    type="email"
                    aria-label="New email address"
                    placeholder="New email address"
                    value={newEmail}
                    onChange={e => setNewEmail(e.target.value)}
                    className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground placeholder:text-foreground-secondary/75 px-3.5 text-sm focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
                  />

                  {emailError && <p role="alert" className="text-xs text-error">{emailError}</p>}

                  <div className="flex gap-2.5 mt-1">
                    <button
                      type="button"
                      onClick={() => setShowChangeEmail(false)}
                      className="flex-1 min-h-11 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleChangeEmail}
                      disabled={emailLoading}
                      className="flex-1 min-h-11 rounded-xl bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs cursor-pointer"
                    >
                      {emailLoading ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Update"}
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
