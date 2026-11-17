from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    CollaborativeAgreement,
    Genre,
    InteractionLog,
    Movie,
    Session,
    SessionOccasionState,
    UserTasteProfile,
)
from core.services.manifest import (
    ActiveManifestImmutableError,
    CADENCE_10_CARD,
    CollaborativeDeckScorer,
    HamiltonManifestAllocator,
    InsufficientCandidatesError,
    ManifestCompilerService,
    NORMAL_CONSENSUS_COUNT,
    NORMAL_GUEST_COUNT,
    NORMAL_HOST_COUNT,
    NORMAL_MANIFEST_SIZE,
    ScoredCandidate,
)
from core.services.retrieval import CandidatePool, HardConstraints
from core.services.scoring import (
    IndividualRelevanceScorer,
    MovieIntelligenceData,
    UserPreferenceData,
)

User = get_user_model()


class HamiltonManifestAllocatorTests(TestCase):
    """
    Test Suite for Hamilton's Largest-Remainder Method (Architecture Section 10).
    Verifies 40/30/30 allocation, floor seats, fractional remainders, and deterministic tie-breaking.
    """

    def test_allocation_for_n_19_worked_example_1(self):
        """
        Architecture Worked Example 1:
        N = 19
        Q_C = 7.6, Q_H = 5.7, Q_G = 5.7
        Floors: I_C = 7, I_H = 5, I_G = 5. Sum = 17. Remaining = 2.
        Fractions: f_C = 0.6, f_H = 0.7, f_G = 0.7.
        Remainders awarded to Host (0.7) and Guest (0.7).
        Final: 7 Consensus, 6 Host, 6 Guest (Sum = 19).
        """
        alloc = HamiltonManifestAllocator.calculate_allocation(19)
        self.assertEqual(alloc["consensus"], 7)
        self.assertEqual(alloc["host_priority"], 6)
        self.assertEqual(alloc["guest_priority"], 6)
        self.assertEqual(sum(alloc.values()), 19)

    def test_allocation_for_n_25_worked_example_2_tie_break(self):
        """
        Architecture Worked Example 2:
        N = 25
        Q_C = 10.0, Q_H = 7.5, Q_G = 7.5
        Floors: I_C = 10, I_H = 7, I_G = 7. Sum = 24. Remaining = 1.
        Fractions: f_C = 0.0, f_H = 0.5, f_G = 0.5.
        Tie between Host (0.5) and Guest (0.5): Tie-break H > G awards seat to Host.
        Final: 10 Consensus, 8 Host, 7 Guest (Sum = 25).
        """
        alloc = HamiltonManifestAllocator.calculate_allocation(25)
        self.assertEqual(alloc["consensus"], 10)
        self.assertEqual(alloc["host_priority"], 8)
        self.assertEqual(alloc["guest_priority"], 7)
        self.assertEqual(sum(alloc.values()), 25)

    def test_allocation_across_required_boutique_sizes(self):
        """
        Verifies exact allocations for N = 16, 17, 20, 30, and 39.
        """
        # N = 16: Q_C=6.4, Q_H=4.8, Q_G=4.8 -> I=(6,4,4), R=2. f_H=0.8, f_G=0.8 > f_C=0.4
        # Alloc: 6C, 5H, 5G
        alloc_16 = HamiltonManifestAllocator.calculate_allocation(16)
        self.assertEqual(alloc_16, {"consensus": 6, "host_priority": 5, "guest_priority": 5})
        self.assertEqual(sum(alloc_16.values()), 16)

        # N = 17: Q_C=6.8, Q_H=5.1, Q_G=5.1 -> I=(6,5,5), R=1. f_C=0.8 > f_H=0.1, f_G=0.1
        # Alloc: 7C, 5H, 5G
        alloc_17 = HamiltonManifestAllocator.calculate_allocation(17)
        self.assertEqual(alloc_17, {"consensus": 7, "host_priority": 5, "guest_priority": 5})
        self.assertEqual(sum(alloc_17.values()), 17)

        # N = 20: Q_C=8.0, Q_H=6.0, Q_G=6.0 -> I=(8,6,6), R=0
        # Alloc: 8C, 6H, 6G
        alloc_20 = HamiltonManifestAllocator.calculate_allocation(20)
        self.assertEqual(alloc_20, {"consensus": 8, "host_priority": 6, "guest_priority": 6})
        self.assertEqual(sum(alloc_20.values()), 20)

        # N = 30: Q_C=12.0, Q_H=9.0, Q_G=9.0 -> I=(12,9,9), R=0
        # Alloc: 12C, 9H, 9G
        alloc_30 = HamiltonManifestAllocator.calculate_allocation(30)
        self.assertEqual(alloc_30, {"consensus": 12, "host_priority": 9, "guest_priority": 9})
        self.assertEqual(sum(alloc_30.values()), 30)

        # N = 39: Q_C=15.6, Q_H=11.7, Q_G=11.7 -> I=(15,11,11), R=2. f_H=0.7, f_G=0.7 > f_C=0.6
        # Alloc: 15C, 12H, 12G
        alloc_39 = HamiltonManifestAllocator.calculate_allocation(39)
        self.assertEqual(alloc_39, {"consensus": 15, "host_priority": 12, "guest_priority": 12})
        self.assertEqual(sum(alloc_39.values()), 39)

    def test_insufficient_candidates_raises_error(self):
        """Candidate counts under 16 raise InsufficientCandidatesError."""
        with self.assertRaises(InsufficientCandidatesError):
            HamiltonManifestAllocator.calculate_allocation(15)
        with self.assertRaises(InsufficientCandidatesError):
            HamiltonManifestAllocator.calculate_allocation(0)


class NormalManifestCompilationTests(TestCase):
    """
    Test Suite for Normal Screening Manifest Compilation (Architecture Section 10).
    - Exactly 40 unique cards.
    - Allocation: 16 Consensus, 12 Host Priority, 12 Guest Priority.
    - 4 repetitions of the approved cadence: [C, H, G, C, H, G, C, C, H, G].
    - Zero duplicates across categories.
    """

    def setUp(self):
        self.host_prefs = UserPreferenceData(
            moods=["uplifted", "thrilled"],
            narrative=["character"],
            themes=["identity_growth"],
            experience="balanced",
        )
        self.guest_prefs = UserPreferenceData(
            moods=["moved", "unsettled"],
            narrative=["ensemble"],
            themes=["mortality"],
            experience="heavy",
        )

        # Create 48 distinct movies
        self.movies = []
        for i in range(48):
            m = Movie.objects.create(
                tmdb_id=10000 + i,
                title=f"Normal Candidate {i}",
                rating=6.5 + (i % 25) * 0.1,
                vote_count=200 + i * 10,
                release_date=date(2010 + (i % 14), 1, 1),
                original_language="en",
            )
            self.movies.append(m)

    def test_normal_manifest_exact_counts_and_cadence(self):
        """Normal manifest produces exactly 40 unique cards with 4 cycles of the cadence."""
        manifest = ManifestCompilerService.compile_manifest(
            candidates=self.movies,
            host_prefs=self.host_prefs,
            guest_prefs=self.guest_prefs,
        )

        # Total count
        self.assertEqual(len(manifest), NORMAL_MANIFEST_SIZE)

        # Category counts
        c_count = sum(1 for c in manifest if c["slot_type"] == "consensus")
        h_count = sum(1 for c in manifest if c["slot_type"] == "host_priority")
        g_count = sum(1 for c in manifest if c["slot_type"] == "guest_priority")

        self.assertEqual(c_count, NORMAL_CONSENSUS_COUNT, "Consensus must have exactly 16 cards")
        self.assertEqual(h_count, NORMAL_HOST_COUNT, "Host Priority must have exactly 12 cards")
        self.assertEqual(g_count, NORMAL_GUEST_COUNT, "Guest Priority must have exactly 12 cards")

        # Zero duplicates guarantee
        movie_ids = [c["movie_id"] for c in manifest]
        self.assertEqual(len(movie_ids), len(set(movie_ids)), "Every card in manifest must be unique")

        # All movie IDs must come from candidate pool
        pool_ids = {m.id for m in self.movies}
        self.assertTrue(set(movie_ids).issubset(pool_ids))

        # Cadence verification: 4 repetitions of [C, H, G, C, H, G, C, C, H, G]
        expected_cadence_40 = CADENCE_10_CARD * 4
        actual_cadence_40 = [c["slot_type"] for c in manifest]
        self.assertEqual(actual_cadence_40, expected_cadence_40, "Cadence must repeat [C,H,G,C,H,G,C,C,H,G] 4 times")

        # Turn field verification
        for card in manifest:
            if card["slot_type"] == "consensus":
                self.assertEqual(card["turn"], "consensus")
            elif card["slot_type"] == "host_priority":
                self.assertEqual(card["turn"], "host")
            else:
                self.assertEqual(card["turn"], "guest")


class BoutiqueManifestCompilationTests(TestCase):
    """
    Test Suite for Boutique Screening Manifest Compilation (16 <= N <= 39).
    - Every candidate used exactly once (Zero Duplicate Rule).
    - Allocation matches Hamilton largest-remainder math.
    - Fractional progression step interleaving.
    """

    def setUp(self):
        self.host_prefs = UserPreferenceData(
            moods=["uplifted"],
            narrative=["character"],
            experience="light",
        )
        self.guest_prefs = UserPreferenceData(
            moods=["moved"],
            narrative=["complex"],
            experience="heavy",
        )

    def _create_candidates(self, count: int, prefix: int = 0) -> List[Movie]:
        candidates = []
        for i in range(count):
            m = Movie.objects.create(
                tmdb_id=20000 + prefix * 1000 + i,
                title=f"Boutique Candidate {prefix}_{count}_{i}",
                rating=7.0 + (i % 20) * 0.1,
                vote_count=100 + i * 5,
                release_date=date(2015, 1, 1),
                original_language="en",
            )
            candidates.append(m)
        return candidates

    def test_boutique_manifest_n_19(self):
        """Boutique manifest with N = 19 candidates."""
        candidates = self._create_candidates(19)
        manifest = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=self.host_prefs,
            guest_prefs=self.guest_prefs,
        )

        self.assertEqual(len(manifest), 19)

        # Category counts: 7C, 6H, 6G
        c_count = sum(1 for c in manifest if c["slot_type"] == "consensus")
        h_count = sum(1 for c in manifest if c["slot_type"] == "host_priority")
        g_count = sum(1 for c in manifest if c["slot_type"] == "guest_priority")

        self.assertEqual(c_count, 7)
        self.assertEqual(h_count, 6)
        self.assertEqual(g_count, 6)

        # Zero duplicates
        movie_ids = [c["movie_id"] for c in manifest]
        self.assertEqual(len(set(movie_ids)), 19)

    def test_boutique_manifest_n_25(self):
        """Boutique manifest with N = 25 candidates (tie-break H > G)."""
        candidates = self._create_candidates(25)
        manifest = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=self.host_prefs,
            guest_prefs=self.guest_prefs,
        )

        self.assertEqual(len(manifest), 25)

        # Category counts: 10C, 8H, 7G
        c_count = sum(1 for c in manifest if c["slot_type"] == "consensus")
        h_count = sum(1 for c in manifest if c["slot_type"] == "host_priority")
        g_count = sum(1 for c in manifest if c["slot_type"] == "guest_priority")

        self.assertEqual(c_count, 10)
        self.assertEqual(h_count, 8)
        self.assertEqual(g_count, 7)

        # Zero duplicates
        movie_ids = [c["movie_id"] for c in manifest]
        self.assertEqual(len(set(movie_ids)), 25)

    def test_boutique_manifest_boundary_sizes(self):
        """Verifies zero duplicates and exact lengths across sizes: 16, 17, 20, 30, and 39."""
        for idx, size in enumerate([16, 17, 20, 30, 39], start=10):
            candidates = self._create_candidates(size, prefix=idx)
            manifest = ManifestCompilerService.compile_manifest(
                candidates=candidates,
                host_prefs=self.host_prefs,
                guest_prefs=self.guest_prefs,
            )
            self.assertEqual(len(manifest), size)
            movie_ids = [c["movie_id"] for c in manifest]
            self.assertEqual(len(set(movie_ids)), size, f"Boutique manifest N={size} must have zero duplicate movies")


class ShortageRedistributionAndFloorTests(TestCase):
    """
    Test Suite for Relevance Floor Protection and Category Shortage Redistribution.
    """

    def setUp(self):
        self.host_prefs = UserPreferenceData(moods=["uplifted"], experience="light")
        self.guest_prefs = UserPreferenceData(moods=["moved"], experience="heavy")

    def test_shortage_redistribution_without_dropping_slots(self):
        """
        When host or guest candidates run short, unfillable slots are redistributed
        first to Consensus, then to partner, guaranteeing no dropped slots and zero duplicates.
        """
        # Create 20 candidates
        candidates = []
        for i in range(20):
            m = Movie.objects.create(
                tmdb_id=30000 + i,
                title=f"Shortage Candidate {i}",
                rating=7.0,
                vote_count=100,
                release_date=date(2020, 1, 1),
            )
            candidates.append(m)

        manifest = ManifestCompilerService.compile_manifest(
            candidates=candidates,
            host_prefs=self.host_prefs,
            guest_prefs=self.guest_prefs,
        )

        self.assertEqual(len(manifest), 20)
        movie_ids = [c["movie_id"] for c in manifest]
        self.assertEqual(len(set(movie_ids)), 20, "All 20 candidates must be uniquely included")


class ReproducibilityAndPersistenceTests(TestCase):
    """
    Test Suite for Manifest Determinism, Persistence, and Immutability.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="host_pers", password="password123")
        self.guest = User.objects.create_user(username="guest_pers", password="password123")
        self.session = Session.objects.create(
            code="MANTEST",
            host=self.host,
            guest=self.guest,
        )
        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            host_soft_preferences={"moods": ["uplifted"], "experience": "light"},
            guest_soft_preferences={"moods": ["moved"], "experience": "heavy"},
        )

        # 42 candidates
        self.candidates = []
        for i in range(42):
            m = Movie.objects.create(
                tmdb_id=40000 + i,
                title=f"Persist Candidate {i}",
                rating=7.5 + (i % 10) * 0.1,
                vote_count=300 + i,
                release_date=date(2021, 1, 1),
                original_language="en",
            )
            self.candidates.append(m)

    def test_deterministic_compilation_reproducibility(self):
        """Compiling twice with identical candidates and preferences yields identical manifests."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=42,
            local_count=42,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        m1 = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )
        m2 = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"]),
            guest_prefs=UserPreferenceData(moods=["moved"]),
        )

        self.assertEqual(len(m1), len(m2))
        for card1, card2 in zip(m1, m2):
            self.assertEqual(card1["card_index"], card2["card_index"])
            self.assertEqual(card1["movie_id"], card2["movie_id"])
            self.assertEqual(card1["slot_type"], card2["slot_type"])
            self.assertEqual(card1["scores"], card2["scores"])

    def test_compile_and_persist_manifest(self):
        """Manifest is safely compiled and persisted into CollaborativeAgreement."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=42,
            local_count=42,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )

        self.assertEqual(len(manifest), NORMAL_MANIFEST_SIZE)

        # Refresh agreement from database
        self.agreement.refresh_from_db()
        self.assertEqual(len(self.agreement.deck_manifest), NORMAL_MANIFEST_SIZE)
        self.assertEqual(self.agreement.deck_manifest[0]["movie_id"], manifest[0]["movie_id"])

    def test_active_manifest_immutability_protection(self):
        """
        When participants have begun swiping (host_card_index > 0),
        attempting to recompile without force_recompile raises ActiveManifestImmutableError.
        """
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=42,
            local_count=42,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        # First compilation
        ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )

        # Simulate host swiping 3 cards
        self.agreement.host_card_index = 3
        self.agreement.save(update_fields=["host_card_index"])

        # Attempt to recompile (with or without force_recompile) must raise ActiveManifestImmutableError
        with self.assertRaises(ActiveManifestImmutableError):
            ManifestCompilerService.compile_and_persist_manifest(
                session=self.session,
                agreement=self.agreement,
                candidate_pool=pool,
                force_recompile=False,
            )

        with self.assertRaises(ActiveManifestImmutableError):
            ManifestCompilerService.compile_and_persist_manifest(
                session=self.session,
                agreement=self.agreement,
                candidate_pool=pool,
                force_recompile=True,
            )


class ManifestLearnedFeedbackIntegrationTests(TestCase):
    """
    Test Suite for Learned Feedback Integration in Manifest Compilation (Workstream 4 / Fix 2).
    Verifies that historical InteractionLog records:
    - Contribute to candidate scoring (positive, negative, half-life decay).
    - Handle undo neutralization and deduplication.
    - Are correctly attributed to host vs guest.
    - Shift candidate ranking during actual manifest compilation.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="manifest_host", password="password123")
        self.guest = User.objects.create_user(username="manifest_guest", password="password123")
        self.session = Session.objects.create(code="FEEDBK", host=self.host, guest=self.guest)
        self.agreement = CollaborativeAgreement.objects.create(
            session=self.session,
            host_soft_preferences={"moods": ["uplifted"], "experience": "balanced"},
            guest_soft_preferences={"moods": ["moved"], "experience": "balanced"},
        )
        self.candidates = []
        for i in range(40):
            m = Movie.objects.create(
                tmdb_id=85000 + i,
                title=f"Feedback Candidate {i}",
                rating=7.0 + (i % 20) * 0.1,
                vote_count=500 + i * 10,
                release_date=date(2020, 1, 1),
            )
            self.candidates.append(m)

        self.signal_movie = Movie.objects.create(
            tmdb_id=89999,
            title="Signal Movie",
            rating=8.0,
            vote_count=1000,
            release_date=date(2018, 1, 1),
        )

    def test_manifest_compilation_with_zero_historical_interactions(self):
        """Manifest compilation succeeds with neutral 0.0 learned feedback when no logs exist."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        self.assertEqual(len(manifest), 40)
        first_card = manifest[0]
        self.assertIn("scores", first_card)
        self.assertGreater(first_card["scores"]["consensus"], 0.0)

    def test_positive_historical_feedback_affects_candidate_scoring(self):
        """Positive feedback (superlike = +3.0) increases host relevance."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_host_score = manifest_base[0]["scores"]["relevance_host"]

        # Host records positive interaction (+3.0)
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="superlike",
            weight=3.0,
        )

        manifest_with_fb = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        fb_host_score = manifest_with_fb[0]["scores"]["relevance_host"]

        # Expected boost: +3.0 / 115.0 ~ +0.0261
        diff = fb_host_score - base_host_score
        self.assertAlmostEqual(diff, 3.0 / 115.0, places=3)
        self.assertGreater(fb_host_score, base_host_score)

    def test_negative_historical_feedback_affects_candidate_scoring(self):
        """Negative feedback (3 dislikes = -3.6) decreases guest relevance."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_guest_score = manifest_base[0]["scores"]["relevance_guest"]

        # Guest records 3 dislikes on different movies
        for idx in range(3):
            m_dis = Movie.objects.create(tmdb_id=91000 + idx, title=f"Disliked {idx}")
            InteractionLog.objects.create(
                user=self.guest,
                session=self.session,
                movie=m_dis,
                event_type="swipe_dislike",
                weight=-1.2,
            )

        manifest_with_fb = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        fb_guest_score = manifest_with_fb[0]["scores"]["relevance_guest"]

        # Expected decrease: -3.6 / 115.0 ~ -0.0313
        diff = fb_guest_score - base_guest_score
        self.assertAlmostEqual(diff, -3.6 / 115.0, places=3)
        self.assertLess(fb_guest_score, base_guest_score)

    def test_expired_feedback_decays_correctly(self):
        """Feedback decays with 60-day half-life: 3.0 at 60 days decays to 1.5."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_host_score = manifest_base[0]["scores"]["relevance_host"]

        log = InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="superlike",
            weight=3.0,
        )
        # Manually backdate created_at by 60 days
        InteractionLog.objects.filter(id=log.id).update(
            created_at=timezone.now() - timedelta(days=60)
        )

        manifest_decayed = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        decayed_host_score = manifest_decayed[0]["scores"]["relevance_host"]

        # At 60 days, decay is 0.5: +1.5 / 115.0 ~ +0.0130
        diff = decayed_host_score - base_host_score
        self.assertAlmostEqual(diff, 1.5 / 115.0, places=3)

    def test_undo_events_neutralize_corresponding_interaction(self):
        """An undo event neutralizes the corresponding swipe in that session."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_host_score = manifest_base[0]["scores"]["relevance_host"]

        # Dislike followed by undo
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="swipe_dislike",
            weight=-1.2,
        )
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="undo",
            weight=0.0,
        )

        manifest_undone = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        undone_host_score = manifest_undone[0]["scores"]["relevance_host"]

        # Host score must equal baseline because dislike was neutralized
        self.assertAlmostEqual(undone_host_score, base_host_score, places=4)

    def test_host_and_guest_feedback_attribution_isolation(self):
        """Host feedback only affects host relevance; guest feedback only affects guest relevance."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_host_score = manifest_base[0]["scores"]["relevance_host"]
        base_guest_score = manifest_base[0]["scores"]["relevance_guest"]

        # Only Host gets feedback
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="superlike",
            weight=3.0,
        )

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        # Host score changes, Guest score is strictly unchanged
        self.assertAlmostEqual(manifest[0]["scores"]["relevance_host"] - base_host_score, 3.0 / 115.0, places=3)
        self.assertEqual(manifest[0]["scores"]["relevance_guest"], base_guest_score)

    def test_feedback_not_double_counted(self):
        """Duplicate swipes on the same movie in the same session are deduplicated."""
        pool = CandidatePool(
            pool_type="normal",
            candidates=self.candidates,
            total_count=40,
            local_count=40,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )
        manifest_base = ManifestCompilerService.compile_manifest(
            candidates=self.candidates,
            host_prefs=UserPreferenceData(moods=["uplifted"], experience="balanced"),
            guest_prefs=UserPreferenceData(moods=["moved"], experience="balanced"),
        )
        base_host_score = manifest_base[0]["scores"]["relevance_host"]

        # Two swipe_like logs for the exact same movie in the same session
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="swipe_like",
            weight=1.0,
        )
        InteractionLog.objects.create(
            user=self.host,
            session=self.session,
            movie=self.signal_movie,
            event_type="swipe_like",
            weight=1.0,
        )

        manifest = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
        )
        # Exactly 1.0 weight (+0.0087), not 2.0
        diff = manifest[0]["scores"]["relevance_host"] - base_host_score
        self.assertAlmostEqual(diff, 1.0 / 115.0, places=3)

    def test_learned_feedback_shifts_manifest_candidate_ranking_integration(self):
        """
        Integration Test: Historical InteractionLog records actively change candidate ranking
        and category slot assignment in the persisted manifest.
        """
        boutique_candidates = []
        for i in range(16):
            m = Movie.objects.create(
                tmdb_id=95000 + i,
                title=f"Rank Movie {i}",
                rating=6.0 + i * 0.2,
                vote_count=500,
                release_date=date(2021, 1, 1),
            )
            boutique_candidates.append(m)

        pool = CandidatePool(
            pool_type="boutique",
            candidates=boutique_candidates,
            total_count=16,
            local_count=16,
            replenished_count=0,
            hard_constraints=HardConstraints(),
            experience_type="screening",
        )

        manifest_1 = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
            force_recompile=True,
        )

        # Host records negative feedback (-12.0)
        for i in range(10):
            m_tmp = Movie.objects.create(tmdb_id=96000 + i, title=f"Dislike Film {i}")
            InteractionLog.objects.create(
                user=self.host,
                session=self.session,
                movie=m_tmp,
                event_type="swipe_dislike",
                weight=-1.2,
            )
        # Guest records positive feedback (+15.0)
        for i in range(5):
            m_tmp2 = Movie.objects.create(tmdb_id=97000 + i, title=f"Superlike Film {i}")
            InteractionLog.objects.create(
                user=self.guest,
                session=self.session,
                movie=m_tmp2,
                event_type="superlike",
                weight=3.0,
            )

        manifest_2 = ManifestCompilerService.compile_and_persist_manifest(
            session=self.session,
            agreement=self.agreement,
            candidate_pool=pool,
            force_recompile=True,
        )

        self.assertLess(manifest_2[0]["scores"]["relevance_host"], manifest_1[0]["scores"]["relevance_host"])
        self.assertGreater(manifest_2[0]["scores"]["relevance_guest"], manifest_1[0]["scores"]["relevance_guest"])
