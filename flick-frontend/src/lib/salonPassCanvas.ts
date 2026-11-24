import QRCode from "qrcode";

export interface SalonPassData {
  movieTitle: string;
  releaseYear?: number;
  rating?: number;
  posterUrl?: string;
  sessionCode?: string;
  userRole?: string | null;
  partnerNames?: string;
  compatibilityScore?: string;
  streamingProviders?: string[];
}

/**
 * Loads an image with crossOrigin="anonymous" and cache-busting query param
 * so previously cached non-CORS <img> loads don't poison canvas export.
 * Resolves to null if loading fails, times out, or CORS prevents export.
 */
function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    if (!src) return resolve(null);
    let settled = false;
    const finish = (val: HTMLImageElement | null) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(val);
      }
    };
    const timer = setTimeout(() => finish(null), 6000);

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => finish(img);
    img.onerror = () => finish(null);

    try {
      const parsed = new URL(src);
      parsed.searchParams.set("cors", "1");
      img.src = parsed.toString();
    } catch {
      img.src = src;
    }
  });
}

/**
 * Draws rounded rectangle path.
 */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

/**
 * Renders the 9:16 high-resolution (1080x1920) Theatrical Salon Pass onto an HTMLCanvasElement.
 */
export async function renderSalonPassToCanvas(
  canvas: HTMLCanvasElement,
  data: SalonPassData
): Promise<void> {
  const width = 1080;
  const height = 1920;

  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Could not get 2D canvas context");

  // 1. Background gradient (Art-house deep emerald noir)
  const bgGrad = ctx.createLinearGradient(0, 0, 0, height);
  bgGrad.addColorStop(0, "#0c100e");
  bgGrad.addColorStop(0.3, "#141a16");
  bgGrad.addColorStop(0.7, "#141a16");
  bgGrad.addColorStop(1, "#0a0d0b");
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, width, height);

  // Subtle radial gold ambient glow at upper-center
  const glow = ctx.createRadialGradient(540, 680, 50, 540, 680, 550);
  glow.addColorStop(0, "rgba(197, 168, 128, 0.12)");
  glow.addColorStop(0.6, "rgba(66, 99, 74, 0.08)");
  glow.addColorStop(1, "rgba(0, 0, 0, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, width, height);

  // 2. Theatrical Borders (Vintage Film Ticket Geometry)
  // Outer fine border
  ctx.strokeStyle = "rgba(197, 168, 128, 0.35)";
  ctx.lineWidth = 2;
  ctx.strokeRect(48, 48, width - 96, height - 96);

  // Inner bold frame
  ctx.strokeStyle = "rgba(197, 168, 128, 0.75)";
  ctx.lineWidth = 3;
  ctx.strokeRect(62, 62, width - 124, height - 124);

  // Art-deco corner ornaments
  const cornerSize = 24;
  ctx.fillStyle = "#C5A880";
  // Top-left
  ctx.fillRect(56, 56, cornerSize, 4);
  ctx.fillRect(56, 56, 4, cornerSize);
  // Top-right
  ctx.fillRect(width - 56 - cornerSize, 56, cornerSize, 4);
  ctx.fillRect(width - 60, 56, 4, cornerSize);
  // Bottom-left
  ctx.fillRect(56, height - 60, cornerSize, 4);
  ctx.fillRect(56, height - 56 - cornerSize, 4, cornerSize);
  // Bottom-right
  ctx.fillRect(width - 56 - cornerSize, height - 60, cornerSize, 4);
  ctx.fillRect(width - 60, height - 56 - cornerSize, 4, cornerSize);

  // 3. Header Masthead
  ctx.textAlign = "center";

  // Brand Name
  ctx.fillStyle = "#C5A880";
  ctx.font = "bold 26px 'Newsreader', Georgia, serif";
  ctx.fillText("FLICK CINÉMA SALON", 540, 130);

  // Subtitle
  ctx.fillStyle = "rgba(245, 242, 235, 0.7)";
  ctx.font = "600 18px 'Manrope', system-ui, sans-serif";
  ctx.fillText("THEATRICAL ADMISSION PASS · ADMIT TWO", 540, 165);

  // Pass Number
  const passCode = (data.sessionCode || "FLICK").toUpperCase();
  ctx.fillStyle = "rgba(197, 168, 128, 0.9)";
  ctx.font = "700 16px 'Courier New', monospace";
  ctx.fillText(`SERIAL NO. ${passCode}-PASS`, 540, 198);

  // 4. Movie Poster Section
  const posterW = 540;
  const posterH = 800;
  const posterX = 270;
  const posterY = 240;

  // Poster drop shadow
  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.85)";
  ctx.shadowBlur = 35;
  ctx.shadowOffsetY = 18;

  // Poster container box with rounded corners
  roundRect(ctx, posterX, posterY, posterW, posterH, 20);
  ctx.fillStyle = "#1e2420";
  ctx.fill();
  ctx.restore();

  // Try loading poster image
  let imageDrawn = false;
  if (data.posterUrl) {
    try {
      const posterImg = await loadImage(data.posterUrl);
      if (posterImg) {
        ctx.save();
        roundRect(ctx, posterX, posterY, posterW, posterH, 20);
        ctx.clip();
        ctx.drawImage(posterImg, posterX, posterY, posterW, posterH);
        ctx.restore();
        imageDrawn = true;
      }
    } catch {
      imageDrawn = false;
    }
  }

  // Fallback if no poster or CORS issue
  if (!imageDrawn) {
    ctx.save();
    roundRect(ctx, posterX, posterY, posterW, posterH, 20);
    ctx.clip();
    const fallbackGrad = ctx.createLinearGradient(posterX, posterY, posterX, posterY + posterH);
    fallbackGrad.addColorStop(0, "#232e26");
    fallbackGrad.addColorStop(1, "#151b17");
    ctx.fillStyle = fallbackGrad;
    ctx.fillRect(posterX, posterY, posterW, posterH);

    // Film reel icon or placeholder text
    ctx.fillStyle = "#C5A880";
    ctx.font = "italic 44px 'Newsreader', Georgia, serif";
    ctx.textAlign = "center";
    ctx.fillText("🎬", 540, posterY + posterH / 2 - 20);

    ctx.fillStyle = "#F5F2EB";
    ctx.font = "bold 32px 'Newsreader', Georgia, serif";
    let fallbackTitle = data.movieTitle;
    const maxFallbackW = posterW - 60;
    if (ctx.measureText(fallbackTitle).width > maxFallbackW) {
      while (fallbackTitle.length > 5 && ctx.measureText(fallbackTitle + "…").width > maxFallbackW) {
        fallbackTitle = fallbackTitle.slice(0, -1);
      }
      fallbackTitle += "…";
    }
    ctx.fillText(fallbackTitle, 540, posterY + posterH / 2 + 40);
    ctx.restore();
  }

  // Golden border around poster
  roundRect(ctx, posterX, posterY, posterW, posterH, 20);
  ctx.strokeStyle = "rgba(197, 168, 128, 0.8)";
  ctx.lineWidth = 3;
  ctx.stroke();

  // 5. Match Verification Banner (Compatibility Score)
  const bannerY = 1080;
  ctx.save();
  ctx.fillStyle = "rgba(66, 99, 74, 0.9)";
  roundRect(ctx, 270, bannerY - 30, 540, 52, 14);
  ctx.fill();
  ctx.strokeStyle = "#C5A880";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  ctx.fillStyle = "#F5F2EB";
  ctx.font = "800 18px 'Manrope', system-ui, sans-serif";
  ctx.textAlign = "center";
  const harmonyBanner = data.compatibilityScore
    ? `✨ ${data.compatibilityScore.toUpperCase()}`
    : "✨ 96% CINEPHILE HARMONY · UNANIMOUS MATCH";
  ctx.fillText(harmonyBanner, 540, bannerY + 3);
  ctx.restore();

  // 6. Movie Title & Info
  ctx.textAlign = "center";
  ctx.fillStyle = "#F5F2EB";
  ctx.font = "bold 48px 'Newsreader', Georgia, serif";

  // Title wrapping if too long
  const maxTitleWidth = 840;
  let displayTitle = data.movieTitle;
  if (ctx.measureText(displayTitle).width > maxTitleWidth) {
    while (displayTitle.length > 5 && ctx.measureText(displayTitle + "…").width > maxTitleWidth) {
      displayTitle = displayTitle.slice(0, -1);
    }
    displayTitle += "…";
  }
  ctx.fillText(displayTitle, 540, 1195);

  // Year & Rating
  const metaParts = [];
  if (data.releaseYear) metaParts.push(`${data.releaseYear}`);
  if (data.rating) metaParts.push(`★ ${data.rating.toFixed(1)} / 10`);
  metaParts.push("Theatrical Selection");

  ctx.fillStyle = "#C5A880";
  ctx.font = "600 24px 'Manrope', system-ui, sans-serif";
  ctx.fillText(metaParts.join("   ·   "), 540, 1245);

  // Partner attribution
  const partnerText = data.partnerNames
    ? `Curated by ${data.partnerNames}`
    : "Decided together with Flick";
  ctx.fillStyle = "rgba(245, 242, 235, 0.75)";
  ctx.font = "italic 20px 'Newsreader', Georgia, serif";
  ctx.fillText(partnerText, 540, 1286);

  // Streaming Options on Pass
  const streamingText =
    data.streamingProviders && data.streamingProviders.length > 0
      ? `STREAMING ON ${data.streamingProviders.slice(0, 3).join(" · ").toUpperCase()}`
      : "STREAMING OPTIONS AVAILABLE ON FLICK";
  ctx.fillStyle = "#C5A880";
  ctx.font = "700 15px 'Courier New', monospace";
  ctx.fillText(streamingText, 540, 1322);

  // 7. Perforated Ticket Divider (Dashed line with edge notch cutouts)
  const perfY = 1360;

  // Notches on left and right borders
  ctx.fillStyle = "#0c100e";
  ctx.beginPath();
  ctx.arc(48, perfY, 26, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "rgba(197, 168, 128, 0.6)";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(width - 48, perfY, 26, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Dashed divider line
  ctx.save();
  ctx.setLineDash([14, 10]);
  ctx.strokeStyle = "rgba(197, 168, 128, 0.4)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(85, perfY);
  ctx.lineTo(width - 85, perfY);
  ctx.stroke();
  ctx.restore();

  // 8. Bottom Ticket Stub (QR Code & Branding)
  const qrX = 140;
  const qrY = 1420;
  const qrSize = 220;

  // Generate QR Code via qrcode library onto an offscreen canvas (points to landing page)
  try {
    const qrCanvas = document.createElement("canvas");
    const targetUrl = "https://flick-kappa.vercel.app";

    await QRCode.toCanvas(qrCanvas, targetUrl, {
      width: qrSize,
      margin: 1,
      color: {
        dark: "#0a0d0b",
        light: "#F5F2EB",
      },
    });

    // Draw white/gold backing for QR
    ctx.save();
    roundRect(ctx, qrX - 10, qrY - 10, qrSize + 20, qrSize + 20, 16);
    ctx.fillStyle = "#F5F2EB";
    ctx.fill();
    ctx.strokeStyle = "#C5A880";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.drawImage(qrCanvas, qrX, qrY, qrSize, qrSize);
    ctx.restore();
  } catch (err) {
    console.warn("QR code generation error:", err);
  }

  // Text next to QR code
  const textX = 420;
  ctx.textAlign = "left";

  ctx.fillStyle = "#C5A880";
  ctx.font = "bold 32px 'Newsreader', Georgia, serif";
  ctx.fillText("FLICK", textX, 1475);

  ctx.fillStyle = "#F5F2EB";
  ctx.font = "bold 22px 'Manrope', system-ui, sans-serif";
  ctx.fillText("Movie Night, Decided.", textX, 1515);

  ctx.fillStyle = "rgba(245, 242, 235, 0.7)";
  ctx.font = "400 19px 'Manrope', system-ui, sans-serif";
  ctx.fillText("Scan QR to swipe and match", textX, 1555);
  ctx.fillText("with your partner in 3 minutes.", textX, 1585);

  ctx.fillStyle = "#42634A";
  ctx.font = "600 18px 'Courier New', monospace";
  ctx.fillText("flick-kappa.vercel.app", textX, 1625);

  // Bottom Footer Micro-copy
  ctx.textAlign = "center";
  ctx.fillStyle = "rgba(197, 168, 128, 0.55)";
  ctx.font = "500 15px 'Manrope', system-ui, sans-serif";
  ctx.fillText("NO MORE 45-MINUTE STREAMING ARGUMENTS · ADMISSION GUARANTEED", 540, 1820);
}

/**
 * Generates PNG Blob from the rendered canvas.
 */
export function getCanvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) resolve(blob);
        else reject(new Error("Canvas toBlob failed"));
      },
      "image/png",
      0.95
    );
  });
}

/**
 * Triggers native file download fallback.
 */
export function triggerFileDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/**
 * Web Share API with robust fallback.
 * Attempts file sharing first. If not supported or user cancels/fails, falls back to download.
 */
export async function shareOrDownloadSalonPass(
  blob: Blob,
  movieTitle: string
): Promise<{ success: boolean; method: "share" | "download"; error?: string }> {
  const filename = `flick-match-${movieTitle.toLowerCase().replace(/[^a-z0-9]/g, "-")}.png`;
  const file = new File([blob], filename, { type: "image/png" });

  const shareData = {
    title: `We matched on ${movieTitle}!`,
    text: `We finally agreed on what to watch tonight on Flick: ${movieTitle}! No more 45-minute streaming debate.`,
    url: "https://flick-kappa.vercel.app",
    files: [file],
  };

  if (typeof navigator !== "undefined" && navigator.canShare && navigator.canShare({ files: [file] })) {
    try {
      await navigator.share(shareData);
      return { success: true, method: "share" };
    } catch (err: unknown) {
      // If user aborted/dismissed the share sheet, return clean success/dismissal
      if (err instanceof Error && err.name === "AbortError") {
        return { success: false, method: "share", error: "Share cancelled" };
      }
      // If sharing failed for permissions/OS reasons, fallback to direct file download
      triggerFileDownload(blob, filename);
      return { success: true, method: "download" };
    }
  }

  // Fallback for desktop / unsupported mobile browsers
  triggerFileDownload(blob, filename);
  return { success: true, method: "download" };
}
