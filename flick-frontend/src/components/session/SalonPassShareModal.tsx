import { useEffect, useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  renderSalonPassToCanvas,
  getCanvasBlob,
  triggerFileDownload,
  shareOrDownloadSalonPass,
  type SalonPassData,
} from "../../lib/salonPassCanvas";
import { Share2, Download, Check, Copy, X } from "lucide-react";
import { ActionButton } from "../motion/ActionButton";
import { IconTransition } from "../motion/IconTransition";
import {
  expandModalVariants,
  expandModalVariantsReduced,
  MASK_REVEAL,
  useActionStatus,
  usePrefersReducedMotion,
} from "../../lib/motion";

export interface SalonPassShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  data: SalonPassData;
}

export default function SalonPassShareModal({
  isOpen,
  onClose,
  data,
}: SalonPassShareModalProps) {
  const shouldReduceMotion = usePrefersReducedMotion();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [shareStatus, setShareStatus] = useState<string | null>(null);
  const {
    status: copyStatus,
    errorMessage: copyError,
    setPending: setCopyPending,
    setConfirmed: setCopyConfirmed,
    setError: setCopyError,
    reset: resetCopy,
  } = useActionStatus({ confirmedDurationMs: 3000, errorDurationMs: 3000 });
  const statusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (statusTimerRef.current !== null) {
        clearTimeout(statusTimerRef.current);
      }
    };
  }, []);

  const providersKey = data.streamingProviders?.join(",") || "";

  // Intercept Escape key so it closes this modal without dismissing CurtainCallMatchModal underneath
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [isOpen, onClose]);

  // Generate pass when opened or primitive pass properties change
  useEffect(() => {
    if (!isOpen) {
      setShareStatus(null);
      resetCopy();
      return;
    }

    let isMounted = true;
    setIsGenerating(true);

    const generate = async () => {
      try {
        const canvas = canvasRef.current || document.createElement("canvas");
        await renderSalonPassToCanvas(canvas, data);
        const generatedBlob = await getCanvasBlob(canvas);
        if (isMounted) {
          setBlob(generatedBlob);
          setPreviewUrl(URL.createObjectURL(generatedBlob));
          setIsGenerating(false);
        }
      } catch (err) {
        console.error("Failed to render Salon Pass:", err);
        if (isMounted) {
          setIsGenerating(false);
          setShareStatus("Failed to render pass preview.");
        }
      }
    };

    generate();

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    isOpen,
    data.movieTitle,
    data.releaseYear,
    data.rating,
    data.posterUrl,
    data.sessionCode,
    data.partnerNames,
    data.compatibilityScore,
    providersKey,
  ]);

  // Clean up preview object URL on unmount
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Handle Share to Instagram / WhatsApp
  const handleShare = useCallback(async () => {
    if (!blob) return;
    setShareStatus("Preparing share...");
    try {
      const res = await shareOrDownloadSalonPass(blob, data.movieTitle);
      if (res.success) {
        setShareStatus(res.method === "share" ? "Shared successfully!" : "Pass downloaded to device!");
      } else if (res.error) {
        setShareStatus(res.error);
      }
    } catch {
      setShareStatus("Downloaded pass fallback.");
    }
    setTimeout(() => setShareStatus(null), 3000);
  }, [blob, data.movieTitle]);

  // Handle direct download
  const handleDownload = useCallback(() => {
    if (!blob) return;
    const filename = `flick-match-${data.movieTitle.toLowerCase().replace(/[^a-z0-9]/g, "-")}.png`;
    triggerFileDownload(blob, filename);
    setShareStatus("Downloaded pass!");
    if (statusTimerRef.current !== null) {
      clearTimeout(statusTimerRef.current);
    }
    statusTimerRef.current = setTimeout(() => {
      setShareStatus(null);
      statusTimerRef.current = null;
    }, 3000);
  }, [blob, data.movieTitle]);

  // Handle Copy Link (points to landing page so viewers can start their own session)
  const handleCopyLink = useCallback(async () => {
    const url = "https://flick-kappa.vercel.app";
    setCopyPending();
    try {
      if (!navigator?.clipboard?.writeText) {
        throw new Error("Clipboard unavailable");
      }
      await navigator.clipboard.writeText(url);
      setCopyConfirmed();
      setShareStatus("Link copied to clipboard!");
      if (statusTimerRef.current !== null) {
        clearTimeout(statusTimerRef.current);
      }
      statusTimerRef.current = setTimeout(() => {
        setShareStatus(null);
        statusTimerRef.current = null;
      }, 3000);
    } catch {
      setCopyError("Could not copy link automatically.");
      setShareStatus(null);
    }
  }, [setCopyPending, setCopyConfirmed, setCopyError]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-labelledby="salon-pass-modal-title"
      onClick={onClose}
    >
        <motion.div
          variants={shouldReduceMotion ? expandModalVariantsReduced : expandModalVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          className="relative w-full max-w-sm sm:max-w-md bg-surface border border-primary/30 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-border/50 bg-surface-secondary/40">
            <div>
              <h2 id="salon-pass-modal-title" className="text-sm font-bold uppercase tracking-wider text-foreground">
                Cinéma Salon Pass
              </h2>
              <p className="text-[11px] text-foreground-secondary">
                Instagram Story & WhatsApp Status ready (9:16)
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-foreground-secondary hover:text-foreground hover:bg-surface-secondary transition-colors cursor-pointer"
              aria-label="Close modal"
            >
              <X size={18} />
            </button>
          </div>

          {/* Ticket Preview Viewport */}
          <div className="p-4 flex-1 flex flex-col items-center justify-center overflow-y-auto min-h-0 bg-background/50">
            <canvas ref={canvasRef} className="hidden" aria-hidden="true" />

            {isGenerating ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <span className="size-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-foreground-secondary font-medium tracking-wide">
                  Engraving Theatrical Salon Pass…
                </p>
              </div>
            ) : previewUrl ? (
              <motion.div
                data-testid="salon-pass-preview-reveal"
                initial={shouldReduceMotion ? MASK_REVEAL.reduced.initial : MASK_REVEAL.ticketPrint.initial}
                animate={shouldReduceMotion ? MASK_REVEAL.reduced.animate : MASK_REVEAL.ticketPrint.animate}
                className="relative group max-h-[52vh] rounded-xl overflow-hidden shadow-xl border border-primary/40"
              >
                <img
                  src={previewUrl}
                  alt={`Salon Pass for ${data.movieTitle}`}
                  className="max-h-[52vh] w-auto object-contain rounded-xl select-none"
                />
              </motion.div>
            ) : (
              <p className="text-xs text-foreground-secondary py-12">Pass preview unavailable.</p>
            )}

            {(copyError || shareStatus) && (
              <p
                role={copyError ? "alert" : "status"}
                className={`text-xs font-semibold mt-2.5 text-center ${
                  copyError ? "text-error" : "text-primary"
                }`}
              >
                {copyError || shareStatus}
              </p>
            )}
          </div>

          {/* Actions Suite */}
          <div className="p-4 border-t border-border/50 bg-surface-secondary/20 flex flex-col gap-2.5">
            {/* Primary Action: Share via Web Share API */}
            <button
              type="button"
              onClick={handleShare}
              disabled={isGenerating || !blob}
              className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs uppercase tracking-wider transition-all shadow-md active:scale-[0.98] flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <Share2 size={16} />
              <span>Share to Instagram / WhatsApp</span>
            </button>

            {/* Secondary Actions: Download PNG & Copy Link */}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={handleDownload}
                disabled={isGenerating || !blob}
                className="min-h-11 h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-medium text-xs tracking-wider transition-all active:scale-[0.98] flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Download size={14} />
                <span>Save PNG</span>
              </button>

              <ActionButton
                type="button"
                status={copyStatus}
                onClick={handleCopyLink}
                confirmedClassName="border-primary/50 bg-primary/10 text-primary"
                errorClassName="border-error/60 bg-error/10 text-error"
                className="min-h-11 h-11 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground font-medium text-xs tracking-wider transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
              >
                <IconTransition iconKey={copyStatus} sizeClassName="size-3.5">
                  {copyStatus === "confirmed" ? (
                    <Check size={14} className="text-primary" />
                  ) : (
                    <Copy size={14} />
                  )}
                </IconTransition>
                <span>
                  {copyStatus === "confirmed"
                    ? "Copied!"
                    : copyStatus === "error"
                    ? "Copy Failed"
                    : "Copy Link"}
                </span>
              </ActionButton>
            </div>
          </div>
        </motion.div>
    </div>
  );
}
