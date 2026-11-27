import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { AuthShell, getPasswordStrength } from "../components/AuthShell";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const uid   = searchParams.get("uid")   ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const strength = getPasswordStrength(password);

  async function handleSubmit() {
    if (!password) { setError("Please enter a new password"); return; }
    if (password.length < 6) { setError("Password must be at least 6 characters"); return; }
    if (password !== confirmPassword) { setError("Passwords do not match"); return; }
    if (!token || !uid) { setError("Invalid or expired reset link. Please request a new one."); return; }
    setError("");
    setIsLoading(true);
    try {
      await apiRequest("/api/auth/password-reset-confirm/", {
        method: "POST",
        body: JSON.stringify({ uid, token, new_password: password }),
      });
      setSuccess(true);
    } catch {
      setError("This link has expired or is invalid. Please request a new one.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell onBack={() => navigate("/login")}>
      <div className="flex-1 overflow-y-auto px-2 pb-6 flex flex-col z-10 relative">

        {/* Header */}
        <div className="mt-4 mb-6 text-center">
          <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center mx-auto mb-4 shadow-xs">
            <span className="material-symbols-outlined text-primary text-[32px]">
              {success ? "lock_open" : "lock"}
            </span>
          </div>
          <h1 className="font-editorial text-3xl font-normal leading-tight tracking-tight text-foreground pb-1">
            {success ? "Password Updated" : "Reset Your Password"}
          </h1>
          <p className="text-foreground-secondary text-xs sm:text-sm font-sans max-w-[280px] mx-auto">
            {success
              ? "Your password has been securely updated. You can now sign in."
              : "Choose a new password for your Flick account."}
          </p>
        </div>

        {success ? (
          <div className="mt-auto pt-6">
            <button
              onClick={() => navigate("/login")}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors flex items-center justify-center shadow-xs"
            >
              Sign In to Flick
            </button>
          </div>
        ) : (
          <>
            <div className="bg-surface-secondary/60 rounded-2xl p-4 sm:p-5 border border-border flex flex-col gap-4">

              {/* New Password */}
              <label className="flex flex-col">
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">New Password</span>
                <div className="relative flex w-full items-stretch">
                  <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">lock</span>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter new password"
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

              {/* Password strength */}
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

              {/* Confirm Password */}
              <label className="flex flex-col">
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Confirm Password</span>
                <div className="relative flex w-full items-stretch">
                  <span className="material-symbols-outlined absolute left-3.5 top-1/2 -translate-y-1/2 text-foreground-secondary text-[18px]">lock_clock</span>
                  <input
                    type={showConfirm ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-10 text-sm font-normal transition-all"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm(!showConfirm)}
                    aria-label={showConfirm ? "Hide confirmation password" : "Show confirmation password"}
                    className="absolute right-0 h-full px-3 text-foreground-secondary hover:text-foreground transition-colors flex items-center justify-center"
                  >
                    <span className="material-symbols-outlined text-[18px]">
                      {showConfirm ? "visibility" : "visibility_off"}
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
            </div>

            {error && (
              <div className="mt-3 p-3 bg-error/10 border border-error/20 rounded-xl">
                <p className="text-xs text-error text-center font-medium">{error}</p>
              </div>
            )}

            <div className="mt-auto pt-6 flex flex-col gap-3">
              <button
                onClick={handleSubmit}
                disabled={isLoading}
                className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
              >
                {isLoading
                  ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
                  : "Save New Password"
                }
              </button>
            </div>
          </>
        )}
      </div>
    </AuthShell>
  );
}
