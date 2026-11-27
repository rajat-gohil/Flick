/* ============================
   SHARED AUTH SHELL — Art-House Editorial Style
   Used by LoginPage, RegisterPage, UsernamePage
============================ */
import AnimatedFlickLogo from "./AnimatedFlickLogo";

export function AuthShell({
  onBack,
  children,
}: {
  onBack: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="relative bg-background text-foreground font-sans min-h-screen flex flex-col items-center justify-center sm:p-6 antialiased transition-colors duration-200">
      <div className="w-full h-full sm:h-auto sm:max-w-[420px] bg-surface text-foreground sm:rounded-2xl sm:shadow-lg overflow-hidden flex flex-col relative sm:border border-border">
        {/* Subtle top editorial rule */}
        <div className="h-1 w-full bg-primary/40" />

        <div className="flex items-center p-4 pb-2 justify-between z-10 border-b border-border/50">
          <button
            onClick={onBack}
            aria-label="Go back"
            className="text-foreground-secondary hover:text-foreground flex size-11 shrink-0 items-center justify-center hover:bg-surface-secondary rounded-full transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[20px]">arrow_back_ios</span>
          </button>
          <div className="flex-1 flex items-center justify-center gap-2 pr-11">
            <AnimatedFlickLogo
              variant="mark"
              decorative
              className="size-7 rounded-lg ring-1 ring-border shadow-2xs"
            />
            <span className="font-display text-base font-bold tracking-tight text-foreground">
              Flick
            </span>
          </div>
        </div>
        <div className="p-6 pt-4 flex-1 flex flex-col justify-between">
          {children}
        </div>
      </div>
    </div>
  );
}

/* ============================
   PASSWORD STRENGTH HELPER
============================ */

export function getPasswordStrength(password: string): {
  score: number;
  label: string;
  color: string;
} {
  if (!password) return { score: 0, label: "", color: "" };
  let score = 0;
  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  const map = [
    { label: "Weak",   color: "bg-error" },
    { label: "Fair",   color: "bg-amber-600" },
    { label: "Good",   color: "bg-amber-500" },
    { label: "Strong", color: "bg-primary" },
    { label: "Strong", color: "bg-primary" },
  ];
  return { score, ...map[score] };
}

/* ============================
   USERNAME SUGGESTIONS
============================ */

export function generateUsernameSuggestions(email: string): string[] {
  const base = email.split("@")[0].replace(/[^a-zA-Z0-9]/g, "");
  return [
    base.toLowerCase(),
    `${base.toLowerCase()}${Math.floor(Math.random() * 1000)}`,
    `${base.toLowerCase()}_${Math.floor(Math.random() * 100)}`,
    `user_${base.toLowerCase()}`,
  ].slice(0, 4);
}
