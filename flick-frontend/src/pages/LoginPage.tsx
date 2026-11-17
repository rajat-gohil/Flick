import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest, ApiError } from "../lib/api";
import { AuthShell } from "../components/AuthShell";

export default function LoginPage() {
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const isEmail = identifier.includes("@");

  async function handleLogin() {
    if (!identifier || !password) { setError("Please fill in all fields"); return; }
    setError("");
    setIsLoading(true);
    try {
      const data = await apiRequest("/api/auth/login/", {
        method: "POST",
        body: JSON.stringify({ username: identifier, password }),
      });
      if (data.success) {
        localStorage.setItem("auth_token", data.token);
        if (data.display_name) {
          localStorage.setItem("display_name", data.display_name);
        }
        if (data.username) {
          localStorage.setItem("username", data.username);
        }
        navigate("/home", { replace: true });
      } else {
        setError(data.error || "Invalid credentials");
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Invalid email/username or password");
      }
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
            Welcome Back
          </h1>
          <p className="text-foreground-secondary text-xs sm:text-sm font-sans max-w-[280px] mx-auto">
            Sign in to continue curating film sessions.
          </p>
        </div>

        {/* Form */}
        <div className="bg-surface-secondary/60 rounded-2xl p-4 sm:p-5 border border-border flex flex-col gap-4">

          {/* Email or Username */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Email or Username</span>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-foreground-secondary text-[18px]">
                {isEmail ? "mail" : "person"}
              </span>
              <input
                type="text"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="Enter email or username"
                autoCapitalize="none"
                autoCorrect="off"
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
                onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                placeholder="Enter your password"
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

          {/* Forgot password */}
          <div className="flex justify-end -mt-1">
            <button
              onClick={() => navigate("/forgot-password")}
              className="text-xs text-primary hover:underline font-medium"
            >
              Forgot password?
            </button>
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
            onClick={handleLogin}
            disabled={isLoading}
            className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
          >
            {isLoading
              ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              : "Sign In"
            }
          </button>
          <p className="text-center text-xs text-foreground-secondary">
            Don't have an account?{" "}
            <button
              onClick={() => navigate("/register")}
              className="text-primary font-semibold hover:underline"
            >
              Register
            </button>
          </p>
          <div className="pt-2 border-t border-border/50 text-center">
            <button
              type="button"
              onClick={() => navigate("/recover")}
              className="inline-flex items-center gap-1.5 text-xs text-foreground-secondary hover:text-foreground font-medium transition-colors"
            >
              <span className="material-symbols-outlined text-[16px] text-primary">key</span>
              <span>Restore with Guest Recovery Code</span>
            </button>
          </div>
        </div>
      </div>
    </AuthShell>
  );
}
