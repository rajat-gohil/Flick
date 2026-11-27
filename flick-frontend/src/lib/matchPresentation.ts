export type MatchPresentationStyle = "antique_brass" | "amber" | "emerald" | "neutral";

/**
 * Strict fail-closed resolution matching backend properties:
 * - 'mutual' + 'mutual_superlike' -> 'antique_brass'
 * - 'host' | 'guest' + 'superlike' -> 'amber'
 * - 'none' + 'ordinary' -> 'emerald'
 * - 'unknown' + 'unknown' or any contradictory mismatch -> 'neutral' (fail-closed)
 */
export function resolveMatchStyle(
  superlikeAttr?: string,
  matchType?: string
): MatchPresentationStyle {
  if (superlikeAttr === "mutual" && matchType === "mutual_superlike") {
    return "antique_brass";
  }
  if ((superlikeAttr === "host" || superlikeAttr === "guest") && matchType === "superlike") {
    return "amber";
  }
  if (superlikeAttr === "none" && matchType === "ordinary") {
    return "emerald";
  }
  return "neutral";
}
