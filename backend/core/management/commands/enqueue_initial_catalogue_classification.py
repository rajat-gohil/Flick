"""
Management command to enqueue initial catalogue classification jobs for existing movies.
Safe to re-run; uses CatalogueQueueService deduplication.
Supports language-targeted filtering, provenance filtering, synthetic record exclusions,
and safe dry-run preview reporting.
"""

import logging
from typing import Any, List, Optional

from django.core.management.base import BaseCommand

from core.models import CatalogueJob, Movie
from core.services.catalogue_queue import CatalogueQueueService
from core.services.enrichment_handlers import is_synthetic_movie

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Enqueues initial catalogue_classification jobs for existing Movie instances. "
        "Supports language-targeted filtering, provenance exclusions, and dry-run preview. "
        "Deduplication ensures that existing active jobs are not duplicated."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "-l",
            "--languages",
            nargs="*",
            default=None,
            help="Filter movies by original language codes (e.g. -l hi ta te gu or -l hi,ta,te,gu).",
        )
        parser.add_argument(
            "--provenance",
            type=str,
            default="needs_review",
            help="Filter by movie provenance (default: 'needs_review'). Pass 'all' to include all.",
        )
        parser.add_argument(
            "--exclude-synthetic",
            action="store_true",
            default=True,
            help="Exclude movies matching synthetic fixture patterns (default: True).",
        )
        parser.add_argument(
            "--priority",
            type=int,
            default=50,
            help="Job priority for classification jobs (default: 50).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate enqueueing without creating actual database jobs.",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Confirm execution of database job enqueueing.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of movies to process.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Batch size for iterating Movie records (default: 500).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        confirm: bool = options["confirm"]
        limit: Optional[int] = options["limit"]
        batch_size: int = options["batch_size"]
        priority: int = options["priority"]
        provenance_filter: str = options.get("provenance", "needs_review")
        exclude_synthetic: bool = options.get("exclude_synthetic", True)

        # Parse languages
        languages_opt = options.get("languages")
        languages: Optional[List[str]] = None
        if languages_opt:
            languages = []
            for entry in languages_opt:
                languages.extend([l.strip().lower() for l in entry.split(",") if l.strip()])

        # Build QuerySet
        qs = Movie.objects.all().order_by("id")
        if provenance_filter and provenance_filter != "all":
            qs = qs.filter(provenance=provenance_filter)

        if languages:
            qs = qs.filter(original_language__in=languages)

        # Filter candidate records (including synthetic check)
        candidate_movies = []
        excluded_synthetic_count = 0
        for movie in qs:
            if exclude_synthetic and is_synthetic_movie(movie):
                excluded_synthetic_count += 1
                continue
            candidate_movies.append(movie)

        if limit is not None and limit > 0:
            candidate_movies = candidate_movies[:limit]

        total_count = len(candidate_movies)

        # Check existing active jobs in the queue for deduplication reporting
        movie_ids_str = [str(m.id) for m in candidate_movies]
        existing_active_jobs_count = CatalogueJob.objects.filter(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id__in=movie_ids_str,
            status__in=[
                CatalogueJob.Status.PENDING,
                CatalogueJob.Status.IN_PROGRESS,
                CatalogueJob.Status.RETRY_WAIT,
            ],
        ).count()

        # Enforce preview / dry-run mode if languages specified but --confirm not provided
        if languages and not dry_run and not confirm:
            self.stdout.write(
                self.style.WARNING(
                    f"Targeted enqueueing for languages {languages} requires --confirm to execute. "
                    "Running in preview mode. Pass --confirm to execute database enqueueing.\n"
                )
            )
            dry_run = True

        if dry_run:
            self.stdout.write(self.style.NOTICE("=" * 70))
            self.stdout.write(self.style.NOTICE("CATALOGUE CLASSIFICATION ENQUEUE — DRY RUN REPORT"))
            self.stdout.write(self.style.NOTICE("=" * 70))
            self.stdout.write(f"Configuration & Filters:")
            self.stdout.write(f"  Provenance:             {provenance_filter}")
            self.stdout.write(f"  Languages:              {', '.join(languages) if languages else 'All'}")
            self.stdout.write(f"  Exclude Synthetic:      {exclude_synthetic} (excluded: {excluded_synthetic_count})")
            self.stdout.write(f"  Limit:                  {limit or 'None (unbounded)'}")
            self.stdout.write(f"  Batch Size:             {batch_size}")
            self.stdout.write(f"  Assigned Job Priority:  {priority}")
            self.stdout.write("-" * 70)
            self.stdout.write(f"Total Eligible Candidates:      {total_count}")
            if languages:
                self.stdout.write("Candidate Breakdown by Language:")
                for lang in languages:
                    c = sum(1 for m in candidate_movies if m.original_language == lang)
                    self.stdout.write(f"  - {lang.upper():<4} ({lang}): {c} movies")
            self.stdout.write(f"Existing Active Jobs in Queue:  {existing_active_jobs_count} (deduplicated)")
            self.stdout.write(f"Net New Jobs to Enqueue:        {total_count - existing_active_jobs_count}")
            self.stdout.write(f"Expected Downstream Enrichment: Up to {total_count} jobs (upon verified TMDB match)")
            self.stdout.write("-" * 70)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DRY-RUN] Found {total_count} movie(s) eligible for catalogue classification enqueueing.\n"
                    f"[DRY-RUN] Simulated enqueue of {total_count} movies with priority {priority} "
                    f"(job_type='catalogue_classification'). No database modifications performed."
                )
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Starting catalogue classification enqueue for {total_count} movie(s) with priority {priority}..."
            )
        )

        enqueued_count = 0
        deduplicated_count = 0
        processed_count = 0

        for movie in candidate_movies:
            _, created = CatalogueQueueService.enqueue(
                job_type="catalogue_classification",
                entity_type="movie",
                entity_id=str(movie.id),
                external_id=str(movie.tmdb_id),
                priority=priority,
                payload={"source": "initial_catalogue_classification", "original_language": movie.original_language},
            )
            if created:
                enqueued_count += 1
            else:
                deduplicated_count += 1

            processed_count += 1
            if processed_count % 100 == 0 or processed_count == total_count:
                self.stdout.write(
                    f"Processed {processed_count}/{total_count} movies "
                    f"({enqueued_count} new, {deduplicated_count} deduplicated)..."
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed classification enqueueing: "
                f"{processed_count} movies processed ({enqueued_count} newly enqueued, "
                f"{deduplicated_count} deduplicated/active)."
            )
        )

