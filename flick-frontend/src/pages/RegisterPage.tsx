import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { AuthShell, getPasswordStrength } from "../components/AuthShell";

/* ── Reuse social login logic from LoginPage ───────────────────── */
async function socialLogin(
  provider: "google" | "apple",
  navigate: ReturnType<typeof useNavigate>,
  setError: (e: string) => void,
  setLoading: (b: boolean) => void
) {
  setLoading(true);
  setError("");
  try {
    let token = "";

    if (provider === "google") {
      token = await new Promise<string>((resolve, reject) => {
        const w = window as any;
        if (!w.google?.accounts?.id) {
          reject(new Error("Google Sign-In SDK not loaded."));
          return;
        }
        w.google.accounts.id.initialize({
          client_id: (window as any).__GOOGLE_CLIENT_ID__ || "",
          callback: (resp: any) => {
            if (resp.credential) resolve(resp.credential);
            else reject(new Error("No credential from Google"));
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        w.google.accounts.id.prompt((notification: any) => {
          if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
            reject(new Error("Google Sign-In was dismissed"));
          }
        });
      });
    } else {
      token = await new Promise<string>((resolve, reject) => {
        const w = window as any;
        if (!w.AppleID) {
          reject(new Error("Apple Sign In SDK not loaded."));
          return;
        }
        w.AppleID.auth.init({
          clientId: (window as any).__APPLE_CLIENT_ID__ || "",
          scope: "name email",
          redirectURI: window.location.origin + "/auth/callback",
          usePopup: true,
        });
        w.AppleID.auth.signIn()
          .then((resp: any) => resolve(resp.authorization?.id_token || ""))
          .catch(reject);
      });
    }

    const data = await apiRequest("/api/auth/social/", {
      method: "POST",
      body: JSON.stringify({ provider, token }),
    });

    if (data.success) {
      localStorage.setItem("auth_token", data.token);
      if (data.needs_username) {
        navigate("/username", { state: { email: data.email }, replace: true });
      } else {
        navigate("/home", { replace: true });
      }
    } else {
      setError(data.error || "Social sign-up failed");
    }
  } catch (err: unknown) {
    const e = err as Record<string, unknown> & { data?: Record<string, unknown> };
    const message =
      (e?.error as string) ||
      (e?.data?.error as string) ||
      (err instanceof Error ? err.message : "") ||
      "Social sign-up failed";
    setError(message);
  } finally {
    setLoading(false);
  }
}

export default function RegisterPage() {
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [agreePrivacy, setAgreePrivacy] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState<"google" | "apple" | null>(null);

  const strength = getPasswordStrength(password);

  async function handleRegister() {
    if (!displayName.trim()) { setError("Please enter your display name"); return; }
    if (displayName.trim().length < 2 || displayName.trim().length > 50) {
      setError("Display name must be between 2 and 50 characters");
      return;
    }
    if (!email || !password) { setError("Please fill in all fields"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Please enter a valid email address"); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters"); return; }
    if (password !== confirmPassword) { setError("Passwords do not match"); return; }
    if (!agreeTerms || !agreePrivacy) { setError("Please accept the terms and privacy policy"); return; }
    setError("");
    setIsLoading(true);
    try {
      const registerData = await apiRequest("/api/auth/register/", {
        method: "POST",
        body: JSON.stringify({ email, password, display_name: displayName.trim() }),
      });
      if (!registerData.success) { setError(registerData.error || "Registration failed"); return; }

      const loginData = await apiRequest("/api/auth/login/", {
        method: "POST",
        body: JSON.stringify({ username: email, password }),
      });
      if (loginData.success) {
        localStorage.setItem("auth_token", loginData.token);
        if (loginData.display_name) {
          localStorage.setItem("display_name", loginData.display_name);
        } else {
          localStorage.setItem("display_name", displayName.trim());
        }
        if (loginData.username) {
          localStorage.setItem("username", loginData.username);
        }
        apiRequest("/api/auth/send-verification/", { method: "POST" }).catch(() => {});
        navigate("/username", { state: { email }, replace: true });
      } else {
        setError("Account created! Please log in to continue.");
        setTimeout(() => navigate("/login", { state: { email } }), 1500);
      }
    } catch (err: unknown) {
      const e = err as Record<string, unknown> & { data?: Record<string, unknown> };
      const message =
        (e?.error as string) ||
        (e?.data?.error as string) ||
        (err instanceof Error ? err.message : "") ||
        "Registration failed. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell onBack={() => navigate("/")}>
      <div className="flex-1 overflow-y-auto px-2 pb-6 flex flex-col z-10 relative">

        {/* Heading */}
        <div className="mt-2 mb-6 text-center">
          <h1 className="font-editorial text-3xl font-normal leading-tight tracking-tight text-foreground pb-1">
            Create an Account
          </h1>
          <p className="text-foreground-secondary text-xs sm:text-sm font-sans max-w-[280px] mx-auto">
            Join Flick to start discovering curated cinema together.
          </p>
        </div>

        {/* Social sign-up */}
        <div className="flex flex-col gap-2.5 mb-5">
          <button
            onClick={() => socialLogin("google", navigate, setError, (b) => setSocialLoading(b ? "google" : null))}
            disabled={!!socialLoading || isLoading}
            className="w-full h-12 rounded-xl bg-surface border border-border flex items-center justify-center gap-3 font-medium text-foreground hover:bg-surface-secondary transition-colors disabled:opacity-60 shadow-xs text-sm"
          >
            {socialLoading === "google" ? (
              <span className="size-4 border-2 border-foreground-secondary border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                Sign up with Google
              </>
            )}
          </button>

          <button
            onClick={() => socialLogin("apple", navigate, setError, (b) => setSocialLoading(b ? "apple" : null))}
            disabled={!!socialLoading || isLoading}
            className="w-full h-12 rounded-xl bg-surface border border-border flex items-center justify-center gap-3 font-medium text-foreground hover:bg-surface-secondary transition-colors disabled:opacity-60 shadow-xs text-sm"
          >
            {socialLoading === "apple" ? (
              <span className="size-4 border-2 border-foreground-secondary border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                </svg>
                Sign up with Apple
              </>
            )}
          </button>
        </div>

        {/* Divider */}
        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-border" />
          <span className="text-[11px] text-foreground-secondary tracking-widest uppercase font-medium">or register with email</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        {/* Form */}
        <div className="bg-surface-secondary/60 rounded-2xl p-4 sm:p-5 border border-border flex flex-col gap-4">

          {/* Display Name */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Your Name</span>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-foreground-secondary text-[18px]">badge</span>
              <input
                type="text"
                value={displayName}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setDisplayName(e.target.value)}
                placeholder="e.g. Rajat"
                maxLength={50}
                className="flex w-full rounded-xl text-foreground focus:outline-hidden focus:ring-1 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/60 pl-10 pr-4 text-sm font-normal transition-all"
              />
            </div>
          </label>

          {/* Email */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Email</span>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-foreground-secondary text-[18px]">mail</span>
              <input
                type="email"
                value={email}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setEmail(e.target.value)}
                placeholder="Enter your email address"
                className="flex w-full rounded-xl text-foreground focus:outline-hidden focus:ring-1 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/60 pl-10 pr-4 text-sm font-normal transition-all"
              />
            </div>
          </label>

          {/* Password */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Password</span>
            <div className="relative flex w-full items-stretch">
              <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">lock</span>
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPassword(e.target.value)}
                placeholder="Create a password"
                className="flex w-full rounded-xl text-foreground focus:outline-hidden focus:ring-1 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/60 pl-10 pr-10 text-sm font-normal transition-all"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-0 h-full px-3 text-foreground-secondary hover:text-foreground transition-colors flex items-center justify-center"
              >
                <span className="material-symbols-outlined text-[18px]">
                  {showPassword ? "visibility" : "visibility_off"}
                </span>
              </button>
            </div>
          </label>

          {/* Strength meter */}
          {password.length > 0 && (
            <div className="flex flex-col gap-1.5 px-0.5 -mt-1">
              <div className="flex gap-1.5 h-1.5 w-full">
                {[0, 1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={`flex-1 rounded-full transition-all ${
                      i < strength.score ? strength.color : "bg-border"
                    }`}
                  />
                ))}
              </div>
              {strength.label && (
                <span className="text-[11px] font-medium text-right text-foreground-secondary">
                  Strength: {strength.label}
                </span>
              )}
            </div>
          )}

          {/* Confirm password */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Confirm Password</span>
            <div className="relative flex w-full items-stretch">
              <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">lock_clock</span>
              <input
                type={showConfirmPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setConfirmPassword(e.target.value)}
                placeholder="Repeat your password"
                className="flex w-full rounded-xl text-foreground focus:outline-hidden focus:ring-1 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/60 pl-10 pr-10 text-sm font-normal transition-all"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                className="absolute right-0 h-full px-3 text-foreground-secondary hover:text-foreground transition-colors flex items-center justify-center"
              >
                <span className="material-symbols-outlined text-[18px]">
                  {showConfirmPassword ? "visibility" : "visibility_off"}
                </span>
              </button>
            </div>
            {confirmPassword.length > 0 && (
              <div className={`flex items-center gap-1.5 mt-1 ml-0.5 text-xs font-medium ${
                password === confirmPassword ? "text-primary" : "text-error"
              }`}>
                <span className="material-symbols-outlined text-[14px]">
                  {password === confirmPassword ? "check_circle" : "cancel"}
                </span>
                {password === confirmPassword ? "Passwords match" : "Passwords do not match"}
              </div>
            )}
          </label>

          {/* Agreements */}
          <div className="flex flex-col gap-2.5 mt-1 pt-1 border-t border-border/50">
            {[
              { checked: agreeTerms,   toggle: () => setAgreeTerms(!agreeTerms),     label: "I agree to the",  linkText: "Terms of Service" },
              { checked: agreePrivacy, toggle: () => setAgreePrivacy(!agreePrivacy), label: "I accept the",    linkText: "Privacy Policy" },
            ].map(({ checked, toggle, label, linkText }) => {
              const href = linkText === "Terms of Service" ? "/terms" : "/privacy";
              return (
                <label key={linkText} className="flex items-start gap-2.5 cursor-pointer">
                  <div className="relative flex items-center justify-center shrink-0 mt-0.5">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={toggle}
                      className="sr-only"
                    />
                    <div
                      onClick={toggle}
                      className={`w-4 h-4 rounded border transition-colors flex items-center justify-center cursor-pointer ${
                        checked ? "bg-primary border-primary text-primary-foreground" : "border-border bg-surface"
                      }`}
                    >
                      {checked && <span className="material-symbols-outlined text-[12px]">check</span>}
                    </div>
                  </div>
                  <span className="text-foreground-secondary text-xs leading-tight flex-1">
                    {label}{" "}
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e: React.MouseEvent<HTMLAnchorElement>) => e.stopPropagation()}
                      className="text-primary hover:underline font-medium"
                    >
                      {linkText}
                    </a>
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="mt-3 p-3 bg-error/10 border border-error/20 rounded-xl">
            <p className="text-xs text-error text-center font-medium">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="mt-6 pt-2 flex flex-col gap-3">
          <button
            onClick={handleRegister}
            disabled={isLoading || !!socialLoading}
            className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
          >
            {isLoading
              ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              : "Create Account"
            }
          </button>
          <p className="text-center text-xs text-foreground-secondary">
            Already have an account?{" "}
            <button
              onClick={() => navigate("/login")}
              className="text-primary font-semibold hover:underline"
            >
              Sign In
            </button>
          </p>
        </div>
      </div>
    </AuthShell>
  );
}
