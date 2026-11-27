import React, { useEffect, useState, useCallback } from "react";
import { apiRequest } from "../../lib/api";
import { trackEvent } from "../../lib/analytics";
import {
  formatConstraintLabel,
  formatConstraintValue,
  updateGenreCache,
} from "../../lib/formatConstraints";

export interface DecisionInfo {
  decision: "approve" | "approved" | "decline" | "declined" | "pending";
  decided_at?: string | null;
}

function parseDecision(dec: string | DecisionInfo | null | undefined): "approved" | "declined" | "pending" {
  if (!dec) return "pending";
  const val = typeof dec === "object" ? dec.decision : dec;
  if (!val) return "pending";
  const normalized = String(val).toLowerCase().trim();
  if (normalized === "approve" || normalized === "approved") return "approved";
  if (normalized === "decline" || normalized === "declined" || normalized === "reject" || normalized === "rejected") return "declined";
  return "pending";
}

export interface ConstraintProposalData {
  id: string;
  session_id: number;
  status:
    | "pending"
    | "approved_queued"
    | "replenishment_running"
    | "replenishment_completed"
    | "replenishment_failed"
    | "replenishment_insufficient"
    | "declined"
    | "expired"
    | "superseded";
  initiated_by_user_id: number;
  initiated_by_username: string;
  original_constraints: Record<string, unknown>;
  proposed_constraints: Record<string, unknown>;
  host_decision: string | DecisionInfo;
  guest_decision: string | DecisionInfo;
  created_at: string;
  expires_at: string;
  completed_at?: string | null;
  error_message?: string | null;
  is_expired: boolean;
  is_mutually_approved: boolean;
}

interface ConstraintExhaustionNoticeModalProps {
  isOpen: boolean;
  sessionId: string | number;
  userRole?: "host" | "guest" | null;
  onClose?: () => void;
  onReplenished?: () => void;
  onConcludeSession?: () => void;
  onAdjustPreferences?: () => void;
}

export const ConstraintExhaustionNoticeModal: React.FC<ConstraintExhaustionNoticeModalProps> = ({
  isOpen,
  sessionId,
  userRole,
  onClose,
  onReplenished,
  onConcludeSession,
  onAdjustPreferences,
}) => {
  const [proposal, setProposal] = useState<ConstraintProposalData | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchProposal = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    try {
      const res = await apiRequest(`/api/sessions/${sessionId}/expand-constraints/`);
      if (res && res.success) {
        const active = res.active_proposal || res.latest_proposal || null;
        setProposal(active);
        if (active?.status === "replenishment_completed" && onReplenished) {
          onReplenished();
        }
      }
    } catch (err: unknown) {
      console.warn("[ConstraintModal] Failed to fetch proposal:", err);
    } finally {
      setLoading(false);
    }
  }, [sessionId, onReplenished]);

  useEffect(() => {
    if (isOpen) {
      fetchProposal();
      const interval = setInterval(fetchProposal, 4000);
      return () => clearInterval(interval);
    }
  }, [isOpen, fetchProposal]);

  useEffect(() => {
    if (isOpen) {
      apiRequest("/api/genres/?industry=mixed")
        .then((res) => {
          if (Array.isArray(res?.genres)) {
            updateGenreCache(res.genres);
          }
        })
        .catch(() => {
          // Seamless fallback to canonical genre data
        });
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handlePropose = async () => {
    setActionLoading(true);
    setErrorMessage(null);
    try {
      await apiRequest(`/api/sessions/${sessionId}/expand-constraints/`, {
        method: "POST",
        body: JSON.stringify({ action: "propose", auto_approve: true }),
      });
      trackEvent("constraint_expansion_proposed", { session_id: Number(sessionId) });
      await fetchProposal();
    } catch (err: unknown) {
      const apiErr = err as { data?: { error?: string }; message?: string };
      setErrorMessage(apiErr?.data?.error || apiErr?.message || "Failed to submit proposal");
    } finally {
      setActionLoading(false);
    }
  };

  const handleRespond = async (decision: "approve" | "decline") => {
    if (!proposal) return;
    setActionLoading(true);
    setErrorMessage(null);
    try {
      await apiRequest(`/api/sessions/${sessionId}/expand-constraints/`, {
        method: "POST",
        body: JSON.stringify({
          action: "respond",
          proposal_id: proposal.id,
          decision,
        }),
      });
      trackEvent(
        decision === "approve" ? "constraint_expansion_accepted" : "constraint_expansion_rejected",
        { session_id: Number(sessionId), proposal_id: proposal.id }
      );
      await fetchProposal();
    } catch (err: unknown) {
      const apiErr = err as { data?: { error?: string }; message?: string };
      setErrorMessage(apiErr?.data?.error || apiErr?.message || "Failed to record response");
    } finally {
      setActionLoading(false);
    }
  };

  const myDecisionRaw = userRole === "host" ? proposal?.host_decision : proposal?.guest_decision;
  const partnerDecisionRaw = userRole === "host" ? proposal?.guest_decision : proposal?.host_decision;
  const myDecisionStr = parseDecision(myDecisionRaw);
  const partnerDecisionStr = parseDecision(partnerDecisionRaw);
  const hasVoted = myDecisionStr !== "pending";
  const isPending = proposal?.status === "pending";
  const isReplenishing =
    proposal?.status === "approved_queued" || proposal?.status === "replenishment_running";
  const isInsufficient = proposal?.status === "replenishment_insufficient";
  const isFailed = proposal?.status === "replenishment_failed";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="constraint-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-xl text-foreground flex flex-col gap-4 animate-in fade-in-50 zoom-in-95">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shrink-0">
            <span className="material-symbols-outlined text-[22px]">tune</span>
          </div>
          <div>
            <span className="text-[10px] uppercase tracking-widest font-semibold text-primary block">
              Curatorial Notice
            </span>
            <h2 id="constraint-modal-title" className="font-editorial text-xl font-semibold leading-snug">
              Candidate Pool Exhausted
            </h2>
          </div>
        </div>

        <p className="text-xs text-foreground-secondary leading-relaxed">
          The collaborative pool currently has fewer than 16 films strictly matching both taste
          profiles. To discover additional films together, mutual constraint expansion is required.
        </p>

        {errorMessage && (
          <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs leading-tight">
            {errorMessage}
          </div>
        )}

        {/* Existing proposal state */}
        {proposal && (
          <div className="p-4 rounded-xl border border-border/80 bg-surface-secondary/50 flex flex-col gap-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-medium text-foreground">Status:</span>
              <span
                data-testid="proposal-status"
                className="font-semibold uppercase text-[10px] tracking-wider px-2 py-0.5 rounded-full bg-primary/15 text-primary"
              >
                {proposal.status.replace(/_/g, " ")}
              </span>
            </div>

            {/* Constraint Diff */}
            {proposal.proposed_constraints && (
              <div className="flex flex-col gap-1.5 pt-1 border-t border-border/50 text-[11px]">
                <span className="font-semibold text-foreground-secondary">Proposed Adjustments:</span>
                <ul className="list-disc list-inside space-y-1 text-foreground-secondary">
                  {Object.entries(proposal.proposed_constraints).map(([key, val]) => (
                    <li key={key} data-testid={`constraint-item-${key}`} className="leading-snug break-words">
                      <span className="font-medium text-foreground-secondary">
                        {formatConstraintLabel(key)}:{" "}
                      </span>
                      <span className="font-semibold text-foreground" data-testid={`constraint-val-${key}`}>
                        {formatConstraintValue(key, val)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Voting summary */}
            <div className="flex items-center justify-between pt-1 border-t border-border/50 text-[11px]">
              <div>
                <span className="text-foreground-secondary">Your vote: </span>
                <span
                  data-testid="my-vote-status"
                  className={`font-semibold capitalize ${
                    myDecisionStr === "approved"
                      ? "text-emerald-500"
                      : myDecisionStr === "declined"
                      ? "text-destructive"
                      : "text-amber-500"
                  }`}
                >
                  {myDecisionStr}
                </span>
              </div>
              <div>
                <span className="text-foreground-secondary">Partner vote: </span>
                <span
                  data-testid="partner-vote-status"
                  className={`font-semibold capitalize ${
                    partnerDecisionStr === "approved"
                      ? "text-emerald-500"
                      : partnerDecisionStr === "declined"
                      ? "text-destructive"
                      : "text-amber-500"
                  }`}
                >
                  {partnerDecisionStr}
                </span>
              </div>
            </div>

            {proposal.expires_at && isPending && (
              <div className="text-[10px] text-foreground-secondary text-right">
                Expires: {new Date(proposal.expires_at).toLocaleTimeString()}
              </div>
            )}
          </div>
        )}

        {/* Action Controls */}
        <div className="flex flex-col gap-2 pt-2">
          {isInsufficient ? (
            <div className="flex flex-col gap-2.5">
              <div
                data-testid="insufficient-exhaustion-notice"
                className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-700 dark:text-amber-300 leading-relaxed"
              >
                Even with expanded parameters, no additional films matched the selected taste profile. Your original language and genre criteria were strictly preserved.
              </div>
              {onAdjustPreferences && (
                <button
                  type="button"
                  onClick={onAdjustPreferences}
                  data-testid="adjust-taste-params-btn"
                  className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm"
                >
                  <span className="material-symbols-outlined text-[16px]">tune</span>
                  Adjust Taste Parameters
                </button>
              )}
            </div>
          ) : isFailed ? (
            <div className="flex flex-col gap-2.5">
              <div className="p-3 rounded-xl bg-destructive/10 border border-destructive/25 text-xs text-destructive leading-relaxed">
                {proposal?.error_message || "Replenishment failed due to a temporary service error."}
              </div>
              <button
                type="button"
                onClick={handlePropose}
                disabled={actionLoading || loading}
                data-testid="retry-proposal-btn"
                className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[16px]">refresh</span>
                Retry Expansion
              </button>
            </div>
          ) : !proposal || proposal.status === "declined" || proposal.status === "expired" || proposal.status === "superseded" ? (
            <button
              type="button"
              onClick={handlePropose}
              disabled={actionLoading || loading}
              className="w-full h-11 rounded-xl bg-primary hover:bg-primary-hover text-surface font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-2 shadow-sm disabled:opacity-50"
            >
              {actionLoading ? (
                <span className="size-4 border-2 border-surface border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  <span className="material-symbols-outlined text-[16px]">tune</span>
                  Request Constraint Expansion
                </>
              )}
            </button>
          ) : isPending && !hasVoted ? (
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => handleRespond("approve")}
                disabled={actionLoading}
                className="flex-1 h-11 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[16px]">check</span>
                Approve
              </button>
              <button
                type="button"
                onClick={() => handleRespond("decline")}
                disabled={actionLoading}
                className="flex-1 h-11 rounded-xl border border-destructive/40 bg-destructive/10 hover:bg-destructive/20 text-destructive font-semibold text-xs tracking-wider uppercase transition-colors flex items-center justify-center gap-1.5 disabled:opacity-50"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
                Decline
              </button>
            </div>
          ) : isPending && hasVoted ? (
            <div className="text-center py-2 text-xs text-foreground-secondary">
              Awaiting partner confirmation…
            </div>
          ) : isReplenishing ? (
            <div className="flex items-center justify-center gap-2 py-3 text-xs text-primary font-medium">
              <span className="size-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              Replenishing curated screening deck…
            </div>
          ) : null}

          {onConcludeSession && (
            <button
              type="button"
              onClick={onConcludeSession}
              className="w-full h-10 rounded-xl border border-border bg-surface hover:bg-surface-secondary text-foreground-secondary hover:text-foreground text-xs font-semibold uppercase tracking-wider transition-colors"
            >
              Conclude Screening
            </button>
          )}

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="w-full text-center py-1 text-xs text-foreground-secondary/70 hover:text-foreground transition-colors"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
