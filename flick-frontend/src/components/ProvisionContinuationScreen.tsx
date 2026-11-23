import React, { useState } from "react";
import { coordinateGuestProvisioning } from "../services/guestProvisionCoordinator";

interface ProvisionContinuationScreenProps {
  onStartFreshSuccess?: () => void;
  onOpenRecovery?: () => void;
}

export const ProvisionContinuationScreen: React.FC<ProvisionContinuationScreenProps> = ({
  onStartFreshSuccess,
  onOpenRecovery,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartFresh = async () => {
    setLoading(true);
    setError(null);
    try {
      localStorage.removeItem("flick_provisioning_key");
      localStorage.removeItem("flick_provisioning_key_ts");
      const res = await coordinateGuestProvisioning();
      if (res && res.token) {
        if (onStartFreshSuccess) {
          onStartFreshSuccess();
        } else {
          window.location.href = "/home";
        }
      }
    } catch (err: any) {
      setError("Unable to initialize fresh session. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4 text-foreground font-sans">
      <div className="w-full max-w-md rounded-2xl bg-surface border border-border p-8 text-center shadow-2xl">
        <div className="size-14 rounded-full bg-primary/10 border border-primary/25 text-primary mx-auto flex items-center justify-center mb-4">
          <span className="material-symbols-outlined text-[28px]">hourglass_disabled</span>
        </div>
        <h2 className="font-editorial text-2xl sm:text-3xl font-semibold tracking-tight text-foreground mb-2">Previous Session Expired</h2>
        <p className="text-xs sm:text-sm text-foreground-secondary mb-6 leading-relaxed">
          The requested guest provisioning window is no longer available. You can start exploring
          immediately with a brand new profile.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-error/10 border border-error/25 text-error text-xs">
            {error}
          </div>
        )}

        <button
          onClick={handleStartFresh}
          disabled={loading}
          className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-surface font-semibold text-sm transition-colors shadow-xs disabled:opacity-50 mb-3 cursor-pointer"
        >
          {loading ? "Starting Fresh..." : "Start Fresh"}
        </button>

        {onOpenRecovery && (
          <button
            onClick={onOpenRecovery}
            className="text-xs text-primary hover:underline font-medium transition-colors cursor-pointer"
          >
            Have a recovery code? Restore your journal
          </button>
        )}
      </div>
    </div>
  );
};

export default ProvisionContinuationScreen;
