import posthog from "posthog-js";

let lastIdentifiedKey: string | null = null;

export function trackEvent(
  name: string,
  properties?: Record<string, unknown>
) {
  try {
    posthog.capture(name, properties);
  } catch {
    // Analytics must never block or crash user interactions
  }
}

export function identifyUser(
  userId: string | number | null | undefined,
  properties?: { is_guest?: boolean; username?: string }
) {
  if (userId === null || userId === undefined) return;
  const distinctId = String(userId).trim();
  if (!distinctId) return;

  const dedupeKey = `${distinctId}:${Boolean(properties?.is_guest)}`;
  if (lastIdentifiedKey === dedupeKey) return;

  try {
    posthog.identify(distinctId, {
      ...(properties?.is_guest !== undefined ? { is_guest: properties.is_guest } : {}),
      ...(properties?.username ? { username: properties.username } : {}),
    });
    lastIdentifiedKey = dedupeKey;
  } catch {
    // Ignore analytics errors
  }
}

export function resetAnalyticsIdentity() {
  lastIdentifiedKey = null;
  try {
    posthog.reset();
  } catch {
    // Ignore analytics errors
  }
}
