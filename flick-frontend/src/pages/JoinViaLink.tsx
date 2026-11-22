import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { trackEvent } from "../lib/analytics";
import { setInvitationCode, coordinateGuestProvisioning } from "../services/guestProvisionCoordinator";

export default function JoinViaLink() {
  const { sessionCode } = useParams<{ sessionCode: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionCode) {
      navigate("/", { replace: true });
      return;
    }

    setInvitationCode(sessionCode);
    trackEvent("invite_link_opened", {
      has_auth_token: Boolean(localStorage.getItem("auth_token")),
    });

    const initJoin = async () => {
      const token = localStorage.getItem("auth_token");
      if (token) {
        // Authenticated user: navigate straight to auto-join
        navigate("/auto-join", { replace: true });
        return;
      }

      // Unauthenticated user: silently provision guest and navigate to auto-join
      try {
        await coordinateGuestProvisioning();
        navigate("/auto-join", { replace: true });
      } catch (err) {
        console.error("Failed to provision guest for invite link:", err);
        setError("Unable to initialize session. Please try again.");
        setLoading(false);
      }
    };

    initJoin();
  }, [sessionCode, navigate]);

  if (!sessionCode) {
    return null;
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground p-6">
        <div className="max-w-md w-full text-center space-y-4">
          <p className="text-red-500 text-sm">{error}</p>
          <button
            onClick={() => navigate("/", { replace: true })}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold cursor-pointer"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground">
        <div className="flex flex-col items-center gap-3">
          <span className="size-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-foreground-secondary">Joining movie night...</p>
        </div>
      </div>
    );
  }

  return null;
}
