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
    <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] p-4 text-white">
      <div className="w-full max-w-md rounded-2xl bg-[#14141d] border border-white/10 p-8 text-center shadow-2xl">
        <div className="w-12 h-12 rounded-full bg-violet-500/20 text-violet-400 mx-auto flex items-center justify-center mb-4 text-xl font-bold">
          !
        </div>
        <h2 className="text-2xl font-bold mb-2">Previous Session Expired</h2>
        <p className="text-sm text-slate-300 mb-6 leading-relaxed">
          The requested guest provisioning window is no longer available. You can start exploring
          immediately with a brand new profile.
        </p>

        {error && (
          <div className="mb-4 p-3 rounded-lg bg-red-950/60 border border-red-500/30 text-red-200 text-xs">
            {error}
          </div>
        )}

        <button
          onClick={handleStartFresh}
          disabled={loading}
          className="w-full py-3.5 px-4 rounded-xl bg-violet-600 hover:bg-violet-500 font-semibold text-sm transition-all duration-150 shadow-lg shadow-violet-600/30 disabled:opacity-50 mb-3"
        >
          {loading ? "Starting Fresh..." : "Start Fresh"}
        </button>

        {onOpenRecovery && (
          <button
            onClick={onOpenRecovery}
            className="text-xs text-slate-400 hover:text-white underline underline-offset-4 transition-colors"
          >
            Have a recovery code? Restore your journal
          </button>
        )}
      </div>
    </div>
  );
};

export default ProvisionContinuationScreen;
