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

  const handleStartFresh = async () => {
    setLoading(true);
    setErrorMessage(null);
    try {
      localStorage.removeItem("flick_provisioning_key");
      localStorage.removeItem("flick_provisioning_key_ts");
      const res = await coordinateGuestProvisioning();
      if (res && res.token) {
        setIsOpen(false);
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
        setIsOpen(false);
        if (onSuccess) onSuccess();
        window.location.reload();
      } else {
        setErrorMessage(res?.error || "Invalid recovery code. Please check the code and try again.");
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
    >
      <div className="w-full max-w-md rounded-2xl bg-[#121218] border border-white/10 p-6 text-white shadow-2xl">
        <h2 className="text-xl font-bold tracking-tight mb-2">Session Expired</h2>
        <p className="text-sm text-slate-300 mb-6 leading-relaxed">
          Your session could not be authenticated. You can restore your previous journal using a
          recovery code, or start completely fresh.
        </p>

        {errorMessage && (
          <div
            role="alert"
            className="mb-4 p-3 rounded-lg bg-red-950/60 border border-red-500/30 text-red-200 text-xs leading-relaxed"
          >
            {errorMessage}
          </div>
        )}

        {!showRestoreForm ? (
          <div className="flex flex-col gap-3">
            <button
              onClick={() => setShowRestoreForm(true)}
              className="w-full py-3 px-4 rounded-xl bg-violet-600 hover:bg-violet-500 font-semibold text-sm transition-colors text-center"
            >
              Restore Journal
            </button>
            <button
              onClick={handleStartFresh}
              disabled={loading}
              className="w-full py-3 px-4 rounded-xl bg-white/10 hover:bg-white/15 text-slate-200 font-semibold text-sm transition-colors text-center disabled:opacity-50"
            >
              {loading ? "Starting Fresh..." : "Start Fresh"}
            </button>
          </div>
        ) : (
          <form onSubmit={handleRestoreSubmit} className="flex flex-col gap-4">
            <div>
              <label
                htmlFor="recovery-code-input"
                className="block text-xs uppercase tracking-wider text-slate-400 mb-1"
              >
                Recovery Code
              </label>
              <input
                id="recovery-code-input"
                type="text"
                value={recoveryCode}
                onChange={(e) => setRecoveryCode(e.target.value.toUpperCase())}
                placeholder="FLICK-XXXX-XXXX-XXXX"
                className="w-full rounded-lg bg-black/40 border border-white/20 px-3 py-2 text-sm text-white placeholder-slate-500 font-mono tracking-wider focus:outline-none focus:border-violet-500"
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
                className="flex-1 py-2.5 px-3 rounded-lg bg-white/10 hover:bg-white/15 text-xs font-semibold text-slate-300"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={loading}
                className="flex-1 py-2.5 px-3 rounded-lg bg-violet-600 hover:bg-violet-500 text-xs font-semibold text-white disabled:opacity-50"
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
