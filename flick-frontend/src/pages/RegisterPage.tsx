import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { AuthShell, getPasswordStrength } from "../components/AuthShell";

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
                className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
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
                className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
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
                className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-10 text-sm font-normal transition-all"
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
                <span className="text-xs font-medium text-right text-foreground-secondary">
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
                className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-10 text-sm font-normal transition-all"
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
            disabled={isLoading}
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
