"""
ISO 639-1 language codes and TMDB language sentinel constants.
"""

# Complete verified set of 184 ISO 639-1 two-letter language codes.
ISO_639_1_CODES: frozenset[str] = frozenset({
    "aa", "ab", "ae", "af", "ak", "am", "an", "ar", "as", "av", "ay", "az",
    "ba", "be", "bg", "bh", "bi", "bm", "bn", "bo", "br", "bs",
    "ca", "ce", "ch", "co", "cr", "cs", "cu", "cv", "cy",
    "da", "de", "dv", "dz",
    "ee", "el", "en", "eo", "es", "et", "eu",
    "fa", "ff", "fi", "fj", "fo", "fr", "fy",
    "ga", "gd", "gl", "gn", "gu", "gv",
    "ha", "he", "hi", "ho", "hr", "ht", "hu", "hy", "hz",
    "ia", "id", "ie", "ig", "ii", "ik", "io", "is", "it", "iu",
    "ja", "jv",
    "ka", "kg", "ki", "kj", "kk", "kl", "km", "kn", "ko", "kr", "ks", "ku", "kv", "kw", "ky",
    "la", "lb", "lg", "li", "ln", "lo", "lt", "lu", "lv",
    "mg", "mh", "mi", "mk", "ml", "mn", "mr", "ms", "mt", "my",
    "na", "nb", "nd", "ne", "ng", "nl", "nn", "no", "nr", "nv", "ny",
    "oc", "oj", "om", "or", "os",
    "pa", "pi", "pl", "ps", "pt",
    "qu",
    "rm", "rn", "ro", "ru", "rw",
    "sa", "sc", "sd", "se", "sg", "si", "sk", "sl", "sm", "sn", "so", "sq", "sr", "ss", "st", "su", "sv", "sw",
    "ta", "te", "tg", "th", "ti", "tk", "tl", "tn", "to", "tr", "ts", "tt", "tw", "ty",
    "ug", "uk", "ur", "uz",
    "ve", "vi", "vo",
    "wa", "wo",
    "xh",
    "yi", "yo",
    "za", "zh", "zu",
})

TMDB_NO_LANGUAGE_SENTINEL: str = "xx"


def validate_movie_language(code: str | None) -> tuple[bool, str]:
    """
    Validate movie original_language code.

    Returns:
        (True, 'iso_639_1') for valid ISO 639-1 two-letter codes.
        (True, 'tmdb_sentinel') for 'xx' (TMDB sentinel for no language / silent).
        (False, 'invalid') otherwise.
    """
    if not code or not isinstance(code, str):
        return (False, "invalid")
    normalized = code.strip().lower()
    if not normalized:
        return (False, "invalid")
    if normalized in ISO_639_1_CODES:
        return (True, "iso_639_1")
    if normalized == TMDB_NO_LANGUAGE_SENTINEL:
        return (True, "tmdb_sentinel")
    return (False, "invalid")
