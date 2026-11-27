/**
 * Formats a movie runtime in minutes into a compact human-readable duration
 * (e.g. 134 -> "2h 14m", 45 -> "45m"). Returns null for missing/invalid values.
 */
export function formatRuntime(minutes?: number | null): string | null {
  if (typeof minutes !== "number" || !Number.isFinite(minutes) || minutes <= 0) {
    return null;
  }
  const totalMinutes = Math.round(minutes);
  if (totalMinutes <= 0) return null;

  const hours = Math.floor(totalMinutes / 60);
  const remainingMinutes = totalMinutes % 60;

  if (hours === 0) return `${remainingMinutes}m`;
  if (remainingMinutes === 0) return `${hours}h`;
  return `${hours}h ${remainingMinutes}m`;
}
