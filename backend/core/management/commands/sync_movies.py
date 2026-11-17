import time
from django.core.management.base import BaseCommand
from core.models import Movie, Genre
from core.services.tmdb import discover_movies, get_movie_trailer_key


class Command(BaseCommand):
    help = "Sync popular movies from TMDB for Hollywood and Bollywood"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pages",
            type=int,
            default=5,
            help="Number of pages to sync per category (default: 5, 20 movies per page)",
        )
        parser.add_argument(
            "--industry",
            type=str,
            default="all",
            choices=["all", "hollywood", "bollywood"],
            help="Industry to sync: all, hollywood, or bollywood",
        )

    def handle(self, *args, **options):
        pages = options.get("pages", 5)
        industry = options.get("industry", "all")
        movies_created = 0
        movies_updated = 0

        categories = []
        if industry in ["all", "hollywood"]:
            categories.append(("en", "Hollywood"))
        if industry in ["all", "bollywood"]:
            categories.append(("hi", "Bollywood (Hindi)"))
            categories.append(("ta", "South Indian (Tamil)"))
            categories.append(("te", "South Indian (Telugu)"))

        for lang, label in categories:
            self.stdout.write(f"Syncing {label} movies ({pages} pages)...")
            for page in range(1, pages + 1):
                try:
                    data = discover_movies(page=page, language=lang, sort_by="popularity.desc")
                    results = data.get("results", [])

                    for item in results:
                        tmdb_id = item.get("id")
                        if not tmdb_id or not item.get("title"):
                            continue

                        raw_genre_ids = item.get("genre_ids", [])
                        movie, created = Movie.objects.update_or_create(
                            tmdb_id=tmdb_id,
                            defaults={
                                "title": item["title"],
                                "overview": item.get("overview", "") or "",
                                "poster_path": item.get("poster_path") or "",
                                "backdrop_path": item.get("backdrop_path") or "",
                                "release_date": item.get("release_date") or None,
                                "rating": item.get("vote_average"),
                                "vote_count": item.get("vote_count"),
                                "original_language": item.get("original_language"),
                                "tmdb_genre_ids": raw_genre_ids,
                            }
                        )

                        if raw_genre_ids:
                            genre_objects = Genre.objects.filter(tmdb_id__in=raw_genre_ids)
                            if genre_objects.exists():
                                movie.genres.set(genre_objects)

                        if created:
                            movies_created += 1
                        else:
                            movies_updated += 1

                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"Failed page {page} for {label}: {e}"))
                time.sleep(0.3)

        total_movies = Movie.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete. New: {movies_created}, Updated: {movies_updated}. Total in DB: {total_movies}"
            )
        )
