/**
 * Human-readable formatters and canonical metadata lookups
 * for Constraint Expansion Proposals.
 *
 * Adheres strictly to Flick's canonical genres, languages, and era boundaries.
 */

/**
 * Canonical TMDB Genre Mappings matching backend DEFAULT_CANONICAL_GENRES.
 */
export const CANONICAL_GENRES: Record<number, string> = {
  28: "Action",
  12: "Adventure",
  16: "Animation",
  35: "Comedy",
  80: "Crime",
  99: "Documentary",
  18: "Drama",
  10751: "Family",
  14: "Fantasy",
  36: "History",
  27: "Horror",
  10402: "Music",
  9648: "Mystery",
  10749: "Romance",
  878: "Science Fiction",
  10770: "TV Movie",
  53: "Thriller",
  10752: "War",
  37: "Western",
};

/**
 * Canonical Language Mappings matching Flick's supported languages (CreateSessionPage & DiscoverPage).
 */
export const CANONICAL_LANGUAGES: Record<string, string> = {
  en: "English",
  hi: "Hindi",
  ta: "Tamil",
  te: "Telugu",
  bn: "Bengali",
  mr: "Marathi",
  gu: "Gujarati",
  kn: "Kannada",
  ml: "Malayalam",
  pa: "Punjabi",
  es: "Spanish",
  fr: "French",
  ko: "Korean",
  ja: "Japanese",
  it: "Italian",
  de: "German",
  zh: "Chinese",
};

/**
 * Canonical Era Mappings matching ERA_DEFINITIONS & PreferencesPage.
 */
export const CANONICAL_ERAS: Record<string, string> = {
  any: "Any Era",
  recent: "Recent (2020+)",
  "2010s": "2010s",
  "2000s": "2000s",
  "90s": "1990s",
  before_1990: "Before 1990",
  pre_1990: "Before 1990",
  classic: "Classic (Before 1990)",
};

// In-memory cache for dynamically fetched genres from /api/genres/
let dynamicGenreCache: Record<number, string> = {};

export function updateGenreCache(
  genres: Array<{ id: number; name: string; tmdb_id?: number }>
): void {
  if (!Array.isArray(genres)) return;
  for (const g of genres) {
    if (g && g.name) {
      if (typeof g.tmdb_id === "number") {
        dynamicGenreCache[g.tmdb_id] = g.name;
      }
      if (typeof g.id === "number") {
        dynamicGenreCache[g.id] = g.name;
      }
    }
  }
}

export function getGenreCache(): Record<number, string> {
  return { ...dynamicGenreCache };
}

export function clearGenreCache(): void {
  dynamicGenreCache = {};
}

/**
 * Resolves a genre ID (number, string, or object) to a human-readable genre name.
 */
export function resolveGenreName(
  genreIdOrObj: any,
  customMap?: Record<number, string>
): string {
  if (genreIdOrObj == null) return "";
  if (typeof genreIdOrObj === "object") {
    if (genreIdOrObj.name) return String(genreIdOrObj.name);
    if (genreIdOrObj.id) genreIdOrObj = genreIdOrObj.id;
    else if (genreIdOrObj.tmdb_id) genreIdOrObj = genreIdOrObj.tmdb_id;
  }
  const numericId = Number(genreIdOrObj);
  if (!isNaN(numericId)) {
    if (customMap && customMap[numericId]) {
      return customMap[numericId];
    }
    if (dynamicGenreCache[numericId]) {
      return dynamicGenreCache[numericId];
    }
    if (CANONICAL_GENRES[numericId]) {
      return CANONICAL_GENRES[numericId];
    }
    return `Genre ${numericId}`;
  }
  return String(genreIdOrObj);
}

/**
 * Converts a language code (e.g. 'gu') to a human-readable name ('Gujarati').
 */
export function formatLanguageName(code: any): string {
  if (code == null) return "";
  const str = String(code).trim();
  if (!str) return "";
  const lower = str.toLowerCase();
  if (CANONICAL_LANGUAGES[lower]) {
    return CANONICAL_LANGUAGES[lower];
  }
  // Check if it's already a capitalized full language name
  const existingName = Object.values(CANONICAL_LANGUAGES).find(
    (n) => n.toLowerCase() === lower
  );
  if (existingName) return existingName;

  // Use Intl.DisplayNames if available
  try {
    if (typeof Intl !== "undefined" && Intl.DisplayNames) {
      const displayName = new Intl.DisplayNames(["en"], { type: "language" }).of(lower);
      if (displayName && displayName !== lower) {
        return displayName;
      }
    }
  } catch {
    // Ignore fallback errors
  }
  return str.length <= 3 ? str.toUpperCase() : str;
}

/**
 * Converts an internal era value (e.g. 'any') to a human-readable label ('Any Era').
 */
export function formatEraName(era: any): string {
  if (era == null) return "";
  const str = String(era).trim();
  if (!str) return "";
  const lower = str.toLowerCase();
  if (CANONICAL_ERAS[lower]) {
    return CANONICAL_ERAS[lower];
  }
  return str
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Formats constraint keys into human-readable labels.
 */
export function formatConstraintLabel(key: string): string {
  const LABELS: Record<string, string> = {
    shared_min_rating: "Min Rating",
    min_rating: "Min Rating",
    shared_max_runtime: "Max Runtime",
    max_runtime: "Max Runtime",
    shared_eras: "Eras",
    eras: "Eras",
    shared_languages: "Languages",
    languages: "Languages",
    required_genre_ids: "Required Genres",
    required_genres: "Required Genres",
    genres: "Required Genres",
    excluded_genre_ids: "Excluded Genres",
    excluded_genres: "Excluded Genres",
  };
  if (LABELS[key]) return LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Formats a constraint value into a user-friendly human-readable representation.
 */
export function formatConstraintValue(
  key: string,
  val: any,
  genreMap?: Record<number, string>
): string {
  const normKey = key.toLowerCase();

  // 1. Minimum Rating
  if (normKey.includes("min_rating") || normKey.includes("rating")) {
    if (val == null || val === "" || val === "any" || val === "none") {
      return "No minimum rating";
    }
    const num = Number(val);
    if (!isNaN(num)) {
      if (num <= 0) return "No minimum rating";
      return `${num.toFixed(1)}+ rating`;
    }
    return String(val);
  }

  // 2. Maximum Runtime
  if (normKey.includes("max_runtime") || normKey.includes("runtime")) {
    if (val == null || val === "" || val === "any" || val === "none") {
      return "No runtime limit";
    }
    const num = Number(val);
    if (!isNaN(num)) {
      if (num <= 0) return "No runtime limit";
      return `${num} minutes`;
    }
    return String(val);
  }

  // 3. Genres (Required or Excluded)
  if (normKey.includes("genre")) {
    if (val == null) return "None";
    const arr = Array.isArray(val) ? val : [val];
    if (arr.length === 0) return "None";
    const resolved = arr
      .map((g) => resolveGenreName(g, genreMap))
      .filter(Boolean);
    return resolved.length > 0 ? resolved.join(", ") : "None";
  }

  // 4. Languages
  if (normKey.includes("lang")) {
    if (val == null) return "None";
    const arr = Array.isArray(val) ? val : [val];
    if (arr.length === 0) return "None";
    const resolved = arr
      .map((l) => formatLanguageName(l))
      .filter(Boolean);
    return resolved.length > 0 ? resolved.join(", ") : "None";
  }

  // 5. Eras
  if (normKey.includes("era")) {
    if (val == null) return "None";
    const arr = Array.isArray(val) ? val : [val];
    if (arr.length === 0) return "None";
    const resolved = arr
      .map((e) => formatEraName(e))
      .filter(Boolean);
    return resolved.length > 0 ? resolved.join(", ") : "None";
  }

  // 6. Generic null / empty handling
  if (val == null) return "None";
  if (Array.isArray(val)) {
    if (val.length === 0) return "None";
    return val.map(String).join(", ");
  }
  if (typeof val === "object") {
    try {
      return JSON.stringify(val);
    } catch {
      return "None";
    }
  }
  return String(val);
}
