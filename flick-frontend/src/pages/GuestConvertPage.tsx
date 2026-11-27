import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AuthShell, getPasswordStrength } from "../components/AuthShell";
import { convertGuestAccount, ApiError } from "../lib/api";
import { isGuest, updateAuthState, getCurrentUser } from "../lib/auth";
import { identifyUser, trackEvent } from "../lib/analytics";

export default function GuestConvertPage() {
  const navigate = useNavigate();
  const currentUser = getCurrentUser();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [displayName, setDisplayName] = useState(currentUser?.display_name || "");
  const [showPassword, setShowPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(false);

  // If already a registered account (not a guest), redirect away
  useEffect(() => {
    if (!isGuest()) {
      navigate("/profile", { replace: true });
    }
  }, [navigate]);

  const passwordStrength = getPasswordStrength(password);

  const handleConvert = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setError("");

    // Basic frontend validation
    if (!email.trim() || !email.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 6) {
      setError("Password must be at least 6 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const data = await convertGuestAccount({
        email: email.trim(),
        password,
        display_name: displayName.trim() || undefined,
      });

      if (data.success) {
        // In-place conversion preserved User.pk and active DRF token.
        // Update local auth state to reflect permanent membership.
        updateAuthState({
          is_guest: false,
          email: data.user.email,
          display_name: data.user.display_name,
          username: data.user.username,
        });
        identifyUser(data.user.id, {
          is_guest: false,
          username: data.user.username,
        });
        trackEvent("guest_converted", { user_id: data.user.id });

        setSuccess(true);
        setTimeout(() => {
          navigate("/profile", { replace: true });
        }, 2200);
      } else {
        setError(data.message || "Failed to convert account. Please check your details.");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An error occurred during account conversion. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell onBack={() => navigate(-1)}>
      <div className="flex flex-col gap-5">
        {/* Header */}
        <div className="flex flex-col gap-1.5 text-center">
          <span className="text-xs font-semibold text-primary uppercase tracking-widest">
            Permanent Account
          </span>
          <h1 className="font-editorial text-2xl sm:text-3xl font-normal tracking-tight text-foreground">
            Save Your Cinema Journal
          </h1>
          <p className="text-sm text-foreground-secondary leading-relaxed font-sans max-w-sm mx-auto">
            Upgrade this device to a permanent account. All your watchlist titles, sessions, and ratings will be preserved.
          </p>
        </div>

        {success ? (
          <div className="py-8 flex flex-col items-center justify-center gap-4 text-center animate-in fade-in zoom-in-95 duration-300">
            <div className="size-14 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[32px]">
                verified
              </span>
            </div>
            <div className="flex flex-col gap-1">
              <h2 className="font-editorial text-2xl font-normal text-foreground">
                Membership Activated
              </h2>
              <p className="text-sm text-foreground-secondary max-w-xs mx-auto">
                Your guest journal is now saved to your account. Returning to your profile...
              </p>
            </div>
          </div>
        ) : (
          <form onSubmit={handleConvert} className="flex flex-col gap-3.5">
            {/* Email */}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary">
                Email Address
              </span>
              <div className="relative flex w-full items-stretch">
                <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">
                  mail
                </span>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  required
                  disabled={loading}
                  className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
                />
              </div>
            </label>

            {/* Display Name */}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary">
                Display Name
              </span>
              <div className="relative flex w-full items-stretch">
                <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">
                  person
                </span>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  disabled={loading}
                  className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
                />
              </div>
            </label>

            {/* Password */}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary">
                Choose Password
              </span>
              <div className="relative flex w-full items-stretch">
                <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">
                  lock
                </span>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Minimum 6 characters"
                  autoComplete="new-password"
                  required
                  disabled={loading}
                  className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-10 text-sm font-normal transition-all"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-0 h-full px-3 text-foreground-secondary hover:text-foreground transition-colors flex items-center justify-center cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[18px]">
                    {showPassword ? "visibility" : "visibility_off"}
                  </span>
                </button>
              </div>
              {password && (
                <div className="flex items-center gap-2 mt-1 px-1">
                  <div className="flex-1 h-1 bg-surface-secondary rounded-full overflow-hidden flex">
                    <div
                      className={`h-full ${passwordStrength.color} transition-all duration-300`}
                      style={{ width: `${(passwordStrength.score / 4) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-foreground-secondary font-medium">
                    {passwordStrength.label}
                  </span>
                </div>
              )}
            </label>

            {/* Confirm Password */}
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary">
                Confirm Password
              </span>
              <div className="relative flex w-full items-stretch">
                <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">
                  lock_reset
                </span>
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-type your password"
                  autoComplete="new-password"
                  required
                  disabled={loading}
                  className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
                />
              </div>
            </label>

            {/* Error message */}
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
              disabled={loading || !email || !password || !confirmPassword}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-xs cursor-pointer mt-2"
            >
              {loading ? (
                <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span>Complete Registration</span>
                  <span className="material-symbols-outlined text-[18px]">
                    arrow_forward
                  </span>
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </AuthShell>
  );
}
