/**
 * Upgrades TMDB backdrop URLs (w500/w780) to w1280 for full-width 16:9 hero/spotlight banners
 * on desktop viewports without altering non-TMDB or poster URLs.
 */
export function toHeroBackdropUrl(url?: string | null): string | null {
  if (!url) return null;
  if (url.includes("image.tmdb.org/t/p/")) {
    return url.replace(/\/t\/p\/w(?:500|780)\//, "/t/p/w1280/");
  }
  return url;
}
