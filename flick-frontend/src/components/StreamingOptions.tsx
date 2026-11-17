import { useEffect, useState, useCallback } from "react";
import { apiRequest } from "../lib/api";

/* ============================
   TYPES
============================ */

export type Provider = {
  id?: number;
  name: string;
  provider_name?: string;
  logo_url: string;
  logo_path?: string;
  url: string;
  link?: string;
  type: "flatrate" | "buy" | "rent" | "free" | "ads";
};

type StreamingData = {
  flatrate: Provider[];
  free: Provider[];
  ads: Provider[];
  rent: Provider[];
  buy: Provider[];
  link?: string | null;
  region?: string;
  attribution?: string;
};

/* ============================
   PROVIDER BADGE
   Editorial styled badge with link
============================ */

function ProviderLogo({ provider }: { provider: Provider }) {
  const [imgError, setImgError] = useState(false);
  const displayName = provider.name || provider.provider_name || "Provider";
  const targetUrl = provider.url || provider.link;

  const content = (
    <div className="flex flex-col items-center gap-1.5 w-[64px] group cursor-pointer transition-transform hover:-translate-y-0.5">
      <div className="w-12 h-12 rounded-xl overflow-hidden bg-surface-secondary border border-border flex items-center justify-center shadow-xs group-hover:border-primary/50 transition-colors">
        {provider.logo_url && !imgError ? (
          <img
            src={provider.logo_url}
            alt={displayName}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <span className="text-foreground font-semibold text-sm">
            {displayName.charAt(0)}
          </span>
        )}
      </div>
      <span className="text-[10px] text-foreground-secondary group-hover:text-foreground text-center leading-tight line-clamp-2 max-w-[60px] font-sans">
        {displayName}
      </span>
    </div>
  );

  if (targetUrl) {
    return (
      <a
        href={targetUrl}
        target="_blank"
        rel="noopener noreferrer"
        title={`View ${displayName} availability`}
        className="focus:outline-hidden"
      >
        {content}
      </a>
    );
  }

  return content;
}

/* ============================
   MAIN COMPONENT
============================ */

/* ============================
   CLIENT-SIDE STREAMING OPTIONS CACHE
   In-flight GET requests are deduplicated centrally by apiRequest()
============================ */

const streamingCache = new Map<string, { data: StreamingData; timestamp: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5-minute memory cache

export default function StreamingOptions({
  movieId,
  movieTitle,
  region,
}: {
  movieId: number;
  movieTitle?: string;
  region?: string;
}) {
  const [data, setData] = useState<StreamingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProviders = useCallback(() => {
    let cancelled = false;
    const cacheKey = `${movieId}-${region || "default"}`;

    // Fast-path: Check memory cache
    const cached = streamingCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
      setData(cached.data);
      setLoading(false);
      setError(null);
      return () => {};
    }

    setLoading(true);
    setError(null);

    const query = region ? `?region=${encodeURIComponent(region)}` : "";

    // In-flight GET deduplication is handled centrally by apiRequest()
    apiRequest(`/api/movies/${movieId}/streaming-options/${query}`)
      .then((res: any) => {
        if (cancelled) return;
        if (!res || !res.success) {
          setError(res?.error || "Unable to load streaming options");
          setLoading(false);
          return;
        }

        const grouped: StreamingData = {
          flatrate: [],
          free: [],
          ads: [],
          rent: [],
          buy: [],
          link: res.link,
          region: res.region,
          attribution: res.attribution || "Streaming data provided by JustWatch via TMDB",
        };

        for (const p of res.providers || []) {
          const type = p.type;
          if (type === "flatrate") grouped.flatrate.push(p);
          else if (type === "free") grouped.free.push(p);
          else if (type === "ads") grouped.ads.push(p);
          else if (type === "rent") grouped.rent.push(p);
          else if (type === "buy") grouped.buy.push(p);
          else grouped.flatrate.push(p);
        }

        streamingCache.set(cacheKey, { data: grouped, timestamp: Date.now() });
        setData(grouped);
        setLoading(false);
      })
      .catch((err: any) => {
        if (!cancelled) {
          setError(err?.message || "Failed to connect to streaming provider directory");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [movieId, region]);

  useEffect(() => {
    const cleanup = fetchProviders();
    return cleanup;
  }, [fetchProviders]);

  /* ── 1. Loading State ── */
  if (loading) {
    return (
      <div className="flex items-center gap-2.5 py-3">
        <div className="size-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        <span className="text-xs text-foreground-secondary font-sans">
          Verifying regional distribution channels...
        </span>
      </div>
    );
  }

  /* ── 2. Error State (Retryable) ── */
  if (error) {
    return (
      <div className="flex flex-col items-start gap-2 py-3 px-3.5 bg-surface-secondary/50 rounded-xl border border-border">
        <div className="flex items-center gap-2 text-foreground-secondary">
          <span className="material-symbols-outlined text-[16px] text-error">error</span>
          <span className="text-xs font-sans text-foreground">
            Unable to check catalogue availability.
          </span>
        </div>
        <button
          onClick={fetchProviders}
          className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-surface border border-border hover:border-primary text-[11px] font-semibold text-primary transition-colors cursor-pointer"
        >
          <span className="material-symbols-outlined text-[13px]">refresh</span>
          Retry lookup
        </button>
      </div>
    );
  }

  /* ── 3. Empty State (No Providers for Region) ── */
  const totalCount =
    (data?.flatrate.length || 0) +
    (data?.free.length || 0) +
    (data?.ads.length || 0) +
    (data?.rent.length || 0) +
    (data?.buy.length || 0);

  if (!data || totalCount === 0) {
    return (
      <div className="py-2.5 space-y-1">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-foreground-secondary text-[16px]">info</span>
          <span className="text-xs text-foreground-secondary font-sans">
            No streaming providers currently cataloged for this region
            {data?.region ? ` (${data.region})` : ""}
            {movieTitle ? ` for "${movieTitle}"` : ""}.
          </span>
        </div>
        {data?.link && (
          <a
            href={data.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-primary hover:underline inline-flex items-center gap-1 mt-1 font-sans"
          >
            Check TMDB / JustWatch directory
            <span className="material-symbols-outlined text-[12px]">open_in_new</span>
          </a>
        )}
      </div>
    );
  }

  /* ── 4. Available Providers State ── */
  const hasFlatrate = data.flatrate.length > 0;
  const hasFree     = (data.free.length + data.ads.length) > 0;
  const hasRent     = data.rent.length > 0;
  const hasBuy      = data.buy.length > 0;

  return (
    <div className="space-y-4">
      {/* Subscription */}
      {hasFlatrate && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="material-symbols-outlined text-primary text-[14px]">check_circle</span>
            <span className="text-[10px] font-semibold text-primary uppercase tracking-widest font-sans">
              Stream Subscription
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {data.flatrate.map((p, idx) => (
              <ProviderLogo key={`flatrate-${p.name}-${idx}`} provider={p} />
            ))}
          </div>
        </div>
      )}

      {/* Free / Ad-Supported */}
      {hasFree && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="material-symbols-outlined text-foreground-secondary text-[14px]">play_circle</span>
            <span className="text-[10px] font-semibold text-foreground-secondary uppercase tracking-widest font-sans">
              Free with Ads
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {[...data.free, ...data.ads].map((p, idx) => (
              <ProviderLogo key={`free-${p.name}-${idx}`} provider={p} />
            ))}
          </div>
        </div>
      )}

      {/* Rent */}
      {hasRent && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="material-symbols-outlined text-foreground-secondary text-[14px]">theaters</span>
            <span className="text-[10px] font-semibold text-foreground-secondary uppercase tracking-widest font-sans">
              Rent Digital
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {data.rent.map((p, idx) => (
              <ProviderLogo key={`rent-${p.name}-${idx}`} provider={p} />
            ))}
          </div>
        </div>
      )}

      {/* Buy */}
      {hasBuy && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <span className="material-symbols-outlined text-foreground-secondary text-[14px]">shopping_bag</span>
            <span className="text-[10px] font-semibold text-foreground-secondary uppercase tracking-widest font-sans">
              Purchase Digital
            </span>
          </div>
          <div className="flex flex-wrap gap-2.5">
            {data.buy.map((p, idx) => (
              <ProviderLogo key={`buy-${p.name}-${idx}`} provider={p} />
            ))}
          </div>
        </div>
      )}

      {/* TMDB & JustWatch Attribution */}
      <div className="pt-2 border-t border-border/50 flex items-center justify-between text-[10px] text-foreground-secondary font-sans">
        <span>Data provided by JustWatch via TMDB</span>
        {data.link && (
          <a
            href={data.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary hover:underline inline-flex items-center gap-0.5"
          >
            All watch options
            <span className="material-symbols-outlined text-[11px]">open_in_new</span>
          </a>
        )}
      </div>
    </div>
  );
}
