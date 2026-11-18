import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { provisionGuest, ApiError } from "../lib/api";
import { saveAuthState } from "../lib/auth";
import { trackEvent } from "../lib/analytics";
import RecoveryCodeModal from "../components/RecoveryCodeModal";

/* ============================
   ENTRY / SPLASH PAGE — Art-House Cinema Editorial
   - Start Exploring → Instant Guest Provisioning with Recovery Key
   - Sign In → /login
   - Restore Guest Account → /recover
============================ */

export default function EntryPage() {
  const navigate = useNavigate();
  const { theme, toggleTheme, logoFull } = useTheme();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("auth_token")) {
      navigate("/home", { replace: true });
    }
  }, [navigate]);

  const handleStartExploring = async () => {
    setError("");
    setLoading(true);

    try {
      const data = await provisionGuest();
      if (data.success && data.token) {
        // Establish authenticated guest session
        saveAuthState({
          token: data.token,
          user: data.user,
        });
        trackEvent("guest_provisioned", { user_id: data.user?.id });

        // Present newly issued recovery code
        setRecoveryCode(data.recovery_code);
        setShowModal(true);
      } else {
        setError("Unable to initialize guest discovery. Please try again.");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message || "Failed to initialize guest account.");
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Network error initializing guest journal. Check your internet connection.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleModalConfirm = () => {
    setShowModal(false);
    navigate("/home", { replace: true });
  };

  return (
    <>
      <div className="relative bg-background text-foreground font-sans antialiased min-h-screen flex flex-col justify-between p-6 sm:p-12 overflow-hidden transition-colors duration-200">
        
        {/* ── Top Bar: Brand mark & Theme Toggle ── */}
        <header className="relative z-10 flex items-center justify-between w-full max-w-4xl mx-auto pt-2">
          <div className="flex items-center gap-3">
            <img src={logoFull} alt="Flick" className="h-8 w-auto object-contain" />
            <span className="text-[10px] font-sans tracking-widest uppercase px-2 py-0.5 rounded-full border border-border text-foreground-secondary">
              Art-House Edition
            </span>
          </div>

          <button
            onClick={toggleTheme}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            className="size-9 rounded-full border border-border flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[18px]">
              {theme === "dark" ? "light_mode" : "dark_mode"}
            </span>
          </button>
        </header>

        {/* ── Main Editorial Centerpiece ── */}
        <main className="relative z-10 w-full max-w-2xl mx-auto my-auto py-12 flex flex-col items-center text-center">
          <div className="mb-6 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-secondary border border-border text-foreground-secondary text-xs tracking-wider uppercase">
            <span className="material-symbols-outlined text-[14px] text-primary">movie</span>
            <span>Collaborative Film Curation</span>
          </div>

          <h1 className="font-editorial text-4xl sm:text-6xl md:text-7xl font-normal leading-[1.08] tracking-tight text-foreground mb-6">
            Movie night, <br />
            <span className="italic font-normal">thoughtfully decided.</span>
          </h1>

          <p className="text-foreground-secondary text-base sm:text-lg max-w-md mx-auto leading-relaxed mb-8 font-sans">
            Swipe through curated cinema with your partner. Discover independent features, festival selections, and world cinema together.
          </p>

          {/* Error Banner if Provisioning Failed */}
          {error && (
            <div
              role="alert"
              className="mb-6 w-full max-w-sm p-3 bg-error/10 border border-error/20 rounded-xl flex items-start gap-2.5 text-left"
            >
              <span className="material-symbols-outlined text-error text-[18px] shrink-0 mt-0.5">
                error
              </span>
              <p className="text-xs text-error font-medium leading-relaxed">{error}</p>
            </div>
          )}

          {/* Action Buttons */}
          <div className="w-full max-w-sm flex flex-col gap-3">
            <button
              onClick={handleStartExploring}
              disabled={loading}
              className="w-full h-13 px-6 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors duration-150 flex items-center justify-center gap-2 shadow-xs cursor-pointer disabled:opacity-60"
            >
              {loading ? (
                <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Start Exploring</span>
                  <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </>
              )}
            </button>

            <div className="flex gap-3 w-full">
              <button
                onClick={() => navigate("/login")}
                disabled={loading}
                className="flex-1 h-12 px-5 rounded-full bg-surface hover:bg-surface-secondary border border-border text-foreground font-semibold text-xs sm:text-sm tracking-wide transition-colors duration-150 flex items-center justify-center cursor-pointer"
              >
                Sign In
              </button>

              <button
                onClick={() => navigate("/recover")}
                disabled={loading}
                className="flex-1 h-12 px-5 rounded-full bg-surface hover:bg-surface-secondary border border-border text-foreground font-semibold text-xs sm:text-sm tracking-wide transition-colors duration-150 flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span className="material-symbols-outlined text-[16px] text-primary">key</span>
                <span>Restore Code</span>
              </button>
            </div>
          </div>
        </main>

        {/* ── Footer ── */}
        <footer className="relative z-10 w-full max-w-4xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 pt-6 border-t border-border/60 text-xs text-foreground-secondary">
          <p>© Flick Cinema Journal. Independent Film Discovery.</p>
          <div className="flex gap-6">
            <button
              onClick={() => navigate("/discover")}
              className="hover:text-foreground transition-colors cursor-pointer"
            >
              Browse Catalogue
            </button>
            <button
              onClick={() => navigate("/terms")}
              className="hover:text-foreground transition-colors cursor-pointer"
            >
              Terms
            </button>
            <button
              onClick={() => navigate("/privacy")}
              className="hover:text-foreground transition-colors cursor-pointer"
            >
              Privacy
            </button>
          </div>
        </footer>

      </div>

      {/* Recovery Code Presentation Modal */}
      {recoveryCode && (
        <RecoveryCodeModal
          isOpen={showModal}
          recoveryCode={recoveryCode}
          onConfirm={handleModalConfirm}
        />
      )}
    </>
  );
}
