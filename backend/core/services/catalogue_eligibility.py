"""
Catalogue eligibility service for Flick.

Evaluates eligibility predicates for movies:
- display_ready: provenance in ELIGIBLE_PROVENANCE_VALUES, non-empty title, non-empty poster_path.
- recommendable: display_ready, release_date >= 1888, has_genres, valid ISO-639-1 / sentinel language.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from django.db.models.signals import m2m_changed

from core.constants.languages import validate_movie_language

if TYPE_CHECKING:
    from core.models import Movie

ELIGIBLE_PROVENANCE_VALUES: frozenset[str] = frozenset({
    "tmdb_catalogue",
    "manual_curated",
})


def evaluate_eligibility_predicates(
    title: str | None,
    poster_path: str | None,
    provenance: str | None,
    release_date: Any,
    original_language: str | None,
    has_genres: bool,
) -> tuple[bool, bool]:
    """
    Evaluate display_ready and recommendable predicates under Option B rules:
    - display_ready: (provenance in ELIGIBLE_PROVENANCE_VALUES) and non-empty title and non-empty poster_path.
      (Empty overview does NOT block; release_date NOT required).
    - recommendable: display_ready and (release_date is not None and release_date.year >= 1888)
      and has_genres and validate_movie_language(original_language)[0].
      (Keywords are NOT an eligibility gate).
    """
    is_prov_eligible = bool(provenance and provenance in ELIGIBLE_PROVENANCE_VALUES)
    has_title = bool(isinstance(title, str) and title.strip())
    has_poster = bool(isinstance(poster_path, str) and poster_path.strip())

    display_ready = is_prov_eligible and has_title and has_poster

    # Check release_date year >= 1888
    release_year: int | None = None
    if isinstance(release_date, (datetime.date, datetime.datetime)):
        release_year = release_date.year
    elif isinstance(release_date, str):
        try:
            release_year = int(release_date[:4])
        except (ValueError, TypeError):
            release_year = None
    elif release_date is not None and hasattr(release_date, "year"):
        release_year = getattr(release_date, "year", None)

    has_valid_year = release_year is not None and release_year >= 1888
    is_lang_valid, _ = validate_movie_language(original_language)

    recommendable = (
        display_ready
        and has_valid_year
        and bool(has_genres)
        and is_lang_valid
    )

    return (bool(display_ready), bool(recommendable))


def recalculate_movie_eligibility(movie: Movie, commit: bool = False) -> tuple[bool, bool]:
    """
    Recalculate eligibility predicates for a Movie instance.
    Updates movie.display_ready and movie.recommendable in memory.
    If commit=True and movie has a primary key, persists via _trusted_update_eligibility.
    """
    if hasattr(movie, "_has_genres"):
        has_genres = bool(movie._has_genres)
    elif movie.pk:
        has_genres = movie.genres.exists()
    else:
        try:
            has_genres = movie.genres.exists()
        except Exception:
            has_genres = False

    display_ready, recommendable = evaluate_eligibility_predicates(
        title=movie.title,
        poster_path=movie.poster_path,
        provenance=movie.provenance,
        release_date=movie.release_date,
        original_language=movie.original_language,
        has_genres=has_genres,
    )

    movie.display_ready = display_ready
    movie.recommendable = recommendable

    if commit and movie.pk:
        from core.models import Movie as MovieModel
        MovieModel.objects._trusted_update_eligibility(
            movie_pk=movie.pk,
            display_ready=display_ready,
            recommendable=recommendable,
        )

    return (display_ready, recommendable)


def movie_genres_changed_handler(sender, instance, action, reverse, model, pk_set, **kwargs):
    """
    m2m_changed signal handler on Movie.genres.through.
    When genres are added, removed, or cleared, immediately recalculates eligibility.
    """
    if action in ("post_add", "post_remove", "post_clear"):
        from core.models import Movie as MovieModel
        if not reverse and isinstance(instance, MovieModel):
            recalculate_movie_eligibility(instance, commit=True)
        elif reverse and pk_set:
            for movie_pk in pk_set:
                movie = MovieModel.objects.filter(pk=movie_pk).first()
                if movie:
                    recalculate_movie_eligibility(movie, commit=True)


def register_eligibility_signals():
    """Register m2m_changed signals for Movie.genres.through."""
    from core.models import Movie as MovieModel
    m2m_changed.connect(
        movie_genres_changed_handler,
        sender=MovieModel.genres.through,
        dispatch_uid="core.services.catalogue_eligibility.movie_genres_changed",
        weak=False,
    )


# Automatically wire on import
try:
    register_eligibility_signals()
except Exception:
    # During initial app loading or early migrations before models are ready
    pass
