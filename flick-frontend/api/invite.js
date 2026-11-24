function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export default async function handler(req, res) {
  const rawCode = Array.isArray(req.query.code) ? req.query.code[0] : req.query.code;
  const code = (rawCode || "").trim().toUpperCase();

  const proto = req.headers["x-forwarded-proto"] || "https";
  const host = req.headers["x-forwarded-host"] || req.headers.host || "flick-kappa.vercel.app";
  const origin = `${proto}://${host}`;
  const targetUrl = code ? `${origin}/join/${code}` : origin;
  const ogImage = `${origin}/og-invite.png`;

  let ogTitle = "🎬 Join Movie Night on Flick";
  let ogDescription =
    "Swipe through movies with your partner or friends. Match on what to watch tonight in under 3 minutes — no sign-up needed!";

  const apiBase = (process.env.VITE_API_BASE_URL || process.env.API_BASE_URL || "").replace(/\/$/, "");
  if (apiBase && code) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1500);
      const response = await fetch(`${apiBase}/api/sessions/${encodeURIComponent(code)}/preview/`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      clearTimeout(timer);

      if (response.ok) {
        const data = await response.json();
        if (data && data.found) {
          const hostName = data.host_name || "A friend";
          const genres = Array.isArray(data.genres) && data.genres.length > 0
            ? ` (${data.genres.slice(0, 3).join(", ")})`
            : "";
          const industry = data.industry
            ? ` ${data.industry.charAt(0).toUpperCase() + data.industry.slice(1)}`
            : "";
          ogTitle = `🎬 ${hostName} invited you to Movie Night on Flick!`;
          ogDescription = `Swipe through${industry} movies${genres} together. Match on what to watch tonight in under 3 minutes — no sign-up needed!`;
        }
      }
    } catch {
      // Fallback cleanly to default OG metadata if backend is unreachable or timed out
    }
  }

  const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(ogTitle)}</title>
  <meta name="description" content="${escapeHtml(ogDescription)}">

  <meta property="og:site_name" content="Flick">
  <meta property="og:title" content="${escapeHtml(ogTitle)}">
  <meta property="og:description" content="${escapeHtml(ogDescription)}">
  <meta property="og:image" content="${escapeHtml(ogImage)}">
  <meta property="og:image:secure_url" content="${escapeHtml(ogImage)}">
  <meta property="og:image:type" content="image/png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="Flick Cinema Salon Admission Pass">
  <meta property="og:url" content="${escapeHtml(targetUrl)}">
  <meta property="og:type" content="website">

  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="${escapeHtml(ogTitle)}">
  <meta name="twitter:description" content="${escapeHtml(ogDescription)}">
  <meta name="twitter:image" content="${escapeHtml(ogImage)}">

  <meta http-equiv="refresh" content="0;url=${escapeHtml(targetUrl)}">
  <script>window.location.replace(${JSON.stringify(targetUrl)});</script>
</head>
<body style="background:#0c100e;color:#F5F2EB;font-family:sans-serif;text-align:center;padding:40px;">
  <h2>${escapeHtml(ogTitle)}</h2>
  <p>${escapeHtml(ogDescription)}</p>
  <p><a href="${escapeHtml(targetUrl)}" style="color:#C5A880;font-weight:bold;">Tap here to join movie night...</a></p>
</body>
</html>`;

  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.setHeader("Cache-Control", "public, s-maxage=60, stale-while-revalidate=300");
  res.status(200).send(html);
}
