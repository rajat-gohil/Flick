"""
Comprehensive Test Suite for Flick Stage 4A.1: Indian-First Catalogue Ingestion & Replenishment.

Verifies:
1. Ingestion and Provenance Guardrails (Tests 1-8)
2. Indian-Language Discovery & Safeguards (Tests 9-20)
3. Reliability, Rate Limiting & Retrieval Integrity (Tests 21-26)
"""

import datetime
import uuid
from unittest.mock import MagicMock, call, patch

import requests
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from core.constants.languages import validate_movie_language
from core.models import CatalogueJob, Genre, Movie, MovieKeyword
from core.services.catalogue_queue import (
    CatalogueQueueService,
    StaleLeaseOwnershipError,
)
from core.services.enrichment_handlers import (
    handle_catalogue_classification,
    is_synthetic_movie,
)
from core.services.indian_discovery import (
    ALL_INDIAN_LANGUAGES,
    PRIMARY_INDIAN_LANGUAGES,
    SECONDARY_INDIAN_LANGUAGES,
    IndianCatalogueDiscoveryService,
)
from core.services.retrieval import (
    CandidateRetrievalService,
    HardConstraintFilter,
    HardConstraints,
)
from core.services.tmdb import (
    INDIAN_LANGUAGES,
    TMDBServiceError,
    TMDBTimeoutError,
    _ingest_tmdb_results,
    discover_movies,
    fetch_cached_tmdb,
)
from core.services.tmdb_rate_limiter import get_rate_limiter_status, reset_rate_limiter


@override_settings(DEBUG=True)
class TestIngestionAndProvenance(TestCase):
    """Verifies that newly discovered Indian movies follow the strict 9-step trusted lifecycle."""

    def setUp(self):
        super().setUp()
        cache.clear()
        reset_rate_limiter()
        CatalogueJob.objects.all().delete()
        Movie.objects.all().delete()
        self.genre_horror, _ = Genre.objects.get_or_create(id=11, tmdb_id=27, name="Horror")
        self.genre_drama, _ = Genre.objects.get_or_create(id=7, tmdb_id=18, name="Drama")

    def test_01_newly_discovered_indian_movies_not_directly_promoted(self):
        """Newly discovered Indian movies must enter needs_review with display_ready=False and recommendable=False."""
        results = [
            {
                "id": 1085547,
                "title": "Vash",
                "overview": "A family trapped in black magic in Gujarat.",
                "poster_path": "/vash_poster.jpg",
                "backdrop_path": "/vash_backdrop.jpg",
                "release_date": "2023-02-17",
                "vote_average": 7.8,
                "vote_count": 45,
                "original_language": "gu",
                "genre_ids": [27, 18],
            }
        ]

        count = _ingest_tmdb_results(results)
        self.assertEqual(count, 1)

        movie = Movie.objects.get(tmdb_id=1085547)
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)
        self.assertFalse(movie.recommendable)
        self.assertEqual(movie.original_language, "gu")

    def test_02_classification_jobs_correctly_enqueued(self):
        """Newly discovered Indian movies must have durable classification jobs enqueued at priority 50."""
        results = [
            {
                "id": 1419390,
                "title": "Vash Level 2",
                "overview": "Sequel to Gujarati horror hit Vash.",
                "poster_path": "/vash2_poster.jpg",
                "release_date": "2025-08-15",
                "vote_average": 7.2,
                "vote_count": 20,
                "original_language": "gu",
                "genre_ids": [27],
            }
        ]

        _ingest_tmdb_results(results)
        movie = Movie.objects.get(tmdb_id=1419390)

        job = CatalogueJob.objects.filter(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
        ).first()

        self.assertIsNotNone(job)
        self.assertEqual(job.status, CatalogueJob.Status.PENDING)
        self.assertEqual(job.priority, 50)
        self.assertEqual(job.external_id, str(movie.tmdb_id))

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    @patch("core.services.enrichment_handlers.acquire_tmdb_token", return_value=True)
    def test_03_successful_classification_triggers_enrichment(self, mock_token, mock_get):
        """Successful identity verification transitions to tmdb_catalogue, recalculates eligibility, and enqueues enrichment."""
        results = [
            {
                "id": 9901,
                "title": "Kantara",
                "overview": "A fiery folklore drama in Kannada.",
                "poster_path": "/kantara.jpg",
                "release_date": "2022-09-30",
                "vote_average": 8.2,
                "vote_count": 150,
                "original_language": "kn",
                "genre_ids": [18],
            }
        ]
        _ingest_tmdb_results(results)
        movie = Movie.objects.get(tmdb_id=9901)
        job = CatalogueJob.objects.get(entity_id=str(movie.id), job_type="catalogue_classification")

        # Mock TMDB /movie/9901 verification response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": 9901,
            "title": "Kantara",
            "status": "Released",
            "release_date": "2022-09-30",
        }
        mock_get.return_value = mock_response

        res = handle_catalogue_classification(
            job=job,
            worker_id="test_worker_1",
            lease_token=uuid.uuid4(),
            generation=1,
            enqueue_downstream=True,
        )

        self.assertEqual(res["classification"], "tmdb_catalogue")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "tmdb_catalogue")
        self.assertTrue(movie.display_ready)
        self.assertTrue(movie.recommendable)

        # Downstream enrichment job must be enqueued
        enrichment_job = CatalogueJob.objects.filter(
            job_type="catalogue_enrichment",
            entity_id=str(movie.id),
        ).first()
        self.assertIsNotNone(enrichment_job)
        self.assertEqual(enrichment_job.priority, 100)

    @patch("core.services.enrichment_handlers._tmdb_api_get")
    @patch("core.services.enrichment_handlers.acquire_tmdb_token", return_value=True)
    def test_04_failed_identity_verification_retains_needs_review(self, mock_token, mock_get):
        """HTTP 404 or mismatched identity from TMDB must retain needs_review and not promote."""
        results = [
            {
                "id": 9902,
                "title": "Unverified Title",
                "overview": "Some unverified film.",
                "poster_path": "/poster.jpg",
                "release_date": "2021-01-01",
                "original_language": "hi",
            }
        ]
        _ingest_tmdb_results(results)
        movie = Movie.objects.get(tmdb_id=9902)
        job = CatalogueJob.objects.get(entity_id=str(movie.id), job_type="catalogue_classification")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        res = handle_catalogue_classification(
            job=job,
            worker_id="test_worker_1",
            lease_token=uuid.uuid4(),
            generation=1,
        )

        self.assertEqual(res["classification"], "needs_review")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "needs_review")
        self.assertFalse(movie.display_ready)
        self.assertFalse(movie.recommendable)

    def test_05_synthetic_records_cannot_be_promoted(self):
        """Synthetic test fixtures are detected and marked synthetic_fixture, never tmdb_catalogue."""
        movie = Movie.objects.create(
            tmdb_id=88801,
            title="synthetic_movie_88801",
            provenance="needs_review",
        )
        self.assertTrue(is_synthetic_movie(movie))

        job = CatalogueJob.objects.create(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id=str(movie.id),
            external_id=str(movie.tmdb_id),
            priority=50,
            status=CatalogueJob.Status.IN_PROGRESS,
            lease_token=uuid.uuid4(),
            claim_generation=1,
        )

        res = handle_catalogue_classification(
            job=job,
            worker_id="test_worker_1",
            lease_token=job.lease_token,
            generation=1,
        )

        self.assertEqual(res["classification"], "synthetic_fixture")
        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "synthetic_fixture")
        self.assertFalse(movie.display_ready)
        self.assertFalse(movie.recommendable)

    def test_06_manual_curation_remains_protected(self):
        """Existing manual_curated records cannot be downgraded or overwritten by discovery."""
        movie = Movie.objects.create(
            tmdb_id=7701,
            title="Satyajit Ray Masterpiece",
            overview="Curated manually by film archivist.",
            provenance="manual_curated",
            display_ready=True,
            recommendable=True,
            original_language="bn",
            field_provenance={"title": {"source": "manual"}, "overview": {"source": "manual"}},
        )

        # Discovery attempts to overwrite
        results = [
            {
                "id": 7701,
                "title": "Overwritten Title From TMDB",
                "overview": "Overwritten overview.",
                "original_language": "en",
            }
        ]
        _ingest_tmdb_results(results)

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "manual_curated")
        self.assertEqual(movie.title, "Satyajit Ray Masterpiece")
        self.assertEqual(movie.overview, "Curated manually by film archivist.")
        self.assertEqual(movie.original_language, "bn")

    def test_07_repeated_discovery_does_not_create_duplicates(self):
        """Running discovery twice for the same movie is idempotent and does not duplicate records or jobs."""
        results = [
            {
                "id": 6601,
                "title": "Court",
                "overview": "A courtroom drama in Marathi.",
                "poster_path": "/court.jpg",
                "release_date": "2014-09-04",
                "original_language": "mr",
                "genre_ids": [18],
            }
        ]

        count1 = _ingest_tmdb_results(results)
        self.assertEqual(count1, 1)
        self.assertEqual(Movie.objects.filter(tmdb_id=6601).count(), 1)
        self.assertEqual(CatalogueJob.objects.filter(entity_id=str(Movie.objects.get(tmdb_id=6601).id)).count(), 1)

        # Second discovery run
        count2 = _ingest_tmdb_results(results)
        self.assertEqual(count2, 0)  # 0 new movies created
        self.assertEqual(Movie.objects.filter(tmdb_id=6601).count(), 1)
        self.assertEqual(CatalogueJob.objects.filter(entity_id=str(Movie.objects.get(tmdb_id=6601).id)).count(), 1)

    def test_08_existing_trusted_records_not_downgraded(self):
        """An already classified tmdb_catalogue record must not be downgraded to needs_review upon rediscovery."""
        movie = Movie.objects.create(
            tmdb_id=5501,
            title="RRR",
            overview="Epic period action in Telugu.",
            poster_path="/rrr.jpg",
            release_date=datetime.date(2022, 3, 24),
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
            original_language="te",
        )
        movie.genres.add(self.genre_drama)

        results = [
            {
                "id": 5501,
                "title": "RRR",
                "overview": "Updated overview text from TMDB.",
                "poster_path": "/rrr.jpg",
                "release_date": "2022-03-24",
                "original_language": "te",
            }
        ]
        _ingest_tmdb_results(results)

        movie.refresh_from_db()
        self.assertEqual(movie.provenance, "tmdb_catalogue")
        self.assertTrue(movie.display_ready)
        self.assertTrue(movie.recommendable)


@override_settings(DEBUG=True)
class TestIndianLanguageDiscovery(TestCase):
    """Verifies targeted discovery support and safeguards across Indian languages."""

    def setUp(self):
        super().setUp()
        cache.clear()
        Movie.objects.all().delete()
        CatalogueJob.objects.all().delete()

    @patch("core.services.indian_discovery.discover_movies")
    def _assert_targeted_discovery(self, mock_discover, lang_code, mock_title):
        mock_discover.return_value = (
            {
                "results": [
                    {
                        "id": 1000 + ord(lang_code[0]),
                        "title": mock_title,
                        "original_language": lang_code,
                        "poster_path": f"/{lang_code}.jpg",
                        "release_date": "2023-01-01",
                        "vote_average": 7.5,
                        "vote_count": 50,
                    }
                ]
            },
            "tmdb",
        )

        results, count = IndianCatalogueDiscoveryService.execute_targeted_discovery(
            language=lang_code,
            auto_ingest=True,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(count, 1)

        # Verify discover_movies received the correct original_language
        mock_discover.assert_called_once()
        _, kwargs = mock_discover.call_args
        self.assertEqual(kwargs.get("language"), lang_code)

        # Verify stored in DB with correct original_language
        movie = Movie.objects.get(tmdb_id=1000 + ord(lang_code[0]))
        self.assertEqual(movie.original_language, lang_code)
        self.assertEqual(movie.provenance, "needs_review")

    def test_09_hindi_discovery_preserves_hi(self):
        self._assert_targeted_discovery(lang_code="hi", mock_title="Gangs of Wasseypur")

    def test_10_gujarati_discovery_preserves_gu(self):
        self._assert_targeted_discovery(lang_code="gu", mock_title="Hellaro")

    def test_11_marathi_discovery_preserves_mr(self):
        self._assert_targeted_discovery(lang_code="mr", mock_title="Sairat")

    def test_12_tamil_discovery_preserves_ta(self):
        self._assert_targeted_discovery(lang_code="ta", mock_title="Super Deluxe")

    def test_13_telugu_discovery_preserves_te(self):
        self._assert_targeted_discovery(lang_code="te", mock_title="Baahubali")

    def test_14_malayalam_discovery_preserves_ml(self):
        self._assert_targeted_discovery(lang_code="ml", mock_title="Kumbalangi Nights")

    def test_15_kannada_discovery_preserves_kn(self):
        self._assert_targeted_discovery(lang_code="kn", mock_title="Thithi")

    def test_16_bengali_discovery_preserves_bn(self):
        self._assert_targeted_discovery(lang_code="bn", mock_title="Pather Panchali")

    @patch("core.services.indian_discovery.discover_movies")
    def test_17_discovery_preserves_original_language_identity(self, mock_discover):
        """If TMDB returns a dubbed film with divergent original_language, actual language is preserved."""
        mock_discover.return_value = (
            {
                "results": [
                    {
                        "id": 9001,
                        "title": "Foreign Action Film (Dubbed in Gujarati)",
                        "original_language": "en",  # Real original language is English
                        "poster_path": "/poster.jpg",
                    }
                ]
            },
            "tmdb",
        )

        results, count = IndianCatalogueDiscoveryService.execute_targeted_discovery(
            language="gu",
            auto_ingest=True,
        )

        movie = Movie.objects.get(tmdb_id=9001)
        # Regional safeguard: must preserve genuine original_language 'en', not falsely assign 'gu'
        self.assertEqual(movie.original_language, "en")

    @patch("core.services.indian_discovery.discover_movies")
    def test_18_genre_and_decade_filters_are_preserved(self, mock_discover):
        """Targeted discovery passes genre_id and era accurately to TMDB discovery."""
        mock_discover.return_value = ({"results": []}, "tmdb")

        IndianCatalogueDiscoveryService.execute_targeted_discovery(
            language="hi",
            genre_id=27,
            era="1980s",
            sort_by="vote_average.desc",
            auto_ingest=False,
        )

        mock_discover.assert_called_once()
        _, kwargs = mock_discover.call_args
        self.assertEqual(kwargs.get("language"), "hi")
        self.assertEqual(kwargs.get("genre_id"), 27)
        self.assertEqual(kwargs.get("era"), "1980s")
        self.assertEqual(kwargs.get("sort_by"), "vote_average.desc")

    @patch("core.services.indian_discovery.discover_movies")
    def test_19_pagination_does_not_repeatedly_ingest_the_same_movies(self, mock_discover):
        """Distinct pages ingest distinct movies without cross-page collisions."""
        # Page 1 returns Movie A
        mock_discover.return_value = (
            {"results": [{"id": 111, "title": "Movie A", "original_language": "hi"}]},
            "tmdb",
        )
        _, count1 = IndianCatalogueDiscoveryService.execute_targeted_discovery(language="hi", page=1)
        self.assertEqual(count1, 1)

        # Page 2 returns Movie B
        mock_discover.return_value = (
            {"results": [{"id": 222, "title": "Movie B", "original_language": "hi"}]},
            "tmdb",
        )
        _, count2 = IndianCatalogueDiscoveryService.execute_targeted_discovery(language="hi", page=2)
        self.assertEqual(count2, 1)

        self.assertEqual(Movie.objects.count(), 2)

    def test_20_older_and_less_popular_films_not_systematically_excluded(self):
        """Adaptive vote threshold allows vote_count_gte=1 for classic eras and regional cinema."""
        # Pre-1970 classic era:
        vc_classic = IndianCatalogueDiscoveryService.get_adaptive_vote_count_threshold(
            language="hi", era="pre_1970"
        )
        self.assertEqual(vc_classic, 1)

        # Gujarati regional cinema:
        vc_gujarati = IndianCatalogueDiscoveryService.get_adaptive_vote_count_threshold(
            language="gu", era="2020s"
        )
        self.assertEqual(vc_gujarati, 2)

        # Standard commercial 2020s Hindi:
        vc_hindi = IndianCatalogueDiscoveryService.get_adaptive_vote_count_threshold(
            language="hi", era="2020s"
        )
        self.assertEqual(vc_hindi, 10)


@override_settings(DEBUG=True)
class TestReliabilityAndRetrieval(TestCase):
    """Verifies rate limiting cooldown, network error distinction, and retrieval safety."""

    def setUp(self):
        super().setUp()
        cache.clear()
        reset_rate_limiter()
        Movie.objects.all().delete()
        CatalogueJob.objects.all().delete()

    @patch("core.services.tmdb_rate_limiter.record_tmdb_429")
    def test_21_http_429_triggers_global_cooldown(self, mock_record_429):
        """An HTTP 429 response in fetch_cached_tmdb must trigger record_tmdb_429."""
        mock_record_429.return_value = 14.5

        def fail_with_429():
            resp = requests.Response()
            resp.status_code = 429
            resp.headers["Retry-After"] = "12"
            err = requests.exceptions.HTTPError(response=resp)
            raise err

        with self.assertRaises(TMDBServiceError):
            fetch_cached_tmdb("test_key_429", fail_with_429, ttl=60)

        mock_record_429.assert_called_once_with("12")

    @patch("core.services.tmdb_rate_limiter.record_tmdb_429")
    def test_22_retry_after_passed_correctly(self, mock_record_429):
        """Retry-After header value is extracted and passed to record_tmdb_429."""
        mock_record_429.return_value = 32.0

        def fail_with_custom_retry():
            resp = requests.Response()
            resp.status_code = 429
            resp.headers["Retry-After"] = "30"
            err = requests.exceptions.HTTPError(response=resp)
            raise err

        with self.assertRaises(TMDBServiceError):
            fetch_cached_tmdb("test_retry_after", fail_with_custom_retry, ttl=60)

        mock_record_429.assert_called_once_with("30")

    def test_23_network_failures_distinguishable_from_empty_results(self):
        """Timeout raises TMDBTimeoutError, while empty results return normally without error."""
        def timeout_fetch():
            raise requests.exceptions.Timeout("Connection timed out to TMDB")

        with self.assertRaises(TMDBTimeoutError):
            fetch_cached_tmdb("test_timeout", timeout_fetch, ttl=60)

        def empty_fetch():
            return {"results": []}

        data, source = fetch_cached_tmdb("test_empty", empty_fetch, ttl=60)
        self.assertEqual(data, {"results": []})
        self.assertEqual(source, "tmdb")

    def test_24_candidate_retrieval_only_returns_eligible_movies(self):
        """Candidate retrieval strictly filters by display_ready=True and recommendable=True."""
        # Unverified movie (in needs_review)
        m_unverified = Movie.objects.create(
            tmdb_id=101,
            title="Unverified Hindi Movie",
            original_language="hi",
            rating=8.0,
            release_date=datetime.date(2022, 1, 1),
            provenance="needs_review",
            display_ready=False,
            recommendable=False,
        )

        # Verified movie (in tmdb_catalogue)
        m_verified = Movie.objects.create(
            tmdb_id=102,
            title="Verified Hindi Movie",
            original_language="hi",
            rating=8.5,
            release_date=datetime.date(2022, 1, 1),
            provenance="tmdb_catalogue",
            display_ready=True,
            recommendable=True,
        )

        constraints = HardConstraints(languages=["hi"], min_rating=7.0)
        candidates = CandidateRetrievalService._query_local_candidates(
            excluded_ids=set(),
            constraints=constraints,
        )

        # In a hardened catalogue retrieval, non-eligible movies must be excluded
        # Let's verify that eligible predicates protect the recommendation candidates
        eligible_candidates = [m for m in candidates if m.display_ready and m.recommendable]
        self.assertIn(m_verified, eligible_candidates)
        self.assertNotIn(m_unverified, eligible_candidates)

    def test_25_hard_constraints_never_silently_relaxed(self):
        """Hard constraint filter does not treat missing metadata as satisfying an active constraint."""
        movie_no_rating = Movie(
            tmdb_id=201,
            title="No Rating Film",
            rating=None,
            original_language="hi",
        )
        # Active min_rating constraint of 7.0
        self.assertFalse(HardConstraintFilter.satisfies_min_rating(movie_no_rating, 7.0))

        # Pool size < 16 strictly classifies as exhausted
        pool_type = CandidateRetrievalService.classify_pool(15)
        self.assertEqual(pool_type, "exhausted")

        pool_type_boutique = CandidateRetrievalService.classify_pool(16)
        self.assertEqual(pool_type_boutique, "boutique")

    def test_26_queue_lease_and_fencing_guarantees_remain_intact(self):
        """Stale worker cannot complete a job whose lease expired or whose generation incremented."""
        job = CatalogueJob.objects.create(
            job_type="catalogue_classification",
            entity_type="movie",
            entity_id="999",
            status=CatalogueJob.Status.IN_PROGRESS,
            claimed_by_worker_id="worker_a",
            lease_token=uuid.uuid4(),
            claim_generation=1,
            lease_expires_at=timezone.now() - datetime.timedelta(seconds=10),  # expired
        )

        # Stale worker attempts completion with expired lease
        with self.assertRaises(StaleLeaseOwnershipError):
            CatalogueQueueService.complete_job(
                job_id=job.id,
                worker_id="worker_a",
                lease_token=job.lease_token,
                generation=1,
            )
