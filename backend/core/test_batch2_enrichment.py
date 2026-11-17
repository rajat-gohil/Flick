"""
Integration and regression tests for Flick Batch 2 Catalogue Intelligence.

Tests cover:
1. Classification handler assigning 'synthetic_fixture' for synthetic pattern / missing TMDB ID.
2. Classification handler assigning 'tmdb_catalogue' for verified identity match.
3. Classification handler enqueuing 'catalogue_enrichment' idempotently without duplicates.
4. Classification handler retaining 'needs_review' on 404 or title mismatch.
5. Enrichment handler enriching an incomplete movie (such as Fight Club PK 367),
   updating metadata, keywords M2M, genres M2M, credits_summary, last_enriched_at,
   and atomically recalculating eligibility (display_ready=True, recommendable=True).
6. Missing handler failing with is_permanent=True and status FAILED_PERMANENT (no silent no-op).
7. Invalid payload failing with is_permanent=True and status FAILED_PERMANENT.
8. Stale worker rejection via StaleLeaseOwnershipError on completion / failure.
"""

import datetime
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import CatalogueJob, Genre, Movie, MovieKeyword
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.services.enrichment_handlers import (
    handle_catalogue_classification,
    handle_catalogue_enrichment,
)
from core.management.commands.run_intelligence_worker import IntelligenceWorkerProcess


@override_settings(DEBUG=True)
class Batch2EnrichmentAndWorkerTests(TestCase):
    """Integration test suite for Batch 2 enrichment handlers and worker execution."""

    def setUp(self):
        super().setUp()
        from core.management.commands.run_intelligence_worker import reset_handlers
        reset_handlers()
        # Clean any preexisting jobs
        CatalogueJob.objects.all().delete()

    # ─────────────────────────────────────────────────────────────────────────
    # 1. CLASSIFICATION HANDLER TESTS
    # ─────────────────────────────────────────────────────────────────────────

    def test_classification_assigns_synthetic_fixture_for_synthetic_pattern(self):
        """Movies with synthetic patterns (e.g. synthetic_movie_123 or negative tmdb_id) become synthetic_fixture."""
        m_synthetic = Movie.objects.create(
            title="synthetic_movie_99",
            tmdb_id=9999999,
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(m_synthetic.id),
            priority=150,
        )

        claims = CatalogueQueueService.claim_jobs("worker-1", batch_size=1)
        self.assertEqual(len(claims), 1)
        claimed_job = claims[0]

        res = handle_catalogue_classification(
            claimed_job,
            worker_id="worker-1",
            lease_token=claimed_job.lease_token,
            generation=claimed_job.claim_generation,
        )

        self.assertEqual(res["classification"], "synthetic_fixture")
        m_synthetic.refresh_from_db()
        self.assertEqual(m_synthetic.provenance, "synthetic_fixture")
        self.assertFalse(m_synthetic.display_ready)
        self.assertFalse(m_synthetic.recommendable)

        # Downstream enrichment job should NOT be enqueued for synthetic
        enrichment_jobs = CatalogueJob.objects.filter(job_type="catalogue_enrichment")
        self.assertEqual(enrichment_jobs.count(), 0)

    def test_classification_assigns_synthetic_fixture_for_negative_tmdb_id(self):
        """Movies with negative tmdb_id become synthetic_fixture."""
        m_negative = Movie.objects.create(
            title="Custom Local Film",
            tmdb_id=-1,
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(m_negative.id),
            priority=150,
        )

        claimed_job = CatalogueQueueService.claim_jobs("worker-1", batch_size=1)[0]
        res = handle_catalogue_classification(
            claimed_job,
            worker_id="worker-1",
            lease_token=claimed_job.lease_token,
            generation=claimed_job.claim_generation,
        )
        self.assertEqual(res["classification"], "synthetic_fixture")
        m_negative.refresh_from_db()
        self.assertEqual(m_negative.provenance, "synthetic_fixture")

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_classification_assigns_tmdb_catalogue_and_enqueues_enrichment(self, mock_get):
        """Genuine movie with matching TMDB details transitions to tmdb_catalogue and enqueues enrichment."""
        movie = Movie.objects.create(
            title="Inception",
            tmdb_id=27205,
            release_date=datetime.date(2010, 7, 16),
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
            priority=150,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 27205,
            "title": "Inception",
            "original_title": "Inception",
            "status": "Released",
            "release_date": "2010-07-16",
        }
        mock_get.return_value = mock_resp

        claimed = CatalogueQueueService.claim_jobs("worker-class", batch_size=1)[0]
        res = handle_catalogue_classification(
            claimed,
            worker_id="worker-class",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )

        self.assertEqual(res["classification"], "tmdb_catalogue")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "tmdb_catalogue")

        # Verify downstream enrichment job was enqueued
        enrichment_job = CatalogueJob.objects.get(
            job_type="catalogue_enrichment",
            entity_id=str(movie.id),
        )
        self.assertEqual(enrichment_job.priority, 100)
        self.assertEqual(enrichment_job.status, CatalogueJob.Status.PENDING)

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_classification_downstream_enqueue_idempotency(self, mock_get):
        """Repeated classification runs or retries do not create duplicate enrichment jobs."""
        movie = Movie.objects.create(
            title="Interstellar",
            tmdb_id=157336,
            release_date=datetime.date(2014, 11, 5),
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
            priority=150,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 157336,
            "title": "Interstellar",
            "status": "Released",
            "release_date": "2014-11-05",
        }
        mock_get.return_value = mock_resp

        claimed = CatalogueQueueService.claim_jobs("worker-class", batch_size=1)[0]
        res1 = handle_catalogue_classification(
            claimed,
            worker_id="worker-class",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )
        self.assertTrue(res1["downstream_job_created"])

        # Second invocation (simulating retry or re-run)
        movie.provenance = "needs_review"
        movie.save(update_fields=["provenance"])
        res2 = handle_catalogue_classification(
            claimed,
            worker_id="worker-class",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )
        self.assertFalse(res2["downstream_job_created"])
        self.assertEqual(
            CatalogueJob.objects.filter(job_type="catalogue_enrichment", entity_id=str(movie.id)).count(),
            1,
        )

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_classification_404_retains_needs_review(self, mock_get):
        """When TMDB returns 404, provenance remains 'needs_review' with audit note."""
        movie = Movie.objects.create(
            title="Nonexistent Movie",
            tmdb_id=99999999,
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        claimed = CatalogueQueueService.claim_jobs("worker-1", batch_size=1)[0]
        res = handle_catalogue_classification(
            claimed,
            worker_id="worker-1",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )
        self.assertEqual(res["classification"], "needs_review")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertTrue(any("404" in str(entry) for entry in audit))

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_classification_title_mismatch_retains_needs_review(self, mock_get):
        """When TMDB title is completely different, provenance remains 'needs_review'."""
        movie = Movie.objects.create(
            title="The Matrix",
            tmdb_id=603,
            provenance="needs_review",
        )
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 603,
            "title": "Totally Unrelated Movie Title",
            "status": "Released",
            "release_date": "1999-03-31",
        }
        mock_get.return_value = mock_resp

        claimed = CatalogueQueueService.claim_jobs("worker-1", batch_size=1)[0]
        res = handle_catalogue_classification(
            claimed,
            worker_id="worker-1",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )
        self.assertEqual(res["classification"], "needs_review")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        audit = movie.field_provenance.get("_classification_audit", [])
        self.assertTrue(any("mismatch" in str(entry).lower() for entry in audit))

    # ─────────────────────────────────────────────────────────────────────────
    # 2. ENRICHMENT HANDLER TESTS
    # ─────────────────────────────────────────────────────────────────────────

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_enrichment_handler_enriches_movie_and_updates_eligibility(self, mock_get):
        """
        Enrichment handler populates metadata, genres, keywords, credits_summary,
        last_enriched_at, and recalculates eligibility into display_ready & recommendable.
        Simulates an incomplete movie record like Fight Club (tmdb_id=550).
        """
        movie = Movie.objects.create(
            title="Fight Club",
            tmdb_id=550,
            overview="",
            poster_path=None,
            original_language=None,
            release_date=datetime.date(1999, 10, 15),
            provenance="tmdb_catalogue",
            display_ready=False,
            recommendable=False,
        )

        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_enrichment",
            entity_type="movie",
            entity_id=str(movie.id),
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 550,
            "title": "Fight Club",
            "overview": "A ticking-time-bomb insomniac and a slippery soap salesman...",
            "poster_path": "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg",
            "backdrop_path": "/hZkgoQYus5vegHoetLkCJzb17zJ.jpg",
            "vote_average": 8.433,
            "vote_count": 26000,
            "original_language": "en",
            "release_date": "1999-10-15",
            "genres": [
                {"id": 18, "name": "Drama"},
                {"id": 53, "name": "Thriller"},
            ],
            "keywords": {
                "keywords": [
                    {"id": 825, "name": "support group"},
                    {"id": 1533, "name": "insomnia"},
                ]
            },
            "credits": {
                "cast": [
                    {"id": 819, "name": "Edward Norton", "character": "The Narrator"},
                    {"id": 287, "name": "Brad Pitt", "character": "Tyler Durden"},
                ],
                "crew": [
                    {"id": 7467, "name": "David Fincher", "job": "Director"},
                ],
            },
        }
        mock_get.return_value = mock_resp

        claimed = CatalogueQueueService.claim_jobs("worker-enrich", batch_size=1)[0]
        res = handle_catalogue_enrichment(
            claimed,
            worker_id="worker-enrich",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )

        self.assertEqual(res["status"], "enriched")
        movie.refresh_from_db()

        # Check updated fields
        self.assertEqual(movie.poster_path, "/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg")
        self.assertEqual(movie.original_language, "en")
        self.assertIn("insomniac", movie.overview)
        self.assertEqual(movie.vote_count, 26000)
        self.assertAlmostEqual(movie.rating, 8.433, places=2)
        self.assertIsNotNone(movie.last_enriched_at)

        # Check M2M genres and keywords
        genre_names = set(movie.genres.values_list("name", flat=True))
        self.assertIn("Drama", genre_names)
        self.assertIn("Thriller", genre_names)

        keyword_names = set(movie.keywords.values_list("name", flat=True))
        self.assertIn("support group", keyword_names)
        self.assertIn("insomnia", keyword_names)

        # Check credits summary
        self.assertEqual(len(movie.credits_summary.get("cast", [])), 2)
        self.assertEqual(len(movie.credits_summary.get("directors", [])), 1)

        # Check eligibility predicates
        self.assertTrue(movie.display_ready)
        self.assertTrue(movie.recommendable)

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    def test_enrichment_respects_manual_override_fields(self, mock_get):
        """Automated enrichment does not overwrite fields that have a manual provenance source."""
        movie = Movie.objects.create(
            title="Custom Curated Title",
            tmdb_id=550,
            poster_path="/custom_poster.jpg",
            provenance="tmdb_catalogue",
            field_provenance={
                "title": {"source": "manual", "updated_by": "curator_admin"},
            },
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 550,
            "title": "TMDB Official Fight Club Title",
            "poster_path": "/new_tmdb_poster.jpg",
            "overview": "Fight Club overview",
            "original_language": "en",
            "release_date": "1999-10-15",
            "genres": [{"id": 18, "name": "Drama"}],
            "keywords": {"keywords": []},
            "credits": {"cast": [], "crew": []},
        }
        mock_get.return_value = mock_resp

        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_enrichment",
            entity_type="movie",
            entity_id=str(movie.id),
        )
        claimed = CatalogueQueueService.claim_jobs("worker-enrich", batch_size=1)[0]
        handle_catalogue_enrichment(
            claimed,
            worker_id="worker-enrich",
            lease_token=claimed.lease_token,
            generation=claimed.claim_generation,
        )

        movie.refresh_from_db()
        # Title must NOT have changed because of manual override!
        self.assertEqual(movie.title, "Custom Curated Title")
        # Divergent value must be recorded in field_provenance
        title_meta = movie.field_provenance["title"]
        self.assertEqual(title_meta["source"], "manual")
        self.assertEqual(title_meta["divergent_tmdb_value"], "TMDB Official Fight Club Title")

        # But un-overridden poster_path was updated
        self.assertEqual(movie.poster_path, "/new_tmdb_poster.jpg")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. WORKER ERROR DISPATCH & DEFECT ELIMINATION
    # ─────────────────────────────────────────────────────────────────────────

    def test_unknown_job_type_fails_permanently(self):
        """
        Eliminating Batch 1 silent no-op defect:
        When a job with an unregistered handler is processed, the worker must fail it
        permanently with is_permanent=True and status FAILED_PERMANENT.
        """
        job, _ = CatalogueQueueService.enqueue(
            job_type="unknown_unregistered_job_type",
            entity_type="system",
            entity_id="test-1",
        )

        worker = IntelligenceWorkerProcess(worker_id="worker-test-unknown", batch_size=1)
        summary = worker.run_loop(once=True)

        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["failed"], 1)

        job.refresh_from_db()
        self.assertEqual(job.status, CatalogueJob.Status.FAILED_PERMANENT)
        self.assertIn("UnknownJobHandlerError", job.last_error)

    def test_invalid_payload_fails_permanently(self):
        """Jobs with non-dict payloads fail permanently."""
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id="1",
        )
        # Force non-dict payload directly in DB
        CatalogueJob.objects.filter(pk=job.id).update(payload="invalid-string-payload")

        worker = IntelligenceWorkerProcess(worker_id="worker-test-payload", batch_size=1)
        summary = worker.run_loop(once=True)

        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["failed"], 1)

        job.refresh_from_db()
        self.assertEqual(job.status, CatalogueJob.Status.FAILED_PERMANENT)
        self.assertIn("InvalidPayloadError", job.last_error)

    def test_stale_worker_rejection_via_stale_lease_ownership_error(self):
        """Worker completing a job after another worker reclaimed it raises StaleLeaseOwnershipError and returns False."""
        job, _ = CatalogueQueueService.enqueue(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id="1",
        )

        worker_a = IntelligenceWorkerProcess(worker_id="worker-A", batch_size=1)
        claimed = CatalogueQueueService.claim_jobs("worker-A", batch_size=1, lease_duration_seconds=5)[0]

        # Simulate expiration and reclamation by worker-B
        CatalogueJob.objects.filter(id=job.id).update(
            lease_expires_at=timezone.now() - datetime.timedelta(seconds=1)
        )
        CatalogueQueueService.reclaim_expired_leases()

        # Worker-A attempts to complete or fail the job
        with self.assertRaises(StaleLeaseOwnershipError):
            CatalogueQueueService.complete_job(
                job_id=job.id,
                worker_id="worker-A",
                lease_token=claimed.lease_token,
                generation=claimed.claim_generation,
            )

        # Worker process_one_job catches StaleLeaseOwnershipError cleanly and returns False
        claimed.status = CatalogueJob.Status.IN_PROGRESS
        success = worker_a.process_one_job(claimed)
        self.assertFalse(success)
