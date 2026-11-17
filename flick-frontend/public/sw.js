/**
 * sw.js — Flick Service Worker
 * Place in /public/sw.js (Vite serves /public at root)
 *
 * Handles:
 *   - App shell caching for offline support
 *   - Push notification display
 *   - Notification click routing
 */

const CACHE_NAME   = "flick-v2";
const ASSETS_CACHE = "flick-assets-v2";

// App shell — these load instantly even offline
const APP_SHELL = [
  "/",
  "/index.html",
  "/manifest.json",
];

// ─────────────────────────────────────────────
// INSTALL — cache app shell
// ─────────────────────────────────────────────
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

// ─────────────────────────────────────────────
// ACTIVATE — clean old caches
// ─────────────────────────────────────────────
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== CACHE_NAME && k !== ASSETS_CACHE)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ─────────────────────────────────────────────
// FETCH — network-first for API, cache-first for assets
// ─────────────────────────────────────────────
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Never intercept or cache localhost development / Vite requests
  if (url.hostname === "localhost" || url.hostname === "127.0.0.1" || url.port === "5173") {
    return;
  }

  // Skip non-GET and API requests (always fresh)
  if (event.request.method !== "GET" || url.pathname.startsWith("/api/")) {
    return;
  }

  // Images from TMDB — cache aggressively (posters don't change)
  if (url.hostname === "image.tmdb.org") {
    event.respondWith(
      caches.open(ASSETS_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const fresh = await fetch(event.request);
        cache.put(event.request, fresh.clone());
        return fresh;
      })
    );
    return;
  }

  // App shell + static assets — cache-first with network fallback
  if (url.pathname.match(/\.(js|css|woff2?|png|svg|ico)$/)) {
    event.respondWith(
      caches.open(ASSETS_CACHE).then(async (cache) => {
        const cached = await cache.match(event.request);
        if (cached) return cached;
        const fresh = await fetch(event.request);
        cache.put(event.request, fresh.clone());
        return fresh;
      })
    );
    return;
  }

  // HTML navigation — network-first, fall back to cached index.html for SPA routing
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match("/index.html")
    )
  );
});

// ─────────────────────────────────────────────
// PUSH — display notification
// ─────────────────────────────────────────────
self.addEventListener("push", (event) => {
  if (!event.data) return;

  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { notification: { title: "Flick", body: event.data.text() } };
  }

  const notification = payload.notification || {};
  const data         = payload.data || {};

  const title   = notification.title || "Flick";
  const options = {
    body:    notification.body  || "",
    icon:    notification.icon  || "/icons/icon-192.png",
    badge:   notification.badge || "/icons/icon-192.png",
    vibrate: [100, 50, 100],
    data:    data,
    actions: buildActions(data.type),
    tag:     data.type || "flick-notification",  // replaces previous notification of same type
    renotify: true,
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

function buildActions(type) {
  if (type === "match") {
    return [
      { action: "open_session", title: "🎬 View Match" },
      { action: "dismiss",      title: "Dismiss" },
    ];
  }
  if (type === "partner_joined") {
    return [
      { action: "open_session", title: "Start Swiping" },
      { action: "dismiss",      title: "Later" },
    ];
  }
  return [];
}

// ─────────────────────────────────────────────
// NOTIFICATION CLICK — route to correct page
// ─────────────────────────────────────────────
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  const data      = event.notification.data || {};
  const sessionId = data.session_id;

  let targetUrl = "/home";
  if (sessionId) {
    targetUrl = `/session/${sessionId}`;
  }

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      // If app is already open, focus it and navigate
      for (const client of clientList) {
        if ("focus" in client) {
          client.focus();
          client.navigate(targetUrl);
          return;
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
