import { useState } from "react";

const STEPS = [
  {
    icon: "group",
    title: "Invite a Partner",
    body: "Create a session and share your invite code or link. Join together in one tap.",
  },
  {
    icon: "touch_app",
    title: "Swipe in Real Time",
    body: "Explore cinematic recommendations simultaneously. Swipe right to like, left to pass.",
  },
  {
    icon: "favorite",
    title: "Instant Mutual Matches",
    body: "When you both appreciate the same film, it's an immediate match. Save to your watchlist and stream.",
  },
];

const STORAGE_KEY = "flick_onboarding_done";

export default function OnboardingOverlay({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const [exiting, setExiting] = useState(false);

  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  const handleNext = () => {
    if (isLast) {
      setExiting(true);
      setTimeout(() => {
        localStorage.setItem(STORAGE_KEY, "1");
        onDone();
      }, 300);
    } else {
      setStep(s => s + 1);
    }
  };

  const handleSkip = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    onDone();
  };

  return (
    <div
      className={`fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background/95 backdrop-blur-md transition-opacity duration-300 ${exiting ? "opacity-0" : "opacity-100"}`}
    >
      <div className="w-full max-w-sm mx-auto px-6 flex flex-col items-center text-center gap-8">

        {/* Step indicator rules */}
        <div className="flex gap-2">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-300 ${
                i === step ? "w-8 bg-primary" : i < step ? "w-4 bg-primary/40" : "w-4 bg-border"
              }`}
            />
          ))}
        </div>

        {/* Icon card */}
        <div className="size-24 rounded-2xl bg-surface border border-border flex items-center justify-center shadow-md transition-all duration-300">
          <span className="material-symbols-outlined text-[44px] text-primary">{current.icon}</span>
        </div>

        {/* Text */}
        <div className="flex flex-col gap-3">
          <h2 className="font-editorial text-3xl font-normal text-foreground leading-tight">
            {current.title}
          </h2>
          <p className="text-foreground-secondary text-sm sm:text-base leading-relaxed">
            {current.body}
          </p>
        </div>

        {/* CTA */}
        <div className="flex flex-col gap-3 w-full">
          <button
            onClick={handleNext}
            className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors duration-150 shadow-sm"
          >
            {isLast ? "Begin Exploring" : "Continue"}
          </button>
          {!isLast && (
            <button
              onClick={handleSkip}
              className="text-xs tracking-wider uppercase text-foreground-secondary hover:text-foreground transition-colors py-2 font-medium"
            >
              Skip Introduction
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
