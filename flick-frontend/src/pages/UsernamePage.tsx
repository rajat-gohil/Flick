import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { apiRequest, ApiError } from "../lib/api";
import { AuthShell, generateUsernameSuggestions } from "../components/AuthShell";

export default function UsernamePage() {
  const navigate = useNavigate();
  const location = useLocation();

  const email = (location.state as { email?: string } | null)?.email ?? "";

  const [username, setUsername] = useState("");
  const [suggestions] = useState<string[]>(() =>
    email ? generateUsernameSuggestions(email) : []
  );
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function handleSubmit() {
    if (!username.trim()) { setError("Please enter a username"); return; }
    setError("");
    setIsLoading(true);
    try {
      const response = await apiRequest("/api/users/update-username/", {
        method: "POST",
        body: JSON.stringify({ username: username.trim() }),
      });
      if (response.success) {
        navigate("/home", { replace: true });
      } else {
        setError(response.error || "Username taken or invalid. Try another.");
      }
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : err instanceof Error ? err.message : "Username taken or invalid. Try another.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <AuthShell onBack={() => navigate("/register")}>
      <div className="flex-1 overflow-y-auto px-2 pb-6 flex flex-col z-10 relative">

        {/* Heading */}
        <div className="mt-4 mb-6 text-center">
          <div className="size-16 rounded-2xl bg-surface-secondary border border-border flex items-center justify-center mx-auto mb-4 shadow-xs">
            <span className="material-symbols-outlined text-primary text-[32px]">badge</span>
          </div>
          <h1 className="font-editorial text-3xl font-normal leading-tight tracking-tight text-foreground pb-1">
            Choose Your Pen Name
          </h1>
          <p className="text-foreground-secondary text-xs sm:text-sm font-sans max-w-[260px] mx-auto">
            This name will appear on shared session cards and mutual matches.
          </p>
        </div>

        {/* Form card */}
        <div className="bg-surface-secondary/60 rounded-2xl p-4 sm:p-5 border border-border flex flex-col gap-4">

          {/* Input */}
          <label className="flex flex-col">
            <span className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary pb-1 ml-0.5">Username</span>
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-3.5 text-foreground-secondary text-[18px]">
                alternate_email
              </span>
              <input
                type="text"
                value={username}
                onChange={(e) =>
                  setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ""))
                }
                placeholder="e.g. moviebuff_42"
                maxLength={20}
                className="flex w-full rounded-xl text-foreground focus-visible:outline-2 focus-visible:outline-focus focus:ring-2 focus:ring-primary border border-border bg-surface h-12 placeholder:text-foreground-secondary/75 pl-10 pr-4 text-sm font-normal transition-all"
              />
            </div>
            <p className="text-xs text-foreground-secondary mt-1 ml-0.5">
              Only lowercase letters, numbers, and underscores
            </p>
          </label>

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-foreground-secondary mb-2 ml-0.5">Suggestions</p>
              <div className="grid grid-cols-2 gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setUsername(s)}
                    className={`rounded-xl border px-3 min-h-11 sm:min-h-9 py-2 text-sm text-left transition-all cursor-pointer ${
                      username === s
                        ? "border-primary bg-primary/10 text-primary font-semibold"
                        : "border-border bg-surface text-foreground-secondary hover:border-primary/50 hover:text-foreground"
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mt-3 p-3 bg-error/10 border border-error/20 rounded-xl">
            <p className="text-xs text-error text-center font-medium">{error}</p>
          </div>
        )}

        {/* Actions */}
        <div className="mt-auto pt-6 flex flex-col gap-3">
          <button
            onClick={handleSubmit}
            disabled={isLoading || !username.trim()}
            className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-60 flex items-center justify-center shadow-xs"
          >
            {isLoading
              ? <span className="size-4 border-2 border-primary-foreground border-t-transparent rounded-full animate-spin" />
              : "Save & Continue"
            }
          </button>
        </div>
      </div>
    </AuthShell>
  );
}
