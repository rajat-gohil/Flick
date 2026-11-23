import React, { useState, useEffect } from "react";
import { recoverGuest } from "../lib/api";
import { saveAuthState } from "../lib/auth";
import { coordinateGuestProvisioning } from "../services/guestProvisionCoordinator";

interface AuthRecoveryPromptProps {
  isOpen?: boolean;
  onClose?: () => void;
  onSuccess?: () => void;
}

export const AuthRecoveryPrompt: React.FC<AuthRecoveryPromptProps> = ({
  isOpen: propsIsOpen,
  onClose,
  onSuccess,
}) => {
  const [isOpen, setIsOpen] = useState(propsIsOpen ?? false);
  const [showRestoreForm, setShowRestoreForm] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (propsIsOpen !== undefined) {
      setIsOpen(propsIsOpen);
    }
  }, [propsIsOpen]);

  useEffect(() => {
    const handleAuthExpired = () => {
      setIsOpen(true);
      setShowRestoreForm(false);
      setErrorMessage(null);
    };

    window.addEventListener("flick:auth_expired", handleAuthExpired);
    return () => {
      window.removeEventListener("flick:auth_expired", handleAuthExpired);
    };
  }, []);

  if (!isOpen) return null;

  const handleClose = () => {
    setIsOpen(false);
    if (onClose) onClose();
  };

  const handleStartFresh = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      localStorage.removeItem("flick_provisioning_key");
      localStorage.removeItem("flick_provisioning_key_ts");
      const res = await coordinateGuestProvisioning();
      if (res && res.token) {
        handleClose();
        if (onSuccess) onSuccess();
        window.location.reload();
      }
    } catch (err: any) {
      setErrorMessage("Failed to start a new session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleRestoreSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recoveryCode.trim()) {
      setErrorMessage("Please enter your recovery code.");
      return;
    }

    setLoading(true);
    setErrorMessage(null);

    try {
      const res = await recoverGuest(recoveryCode.trim());
      if (res && res.success && res.token) {
        saveAuthState({
          token: res.token,
          user: res.user,
        });
        handleClose();
        if (onSuccess) onSuccess();
        window.location.reload();
      } else {
        setErrorMessage("Invalid recovery code. Please check the code and try again.");
      }
    } catch (err: any) {
      // Per spec: Generic 400 error message handling
      const message =
        err?.data?.error ||
        err?.message ||
        "Invalid recovery code. Please check the code and try again.";
      setErrorMessage(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4"
    >
      <div className="relative w-full max-w-md rounded-2xl bg-surface border border-border p-6 sm:p-7 text-foreground shadow-2xl">
        <div className="h-1 w-12 bg-primary rounded-full mb-3" />
        {onClose && (
          <button
            type="button"
            onClick={handleClose}
            className="absolute top-4 right-4 text-foreground-secondary hover:text-foreground size-8 flex items-center justify-center rounded-full hover:bg-surface-secondary transition-colors"
            aria-label="Close"
          >
            <span className="material-symbols-outlined text-[18px]">close</span>
          </button>
        )}
        <h2 className="font-editorial text-2xl font-semibold tracking-tight text-foreground mb-1.5">Session Expired</h2>
        <p className="text-xs sm:text-sm text-foreground-secondary mb-6 leading-relaxed">
          Your session could not be authenticated. You can restore your previous journal using a
          recovery code, or start completely fresh.
        </p>

        {errorMessage && (
          <div
            role="alert"
            className="mb-4 p-3 rounded-xl bg-error/10 border border-error/25 text-error text-xs leading-relaxed"
          >
            {errorMessage}
          </div>
        )}

        {!showRestoreForm ? (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setShowRestoreForm(true)}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-surface font-semibold text-sm transition-colors text-center cursor-pointer shadow-xs"
            >
              Restore Journal
            </button>
            <button
              onClick={handleStartFresh}
              disabled={loading}
              className="w-full h-12 rounded-full bg-surface-secondary hover:bg-surface border border-border text-foreground font-semibold text-sm transition-colors text-center disabled:opacity-50 cursor-pointer"
            >
              {loading ? "Starting Fresh..." : "Start Fresh"}
            </button>
          </div>
        ) : (
          <form onSubmit={handleRestoreSubmit} className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="recovery-code-input"
                className="block text-[11px] font-semibold uppercase tracking-wider text-foreground-secondary mb-1.5"
              >
                Recovery Code
              </label>
              <input
                id="recovery-code-input"
                type="text"
                value={recoveryCode}
                onChange={(e) => setRecoveryCode(e.target.value.toUpperCase())}
                placeholder="FLICK-XXXX-XXXX-XXXX"
                className="w-full h-12 rounded-xl bg-surface-secondary border border-border px-3.5 text-sm text-foreground placeholder:text-foreground-secondary/40 font-mono tracking-wider focus:outline-none focus:ring-1 focus:ring-primary"
                autoFocus
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowRestoreForm(false);
                  setErrorMessage(null);
                }}
                className="flex-1 h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-xs font-semibold text-foreground transition-colors cursor-pointer"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface text-xs font-semibold uppercase tracking-wider transition-colors disabled:opacity-50 cursor-pointer shadow-xs"
              >
                {loading ? "Restoring..." : "Submit Code"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
};

export default AuthRecoveryPrompt;
