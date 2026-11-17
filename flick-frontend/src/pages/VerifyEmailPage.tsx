import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { apiRequest } from "../lib/api";
import { AuthShell } from "../components/AuthShell";

/* ======================================================
   VERIFY EMAIL PAGE — Art-House Editorial Style
====================================================== */
export default function VerifyEmailPage() {
  const navigate     = useNavigate();
  const [params]     = useSearchParams();
  const uid          = params.get("uid");
  const token        = params.get("token");

  const [status, setStatus]   = useState<"idle" | "verifying" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [resending, setResending] = useState(false);
  const [resent, setResent]    = useState(false);

  useEffect(() => {
    if (uid && token) {
      setStatus("verifying");
      apiRequest("/api/auth/verify-email/", {
        method: "POST",
        body: JSON.stringify({ uid, token }),
      })
        .then((data) => {
          if (data.success) {
            setStatus("success");
          } else {
            setStatus("error");
            setMessage(data.error || "Verification failed. The link may have expired.");
          }
        })
        .catch(() => {
          setStatus("error");
          setMessage("Something went wrong. Please try again.");
        });
    }
  }, [uid, token]);

  const handleResend = async () => {
    setResending(true);
    try {
      await apiRequest("/api/auth/send-verification/", { method: "POST" });
      setResent(true);
    } catch {
      // silent
    } finally {
      setResending(false);
    }
  };

  return (
    <AuthShell onBack={() => navigate("/home")}>
      <div className="flex-1 overflow-y-auto px-2 pb-6 flex flex-col items-center justify-center text-center z-10 relative">

        {/* ── Verifying ── */}
        {status === "verifying" && (
          <div className="flex flex-col items-center gap-4 my-auto">
            <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center shadow-xs">
              <div className="size-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            </div>
            <div>
              <h1 className="font-editorial text-2xl font-normal mb-1 text-foreground">Verifying credentials…</h1>
              <p className="text-foreground-secondary text-xs sm:text-sm font-sans">Connecting your account to Flick.</p>
            </div>
          </div>
        )}

        {/* ── Success ── */}
        {status === "success" && (
          <div className="flex flex-col items-center gap-5 my-auto w-full max-w-xs">
            <div className="size-16 rounded-full bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[36px]">verified</span>
            </div>
            <div>
              <h1 className="font-editorial text-3xl font-normal mb-2 text-foreground">Email Confirmed</h1>
              <p className="text-foreground-secondary text-xs sm:text-sm leading-relaxed">
                Your email address has been confirmed. You now have full access to discovery sessions.
              </p>
            </div>
            <button
              onClick={() => navigate("/home", { replace: true })}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors shadow-xs mt-2"
            >
              Enter Flick
            </button>
          </div>
        )}

        {/* ── Error ── */}
        {status === "error" && (
          <div className="flex flex-col items-center gap-5 my-auto w-full max-w-xs">
            <div className="size-16 rounded-2xl bg-error/10 border border-error/25 flex items-center justify-center text-error">
              <span className="material-symbols-outlined text-[36px]">link_off</span>
            </div>
            <div>
              <h1 className="font-editorial text-3xl font-normal mb-2 text-foreground">Link Expired</h1>
              <p className="text-foreground-secondary text-xs sm:text-sm leading-relaxed">
                {message || "This verification link is invalid or has timed out."}
              </p>
            </div>
            <button
              onClick={handleResend}
              disabled={resending || resent}
              className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-60 shadow-xs mt-2"
            >
              {resent ? "Email Dispatched!" : resending ? "Sending..." : "Request New Link"}
            </button>
            <button
              onClick={() => navigate("/home")}
              className="text-xs text-foreground-secondary hover:text-foreground font-medium py-1"
            >
              Continue to Home
            </button>
          </div>
        )}

        {/* ── Idle (holding screen right after register) ── */}
        {status === "idle" && (
          <div className="flex flex-col items-center gap-5 my-auto w-full max-w-xs">
            <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center text-primary shadow-xs">
              <span className="material-symbols-outlined text-[36px]">mark_email_unread</span>
            </div>
            <div>
              <h1 className="font-editorial text-3xl font-normal mb-2 text-foreground">Check Your Email</h1>
              <p className="text-foreground-secondary text-xs sm:text-sm leading-relaxed">
                We've sent a verification link to your registered email. Click the link to complete verification.
              </p>
            </div>
            <div className="w-full flex flex-col gap-2.5 mt-2">
              <button
                onClick={handleResend}
                disabled={resending || resent}
                className="w-full h-12 rounded-full border border-border hover:bg-surface-secondary text-foreground font-semibold text-sm transition-colors disabled:opacity-60"
              >
                {resent ? "Link Sent!" : resending ? "Sending..." : "Resend Verification Email"}
              </button>
              <button
                onClick={() => navigate("/home")}
                className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors shadow-xs"
              >
                Proceed to Home
              </button>
            </div>
          </div>
        )}

      </div>
    </AuthShell>
  );
}
