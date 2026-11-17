import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { AuthShell } from "../components/AuthShell";

export default function ForgotPasswordPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit() {
    if (!email.trim()) {
      setError("Please enter your email address");
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      await apiRequest("/api/auth/password-reset/", {
        method: "POST",
        body: JSON.stringify({ email }),
      });
      setSent(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell onBack={() => navigate(-1)}>
      <div className="flex-1 overflow-y-auto px-2 pb-6 flex flex-col z-10 relative">

        {/* Header */}
        <div className="mt-4 mb-6 text-center">
          <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center mx-auto mb-4 shadow-xs">
            <span className="material-symbols-outlined text-primary text-[32px]">lock_reset</span>
          </div>
          <h1 className="font-editorial text-3xl font-normal leading-tight tracking-tight text-foreground pb-1">
            Forgot Password?
          </h1>
          <p className="text-foreground-secondary text-xs sm:text-sm font-sans max-w-[280px] mx-auto">
            Enter your email and we'll dispatch a secure recovery link.
          </p>
        </div>

        {/* ── SENT STATE ── */}
        {sent ? (
          <div className="flex flex-col items-center text-center gap-5 my-auto">
            <div className="size-16 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[32px]">mark_email_read</span>
            </div>
            <div>
              <h2 className="font-editorial text-2xl font-normal mb-2 text-foreground">Check your inbox</h2>
              <p className="text-foreground-secondary text-xs sm:text-sm leading-relaxed max-w-[260px] mx-auto">
                We sent a reset link to{" "}
                <span className="text-foreground font-medium">{email}</span>.
                Please check your inbox or spam directory.
              </p>
            </div>

            <div className="bg-surface-secondary/70 rounded-xl p-3 border border-border w-full text-left">
              <p className="text-[10px] text-foreground-secondary mb-1 font-semibold uppercase tracking-wider">Didn't receive it?</p>
              <button
                onClick={() => { setSent(false); setEmail(""); }}
                className="text-xs text-primary font-medium hover:underline"
              >
                Try a different email address
              </button>
            </div>

            <button
              onClick={() => navigate("/login")}
              className="w-full h-12 rounded-full border border-border hover:bg-surface-secondary text-foreground font-semibold text-sm transition-colors mt-2"
            >
              Back to Sign In
            </button>
          </div>
        ) : (
          <>
            <div className="bg-surface-secondary/60 rounded-2xl p-4 sm:p-5 border border-border flex flex-col gap-4">
              <label className="flex flex-col">
                <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Email Address</span>
                <div className="relative flex items-center">
                  <span className="material-symbols-outlined absolute left-3.5 text-foreground-secondary text-[18px]">mail</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
                    placeholder="Enter registered email"
                    className="flex w-full rounded-xl text-foreground focus:outline-hidden focus:ring-1 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/60 pl-10 pr-4 text-sm font-normal transition-all"
                  />
                </div>
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
                  : "Send Recovery Link"
                }
              </button>
              <button
                onClick={() => navigate("/login")}
                className="text-center text-xs text-foreground-secondary hover:text-foreground font-medium py-1"
              >
                Return to Sign In
              </button>
            </div>
          </>
        )}
      </div>
    </AuthShell>
  );
}
