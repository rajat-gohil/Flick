"""
Management command: batch_sync_prelaunch
Usage:
  python manage.py batch_sync_prelaunch --mode keywords
  python manage.py batch_sync_prelaunch --mode streaming
  python manage.py batch_sync_prelaunch --mode both        (default)

Runs in a loop until all movies are synced, sleeping between batches
to respect TMDB rate limits (40 req/10s on free tier).

Place this file at:
  backend/core/management/commands/batch_sync_prelaunch.py
  (create the management/commands/ dirs and empty __init__.py files if needed)
"""

import time
import random
from django.core.management.base import BaseCommand
from django.conf import settings
from core.models import Movie, MovieKeyword, MovieStreamingAvailability, StreamingProvider
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _make_session() -> requests.Session:
    """
    Persistent HTTP session with automatic retry on connection-level failures.
    Handles ConnectionResetError / ConnectionAbortedError (errno 10054 / 10053)
    which TMDB triggers when requests arrive too fast or the TCP pool is stale.
    """
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1.5,          # waits: 0s, 1.5s, 3s, 6s, 12s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _tmdb_get(session: requests.Session, url: str, params: dict, stdout=None):
    """
    Wrapper around session.get() that:
      - retries up to 3 times on ConnectionReset before giving up
      - handles 429 rate-limit with a 12-second sleep + retry
      - adds a small random jitter after every request to avoid TCP RST storms
    Returns the Response, or None if all attempts failed.
    """
    for attempt in range(3):
        try:
            resp = session.get(url, params=params, timeout=12)
            # small per-request jitter: 0.2–0.7 s
            time.sleep(random.uniform(0.2, 0.7))

            if resp.status_code == 429:
                wait = 12 + random.uniform(0, 3)
                if stdout:
                    stdout.write(f"  Rate limited — sleeping {wait:.1f}s...")
                time.sleep(wait)
                continue  # retry same attempt slot

            return resp

        except (ConnectionResetError, ConnectionAbortedError,
                requests.exceptions.ConnectionError) as exc:
            wait = 2 ** attempt + random.uniform(0, 1)
            if stdout:
                stdout.write(f"  Connection error (attempt {attempt+1}/3), retrying in {wait:.1f}s: {exc}")
            time.sleep(wait)
            # Recreate the session — the underlying TCP connection is dead
            session = _make_session()

    return None   # all attempts exhausted


class Command(BaseCommand):
    help = "Batch sync TMDB keywords + streaming data for all movies before launch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--mode",
            choices=["keywords", "streaming", "both"],
            default="both",
            help="What to sync (default: both)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=50,
            help="Movies per batch (default: 50 — safe for TMDB free tier)",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=3.0,
            help="Seconds to sleep between batches (default: 3)",
        )
        parser.add_argument(
            "--country",
            default="IN",
            help="Country code for streaming data (default: IN)",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "TMDB_API_KEY", None)
        if not api_key:
            self.stderr.write("ERROR: TMDB_API_KEY not set in settings.")
            return

        mode       = options["mode"]
        batch_size = options["batch_size"]
        sleep_sec  = options["sleep"]
        country    = options["country"].upper()

        # One persistent session shared across both sync passes — keeps TCP
        # connections alive and applies the retry/backoff adapter automatically.
        session = _make_session()

        if mode in ("keywords", "both"):
            self.stdout.write(self.style.MIGRATE_HEADING("\n=== Syncing Keywords ==="))
            self._sync_keywords(api_key, batch_size, sleep_sec, session)

        if mode in ("streaming", "both"):
            self.stdout.write(self.style.MIGRATE_HEADING("\n=== Syncing Streaming Data ==="))
            self._sync_streaming(api_key, batch_size, sleep_sec, country, session)

        self.stdout.write(self.style.SUCCESS("\n✓ Pre-launch sync complete!"))

    # ──────────────────────────────────────────────────────────────
    def _sync_keywords(self, api_key: str, batch_size: int, sleep_sec: float,
                       session: requests.Session):
        # Use the M2M through-table to find movies that have had keywords
        # written at least once — movies with zero keywords still get a
        # through-table row when keywords.set([]) is called, so this correctly
        # identifies "never processed" movies without looping forever.
        processed_ids = set(
            Movie.keywords.through.objects
            .values_list("movie_id", flat=True)
            .distinct()
        )
        total = Movie.objects.exclude(id__in=processed_ids).count()
        self.stdout.write(f"  Movies without keywords: {total}")

        if total == 0:
            self.stdout.write("  All movies already have keywords. Nothing to do.")
            return

        # Track processed IDs in-memory so the exclude set grows each batch
        # without re-hitting the DB for the full set every time.
        done = 0
        while True:
            movies = list(
                Movie.objects.exclude(id__in=processed_ids)
                .order_by("id")[:batch_size]
            )
            if not movies:
                break

            updated = 0
            for movie in movies:
                try:
                    resp = _tmdb_get(
                        session,
                        f"https://api.themoviedb.org/3/movie/{movie.tmdb_id}/keywords",
                        {"api_key": api_key},
                        stdout=self.stdout,
                    )
                    if resp is None or resp.status_code != 200:
                        self.stderr.write(
                            f"  Skipping movie {movie.id} ({movie.title}): "
                            f"{'no response after retries' if resp is None else f'HTTP {resp.status_code}'}"
                        )
                        # Still mark as processed so we don't retry it endlessly
                        processed_ids.add(movie.id)
                        continue

                    keyword_data = resp.json().get("keywords", [])
                    kw_objs = []
                    for kw in keyword_data:
                        obj, _ = MovieKeyword.objects.get_or_create(
                            tmdb_id=kw["id"],
                            defaults={"name": kw["name"]},
                        )
                        kw_objs.append(obj)
                    movie.keywords.set(kw_objs)
                    processed_ids.add(movie.id)
                    updated += 1
                except Exception as e:
                    self.stderr.write(f"  Failed for movie {movie.id} ({movie.title}): {e}")
                    # Mark processed to avoid infinite retry on persistent errors
                    processed_ids.add(movie.id)

            done += len(movies)
            pct = round(done / total * 100, 1)
            self.stdout.write(f"  [{pct}%] {done}/{total} — {updated}/{len(movies)} updated in batch")
            time.sleep(sleep_sec)

    # ──────────────────────────────────────────────────────────────
    def _sync_streaming(self, api_key: str, batch_size: int, sleep_sec: float,
                        country: str, session: requests.Session):
        # Build processed set from DB — movies that already have at least one
        # streaming row (real provider) OR a sentinel "no-data" row (provider
        # named "__none__") so we never re-query them.
        processed_ids = set(
            MovieStreamingAvailability.objects
            .values_list("movie_id", flat=True)
            .distinct()
        )
        total = Movie.objects.exclude(id__in=processed_ids).count()
        self.stdout.write(f"  Movies without streaming data ({country}): {total}")

        if total == 0:
            self.stdout.write("  All movies already have streaming data. Nothing to do.")
            return

        # Sentinel provider used to mark "checked, no IN data" so the movie
        # is excluded from future runs without polluting real provider rows.
        sentinel_provider, _ = StreamingProvider.objects.get_or_create(
            name="__none__",
            country_code=country,
            defaults={"logo_url": ""},
        )

        done = 0
        while True:
            movies = list(
                Movie.objects.exclude(id__in=processed_ids)
                .order_by("id")[:batch_size]
            )
            if not movies:
                break

            updated = 0
            no_data = 0
            for movie in movies:
                try:
                    resp = _tmdb_get(
                        session,
                        f"https://api.themoviedb.org/3/movie/{movie.tmdb_id}/watch/providers",
                        {"api_key": api_key},
                        stdout=self.stdout,
                    )
                    if resp is None or resp.status_code != 200:
                        self.stderr.write(
                            f"  Skipping movie {movie.id} ({movie.title}): "
                            f"{'no response after retries' if resp is None else f'HTTP {resp.status_code}'}"
                        )
                        # Write sentinel so this movie is not retried next run
                        MovieStreamingAvailability.objects.get_or_create(
                            movie=movie, provider=sentinel_provider,
                            defaults={"url": "", "monetization_type": "none"},
                        )
                        processed_ids.add(movie.id)
                        continue

                    country_data = resp.json().get("results", {}).get(country, {})
                    if not country_data:
                        # No IN streaming data — write sentinel to mark as checked
                        MovieStreamingAvailability.objects.get_or_create(
                            movie=movie, provider=sentinel_provider,
                            defaults={"url": "", "monetization_type": "none"},
                        )
                        processed_ids.add(movie.id)
                        no_data += 1
                        continue

                    for mtype, providers_list in [
                        ("flatrate", country_data.get("flatrate", [])),
                        ("rent",     country_data.get("rent", [])),
                        ("buy",      country_data.get("buy", [])),
                    ]:
                        for pdata in providers_list:
                            provider, _ = StreamingProvider.objects.get_or_create(
                                name=pdata["provider_name"],
                                country_code=country,
                                defaults={
                                    "logo_url": (
                                        f"https://image.tmdb.org/t/p/original{pdata.get('logo_path', '')}"
                                        if pdata.get("logo_path") else ""
                                    ),
                                },
                            )
                            MovieStreamingAvailability.objects.get_or_create(
                                movie=movie,
                                provider=provider,
                                defaults={
                                    "url": country_data.get("link", ""),
                                    "monetization_type": mtype,
                                },
                            )
                    processed_ids.add(movie.id)
                    updated += 1
                except Exception as e:
                    self.stderr.write(f"  Failed for movie {movie.id} ({movie.title}): {e}")
                    processed_ids.add(movie.id)

            done += len(movies)
            pct = round(done / total * 100, 1) if total else 100
            self.stdout.write(
                f"  [{pct}%] {done}/{total} — "
                f"{updated} with providers, {no_data} no IN data, "
                f"{len(movies) - updated - no_data} errors"
            )
            time.sleep(sleep_sec)