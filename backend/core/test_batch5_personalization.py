"""
Three-Account Personalization Evaluation and 12-Criterion Test Suite for Flick Batch 5.

Implements the mandatory personalization evaluation across five distinct account archetypes:
- Account A: Sci-Fi / Mystery affinity (Speculative / Mind-Bending).
- Account B: Romance / Drama affinity (Humanistic / Emotional / Period).
- Account C: Action / Crime affinity (High-Stakes / Adrenaline / Crime).
- Account D: Cold-Start (0 interactions, pristine state).
- Account E: Canonical account with linked guest actor.

Validates all 12 criteria in Section 8 of the prompt:
1. Personalized recommendations reflect each account's distinct interaction history.
2. Cohort divergence target met: Jaccard similarity between different taste accounts < 0.30.
3. Curator's Selection prioritizes higher quality and higher confidence matches than generic discovery.
4. The 5 Your Archive shelves have distinct non-identical outputs.
5. Complete Catalogue returns identical results regardless of which user is authenticated.
6. Disliked genres/keywords are penalized in recommendations.
7. Undo reverses preference signals.
8. Linked guest history correctly flows into canonical user recommendations.
9. Strict account isolation: Account A interactions do not alter Accounts B or C.
10. Cold-start account returns honest COLD_START label and fallback explanations.
11. Repeat exposure handles fatigue according to policy.
12. Deterministic scoring for identical inputs.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Set
import unittest.mock
import uuid

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import (
    Genre,
    InteractionLog,
    LinkType,
    Movie,
    MovieExposure,
    MovieKeyword,
    MovieTag,
    Session,
    Swipe,
    UserIdentityLink,
    UserTasteProfile,
)
from core.services.archive_shelves import ArchiveShelvesService
from core.services.identity_linking import IdentityLinkingService
from core.services.recommendation_engine import PersonalizedRecommendationEngine
from core.services.recommendation_evaluation import (
    RecommendationEvaluationService,
    compute_cohort_divergence,
    compute_negative_response_rate,
    compute_preference_alignment,
    compute_shelf_diversity,
    compute_unexposed_discovery_ratio,
)
from core.services.taste_engine import TasteEngineService

User = get_user_model()


class Batch5PersonalizationEvaluationTests(APITestCase):
    """
    Comprehensive verification of the 5-account personalization evaluation and 12 criteria.
    """

    def setUp(self):
        # 1. Setup Canonical TMDB Genres
        # Cohort A Genres (Speculative Fiction)
        self.genre_scifi = Genre.objects.get_or_create(tmdb_id=878, defaults={"name": "Science Fiction"})[0]
        self.genre_mystery = Genre.objects.get_or_create(tmdb_id=9648, defaults={"name": "Mystery"})[0]
        self.genre_fantasy = Genre.objects.get_or_create(tmdb_id=14, defaults={"name": "Fantasy"})[0]
        self.genre_animation = Genre.objects.get_or_create(tmdb_id=16, defaults={"name": "Animation"})[0]

        # Cohort B Genres (Romance / Drama / Humanistic)
        self.genre_romance = Genre.objects.get_or_create(tmdb_id=10749, defaults={"name": "Romance"})[0]
        self.genre_drama = Genre.objects.get_or_create(tmdb_id=18, defaults={"name": "Drama"})[0]
        self.genre_music = Genre.objects.get_or_create(tmdb_id=10402, defaults={"name": "Music"})[0]
        self.genre_history = Genre.objects.get_or_create(tmdb_id=36, defaults={"name": "History"})[0]

        # Cohort C Genres (Action / Crime / High-Stakes)
        self.genre_action = Genre.objects.get_or_create(tmdb_id=28, defaults={"name": "Action"})[0]
        self.genre_crime = Genre.objects.get_or_create(tmdb_id=80, defaults={"name": "Crime"})[0]
        self.genre_thriller = Genre.objects.get_or_create(tmdb_id=53, defaults={"name": "Thriller"})[0]
        self.genre_adventure = Genre.objects.get_or_create(tmdb_id=12, defaults={"name": "Adventure"})[0]

        # Distaste Genre
        self.genre_horror = Genre.objects.get_or_create(tmdb_id=27, defaults={"name": "Horror"})[0]

        # 2. Setup Tags and Keywords
        self.tag_cyberpunk = MovieTag.objects.create(name="cyberpunk")
        self.tag_noir = MovieTag.objects.create(name="noir")
        self.tag_love = MovieTag.objects.create(name="romantic")
        self.tag_period = MovieTag.objects.create(name="period-piece")
        self.tag_heist = MovieTag.objects.create(name="heist")
        self.tag_martial = MovieTag.objects.create(name="martial-arts")
        self.tag_mob = MovieTag.objects.create(name="mobster")
        self.tag_explosive = MovieTag.objects.create(name="explosive")
        self.tag_jumpscare = MovieTag.objects.create(name="jump-scare")

        self.kw_ai = MovieKeyword.objects.create(name="artificial intelligence", tmdb_id=201)
        self.kw_space = MovieKeyword.objects.create(name="space travel", tmdb_id=202)
        self.kw_wedding = MovieKeyword.objects.create(name="wedding", tmdb_id=203)
        self.kw_mafia = MovieKeyword.objects.create(name="mafia", tmdb_id=204)

        # 3. Candidate Movies Pool (All recommendable, display_ready, with valid posters and en language)

        # --- Sci-Fi / Mystery Cohort (A) (12 movies, 4 primary genres) ---
        # Primary Sci-Fi (878)
        self.movie_blade_runner = self._create_movie(
            tmdb_id=5001,
            title="Blade Runner 2049",
            genres=[self.genre_scifi],
            genre_ids=[878],
            tags=[self.tag_cyberpunk, self.tag_noir],
            keywords=[self.kw_ai],
            rating=8.0,
            vote_count=12000,
            release_date=datetime.date(2017, 10, 6),
        )
        self.movie_arrival = self._create_movie(
            tmdb_id=5002,
            title="Arrival",
            genres=[self.genre_scifi],
            genre_ids=[878],
            tags=[self.tag_noir],
            keywords=[self.kw_space],
            rating=7.9,
            vote_count=15000,
            release_date=datetime.date(2016, 11, 11),
        )
        self.movie_ex_machina = self._create_movie(
            tmdb_id=5003,
            title="Ex Machina",
            genres=[self.genre_scifi],
            genre_ids=[878],
            tags=[self.tag_cyberpunk],
            keywords=[self.kw_ai],
            rating=7.7,
            vote_count=13000,
            release_date=datetime.date(2014, 12, 16),
        )
        # Primary Mystery (9648)
        self.movie_dark_city = self._create_movie(
            tmdb_id=5004,
            title="Dark City",
            genres=[self.genre_mystery],
            genre_ids=[9648],
            tags=[self.tag_cyberpunk, self.tag_noir],
            rating=7.6,
            vote_count=3500,
            release_date=datetime.date(1998, 2, 27),
        )
        self.movie_solaris = self._create_movie(
            tmdb_id=5005,
            title="Solaris",
            genres=[self.genre_mystery],
            genre_ids=[9648],
            tags=[self.tag_noir],
            keywords=[self.kw_space],
            rating=8.0,
            vote_count=4000,
            release_date=datetime.date(1972, 3, 20),
        )
        self.movie_memento = self._create_movie(
            tmdb_id=5006,
            title="Memento",
            genres=[self.genre_mystery],
            genre_ids=[9648],
            tags=[self.tag_noir],
            rating=8.4,
            vote_count=14000,
            release_date=datetime.date(2000, 10, 11),
        )
        # Primary Fantasy (14)
        self.movie_pans_labyrinth = self._create_movie(
            tmdb_id=5007,
            title="Pan's Labyrinth",
            genres=[self.genre_fantasy],
            genre_ids=[14],
            tags=[self.tag_noir],
            rating=8.2,
            vote_count=11000,
            release_date=datetime.date(2006, 10, 11),
        )
        self.movie_stalker = self._create_movie(
            tmdb_id=5008,
            title="Stalker",
            genres=[self.genre_fantasy],
            genre_ids=[14],
            tags=[self.tag_cyberpunk],
            rating=8.1,
            vote_count=5000,
            release_date=datetime.date(1979, 5, 29),
        )
        self.movie_spirited_away = self._create_movie(
            tmdb_id=5009,
            title="Spirited Away",
            genres=[self.genre_fantasy],
            genre_ids=[14],
            tags=[self.tag_cyberpunk],
            rating=8.5,
            vote_count=16000,
            release_date=datetime.date(2001, 7, 20),
        )
        # Primary Animation (16)
        self.movie_ghost_in_shell = self._create_movie(
            tmdb_id=5010,
            title="Ghost in the Shell",
            genres=[self.genre_animation],
            genre_ids=[16],
            tags=[self.tag_cyberpunk],
            keywords=[self.kw_ai],
            rating=8.0,
            vote_count=8000,
            release_date=datetime.date(1995, 11, 18),
        )
        self.movie_akira = self._create_movie(
            tmdb_id=5011,
            title="Akira",
            genres=[self.genre_animation],
            genre_ids=[16],
            tags=[self.tag_cyberpunk],
            rating=8.0,
            vote_count=9000,
            release_date=datetime.date(1988, 7, 16),
        )
        self.movie_paprika = self._create_movie(
            tmdb_id=5012,
            title="Paprika",
            genres=[self.genre_animation],
            genre_ids=[16],
            tags=[self.tag_noir],
            rating=7.8,
            vote_count=6000,
            release_date=datetime.date(2006, 11, 25),
        )

        # --- Romance / Drama Cohort (B) (12 movies, 4 primary genres) ---
        # Primary Romance (10749)
        self.movie_notebook = self._create_movie(
            tmdb_id=5021,
            title="The Notebook",
            genres=[self.genre_romance],
            genre_ids=[10749],
            tags=[self.tag_love],
            rating=7.9,
            vote_count=11000,
            release_date=datetime.date(2004, 6, 25),
        )
        self.movie_pride_prejudice = self._create_movie(
            tmdb_id=5022,
            title="Pride and Prejudice",
            genres=[self.genre_romance],
            genre_ids=[10749],
            tags=[self.tag_period, self.tag_love],
            keywords=[self.kw_wedding],
            rating=8.1,
            vote_count=8000,
            release_date=datetime.date(2005, 9, 16),
        )
        self.movie_la_la_land = self._create_movie(
            tmdb_id=5023,
            title="La La Land",
            genres=[self.genre_romance],
            genre_ids=[10749],
            tags=[self.tag_love],
            rating=8.0,
            vote_count=16000,
            release_date=datetime.date(2016, 12, 9),
        )
        # Primary Drama (18)
        self.movie_before_sunrise = self._create_movie(
            tmdb_id=5024,
            title="Before Sunrise",
            genres=[self.genre_drama],
            genre_ids=[18],
            tags=[self.tag_love],
            rating=8.1,
            vote_count=6000,
            release_date=datetime.date(1995, 1, 27),
        )
        self.movie_casablanca = self._create_movie(
            tmdb_id=5025,
            title="Casablanca",
            genres=[self.genre_drama],
            genre_ids=[18],
            tags=[self.tag_period, self.tag_love],
            rating=8.5,
            vote_count=5000,
            release_date=datetime.date(1942, 11, 26),
        )
        self.movie_portrait_lady = self._create_movie(
            tmdb_id=5026,
            title="Portrait of a Lady on Fire",
            genres=[self.genre_drama],
            genre_ids=[18],
            tags=[self.tag_period, self.tag_love],
            rating=8.1,
            vote_count=3500,
            release_date=datetime.date(2019, 9, 18),
        )
        # Primary Music (10402)
        self.movie_whiplash = self._create_movie(
            tmdb_id=5027,
            title="Whiplash",
            genres=[self.genre_music],
            genre_ids=[10402],
            tags=[self.tag_love],
            rating=8.5,
            vote_count=14000,
            release_date=datetime.date(2014, 10, 10),
        )
        self.movie_sound_of_music = self._create_movie(
            tmdb_id=5028,
            title="The Sound of Music",
            genres=[self.genre_music],
            genre_ids=[10402],
            tags=[self.tag_period, self.tag_love],
            rating=8.0,
            vote_count=8000,
            release_date=datetime.date(1965, 3, 29),
        )
        self.movie_amadeus = self._create_movie(
            tmdb_id=5029,
            title="Amadeus",
            genres=[self.genre_music],
            genre_ids=[10402],
            tags=[self.tag_period],
            rating=8.4,
            vote_count=6000,
            release_date=datetime.date(1984, 9, 19),
        )
        # Primary History (36)
        self.movie_atonement = self._create_movie(
            tmdb_id=5030,
            title="Atonement",
            genres=[self.genre_history],
            genre_ids=[36],
            tags=[self.tag_period, self.tag_love],
            rating=7.7,
            vote_count=5000,
            release_date=datetime.date(2007, 9, 7),
        )
        self.movie_sense_sensibility = self._create_movie(
            tmdb_id=5031,
            title="Sense and Sensibility",
            genres=[self.genre_history],
            genre_ids=[36],
            tags=[self.tag_period, self.tag_love],
            keywords=[self.kw_wedding],
            rating=7.8,
            vote_count=4000,
            release_date=datetime.date(1995, 12, 13),
        )
        self.movie_doctor_zhivago = self._create_movie(
            tmdb_id=5032,
            title="Doctor Zhivago",
            genres=[self.genre_history],
            genre_ids=[36],
            tags=[self.tag_period, self.tag_love],
            rating=8.0,
            vote_count=3000,
            release_date=datetime.date(1965, 12, 22),
        )

        # --- Action / Crime Cohort (C) (12 movies, 4 primary genres) ---
        # Primary Action (28)
        self.movie_dark_knight = self._create_movie(
            tmdb_id=5041,
            title="The Dark Knight",
            genres=[self.genre_action],
            genre_ids=[28],
            tags=[self.tag_explosive],
            rating=8.5,
            vote_count=32000,
            release_date=datetime.date(2008, 7, 18),
        )
        self.movie_die_hard = self._create_movie(
            tmdb_id=5042,
            title="Die Hard",
            genres=[self.genre_action],
            genre_ids=[28],
            tags=[self.tag_heist],
            rating=7.8,
            vote_count=11000,
            release_date=datetime.date(1988, 7, 15),
        )
        self.movie_john_wick = self._create_movie(
            tmdb_id=5043,
            title="John Wick",
            genres=[self.genre_action],
            genre_ids=[28],
            tags=[self.tag_martial],
            rating=7.4,
            vote_count=18000,
            release_date=datetime.date(2014, 10, 24),
        )
        # Primary Crime (80)
        self.movie_heat = self._create_movie(
            tmdb_id=5044,
            title="Heat",
            genres=[self.genre_crime],
            genre_ids=[80],
            tags=[self.tag_heist],
            rating=8.3,
            vote_count=7500,
            release_date=datetime.date(1995, 12, 15),
        )
        self.movie_goodfellas = self._create_movie(
            tmdb_id=5045,
            title="Goodfellas",
            genres=[self.genre_crime],
            genre_ids=[80],
            tags=[self.tag_mob],
            keywords=[self.kw_mafia],
            rating=8.5,
            vote_count=13000,
            release_date=datetime.date(1990, 9, 19),
        )
        self.movie_pulp_fiction = self._create_movie(
            tmdb_id=5046,
            title="Pulp Fiction",
            genres=[self.genre_crime],
            genre_ids=[80],
            tags=[self.tag_mob],
            keywords=[self.kw_mafia],
            rating=8.5,
            vote_count=28000,
            release_date=datetime.date(1994, 10, 14),
        )
        # Primary Thriller (53)
        self.movie_casino = self._create_movie(
            tmdb_id=5047,
            title="Casino",
            genres=[self.genre_thriller],
            genre_ids=[53],
            tags=[self.tag_mob],
            keywords=[self.kw_mafia],
            rating=8.2,
            vote_count=6000,
            release_date=datetime.date(1995, 11, 22),
        )
        self.movie_sicario = self._create_movie(
            tmdb_id=5048,
            title="Sicario",
            genres=[self.genre_thriller],
            genre_ids=[53],
            tags=[self.tag_mob],
            rating=7.6,
            vote_count=8000,
            release_date=datetime.date(2015, 9, 17),
        )
        self.movie_departed = self._create_movie(
            tmdb_id=5049,
            title="The Departed",
            genres=[self.genre_thriller],
            genre_ids=[53],
            tags=[self.tag_heist, self.tag_mob],
            keywords=[self.kw_mafia],
            rating=8.2,
            vote_count=14000,
            release_date=datetime.date(2006, 10, 5),
        )
        # Primary Adventure (12)
        self.movie_mad_max = self._create_movie(
            tmdb_id=5050,
            title="Mad Max: Fury Road",
            genres=[self.genre_adventure],
            genre_ids=[12],
            tags=[self.tag_heist],
            rating=7.6,
            vote_count=21000,
            release_date=datetime.date(2015, 5, 13),
        )
        self.movie_raiders = self._create_movie(
            tmdb_id=5051,
            title="Raiders of the Lost Ark",
            genres=[self.genre_adventure],
            genre_ids=[12],
            tags=[self.tag_heist],
            rating=8.2,
            vote_count=12000,
            release_date=datetime.date(1981, 6, 12),
        )
        self.movie_gladiator = self._create_movie(
            tmdb_id=5052,
            title="Gladiator",
            genres=[self.genre_adventure],
            genre_ids=[12],
            tags=[self.tag_martial],
            rating=8.2,
            vote_count=17000,
            release_date=datetime.date(2000, 5, 4),
        )

        # Distaste / Penalty Movies (Horror)
        self.movie_conjuring = self._create_movie(
            tmdb_id=5061,
            title="The Conjuring",
            genres=[self.genre_horror],
            genre_ids=[27],
            tags=[self.tag_jumpscare],
            rating=7.5,
            vote_count=11500,
            release_date=datetime.date(2013, 7, 19),
        )
        self.movie_hereditary = self._create_movie(
            tmdb_id=5062,
            title="Hereditary",
            genres=[self.genre_horror],
            genre_ids=[27],
            tags=[self.tag_jumpscare],
            rating=7.3,
            vote_count=7500,
            release_date=datetime.date(2018, 6, 7),
        )

        # 4. Setup The Five Accounts
        self.account_a = User.objects.create_user(username="account_a_scifi", password="pw")
        self.account_b = User.objects.create_user(username="account_b_romance", password="pw")
        self.account_c = User.objects.create_user(username="account_c_action", password="pw")
        self.account_d = User.objects.create_user(username="account_d_coldstart", password="pw")
        self.account_e = User.objects.create_user(username="account_e_canonical", password="pw")
        self.guest_e = User.objects.create_user(username="guest_actor_e", password="pw")

        # Link guest_e to account_e
        IdentityLinkingService.link_guest_to_user(
            canonical_user=self.account_e,
            guest_user=self.guest_e,
            link_type=LinkType.GUEST_CONVERSION,
        )

        # 5. Populate Interaction Histories
        # Account A: Sci-Fi / Mystery / Fantasy / Animation + Dislike Horror (11 interactions -> HIGH confidence)
        self._record_interactions(
            user=self.account_a,
            likes=[
                self.movie_blade_runner,
                self.movie_arrival,
                self.movie_dark_city,
                self.movie_solaris,
                self.movie_pans_labyrinth,
                self.movie_ghost_in_shell,
            ],
            superlikes=[self.movie_blade_runner, self.movie_dark_city],
            matches=[self.movie_arrival, self.movie_akira],
            dislikes=[self.movie_conjuring],
        )
        TasteEngineService.recompute_user_taste_profile(self.account_a, force=True)

        # Account B: Romance / Drama / Music / History (11 interactions -> HIGH confidence)
        self._record_interactions(
            user=self.account_b,
            likes=[
                self.movie_notebook,
                self.movie_pride_prejudice,
                self.movie_la_la_land,
                self.movie_before_sunrise,
                self.movie_casablanca,
                self.movie_whiplash,
            ],
            superlikes=[self.movie_notebook, self.movie_pride_prejudice],
            matches=[self.movie_la_la_land, self.movie_before_sunrise, self.movie_atonement],
        )
        TasteEngineService.recompute_user_taste_profile(self.account_b, force=True)

        # Account C: Action / Crime / Thriller / Adventure (11 interactions -> HIGH confidence)
        self._record_interactions(
            user=self.account_c,
            likes=[
                self.movie_dark_knight,
                self.movie_heat,
                self.movie_goodfellas,
                self.movie_pulp_fiction,
                self.movie_casino,
                self.movie_mad_max,
            ],
            superlikes=[self.movie_dark_knight, self.movie_heat],
            matches=[self.movie_goodfellas, self.movie_pulp_fiction, self.movie_raiders],
        )
        TasteEngineService.recompute_user_taste_profile(self.account_c, force=True)

        # Account D: 0 interactions (Pristine Cold-Start)

        # Account E: Canonical account has 0 direct interactions, but linked guest_e has 10 interactions on Sci-Fi / Mystery
        self._record_interactions(
            user=self.guest_e,
            likes=[
                self.movie_blade_runner,
                self.movie_arrival,
                self.movie_dark_city,
                self.movie_ex_machina,
                self.movie_pans_labyrinth,
            ],
            superlikes=[self.movie_blade_runner, self.movie_arrival],
            matches=[self.movie_ex_machina, self.movie_dark_city, self.movie_solaris],
        )
        TasteEngineService.recompute_user_taste_profile(self.account_e, force=True)

    def _create_movie(
        self,
        tmdb_id: int,
        title: str,
        genres: List[Genre],
        rating: float,
        vote_count: int,
        release_date: datetime.date,
        genre_ids: List[int] = None,
        tags: List[MovieTag] = None,
        keywords: List[MovieKeyword] = None,
    ) -> Movie:
        t_ids = genre_ids if genre_ids is not None else [g.tmdb_id for g in genres if g.tmdb_id]
        m = Movie.objects.create(
            tmdb_id=tmdb_id,
            title=title,
            rating=rating,
            vote_count=vote_count,
            release_date=release_date,
            poster_path=f"/posters/{tmdb_id}.jpg",
            original_language="en",
            display_ready=True,
            recommendable=True,
            provenance="tmdb_catalogue",
            tmdb_genre_ids=t_ids,
        )
        m.genres.set(genres)
        if tags:
            m.tags.set(tags)
        if keywords:
            m.keywords.set(keywords)
        return m

    def _record_interactions(
        self,
        user: User,
        likes: List[Movie] = None,
        superlikes: List[Movie] = None,
        matches: List[Movie] = None,
        dislikes: List[Movie] = None,
    ):
        session = Session.objects.create(code=uuid.uuid4().hex[:6].upper(), host=user)
        for m in likes or []:
            InteractionLog.objects.create(
                user=user,
                movie=m,
                event_type="like",
                weight=1.0,
                processing_status="pending",
            )
            Swipe.objects.update_or_create(
                session=session,
                user=user,
                movie=m,
                defaults={"reaction": Swipe.LIKE},
            )

        for m in superlikes or []:
            InteractionLog.objects.create(
                user=user,
                movie=m,
                event_type="superlike",
                weight=3.0,
                processing_status="pending",
            )
            Swipe.objects.update_or_create(
                session=session,
                user=user,
                movie=m,
                defaults={"reaction": Swipe.SUPERLIKE},
            )

        for m in matches or []:
            InteractionLog.objects.create(
                user=user,
                movie=m,
                event_type="match",
                weight=2.5,
                processing_status="pending",
            )

        for m in dislikes or []:
            InteractionLog.objects.create(
                user=user,
                movie=m,
                event_type="dislike",
                weight=-1.2,
                processing_status="pending",
            )
            Swipe.objects.update_or_create(
                session=session,
                user=user,
                movie=m,
                defaults={"reaction": Swipe.DISLIKE},
            )

    # =========================================================================
    # Criterion 1: Personalized recommendations reflect distinct interaction history
    # =========================================================================
    def test_criterion_1_recommendations_reflect_distinct_interaction_histories(self):
        """
        Verify that Account A, B, and C recommendations each strongly align with their
        distinct affinity profiles (Sci-Fi/Mystery vs Romance/Drama vs Action/Crime).
        """
        res_a = PersonalizedRecommendationEngine.get_recommendations(self.account_a, limit=10)
        res_b = PersonalizedRecommendationEngine.get_recommendations(self.account_b, limit=10)
        res_c = PersonalizedRecommendationEngine.get_recommendations(self.account_c, limit=10)

        self.assertEqual(res_a["confidence"], "HIGH")
        self.assertEqual(res_b["confidence"], "HIGH")
        self.assertEqual(res_c["confidence"], "HIGH")

        alignment_a = compute_preference_alignment(self.account_a, res_a["movies"])
        alignment_b = compute_preference_alignment(self.account_b, res_b["movies"])
        alignment_c = compute_preference_alignment(self.account_c, res_c["movies"])

        self.assertGreaterEqual(alignment_a, 0.70)
        self.assertGreaterEqual(alignment_b, 0.70)
        self.assertGreaterEqual(alignment_c, 0.70)

        # Inspect top movie attributes
        top_a_genres = [g.name for g in res_a["movies"][0].genres.all()]
        self.assertTrue("Science Fiction" in top_a_genres or "Mystery" in top_a_genres or "Fantasy" in top_a_genres or "Animation" in top_a_genres)

        top_b_genres = [g.name for g in res_b["movies"][0].genres.all()]
        self.assertTrue("Romance" in top_b_genres or "Drama" in top_b_genres or "Music" in top_b_genres or "History" in top_b_genres)

        top_c_genres = [g.name for g in res_c["movies"][0].genres.all()]
        self.assertTrue("Action" in top_c_genres or "Crime" in top_c_genres or "Thriller" in top_c_genres or "Adventure" in top_c_genres)

    # =========================================================================
    # Criterion 2: Cohort divergence target met (Jaccard similarity < 0.30)
    # =========================================================================
    def test_criterion_2_cohort_divergence_target_met(self):
        """
        Verify that Jaccard similarity between recommendations for accounts with
        different taste archetypes is strictly less than 0.30 (cohort divergence target).
        """
        recs_a = PersonalizedRecommendationEngine.get_recommendations(self.account_a, limit=10)["movies"]
        recs_b = PersonalizedRecommendationEngine.get_recommendations(self.account_b, limit=10)["movies"]
        recs_c = PersonalizedRecommendationEngine.get_recommendations(self.account_c, limit=10)["movies"]

        ids_a = [m.id for m in recs_a]
        ids_b = [m.id for m in recs_b]
        ids_c = [m.id for m in recs_c]

        sim_ab = compute_cohort_divergence(ids_a, ids_b)
        sim_ac = compute_cohort_divergence(ids_a, ids_c)
        sim_bc = compute_cohort_divergence(ids_b, ids_c)

        self.assertLess(sim_ab, 0.30, f"Account A vs B Jaccard similarity {sim_ab} exceeded 0.30")
        self.assertLess(sim_ac, 0.30, f"Account A vs C Jaccard similarity {sim_ac} exceeded 0.30")
        self.assertLess(sim_bc, 0.30, f"Account B vs C Jaccard similarity {sim_bc} exceeded 0.30")

    # =========================================================================
    # Criterion 3: Curator's Selection prioritizes higher quality & confidence
    # =========================================================================
    def test_criterion_3_curators_selection_prioritizes_high_quality_and_confidence(self):
        """
        Verify Curator's Selection returns high-confidence recommendations with
        quality filtering and grounded explanations.
        """
        self.client.force_authenticate(user=self.account_a)
        response = self.client.get("/api/curators-selection/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["confidence"], "HIGH")
        self.assertGreaterEqual(len(data["movies"]), 5)

        # Check that returned movies have high ratings
        ratings = [float(m.get("rating") or m.get("vote_average") or 0.0) for m in data["movies"]]
        avg_rating = sum(ratings) / len(ratings)
        self.assertGreaterEqual(avg_rating, 7.5)

        # Check grounded explanations
        for movie in data["movies"]:
            explanation = movie.get("explanation")
            self.assertIsNotNone(explanation)
            self.assertIn("reason", explanation)
            self.assertIn("confidence", explanation)
            self.assertEqual(explanation["confidence"], "HIGH")
            self.assertTrue(len(explanation["reason"]) > 0)

    # =========================================================================
    # Criterion 4: The 5 Your Archive shelves have distinct non-identical outputs
    # =========================================================================
    def test_criterion_4_archive_shelves_have_distinct_non_identical_outputs(self):
        """
        Verify that Your Archive generates all 5 distinct shelves with cross-shelf
        deduplication and high inter-shelf diversity (> 0.70).
        """
        self.client.force_authenticate(user=self.account_a)
        response = self.client.get("/api/your-archive/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        self.assertTrue(data["success"])

        expected_shelves = [
            "recommended_for_you",
            "because_you_liked",
            "explore_your_genres",
            "explore_by_era",
            "outside_your_comfort_zone",
        ]

        shelves = data.get("shelves", {})
        for s_key in expected_shelves:
            self.assertIn(s_key, shelves, f"Shelf '{s_key}' missing from /api/your-archive/")
            self.assertGreater(len(shelves[s_key]), 0, f"Shelf '{s_key}' was empty")

        # Evaluate shelf diversity
        diversity_score = compute_shelf_diversity(shelves)
        self.assertGreaterEqual(
            diversity_score,
            0.70,
            f"Inter-shelf diversity score {diversity_score} was lower than 0.70",
        )

        # Verify strict cross-shelf deduplication
        all_ids: List[int] = []
        for s_key, items in shelves.items():
            for item in items:
                mid = item.get("id")
                self.assertNotIn(mid, all_ids, f"Movie ID {mid} appeared in multiple shelves")
                all_ids.append(mid)

    # =========================================================================
    # Criterion 5: Complete Catalogue returns identical results regardless of auth
    # =========================================================================
    def test_criterion_5_complete_catalogue_returns_identical_unpersonalized_results(self):
        """
        Verify Complete Catalogue (/api/catalogue/) is 100% unpersonalized and returns
        identical results for unauthenticated, Account A, and Account B.
        """
        # Unauthenticated request
        self.client.logout()
        res_anon = self.client.get("/api/catalogue/").json()

        # Account A request
        self.client.force_authenticate(user=self.account_a)
        res_a = self.client.get("/api/catalogue/").json()

        # Account B request
        self.client.force_authenticate(user=self.account_b)
        res_b = self.client.get("/api/catalogue/").json()

        self.assertEqual(res_anon["count"], res_a["count"])
        self.assertEqual(res_a["count"], res_b["count"])

        anon_ids = [m["id"] for m in res_anon["results"]]
        a_ids = [m["id"] for m in res_a["results"]]
        b_ids = [m["id"] for m in res_b["results"]]

        self.assertEqual(anon_ids, a_ids, "Account A received personalized results on /api/catalogue/")
        self.assertEqual(a_ids, b_ids, "Account B received differing results on /api/catalogue/")

        # Test filtering on catalogue
        res_filter = self.client.get("/api/catalogue/?genre=Science Fiction").json()
        self.assertGreater(len(res_filter["results"]), 0)
        for m in res_filter["results"]:
            movie_obj = Movie.objects.get(id=m["id"])
            genre_names = list(movie_obj.genres.values_list("name", flat=True))
            t_ids = movie_obj.tmdb_genre_ids or []
            self.assertTrue(
                "Science Fiction" in genre_names or 878 in t_ids,
                f"Movie {m['title']} failed genre filter",
            )

    # =========================================================================
    # Criterion 6: Disliked genres/keywords are penalized in recommendations
    # =========================================================================
    def test_criterion_6_disliked_genres_penalized(self):
        """
        Verify that Account A's disliked genre (Horror) is penalized and has 0.0 representation
        in top recommendations.
        """
        res_a = PersonalizedRecommendationEngine.get_recommendations(self.account_a, limit=10)
        neg_rate = compute_negative_response_rate(self.account_a, res_a["movies"])
        self.assertEqual(neg_rate, 0.0, f"Negative response rate was {neg_rate}, expected 0.0")

        # Explicitly ensure neither Conjuring nor Hereditary appears
        rec_ids = {m.id for m in res_a["movies"]}
        self.assertNotIn(self.movie_conjuring.id, rec_ids)
        self.assertNotIn(self.movie_hereditary.id, rec_ids)

    # =========================================================================
    # Criterion 7: Undo reverses preference signals
    # =========================================================================
    def test_criterion_7_undo_reverses_preference_signals(self):
        """
        Verify that logging an undo event reverses preference weights back to baseline.
        """
        # User B likes a Sci-Fi movie (Arrival)
        InteractionLog.objects.create(
            user=self.account_b,
            movie=self.movie_arrival,
            event_type="like",
            weight=1.0,
            processing_status="pending",
        )
        TasteEngineService.recompute_user_taste_profile(self.account_b, force=True)
        profile_after_like = UserTasteProfile.objects.get(user=self.account_b)
        self.assertGreater(
            profile_after_like.learned_weights.get("genres", {}).get("Science Fiction", 0.0),
            0.0,
        )

        # Log Undo event
        InteractionLog.objects.create(
            user=self.account_b,
            movie=self.movie_arrival,
            event_type="undo",
            weight=0.0,
            metadata={"undone_reaction": "like"},
            processing_status="pending",
        )
        TasteEngineService.recompute_user_taste_profile(self.account_b, force=True)
        profile_after_undo = UserTasteProfile.objects.get(user=self.account_b)
        self.assertEqual(
            profile_after_undo.learned_weights.get("genres", {}).get("Science Fiction", 0.0),
            0.0,
        )

    # =========================================================================
    # Criterion 8: Linked guest history correctly flows into canonical user
    # =========================================================================
    def test_criterion_8_linked_guest_history_flows_into_canonical_user(self):
        """
        Verify Account E (canonical with 0 direct interactions) receives personalized
        recommendations driven by linked guest_e's interaction history.
        """
        res_e = PersonalizedRecommendationEngine.get_recommendations(self.account_e, limit=10)
        self.assertEqual(res_e["confidence"], "HIGH")

        alignment = compute_preference_alignment(self.account_e, res_e["movies"])
        self.assertGreaterEqual(alignment, 0.70)

        # Top movie should match guest's Sci-Fi/Mystery preference
        top_genres = [g.name for g in res_e["movies"][0].genres.all()]
        self.assertTrue("Science Fiction" in top_genres or "Mystery" in top_genres or "Fantasy" in top_genres)

    # =========================================================================
    # Criterion 9: Strict account isolation
    # =========================================================================
    def test_criterion_9_strict_account_isolation(self):
        """
        Verify that heavy interactions on Account A do not alter recommendations
        or scores for Account B or Account C.
        """
        recs_b_before = PersonalizedRecommendationEngine.get_recommendations(self.account_b, limit=10)
        recs_c_before = PersonalizedRecommendationEngine.get_recommendations(self.account_c, limit=10)

        ids_b_before = [m.id for m in recs_b_before["movies"]]
        ids_c_before = [m.id for m in recs_c_before["movies"]]

        # Inject new interactions for Account A
        self._record_interactions(
            user=self.account_a,
            likes=[self.movie_heat, self.movie_goodfellas],
            superlikes=[self.movie_heat],
        )
        TasteEngineService.recompute_user_taste_profile(self.account_a, force=True)

        # Re-fetch B and C recommendations
        recs_b_after = PersonalizedRecommendationEngine.get_recommendations(self.account_b, limit=10)
        recs_c_after = PersonalizedRecommendationEngine.get_recommendations(self.account_c, limit=10)

        ids_b_after = [m.id for m in recs_b_after["movies"]]
        ids_c_after = [m.id for m in recs_c_after["movies"]]

        self.assertEqual(ids_b_before, ids_b_after, "Account B recommendations mutated after Account A updates")
        self.assertEqual(ids_c_before, ids_c_after, "Account C recommendations mutated after Account A updates")

    # =========================================================================
    # Criterion 10: Cold-start account returns honest COLD_START label & fallback
    # =========================================================================
    def test_criterion_10_cold_start_account_returns_honest_cold_start(self):
        """
        Verify Account D (0 interactions) receives honest 'COLD_START' confidence
        and the fallback editorial explanation without fabricated reasons.
        """
        res_d = PersonalizedRecommendationEngine.get_recommendations(self.account_d, limit=10)
        self.assertEqual(res_d["confidence"], "COLD_START")

        for movie in res_d["movies"]:
            explanation = movie.explanation
            self.assertEqual(explanation["confidence"], "COLD_START")
            self.assertEqual(
                explanation["reason"],
                "Editorial Selection: Highly rated in the Flick collection",
            )
            self.assertEqual(explanation["matched_signals"], [])

        # Verify via Curator's Selection endpoint
        self.client.force_authenticate(user=self.account_d)
        res_endpoint = self.client.get("/api/curators-selection/").json()
        self.assertEqual(res_endpoint["confidence"], "COLD_START")
        for m in res_endpoint["movies"]:
            self.assertEqual(m["explanation"]["confidence"], "COLD_START")

    # =========================================================================
    # Criterion 11: Repeat exposure handles fatigue according to policy
    # =========================================================================
    def test_criterion_11_repeat_exposure_handles_fatigue(self):
        """
        Verify that movies repeatedly exposed to a user incur fatigue penalty
        and are penalized in scoring compared to fresh candidates.
        """
        # Baseline score calculation for Blade Runner under Account A
        recs_before = PersonalizedRecommendationEngine.get_recommendations(
            self.account_a, limit=10, apply_diversity=False
        )
        blade_runner_before = next(
            m for m in recs_before["movies"] if m.id == self.movie_blade_runner.id
        )

        # Mock user exposure record with high exposure count
        mock_exp = type(
            "MockExposure",
            (),
            {
                "movie": self.movie_blade_runner,
                "movie_id": self.movie_blade_runner.id,
                "exposed_count": 10,
                "last_exposed_at": timezone.now(),
            },
        )()

        with unittest.mock.patch.object(
            PersonalizedRecommendationEngine,
            "get_user_exposures",
            return_value={self.movie_blade_runner.id: mock_exp},
        ):
            recs_after = PersonalizedRecommendationEngine.get_recommendations(
                self.account_a, limit=10, apply_diversity=False
            )
            blade_runner_after = next(
                m for m in recs_after["movies"] if m.id == self.movie_blade_runner.id
            )

            # Score after fatigue penalty must be lower than score before
            self.assertLess(
                blade_runner_after.score,
                blade_runner_before.score,
                "Fatigue penalty was not applied to frequently exposed movie",
            )

    # =========================================================================
    # Criterion 12: Deterministic scoring for identical inputs
    # =========================================================================
    def test_criterion_12_deterministic_scoring_for_identical_inputs(self):
        """
        Verify that calling get_recommendations multiple times with identical user state
        yields bit-for-bit identical movie sequences and numerical scores.
        """
        run_1 = PersonalizedRecommendationEngine.get_recommendations(self.account_a, limit=10)
        run_2 = PersonalizedRecommendationEngine.get_recommendations(self.account_a, limit=10)

        ids_1 = [m.id for m in run_1["movies"]]
        ids_2 = [m.id for m in run_2["movies"]]
        self.assertEqual(ids_1, ids_2)

        scores_1 = [m.score for m in run_1["movies"]]
        scores_2 = [m.score for m in run_2["movies"]]
        self.assertEqual(scores_1, scores_2)

        reasons_1 = [m.explanation["reason"] for m in run_1["movies"]]
        reasons_2 = [m.explanation["reason"] for m in run_2["movies"]]
        self.assertEqual(reasons_1, reasons_2)
