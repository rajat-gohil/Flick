import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "../context/ThemeContext";
import { ApiError } from "../lib/api";
import { coordinateGuestProvisioning } from "../services/guestProvisionCoordinator";
import RecoveryCodeModal from "../components/RecoveryCodeModal";

/* ============================
   ENTRY / SPLASH PAGE — Art-House Cinema Editorial
   - Hero: Instant Guest Provisioning & Direct Actions
   - How Access Works: In-depth explanation of Guest vs Sign-Up vs Sign-In vs Recovery Key
   - Comparison Matrix & 3-Step Film Night Walkthrough
============================ */

export default function EntryPage() {
  const navigate = useNavigate();
  const { theme, toggleTheme, logoFull } = useTheme();

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recoveryCode, setRecoveryCode] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [activeFaq, setActiveFaq] = useState<number | null>(null);
  const [leftPosterErr, setLeftPosterErr] = useState(false);
  const [rightPosterErr, setRightPosterErr] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("auth_token")) {
      navigate("/home", { replace: true });
    }
  }, [navigate]);

  const handleStartExploring = async () => {
    setError("");
    setLoading(true);

    try {
      const data = await coordinateGuestProvisioning();
      if (data && data.token) {
        if (data.recovery_code) {
          setRecoveryCode(data.recovery_code);
        }
        // Silently provisioned, navigate directly to /home without modal
        navigate("/home", { replace: true });
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

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth" });
    }
  };

  return (
    <>
      <div className="relative bg-background text-foreground font-sans antialiased min-h-screen flex flex-col justify-between overflow-x-clip transition-colors duration-200">
        
        {/* ── Top Bar: Brand mark & Actions ── */}
        <header className="relative z-10 flex items-center justify-between w-full max-w-6xl mx-auto px-4 sm:px-6 py-4">
          <div className="flex items-center gap-3">
            <img src={logoFull} alt="Flick" className="h-8 w-auto object-contain" />
            <span className="hidden sm:inline-block text-[10px] font-mono tracking-widest uppercase text-foreground-secondary">
              Art-House Edition
            </span>
          </div>

          <div className="flex items-center gap-1.5 sm:gap-3">
            <button
              onClick={() => scrollToSection("screening-flow")}
              className="min-h-11 sm:min-h-9 inline-flex items-center text-xs font-semibold text-foreground-secondary hover:text-foreground transition-colors px-2.5 rounded-lg cursor-pointer"
            >
              How It Works
            </button>

            <button
              onClick={() => navigate("/register")}
              className="hidden sm:inline-flex min-h-9 items-center text-xs font-semibold text-foreground-secondary hover:text-foreground transition-colors px-2.5 rounded-lg cursor-pointer"
            >
              Sign Up
            </button>

            <button
              onClick={() => navigate("/login")}
              className="min-h-11 sm:min-h-9 inline-flex items-center text-xs font-semibold text-foreground-secondary hover:text-foreground transition-colors px-3.5 rounded-full border border-border/80 hover:bg-surface-secondary active:scale-[0.99] cursor-pointer"
            >
              Sign In
            </button>

            <button
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              className="size-11 sm:size-9 rounded-full border border-border flex items-center justify-center text-foreground-secondary hover:text-foreground hover:bg-surface-secondary active:scale-[0.99] transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-[18px]">
                {theme === "dark" ? "light_mode" : "dark_mode"}
              </span>
            </button>
          </div>
        </header>

        {/* ── Hero Section ── */}
        <main className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 min-h-[calc(100dvh-4.75rem)] flex items-center py-8 sm:py-12 lg:py-16">
          <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">

            {/* Left Column: Core Narrative & 2 Primary CTAs */}
            <div className="lg:col-span-6 flex flex-col items-center lg:items-start text-center lg:text-left">
              <p className="mb-4 font-mono text-[11px] font-semibold tracking-widest uppercase text-primary">
                Collaborative Film Curation
              </p>

              <h1 className="font-editorial text-4xl sm:text-5xl xl:text-6xl font-normal leading-[1.08] tracking-tight text-foreground mb-5">
                Movie night, <br />
                <span className="italic font-normal">thoughtfully decided.</span>
              </h1>

              <p className="text-foreground-secondary text-base sm:text-lg max-w-lg leading-relaxed mb-7 font-sans">
                Swipe through curated cinema with your partner. Discover independent features, festival selections, and world cinema together.
              </p>

              {/* Error Banner if Provisioning Failed */}
              {error && (
                <div
                  role="alert"
                  className="mb-6 w-full max-w-md p-3.5 bg-error/10 border border-error/20 rounded-xl flex items-start gap-2.5 text-left"
                >
                  <span className="material-symbols-outlined text-error text-[18px] shrink-0 mt-0.5">
                    error
                  </span>
                  <p className="text-xs text-error font-medium leading-relaxed">{error}</p>
                </div>
              )}

              {/* Primary & Secondary CTA Pair */}
              <div className="w-full max-w-md flex flex-col sm:flex-row gap-3">
                <button
                  onClick={handleStartExploring}
                  disabled={loading}
                  className="flex-1 min-h-12 sm:h-13 px-6 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors duration-150 active:scale-[0.99] flex items-center justify-center gap-2 shadow-xs cursor-pointer disabled:opacity-60"
                >
                  {loading ? (
                    <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>Start a Movie Night</span>
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </>
                  )}
                </button>

                <button
                  onClick={() => navigate("/login")}
                  disabled={loading}
                  className="min-h-12 sm:h-13 px-6 rounded-full bg-surface hover:bg-surface-secondary border border-border text-foreground font-semibold text-sm tracking-wide transition-colors duration-150 active:scale-[0.99] flex items-center justify-center cursor-pointer"
                >
                  Sign In
                </button>
              </div>

              {/* Micro-clarity hint + secondary Restore link */}
              <div className="mt-4 flex flex-wrap items-center justify-center lg:justify-start gap-x-4 gap-y-2 text-[11px] text-foreground-secondary">
                <span className="inline-flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[14px] text-primary">bolt</span>
                  <span>Instant guest session • No email or registration required</span>
                </span>
                <button
                  type="button"
                  onClick={() => navigate("/recover")}
                  className="inline-flex items-center gap-1 font-semibold text-foreground hover:text-primary underline underline-offset-4 transition-colors cursor-pointer py-1"
                  title="Restore with your 16-character recovery key"
                >
                  <span>Restore key</span>
                </button>
              </div>
            </div>

            {/* Right Column: Illustrative Two-Poster Consensus Composition */}
            <div className="lg:col-span-6 w-full max-w-md mx-auto lg:max-w-none">
              <div
                aria-label="Illustrative preview showing how two viewers match on a film"
                className="relative rounded-2xl border border-border bg-surface p-5 sm:p-7 shadow-md"
              >
                {/* Explicit Illustrative Label */}
                <div className="flex items-center justify-between pb-3 mb-5 border-b border-border/60">
                  <span className="font-mono text-[10px] uppercase tracking-widest text-foreground-secondary font-semibold">
                    Illustrative Preview
                  </span>
                  <span className="font-mono text-[10px] uppercase tracking-wider text-primary font-semibold">
                    Mutual Match
                  </span>
                </div>

                {/* Two Opposite Film Posters Connected by Central Consensus Seal */}
                <div className="relative flex items-center justify-between gap-2 sm:gap-4 py-2">
                  {/* Subtle horizontal connection line spanning behind posters & seal */}
                  <div
                    aria-hidden="true"
                    className="absolute left-12 right-12 top-1/2 -translate-y-1/2 border-t border-dashed border-primary/45 pointer-events-none z-0"
                  />

                  {/* Left Film Poster */}
                  <div className="relative z-10 w-[38%] sm:w-[36%] aspect-[2/3] rounded-xl overflow-hidden border border-border bg-surface-secondary shadow-sm">
                    {!leftPosterErr ? (
                      <img
                        src="https://image.tmdb.org/t/p/w500/yQvGrMoipbRoddT0ZR8tPoR7NfX.jpg"
                        alt="Interstellar film poster"
                        className="w-full h-full object-cover"
                        onError={() => setLeftPosterErr(true)}
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center p-3 text-center text-foreground-secondary">
                        <span className="material-symbols-outlined text-3xl mb-1">movie</span>
                        <span className="font-editorial text-xs font-semibold text-foreground">Interstellar</span>
                      </div>
                    )}
                  </div>

                  {/* Central Consensus Seal */}
                  <div className="relative z-10 shrink-0 flex flex-col items-center">
                    <div className="size-12 sm:size-14 rounded-full bg-surface border-2 border-primary/70 shadow-sm flex items-center justify-center text-primary">
                      <span
                        className="material-symbols-outlined text-[24px] sm:text-[26px]"
                        style={{ fontVariationSettings: "'FILL' 1" }}
                      >
                        verified
                      </span>
                    </div>
                  </div>

                  {/* Right Film Poster */}
                  <div className="relative z-10 w-[38%] sm:w-[36%] aspect-[2/3] rounded-xl overflow-hidden border border-border bg-surface-secondary shadow-sm">
                    {!rightPosterErr ? (
                      <img
                        src="https://image.tmdb.org/t/p/w500/vQWk5YBFWF4bZaofAbv0tShwBvQ.jpg"
                        alt="Pulp Fiction film poster"
                        className="w-full h-full object-cover"
                        onError={() => setRightPosterErr(true)}
                      />
                    ) : (
                      <div className="w-full h-full flex flex-col items-center justify-center p-3 text-center text-foreground-secondary">
                        <span className="material-symbols-outlined text-3xl mb-1">movie</span>
                        <span className="font-editorial text-xs font-semibold text-foreground">Pulp Fiction</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Concise Message & Supporting Explanation */}
                <div className="mt-5 pt-4 border-t border-border/60 text-center space-y-1">
                  <p className="font-editorial text-xl sm:text-2xl font-semibold text-foreground tracking-tight">
                    Two tastes. One movie night.
                  </p>
                  <p className="text-xs text-foreground-secondary leading-relaxed">
                    A match happens when both people choose the same film.
                  </p>
                </div>
              </div>
            </div>

          </div>
        </main>

        {/* ── Section: 3-Step Film Night Walkthrough (Product-First) ── */}
        <section
          id="screening-flow"
          className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-16 border-t border-border/60"
        >
          <div className="text-center max-w-lg mx-auto mb-10">
            <p className="font-mono text-[11px] font-semibold text-primary uppercase tracking-widest">
              The Screening Flow
            </p>
            <h2 className="font-editorial text-3xl sm:text-4xl font-normal text-foreground mt-3 mb-2">
              Three Steps to Movie Night
            </h2>
            <p className="text-xs sm:text-sm text-foreground-secondary font-sans">
              Designed to eliminate endless scrolling and make movie selection joyful.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex flex-col items-center text-center p-6 rounded-2xl bg-surface border border-border/80">
              <div className="size-10 rounded-full bg-surface-secondary flex items-center justify-center font-editorial font-bold text-base text-primary mb-3">
                1
              </div>
              <h4 className="font-editorial text-lg font-bold text-foreground mb-1">
                Open a Room
              </h4>
              <p className="text-xs text-foreground-secondary leading-relaxed">
                Create a session in one tap and send the 6-letter room code or link to your partner. No app install needed.
              </p>
            </div>

            <div className="flex flex-col items-center text-center p-6 rounded-2xl bg-surface border border-border/80">
              <div className="size-10 rounded-full bg-surface-secondary flex items-center justify-center font-editorial font-bold text-base text-primary mb-3">
                2
              </div>
              <h4 className="font-editorial text-lg font-bold text-foreground mb-1">
                Swipe in Sync
              </h4>
              <p className="text-xs text-foreground-secondary leading-relaxed">
                Swipe right to Recommend, left to Pass, or Star to Super-Like. Cards pre-buffer instantly with zero delay.
              </p>
            </div>

            <div className="flex flex-col items-center text-center p-6 rounded-2xl bg-surface border border-border/80">
              <div className="size-10 rounded-full bg-surface-secondary flex items-center justify-center font-editorial font-bold text-base text-primary mb-3">
                3
              </div>
              <h4 className="font-editorial text-lg font-bold text-foreground mb-1">
                Instant Consensus
              </h4>
              <p className="text-xs text-foreground-secondary leading-relaxed">
                When you both swipe right, Flick locks in your mutual match with streaming options and a shareable Salon Pass.
              </p>
            </div>
          </div>
        </section>

        {/* ── Section: How Account Access Works ── */}
        <section
          id="access-guide"
          className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-16 border-t border-border/60"
        >
          <div className="text-center max-w-xl mx-auto mb-12">
            <p className="font-mono text-[11px] font-semibold text-primary uppercase tracking-widest">
              Access Guide
            </p>
            <h2 className="font-editorial text-3xl sm:text-4xl font-normal text-foreground mt-3 mb-3">
              How Sign-Up, Sign-In & Guest Access Work
            </h2>
            <p className="text-sm text-foreground-secondary leading-relaxed font-sans">
              Flick gives you complete control over your privacy and experience. Choose between zero-friction guest discovery or a permanent synchronized cinema account.
            </p>
          </div>

          {/* Three Access Pillars */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

            {/* Pillar 1: Instant Guest */}
            <div className="bg-surface border border-border/80 rounded-2xl p-6 sm:p-7 flex flex-col justify-between shadow-2xs hover:border-primary/50 transition-colors">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[22px]">explore</span>
                  </div>
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-foreground-secondary">
                    Quickest Start
                  </span>
                </div>

                <h3 className="font-editorial text-xl font-bold text-foreground mb-2">
                  1. Instant Guest Mode
                </h3>
                <p className="text-xs text-foreground-secondary leading-relaxed mb-5">
                  Tap <strong>Start a Movie Night</strong> to begin immediately. No name, email, or password is needed. Flick provisions a private guest journal saved in your browser.
                </p>

                <ul className="text-xs text-foreground-secondary space-y-2 mb-6">
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Zero forms — jump into rooms in seconds</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Full screening deck & real-time matching</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Generates a private 16-character backup key</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Can be converted to a permanent account anytime</span>
                  </li>
                </ul>
              </div>

              <button
                onClick={handleStartExploring}
                disabled={loading}
                className="w-full min-h-11 py-2.5 px-4 rounded-xl bg-surface-secondary hover:bg-border text-foreground text-xs font-semibold tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>Start a Movie Night</span>
                <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
              </button>
            </div>

            {/* Pillar 2: Permanent Account */}
            <div className="bg-surface border-2 border-primary/40 rounded-2xl p-6 sm:p-7 flex flex-col justify-between shadow-xs relative">
              <div className="absolute -top-3 right-6 bg-primary text-primary-foreground text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full shadow-2xs">
                Recommended
              </div>

              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[22px]">badge</span>
                  </div>
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-primary">
                    Permanent Sync
                  </span>
                </div>

                <h3 className="font-editorial text-xl font-bold text-foreground mb-2">
                  2. Permanent Cinema Account
                </h3>
                <p className="text-xs text-foreground-secondary leading-relaxed mb-5">
                  Register with an email and password to permanently save your taste profile, partner consensus matches, and custom watchlists across all devices.
                </p>

                <ul className="text-xs text-foreground-secondary space-y-2 mb-6">
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Seamless cloud sync across phones, tablets & desktop</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Permanent match history & collaborative lists</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Secure email sign-in & password recovery</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Custom display names for room hosts and guests</span>
                  </li>
                </ul>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => navigate("/register")}
                  className="flex-1 min-h-11 py-2.5 px-3 rounded-xl bg-primary hover:bg-primary-hover text-primary-foreground text-xs font-semibold tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-1 cursor-pointer"
                >
                  <span>Sign Up</span>
                </button>
                <button
                  onClick={() => navigate("/login")}
                  className="flex-1 min-h-11 py-2.5 px-3 rounded-xl bg-surface-secondary hover:bg-border text-foreground text-xs font-semibold tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-1 cursor-pointer"
                >
                  <span>Sign In</span>
                </button>
              </div>
            </div>

            {/* Pillar 3: Recovery Key */}
            <div className="bg-surface border border-border/80 rounded-2xl p-6 sm:p-7 flex flex-col justify-between shadow-2xs hover:border-primary/50 transition-colors">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="size-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
                    <span className="material-symbols-outlined text-[22px]">key</span>
                  </div>
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-foreground-secondary">
                    Device Transfer
                  </span>
                </div>

                <h3 className="font-editorial text-xl font-bold text-foreground mb-2">
                  3. Key-Based Recovery
                </h3>
                <p className="text-xs text-foreground-secondary leading-relaxed mb-5">
                  Started on mobile and want to continue on your living room laptop? Or cleared your cache? Use your 16-character recovery key to instantly restore your journal.
                </p>

                <ul className="text-xs text-foreground-secondary space-y-2 mb-6">
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>No personal data or email needed to transfer</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Issued automatically when you start a movie night</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Rotates a fresh key upon restoration for security</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="material-symbols-outlined text-primary text-[15px] shrink-0 mt-0.5">check_circle</span>
                    <span>Accessible anytime from your profile settings</span>
                  </li>
                </ul>
              </div>

              <button
                onClick={() => navigate("/recover")}
                className="w-full min-h-11 py-2.5 px-4 rounded-xl bg-surface-secondary hover:bg-border text-foreground text-xs font-semibold tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <span>Enter Recovery Code</span>
                <span className="material-symbols-outlined text-[15px]">arrow_forward</span>
              </button>
            </div>

          </div>
        </section>

        {/* ── Section: Feature Comparison Table ── */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-12">
          <div className="bg-surface border border-border/80 rounded-2xl overflow-hidden shadow-xs">
            <div className="p-6 border-b border-border/60">
              <h3 className="font-editorial text-2xl font-bold text-foreground">
                Comparing Account Modes
              </h3>
              <p className="text-xs text-foreground-secondary mt-1">
                Both modes enjoy full access to Flick's collaborative screening engine. Here is how they differ:
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-surface-secondary/60 text-foreground-secondary font-semibold border-b border-border">
                    <th className="py-3 px-5">Feature</th>
                    <th className="py-3 px-5">Instant Guest Mode</th>
                    <th className="py-3 px-5 text-primary">Permanent Cinema Account</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Sign-up Required</td>
                    <td className="py-3 px-5 text-emerald-600 dark:text-emerald-400 font-semibold">None (0 seconds)</td>
                    <td className="py-3 px-5 text-foreground-secondary">Email + Password (~30s)</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Curated 40-Film Deck Swiping</td>
                    <td className="py-3 px-5 text-foreground-secondary">Full Access</td>
                    <td className="py-3 px-5 text-foreground-secondary">Full Access</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Real-Time Partner Rooms</td>
                    <td className="py-3 px-5 text-foreground-secondary">Full Access</td>
                    <td className="py-3 px-5 text-foreground-secondary">Full Access</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Switch Devices</td>
                    <td className="py-3 px-5 text-foreground-secondary">Via 16-character Recovery Key</td>
                    <td className="py-3 px-5 text-primary font-semibold">One-click Sign In</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Permanent Cloud History</td>
                    <td className="py-3 px-5 text-foreground-secondary">Retained with recovery key</td>
                    <td className="py-3 px-5 text-primary font-semibold">Saved permanently</td>
                  </tr>
                  <tr>
                    <td className="py-3 px-5 font-medium text-foreground">Upgrade / Convert</td>
                    <td className="py-3 px-5 text-emerald-600 dark:text-emerald-400 font-semibold">Convert anytime from Profile</td>
                    <td className="py-3 px-5 text-foreground-secondary">Already permanent</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        {/* ── Section: Common Questions Accordion ── */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-12 border-t border-border/60">
          <div className="max-w-3xl mx-auto">
            <div className="text-center mb-8">
              <h3 className="font-editorial text-2xl font-bold text-foreground">
                Frequently Asked Questions
              </h3>
            </div>

            <div className="space-y-3">
              {[
                {
                  q: "Do I need to create an account to use Flick?",
                  a: "No! You can tap 'Start a Movie Night' to immediately start swiping and creating rooms with your partner as an anonymous guest. No email or password is ever required for guest mode.",
                },
                {
                  q: "What is the 16-character recovery code?",
                  a: "When you start as a guest, Flick gives you a unique 16-character key (e.g. ABCD-1234-EFGH-5678). If you switch phones, open a new laptop, or clear browser data, simply go to 'Restore key' and enter your key to bring back all your matches and watchlist.",
                },
                {
                  q: "Can I convert my guest account into a permanent account later?",
                  a: "Yes! If you start as a guest and later decide you want a permanent account with email sign-in, you can visit your Profile page at any time and click 'Convert to Permanent Account'. All your existing history will be seamlessly transferred.",
                },
                {
                  q: "How does my partner join my screening session?",
                  a: "When you create a session, Flick generates a 6-letter room code (e.g. CINEMA) and a direct join link. Send the link to your partner; they can tap it to join directly from any browser.",
                },
              ].map((faq, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-border/80 bg-surface overflow-hidden transition-colors"
                >
                  <button
                    onClick={() => setActiveFaq(activeFaq === index ? null : index)}
                    className="w-full px-5 py-4 text-left flex items-center justify-between gap-4 cursor-pointer hover:bg-surface-secondary/40 transition-colors"
                  >
                    <span className="text-sm font-semibold text-foreground">
                      {faq.q}
                    </span>
                    <span className="material-symbols-outlined text-[18px] text-foreground-secondary transition-transform duration-200" style={{ transform: activeFaq === index ? "rotate(180deg)" : "rotate(0deg)" }}>
                      keyboard_arrow_down
                    </span>
                  </button>
                  {activeFaq === index && (
                    <div className="px-5 pb-4 pt-1 text-xs text-foreground-secondary leading-relaxed border-t border-border/40 bg-surface-secondary/20">
                      {faq.a}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Section: Ready to Decide CTA Banner ── */}
        <section className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-12">
          <div className="rounded-3xl bg-surface border border-border/80 p-8 sm:p-12 text-center shadow-xs flex flex-col items-center">
            <h2 className="font-editorial text-3xl sm:text-4xl font-normal text-foreground mb-3">
              Ready for film night?
            </h2>
            <p className="text-sm text-foreground-secondary max-w-md mx-auto mb-6">
              Start immediately as a guest in one tap, or create your permanent cinema profile.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 w-full max-w-sm">
              <button
                onClick={handleStartExploring}
                disabled={loading}
                className="flex-1 h-12 px-6 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-xs sm:text-sm tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center gap-1.5 cursor-pointer shadow-xs disabled:opacity-60"
              >
                <span>Start a Movie Night</span>
                <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
              </button>
              <button
                onClick={() => navigate("/register")}
                className="flex-1 h-12 px-6 rounded-full bg-surface-secondary hover:bg-border text-foreground font-semibold text-xs sm:text-sm tracking-wide transition-colors active:scale-[0.99] flex items-center justify-center cursor-pointer"
              >
                Create Account
              </button>
            </div>
          </div>
        </section>

        {/* ── Footer ── */}
        <footer className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-8 border-t border-border/60 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-foreground-secondary">
          <p>© Flick Cinema Journal. Independent Film Discovery.</p>
          <div className="flex gap-6">
            <button
              onClick={() => navigate("/discover")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Browse Movies
            </button>
            <button
              onClick={() => navigate("/terms")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Terms
            </button>
            <button
              onClick={() => navigate("/privacy")}
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Privacy
            </button>
            <a
              href="mailto:discoverflick@gmail.com"
              className="hover:text-foreground transition-colors cursor-pointer min-h-11 sm:min-h-0 flex items-center"
            >
              Contact
            </a>
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
