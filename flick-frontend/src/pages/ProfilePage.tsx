import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest, ApiError } from "../lib/api";
import { identifyUser, resetAnalyticsIdentity, trackEvent } from "../lib/analytics";
import { isGuest } from "../lib/auth";
import { resetAllTours } from "../lib/tutorial";
import { useAccessibleDialog } from "../lib/useAccessibleDialog";
import { useTheme } from "../context/ThemeContext";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

type UserProfile = {
  id?: number;
  username: string;
  email: string;
  date_joined?: string;
  total_matches?: number;
  total_swiped?: number;
  avatar_url?: string;
  display_name?: string;
};

function safeIsGuest(): boolean {
  try {
    return isGuest();
  } catch {
    return false;
  }
}

function MenuItem({
  icon,
  label,
  onClick,
  danger = false,
  showChevron = true,
}: {
  icon: string;
  label: string;
  onClick?: () => void;
  danger?: boolean;
  showChevron?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-3.5 w-full px-4 min-h-14 rounded-xl border transition-colors text-left cursor-pointer ${
        danger
          ? "bg-error/5 border-error/20 hover:bg-error/10 text-error"
          : "bg-surface border-border hover:bg-surface-secondary text-foreground"
      }`}
    >
      <div className={`flex items-center justify-center rounded-lg shrink-0 size-9 ${
        danger ? "bg-error/10 text-error" : "bg-surface-secondary text-foreground-secondary"
      }`}>
        <span className="material-symbols-outlined text-[18px]">{icon}</span>
      </div>
      <p className="text-sm font-semibold leading-normal flex-1 truncate">{label}</p>
      {showChevron && (
        <span className={`material-symbols-outlined text-[18px] shrink-0 ${danger ? "text-error/75" : "text-foreground-secondary"}`}>
          chevron_right
        </span>
      )}
    </button>
  );
}

function ThemeToggleItem({ isDark, onToggle }: { isDark: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label={`Toggle dark appearance (${isDark ? "currently dark" : "currently light"})`}
      onClick={onToggle}
      className="flex items-center gap-3.5 w-full px-4 min-h-14 rounded-xl border bg-surface border-border hover:bg-surface-secondary transition-colors text-left text-foreground cursor-pointer"
    >
      <div className="flex items-center justify-center rounded-lg shrink-0 size-9 bg-surface-secondary text-foreground-secondary">
        <span className="material-symbols-outlined text-[18px]">{isDark ? "dark_mode" : "light_mode"}</span>
      </div>
      <p className="text-sm font-semibold leading-normal flex-1 truncate">
        {isDark ? "Dark Theme" : "Light Theme"}
      </p>
      <div className={`relative w-10 h-5 rounded-full transition-colors shrink-0 ${isDark ? "bg-primary" : "bg-surface-secondary border border-border"}`}>
        <div className={`absolute top-0.5 size-4 rounded-full bg-surface shadow-xs transition-transform ${isDark ? "translate-x-5" : "translate-x-0.5"}`} />
      </div>
    </button>
  );
}

export default function ProfilePage() {
  const navigate = useNavigate();
  const { isDark, toggleTheme } = useTheme();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [editingDisplayName, setEditingDisplayName] = useState(false);
  const [newDisplayName, setNewDisplayName] = useState("");
  const [displayNameLoading, setDisplayNameLoading] = useState(false);
  const [error, setError] = useState("");
  const [saveLoading, setSaveLoading] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const [emailVerified, setEmailVerified] = useState<boolean | null>(null);
  const [tutorialsResetNotice, setTutorialsResetNotice] = useState(false);
  const resetNoticeTimerRef = useRef<number | null>(null);
  const deleteDialogRef = useRef<HTMLDivElement>(null);

  const closeDeleteModal = useCallback(() => {
    setShowDeleteConfirm(false);
    setDeletePassword("");
    setDeleteError("");
  }, []);

  useAccessibleDialog(showDeleteConfirm, () => !deleteLoading && closeDeleteModal(), deleteDialogRef);

  useEffect(() => {
    return () => {
      if (resetNoticeTimerRef.current !== null) {
        window.clearTimeout(resetNoticeTimerRef.current);
      }
    };
  }, []);

  const fetchUserProfile = useCallback(async () => {
    try {
      const response = await apiRequest("/api/users/profile/");
      if (response.success) {
        setUser(response.user);
        setNewUsername(response.user.username);
        setNewDisplayName(response.user.display_name || "");
        if (response.user.id !== undefined && response.user.id !== null) {
          try {
            const nextUserId = String(response.user.id);
            if (localStorage.getItem("user_id") !== nextUserId) {
              localStorage.setItem("user_id", nextUserId);
            }
          } catch {
            // Ignore storage access errors
          }
          identifyUser(response.user.id, {
            is_guest: safeIsGuest(),
            username: response.user.username,
          });
        }
        if (response.user.display_name) {
          try {
            localStorage.setItem("display_name", response.user.display_name);
          } catch {
            // Ignore storage access errors
          }
        }
        if (response.user.avatar_url) setAvatarPreview(response.user.avatar_url);
        if (response.user.email_verified !== undefined) setEmailVerified(response.user.email_verified);
      }
    } catch {
      navigate("/");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  const handleReplayTutorials = () => {
    try {
      resetAllTours({ userId: user?.id, username: user?.username });
    } catch {
      // Ignore storage access errors
    }
    trackEvent("tutorial_replayed");
    setTutorialsResetNotice(true);
    if (resetNoticeTimerRef.current !== null) {
      window.clearTimeout(resetNoticeTimerRef.current);
    }
    resetNoticeTimerRef.current = window.setTimeout(() => {
      setTutorialsResetNotice(false);
      resetNoticeTimerRef.current = null;
    }, 8000);
  };

  useEffect(() => {
    fetchUserProfile();
  }, [fetchUserProfile]);

  const handleSaveDisplayName = async () => {
    if (!newDisplayName.trim()) { setError("Display name cannot be empty"); return; }
    if (newDisplayName.trim() === user?.display_name) { setEditingDisplayName(false); setError(""); return; }
    setDisplayNameLoading(true); setError("");
    try {
      const response = await apiRequest("/api/users/profile/", {
        method: "PATCH",
        body: JSON.stringify({ display_name: newDisplayName.trim() }),
      });
      if (response.success) {
        setUser(prev => (prev ? { ...prev, display_name: newDisplayName.trim() } : prev));
        localStorage.setItem("display_name", newDisplayName.trim());
        setEditingDisplayName(false);
        setError("");
      } else {
        setError(response.error || "Failed to update display name");
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Failed to update display name");
    } finally {
      setDisplayNameLoading(false);
    }
  };

  const handleSaveUsername = async () => {
    if (!newUsername.trim()) { setError("Username cannot be empty"); return; }
    if (newUsername.trim() === user?.username) { setEditing(false); setError(""); return; }
    setSaveLoading(true); setError("");
    try {
      const response = await apiRequest("/api/users/update-username/", {
        method: "POST",
        body: JSON.stringify({ username: newUsername.trim() }),
      });
      if (response.success) {
        setUser(prev => (prev ? { ...prev, username: newUsername.trim() } : prev));
        setEditing(false); setError("");
      } else {
        setError(response.error || "Failed to update username");
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Failed to update username");
    } finally {
      setSaveLoading(false);
    }
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = ev => setAvatarPreview(ev.target?.result as string);
    reader.readAsDataURL(file);

    setAvatarLoading(true);
    try {
      const base64 = await new Promise<string>((res, rej) => {
        const r = new FileReader();
        r.onload = () => res((r.result as string).split(",")[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
      });
      const response = await apiRequest("/api/users/upload-avatar/", {
        method: "POST",
        body: JSON.stringify({ avatar_base64: base64, content_type: file.type }),
      });
      if (response.avatar_url) {
        setAvatarPreview(response.avatar_url);
        setUser(prev => (prev ? { ...prev, avatar_url: response.avatar_url } : prev));
      }
    } catch {
      /* silent */
    } finally {
      setAvatarLoading(false);
    }
  };

  const handleDeleteAccount = async () => {
    if (!deletePassword) { setDeleteError("Please enter your password to confirm."); return; }
    setDeleteLoading(true); setDeleteError("");
    try {
      const res = await apiRequest("/api/users/delete-account/", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword }),
      });
      if (res.success) {
        ["auth_token", "username", "display_name", "email", "user_id"].forEach(k =>
          localStorage.removeItem(k)
        );
        resetAnalyticsIdentity();
        navigate("/", { replace: true });
      } else {
        setDeleteError(res.error || "Failed to delete account.");
      }
    } catch (err: unknown) {
      setDeleteError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleLogout = () => {
    ["auth_token", "username", "display_name", "email", "user_id"].forEach(k =>
      localStorage.removeItem(k)
    );
    resetAnalyticsIdentity();
    navigate("/");
  };

  if (loading) {
    return (
      <div className="bg-background font-sans text-foreground min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-foreground-secondary text-xs uppercase tracking-widest font-semibold">Loading Member Dossier...</p>
        </div>
      </div>
    );
  }

  const joinDate = user?.date_joined
    ? new Date(user.date_joined).toLocaleDateString("en-US", { month: "long", year: "numeric" })
    : null;

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* Editorial Header */}
      <CinemaHeader
        current="profile"
        title="Member Profile"
        onBack={() => navigate(-1)}
      />

      <main className="w-full max-w-2xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-6 pb-24 md:pb-12">

        {/* Avatar + Name */}
        <div className="flex flex-col items-center gap-3.5 pt-6 pb-2">
          <div className="relative">
            <div className="size-24 rounded-full overflow-hidden bg-surface-secondary border-2 border-border flex items-center justify-center shadow-sm">
              {avatarPreview ? (
                <img src={avatarPreview} alt="avatar" className="w-full h-full object-cover" />
              ) : (
                <span className="font-editorial text-3xl font-bold text-primary">{user?.username?.[0]?.toUpperCase() ?? "?"}</span>
              )}
              {avatarLoading && (
                <div className="absolute inset-0 bg-black/40 flex items-center justify-center rounded-full">
                  <div className="size-5 border-2 border-surface border-t-transparent rounded-full animate-spin" />
                </div>
              )}
            </div>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="absolute -bottom-1 -right-1 bg-primary text-primary-foreground rounded-full size-11 sm:size-9 flex items-center justify-center shadow-sm hover:bg-primary-hover transition-colors cursor-pointer"
              aria-label="Change portrait"
            >
              <span className="material-symbols-outlined text-[18px]">photo_camera</span>
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarChange}
            />
          </div>

          {editing ? (
            <div className="w-full max-w-xs flex flex-col items-center gap-3 mt-1">
              <input
                type="text"
                aria-label="New handle"
                value={newUsername}
                onChange={e => setNewUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))}
                placeholder="New handle"
                maxLength={20}
                className="w-full rounded-xl border border-border bg-surface text-foreground placeholder:text-foreground-secondary/75 text-center text-sm font-semibold h-11 px-4 focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
              />
              {error && <p role="alert" className="text-xs text-error">{error}</p>}
              <div className="flex gap-2 w-full">
                <button
                  type="button"
                  onClick={() => { setEditing(false); setNewUsername(user?.username ?? ""); setError(""); }}
                  className="flex-1 min-h-11 sm:min-h-9 rounded-lg border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveUsername}
                  disabled={saveLoading}
                  className="flex-1 min-h-11 sm:min-h-9 rounded-lg bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center cursor-pointer"
                >
                  {saveLoading ? <span className="size-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Save"}
                </button>
              </div>
            </div>
          ) : editingDisplayName ? (
            <div className="w-full max-w-xs flex flex-col items-center gap-3 mt-1">
              <input
                type="text"
                aria-label="Display name"
                value={newDisplayName}
                onChange={e => setNewDisplayName(e.target.value)}
                placeholder="Your Display Name"
                maxLength={50}
                className="w-full rounded-xl border border-border bg-surface text-foreground placeholder:text-foreground-secondary/75 text-center text-sm font-semibold h-11 px-4 focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary"
              />
              {error && <p role="alert" className="text-xs text-error">{error}</p>}
              <div className="flex gap-2 w-full">
                <button
                  type="button"
                  onClick={() => { setEditingDisplayName(false); setNewDisplayName(user?.display_name ?? ""); setError(""); }}
                  className="flex-1 min-h-11 sm:min-h-9 rounded-lg border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveDisplayName}
                  disabled={displayNameLoading}
                  className="flex-1 min-h-11 sm:min-h-9 rounded-lg bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center cursor-pointer"
                >
                  {displayNameLoading ? <span className="size-3.5 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" /> : "Save"}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-0.5">
              <p className="font-editorial text-2xl font-bold text-foreground text-center">
                {user?.display_name || user?.username || "—"}
              </p>
              <p className="text-sm text-foreground-secondary text-center">@{user?.username} · {user?.email}</p>
              {joinDate && <p className="text-xs text-foreground-secondary mt-0.5 uppercase tracking-wider">Member since {joinDate}</p>}
              <div className="flex items-center gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => { setEditingDisplayName(true); setEditing(false); setError(""); }}
                  className="min-h-11 sm:min-h-9 px-3 rounded-lg text-sm font-semibold text-primary hover:underline cursor-pointer"
                >
                  Edit Name
                </button>
                <span className="text-foreground-secondary/75 text-xs" aria-hidden="true">·</span>
                <button
                  type="button"
                  onClick={() => { setEditing(true); setEditingDisplayName(false); setError(""); }}
                  className="min-h-11 sm:min-h-9 px-3 rounded-lg text-sm font-semibold text-foreground-secondary hover:text-foreground hover:underline cursor-pointer"
                >
                  Edit Handle
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 py-4">
          <div className="flex flex-col gap-0.5 rounded-xl bg-surface border border-border p-4 items-center text-center shadow-xs">
            <p className="font-editorial text-2xl font-bold text-primary">{user?.total_matches ?? "—"}</p>
            <p className="text-foreground-secondary text-xs font-semibold uppercase tracking-widest">Consensus</p>
          </div>
          <div className="flex flex-col gap-0.5 rounded-xl bg-surface border border-border p-4 items-center text-center shadow-xs">
            <p className="font-editorial text-2xl font-bold text-primary">
              {user?.total_swiped
                ? user.total_swiped >= 1000 ? `${(user.total_swiped / 1000).toFixed(1)}k` : user.total_swiped
                : "—"}
            </p>
            <p className="text-foreground-secondary text-xs font-semibold uppercase tracking-widest">Reviewed</p>
          </div>
        </div>

        {/* Guest Upgrade Callout Banner */}
        {safeIsGuest() && (
          <div className="mb-4 p-4 rounded-xl bg-primary/10 border border-primary/25 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-2xs">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-primary text-[22px] shrink-0 mt-0.5">
                workspace_premium
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">Guest Member Journal</p>
                <p className="text-xs text-foreground-secondary mt-0.5 leading-snug">
                  Claim your journal with email and password to access on any browser.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => navigate("/convert")}
              className="shrink-0 min-h-11 sm:min-h-9 px-4 rounded-lg bg-primary hover:bg-primary-hover text-primary-foreground text-sm font-semibold uppercase tracking-wider transition-colors shadow-2xs flex items-center gap-1.5 cursor-pointer"
            >
              <span>Upgrade</span>
              <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
            </button>
          </div>
        )}

        {/* Menu Items */}
        <div className="flex flex-col gap-2 pt-1">
          <MenuItem icon="history" label="Screening Archives" onClick={() => navigate("/sessions?tab=history")} />
          <MenuItem icon="bookmark" label="Personal Watchlist" onClick={() => navigate("/watchlist")} />
          <MenuItem icon="person" label="Account Security & Access" onClick={() => navigate("/account-settings")} />
          <MenuItem icon="notifications" label="Notification Preferences" onClick={() => navigate("/notifications-settings")} />
          <ThemeToggleItem isDark={isDark} onToggle={toggleTheme} />
          <MenuItem
            icon="school"
            label="Replay Tutorials"
            onClick={handleReplayTutorials}
            showChevron={false}
          />
          {tutorialsResetNotice && (
            <div
              role="status"
              aria-live="polite"
              className="p-3 rounded-xl bg-primary/10 border border-primary/25 flex items-center justify-between gap-3"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <span className="material-symbols-outlined text-primary text-[18px] shrink-0">
                  check_circle
                </span>
                <p className="text-xs font-medium text-foreground leading-snug">
                  Tutorials reset — visit Home or a Screening to view them again.
                </p>
              </div>
              <button
                type="button"
                onClick={() => navigate("/home")}
                className="inline-flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center text-xs font-semibold text-primary bg-primary/15 hover:bg-primary/25 px-3.5 rounded-lg transition-colors cursor-pointer touch-manipulation"
              >
                Go to Home
              </button>
            </div>
          )}
          <MenuItem icon="security" label="Privacy & Data Policy" onClick={() => navigate("/privacy")} />
          <MenuItem icon="gavel" label="Terms of Service" onClick={() => navigate("/terms")} />
          <MenuItem
            icon="mail"
            label="Support & Feedback"
            onClick={() => {
              window.location.href = "mailto:discoverflick@gmail.com?subject=Flick Support & Feedback";
            }}
          />

          {/* Email verification alert */}
          {emailVerified === false && !safeIsGuest() && (
            <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center gap-3">
              <span className="material-symbols-outlined text-amber-600 dark:text-amber-400 text-lg shrink-0">mail_lock</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-amber-800 dark:text-amber-300">Email Unverified</p>
                <p className="text-xs text-amber-800 dark:text-amber-300">Confirm address to protect account access</p>
              </div>
              <button
                type="button"
                onClick={() => navigate("/verify-email")}
                className="shrink-0 min-h-11 sm:min-h-9 text-sm font-semibold text-amber-900 dark:text-amber-200 bg-amber-500/25 px-3.5 rounded-md hover:bg-amber-500/35 transition-colors cursor-pointer"
              >
                Verify
              </button>
            </div>
          )}

          <div className="mt-3 flex flex-col gap-2">
            <MenuItem
              icon="delete_forever"
              label="Delete Member Account"
              onClick={() => setShowDeleteConfirm(true)}
              danger={true}
              showChevron={true}
            />
            <MenuItem
              icon="logout"
              label="Sign Out"
              onClick={handleLogout}
              danger={true}
              showChevron={false}
            />
          </div>

          {/* Delete Account Modal */}
          {showDeleteConfirm && (
            <div
              className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm p-4"
              onClick={() => !deleteLoading && closeDeleteModal()}
            >
              <div
                ref={deleteDialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="delete-account-dialog-title"
                tabIndex={-1}
                className="w-full max-w-sm bg-surface border border-error/30 rounded-3xl p-6 flex flex-col gap-4 shadow-2xl"
                onClick={e => e.stopPropagation()}
              >
                <div className="flex flex-col items-center text-center gap-2">
                  <span className="material-symbols-outlined text-error text-3xl">delete_forever</span>
                  <h2 id="delete-account-dialog-title" className="font-editorial text-xl font-bold text-foreground">Delete Account?</h2>
                  <p className="text-sm text-foreground-secondary leading-relaxed">
                    This permanently deletes your account, screening history, and saved watchlist items. This action cannot be undone.
                  </p>
                </div>

                <input
                  type="password"
                  aria-label="Current password"
                  value={deletePassword}
                  onChange={e => { setDeletePassword(e.target.value); setDeleteError(""); }}
                  placeholder="Enter current password"
                  className="w-full h-11 rounded-xl border border-border bg-surface-secondary text-foreground placeholder:text-foreground-secondary/75 px-3.5 text-sm focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-error"
                />

                {deleteError && (
                  <p role="alert" className="text-xs text-error text-center -mt-1">{deleteError}</p>
                )}

                <div className="flex gap-2.5">
                  <button
                    type="button"
                    onClick={closeDeleteModal}
                    disabled={deleteLoading}
                    className="flex-1 min-h-11 rounded-xl border border-border text-foreground text-sm font-semibold hover:bg-surface-secondary transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleDeleteAccount}
                    disabled={deleteLoading}
                    className="flex-1 min-h-11 rounded-xl bg-error hover:opacity-90 text-surface text-sm font-semibold uppercase tracking-wider transition-colors disabled:opacity-60 flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    {deleteLoading ? (
                      <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
                    ) : (
                      "Confirm Delete"
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Bottom Nav */}
      <BottomNav current="profile" />
    </div>
  );
}
