import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthShell } from "../components/AuthShell";
import { recoverGuest, acknowledgeRecovery, ApiError } from "../lib/api";
import { saveAuthState } from "../lib/auth";
import RecoveryCodeModal from "../components/RecoveryCodeModal";

export default function GuestRecoveryPage() {
  const navigate = useNavigate();

  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Replacement modal state
  const [replacementCode, setReplacementCode] = useState<string | null>(null);
  const [showReplacementModal, setShowReplacementModal] = useState(false);
  const [ackLoading, setAckLoading] = useState(false);
  const [ackError, setAckError] = useState("");

  const handleFormatCode = (val: string) => {
    // Keep alphanumerics and dashes, uppercase
    const cleaned = val.toUpperCase().replace(/[^A-Z0-9-]/g, "");
    setCode(cleaned);
  };

  const handleRecover = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const raw = code.trim();
    if (!raw) {
      setError("Please enter your 16-character recovery code.");
      return;
    }

    setError("");
    setLoading(true);

    try {
      const data = await recoverGuest(raw);
      if (data.success && data.token) {
        // Establish authenticated session with the rotated token
        saveAuthState({
          token: data.token,
          user: data.user,
        });

        // Present replacement recovery code
        setReplacementCode(data.recovery_code);
        setShowReplacementModal(true);
      } else {
        setError("Invalid recovery code. Please check and try again.");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 429) {
          setError("Too many recovery attempts. Please wait a moment and try again.");
        } else {
          setError(err.message || "Invalid recovery code. Please check and try again.");
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unable to restore guest account. Please verify your internet connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmReplacement = async () => {
    setAckLoading(true);
    setAckError("");

    try {
      // Send explicit recovery acknowledgment to retire previous credentials
      await acknowledgeRecovery();
      setShowReplacementModal(false);
      navigate("/home", { replace: true });
    } catch (err: unknown) {
      // Safe retry: do NOT destroy the authenticated session if acknowledgment network request fails
      if (err instanceof ApiError) {
        setAckError(err.message || "Failed to confirm code replacement. You may retry or continue.");
      } else {
        setAckError("Network glitch during confirmation. You may retry or continue.");
      }
    } finally {
      setAckLoading(false);
    }
  };

  const handleSkipOrContinueAnyway = () => {
    // If acknowledgment failed after multiple tries, user has saved their code and can proceed
    setShowReplacementModal(false);
    navigate("/home", { replace: true });
  };

  return (
    <>
      <AuthShell onBack={() => navigate(-1)}>
        <div className="flex flex-col gap-6">
          {/* Header */}
          <div className="flex flex-col gap-1.5 text-center">
            <span className="text-xs font-semibold text-primary uppercase tracking-widest">
              Account Restoration
            </span>
            <h1 className="font-editorial text-2xl sm:text-3xl font-normal tracking-tight text-foreground">
              Restore Guest Account
            </h1>
            <p className="text-sm text-foreground-secondary leading-relaxed font-sans max-w-sm mx-auto">
              Enter the 16-character recovery code issued when you created your guest journal.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleRecover} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary">
                Recovery Code
              </span>
              <div className="relative flex w-full items-stretch">
                <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[20px]">
                  vpn_key
                </span>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => handleFormatCode(e.target.value)}
                  placeholder="e.g. 4F9K-2M8P-7Q1X-0R5T"
                  autoCapitalize="characters"
                  autoCorrect="off"
                  spellCheck="false"
                  disabled={loading}
                  className="flex w-full rounded-xl text-foreground font-mono focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 placeholder:font-sans pl-11 pr-4 text-sm tracking-wider uppercase transition-all"
                />
              </div>
            </label>

            {/* Error banner */}
            {error && (
              <div
                role="alert"
                className="p-3 bg-error/10 border border-error/20 rounded-xl flex items-start gap-2.5 text-left"
              >
                <span className="material-symbols-outlined text-error text-[18px] shrink-0 mt-0.5">
                  error
                </span>
                <p className="text-xs text-error font-medium leading-relaxed">{error}</p>
              </div>
            )}

            {/* Submit button */}
            <button
              type="submit"
              disabled={loading || !code.trim()}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-xs cursor-pointer mt-2"
            >
              {loading ? (
                <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Restore Journal</span>
                  <span className="material-symbols-outlined text-[18px]">
                    arrow_forward
                  </span>
                </>
              )}
            </button>
          </form>

          {/* Alternative navigation */}
          <div className="pt-2 border-t border-border/60 text-center flex flex-col gap-2">
            <p className="text-xs text-foreground-secondary">
              Remember your email and password?{" "}
              <button
                type="button"
                onClick={() => navigate("/login")}
                className="text-primary font-semibold hover:underline cursor-pointer"
              >
                Sign In
              </button>
            </p>
            <p className="text-xs text-foreground-secondary">
              Want a fresh start?{" "}
              <button
                type="button"
                onClick={() => navigate("/")}
                className="text-primary font-semibold hover:underline cursor-pointer"
              >
                Begin Discovery
              </button>
            </p>
          </div>
        </div>
      </AuthShell>

      {/* Replacement Recovery Code Modal */}
      {replacementCode && (
        <RecoveryCodeModal
          isOpen={showReplacementModal}
          recoveryCode={replacementCode}
          isReplacement={true}
          title="Replacement Recovery Code"
          subtitle="Your previous recovery code has been rotated. Save this new credential to restore access in the future."
          confirmLabel={ackLoading ? "Confirming..." : "I've Saved My Replacement Code"}
          onConfirm={handleConfirmReplacement}
        />
      )}

      {/* If Acknowledgment Error Occurred */}
      {ackError && showReplacementModal && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-60 w-full max-w-sm px-4">
          <div className="p-4 bg-surface border border-error/30 rounded-2xl shadow-xl flex flex-col gap-2 text-center">
            <p className="text-xs text-error font-medium">{ackError}</p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleConfirmReplacement}
                className="flex-1 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-semibold"
              >
                Retry
              </button>
              <button
                type="button"
                onClick={handleSkipOrContinueAnyway}
                className="flex-1 py-1.5 rounded-lg border border-border text-foreground text-xs font-medium"
              >
                Continue Anyway
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
