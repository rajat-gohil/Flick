import { useState } from "react";

interface RecoveryCodeModalProps {
  recoveryCode: string;
  isOpen: boolean;
  onConfirm: () => void;
  title?: string;
  subtitle?: string;
  confirmLabel?: string;
  isReplacement?: boolean;
}

export default function RecoveryCodeModal({
  recoveryCode,
  isOpen,
  onConfirm,
  title = "Your Guest Recovery Code",
  subtitle = "Store this credential in a secure place.",
  confirmLabel = "I've Saved My Code — Continue",
  isReplacement = false,
}: RecoveryCodeModalProps) {
  const [copied, setCopied] = useState(false);
  const [hasConfirmedSaved, setHasConfirmedSaved] = useState(false);
  const [copyError, setCopyError] = useState(false);

  if (!isOpen || !recoveryCode) return null;

  // Format code into 4-character blocks for visual clarity (e.g. 4F9K - 2M8P - 7Q1X - 0R5T)
  const cleanCode = recoveryCode.replace(/[^A-Za-z0-9]/g, "").toUpperCase();
  const formattedBlocks = cleanCode.match(/.{1,4}/g) || [cleanCode];

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(recoveryCode);
        setCopied(true);
        setCopyError(false);
        setTimeout(() => setCopied(false), 2500);
      } else {
        throw new Error("Clipboard API unavailable");
      }
    } catch {
      setCopyError(true);
      // Fallback: prompt user to manually select text
      setTimeout(() => setCopyError(false), 3000);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="recovery-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-xs transition-opacity"
    >
      <div
        className="relative w-full max-w-md bg-surface border border-border rounded-2xl shadow-2xl p-6 sm:p-8 flex flex-col gap-5 text-foreground animate-in fade-in zoom-in-95 duration-200"
        style={{ overflowWrap: "break-word", minWidth: 0 }}
      >
        {/* Editorial Accent */}
        <div className="h-1 w-16 bg-primary rounded-full mb-1" />

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[22px]">
              key
            </span>
            <span className="text-[11px] font-semibold text-primary uppercase tracking-widest">
              {isReplacement ? "Replacement Credential" : "Identity Key"}
            </span>
          </div>

          <h2
            id="recovery-modal-title"
            className="font-editorial text-2xl sm:text-3xl font-normal tracking-tight text-foreground"
          >
            {title}
          </h2>

          <p className="text-xs sm:text-sm text-foreground-secondary leading-relaxed font-sans">
            {subtitle}
          </p>
        </div>

        {/* Recovery Code Display */}
        <div className="bg-surface-secondary border border-border/80 rounded-xl p-4 sm:p-5 flex flex-col items-center justify-center gap-3">
          <div
            data-testid="recovery-code-display"
            className="font-mono text-xl sm:text-2xl font-bold tracking-widest text-foreground select-all text-center flex flex-wrap justify-center items-center gap-2 sm:gap-3 py-1"
          >
            {formattedBlocks.map((block, idx) => (
              <span key={idx} className="bg-surface px-2.5 py-1 rounded-md border border-border/50 shadow-2xs">
                {block}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full border border-border bg-surface hover:bg-surface-secondary text-xs font-semibold text-foreground transition-colors cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px] text-primary">
              {copied ? "check" : "content_copy"}
            </span>
            <span>{copied ? "Copied to Clipboard" : "Copy Recovery Code"}</span>
          </button>

          {copyError && (
            <p className="text-[11px] text-foreground-secondary text-center">
              Please manually highlight and copy the code above.
            </p>
          )}
        </div>

        {/* Security Warning Callout */}
        <div className="rounded-xl p-3.5 bg-primary/10 border border-primary/20 flex items-start gap-3 text-left">
          <span className="material-symbols-outlined text-primary text-[18px] shrink-0 mt-0.5">
            shield
          </span>
          <p className="text-[11px] text-foreground-secondary leading-relaxed">
            {isReplacement
              ? "This new code replaces your previous recovery code. Once acknowledged, the old code can no longer restore your journal."
              : "Flick does not store your email or password. This 16-character code is the only way to restore your watchlist and history on another device."}
          </p>
        </div>

        {/* Explicit confirmation checkbox */}
        <label className="flex items-start gap-3 cursor-pointer select-none py-1">
          <input
            type="checkbox"
            checked={hasConfirmedSaved}
            onChange={(e) => setHasConfirmedSaved(e.target.checked)}
            className="mt-0.5 size-4 rounded border-border text-primary focus:ring-primary cursor-pointer accent-primary"
          />
          <span className="text-xs text-foreground font-medium leading-snug">
            I understand that without this code, I cannot restore my cinema journal if I switch devices.
          </span>
        </label>

        {/* Confirmation Button */}
        <button
          type="button"
          onClick={onConfirm}
          disabled={!hasConfirmedSaved}
          className="w-full h-12 rounded-full bg-primary hover:bg-primary-hover text-primary-foreground font-semibold text-sm tracking-wide transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-xs cursor-pointer"
        >
          <span>{confirmLabel}</span>
          <span className="material-symbols-outlined text-[18px]">
            arrow_forward
          </span>
        </button>
      </div>
    </div>
  );
}
