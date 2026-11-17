import uuid
from django.test import TestCase, Client
from rest_framework.authtoken.models import Token
from core.models import User, Session, Movie, Swipe, Match, SessionStats, CollaborativeAgreement
from core.services.deck_state import DeckAdvancementService, ConflictingResponseError


class SuperLikeReactionMatrixIntegrationTests(TestCase):
    """
    Exhaustive integration tests for the 9-cell Reaction Matrix across both:
    1. The REST API: POST /api/swipes/
    2. The Deck State Machine: DeckAdvancementService.record_swipe_response
    """

    def setUp(self):
        self.host = User.objects.create_user(username="matrix_host", password="password123")
        self.guest = User.objects.create_user(username="matrix_guest", password="password123")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.client = Client()

    def _create_session_and_movie(self, code_prefix="MAT"):
        movie = Movie.objects.create(
            tmdb_id=int(uuid.uuid4().int % 1000000),
            title=f"Film {uuid.uuid4().hex[:6]}",
            rating=8.0,
            vote_count=100
        )
        session = Session.objects.create(
            code=uuid.uuid4().hex[:6].upper(),
            host=self.host,
            guest=self.guest,
        )
        SessionStats.objects.create(session=session)
        return session, movie

    # -------------------------------------------------------------
    # REST API: POST /api/swipes/ Reaction Matrix Tests (9 cases)
    # -------------------------------------------------------------

    def test_api_matrix_1_like_like_ordinary_match(self):
        """Matrix 1: Host Like + Guest Like = Ordinary match (attribution=none)."""
        session, movie = self._create_session_and_movie()

        # Host swipes Like -> Pending
        res_h = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_h.status_code, 201)
        self.assertFalse(res_h.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

        # Guest swipes Like -> Ordinary Match formed
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        data = res_g.json()
        self.assertTrue(data["match"])
        self.assertEqual(data["superlike_attribution"], "none")
        self.assertEqual(data["match_type"], "ordinary")
        self.assertTrue(Match.objects.filter(session=session, movie=movie).exists())

    def test_api_matrix_2_like_superlike_guest_attribution(self):
        """Matrix 2: Host Like + Guest Super-Like = Match with guest Super-Like attribution."""
        session, movie = self._create_session_and_movie()

        # Host Like
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )

        # Guest Super-Like
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        data = res_g.json()
        self.assertTrue(data["match"])
        self.assertEqual(data["superlike_attribution"], "guest")
        self.assertEqual(data["match_type"], "superlike")

        match = Match.objects.get(session=session, movie=movie)
        self.assertEqual(match.superlike_attribution, "guest")
        self.assertEqual(match.match_type, "superlike")

    def test_api_matrix_3_superlike_like_host_attribution(self):
        """Matrix 3: Host Super-Like + Guest Like = Match with host Super-Like attribution."""
        session, movie = self._create_session_and_movie()

        # Host Super-Like -> Must remain pending!
        res_h = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_h.status_code, 201)
        self.assertFalse(res_h.json()["match"], "Single Super-Like must remain pending")
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

        # Guest Like -> Match formed with host attribution
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        data = res_g.json()
        self.assertTrue(data["match"])
        self.assertEqual(data["superlike_attribution"], "host")
        self.assertEqual(data["match_type"], "superlike")

        match = Match.objects.get(session=session, movie=movie)
        self.assertEqual(match.superlike_attribution, "host")
        self.assertEqual(match.match_type, "superlike")

    def test_api_matrix_4_superlike_superlike_mutual(self):
        """Matrix 4: Host Super-Like + Guest Super-Like = Mutual Super-Like."""
        session, movie = self._create_session_and_movie()

        # Host Super-Like -> Pending
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )

        # Guest Super-Like -> Mutual match
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        data = res_g.json()
        self.assertTrue(data["match"])
        self.assertEqual(data["superlike_attribution"], "mutual")
        self.assertEqual(data["match_type"], "mutual_superlike")

        match = Match.objects.get(session=session, movie=movie)
        self.assertEqual(match.superlike_attribution, "mutual")
        self.assertEqual(match.match_type, "mutual_superlike")

    def test_api_matrix_5_like_dislike_no_match(self):
        """Matrix 5: Host Like + Guest Dislike = No match."""
        session, movie = self._create_session_and_movie()
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        self.assertFalse(res_g.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

    def test_api_matrix_6_dislike_like_no_match(self):
        """Matrix 6: Host Dislike + Guest Like = No match."""
        session, movie = self._create_session_and_movie()
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        self.assertFalse(res_g.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

    def test_api_matrix_7_superlike_dislike_no_match(self):
        """Matrix 7: Host Super-Like + Guest Dislike = No match (dislike vetoes Super-Like)."""
        session, movie = self._create_session_and_movie()
        res_h = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertFalse(res_h.json()["match"])

        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        self.assertFalse(res_g.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

    def test_api_matrix_8_dislike_superlike_no_match(self):
        """Matrix 8: Host Dislike + Guest Super-Like = No match (prior dislike vetoes Super-Like)."""
        session, movie = self._create_session_and_movie()
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        self.assertFalse(res_g.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

    def test_api_matrix_9_dislike_dislike_no_match(self):
        """Matrix 9: Host Dislike + Guest Dislike = No match."""
        session, movie = self._create_session_and_movie()
        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        res_g = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g.status_code, 201)
        self.assertFalse(res_g.json()["match"])
        self.assertFalse(Match.objects.filter(session=session, movie=movie).exists())

    # -------------------------------------------------------------
    # DeckAdvancementService Reaction Matrix Tests (9 cases)
    # -------------------------------------------------------------

    def _setup_deck_session(self):
        movie = Movie.objects.create(
            tmdb_id=int(uuid.uuid4().int % 1000000),
            title=f"Deck Film {uuid.uuid4().hex[:6]}",
            rating=8.0,
            vote_count=100
        )
        session = Session.objects.create(
            code=uuid.uuid4().hex[:6].upper(),
            host=self.host,
            guest=self.guest,
        )
        SessionStats.objects.create(session=session)
        agreement = CollaborativeAgreement.objects.create(
            session=session,
            deck_manifest=[{"movie_id": movie.id, "slot_type": "consensus", "turn": 0}],
            host_card_index=0,
            guest_card_index=0,
            resolved_card_index=0,
        )
        return session, movie, agreement

    def test_deck_matrix_1_like_like_ordinary(self):
        session, movie, _ = self._setup_deck_session()
        r1 = DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "like")
        self.assertFalse(r1["jointly_resolved"])
        self.assertFalse(r1["match_formed"])

        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "like")
        self.assertTrue(r2["jointly_resolved"])
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["superlike_attribution"], "none")
        self.assertEqual(r2["match_type"], "ordinary")
        self.assertTrue(Match.objects.filter(session=session, movie_id=movie.id).exists())

    def test_deck_matrix_2_like_superlike_guest(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "like")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "superlike")
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["superlike_attribution"], "guest")
        self.assertEqual(r2["match_type"], "superlike")

    def test_deck_matrix_3_superlike_like_host(self):
        session, movie, _ = self._setup_deck_session()
        r1 = DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "superlike")
        self.assertFalse(r1["jointly_resolved"])
        self.assertFalse(r1["match_formed"])

        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "like")
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["superlike_attribution"], "host")
        self.assertEqual(r2["match_type"], "superlike")

    def test_deck_matrix_4_superlike_superlike_mutual(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "superlike")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "superlike")
        self.assertTrue(r2["match_formed"])
        self.assertEqual(r2["superlike_attribution"], "mutual")
        self.assertEqual(r2["match_type"], "mutual_superlike")

    def test_deck_matrix_5_like_dislike_no_match(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "like")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "dislike")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"])
        self.assertFalse(Match.objects.filter(session=session, movie_id=movie.id).exists())

    def test_deck_matrix_6_dislike_like_no_match(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "dislike")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "like")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"])
        self.assertFalse(Match.objects.filter(session=session, movie_id=movie.id).exists())

    def test_deck_matrix_7_superlike_dislike_no_match(self):
        session, movie, _ = self._setup_deck_session()
        r1 = DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "superlike")
        self.assertFalse(r1["match_formed"])
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "dislike")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"], "Superlike must NOT override partner dislike")
        self.assertFalse(Match.objects.filter(session=session, movie_id=movie.id).exists())

    def test_deck_matrix_8_dislike_superlike_no_match(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "dislike")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "superlike")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"], "Partner dislike must veto Super-Like")
        self.assertFalse(Match.objects.filter(session=session, movie_id=movie.id).exists())

    def test_deck_matrix_9_dislike_dislike_no_match(self):
        session, movie, _ = self._setup_deck_session()
        DeckAdvancementService.record_swipe_response(session.id, self.host, 0, movie.id, "dislike")
        r2 = DeckAdvancementService.record_swipe_response(session.id, self.guest, 0, movie.id, "dislike")
        self.assertTrue(r2["jointly_resolved"])
        self.assertFalse(r2["match_formed"])
        self.assertFalse(Match.objects.filter(session=session, movie_id=movie.id).exists())


class SuperLikePersistenceAndAttributionTests(TestCase):
    """
    Tests persistence, refresh survival, and attribution immutability.
    """

    def setUp(self):
        self.host = User.objects.create_user(username="attr_host", password="password123")
        self.guest = User.objects.create_user(username="attr_guest", password="password123")
        self.host_token = Token.objects.create(user=self.host)
        self.guest_token = Token.objects.create(user=self.guest)
        self.client = Client()

    def test_attribution_survives_refresh_in_match_list_api(self):
        """Host and Guest Super-Like attributions survive page refresh in GET /api/matches/."""
        session = Session.objects.create(code=uuid.uuid4().hex[:6].upper(), host=self.host, guest=self.guest)
        SessionStats.objects.create(session=session)
        
        m_host_sl = Movie.objects.create(tmdb_id=101, title="Host Superliked Film")
        m_guest_sl = Movie.objects.create(tmdb_id=102, title="Guest Superliked Film")
        m_mutual_sl = Movie.objects.create(tmdb_id=103, title="Mutual Superliked Film")
        m_ord = Movie.objects.create(tmdb_id=104, title="Ordinary Film")

        # 1. Host SL + Guest Like
        Swipe.objects.create(session=session, user=self.host, movie=m_host_sl, reaction=Swipe.SUPERLIKE)
        Swipe.objects.create(session=session, user=self.guest, movie=m_host_sl, reaction=Swipe.LIKE)
        Match.objects.create(session=session, movie=m_host_sl)

        # 2. Host Like + Guest SL
        Swipe.objects.create(session=session, user=self.host, movie=m_guest_sl, reaction=Swipe.LIKE)
        Swipe.objects.create(session=session, user=self.guest, movie=m_guest_sl, reaction=Swipe.SUPERLIKE)
        Match.objects.create(session=session, movie=m_guest_sl)

        # 3. Host SL + Guest SL
        Swipe.objects.create(session=session, user=self.host, movie=m_mutual_sl, reaction=Swipe.SUPERLIKE)
        Swipe.objects.create(session=session, user=self.guest, movie=m_mutual_sl, reaction=Swipe.SUPERLIKE)
        Match.objects.create(session=session, movie=m_mutual_sl)

        # 4. Host Like + Guest Like
        Swipe.objects.create(session=session, user=self.host, movie=m_ord, reaction=Swipe.LIKE)
        Swipe.objects.create(session=session, user=self.guest, movie=m_ord, reaction=Swipe.LIKE)
        Match.objects.create(session=session, movie=m_ord)

        # Fetch match list as Host
        res = self.client.get(f"/api/matches/?session_id={session.id}", HTTP_AUTHORIZATION=f"Token {self.host_token.key}")
        self.assertEqual(res.status_code, 200)
        matches = {m["movie_id"]: m for m in res.json()["matches"]}

        self.assertEqual(matches[m_host_sl.id]["superlike_attribution"], "host")
        self.assertEqual(matches[m_host_sl.id]["match_type"], "superlike")

        self.assertEqual(matches[m_guest_sl.id]["superlike_attribution"], "guest")
        self.assertEqual(matches[m_guest_sl.id]["match_type"], "superlike")

        self.assertEqual(matches[m_mutual_sl.id]["superlike_attribution"], "mutual")
        self.assertEqual(matches[m_mutual_sl.id]["match_type"], "mutual_superlike")

        self.assertEqual(matches[m_ord.id]["superlike_attribution"], "none")
        self.assertEqual(matches[m_ord.id]["match_type"], "ordinary")

    def test_conflicting_retries_rejected_and_do_not_corrupt_attribution(self):
        """A user cannot overwrite their reaction or corrupt match attribution via conflicting retries."""
        session = Session.objects.create(code=uuid.uuid4().hex[:6].upper(), host=self.host, guest=self.guest)
        SessionStats.objects.create(session=session)
        movie = Movie.objects.create(tmdb_id=201, title="Corrupt Prevention Film")

        # Host submits Super-Like
        r1 = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(r1.status_code, 201)

        # Host attempts conflicting swipe (change to dislike) -> 409 Conflict
        r2 = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.DISLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 409)

        # Persisted reaction remains Super-Like
        host_swipe = Swipe.objects.get(session=session, user=self.host, movie=movie)
        self.assertEqual(host_swipe.reaction, Swipe.SUPERLIKE)

        # Guest completes match with Like
        r3 = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(r3.status_code, 201)
        self.assertTrue(r3.json()["match"])

        # Match attribution is correctly Host
        match = Match.objects.get(session=session, movie=movie)
        self.assertEqual(match.superlike_attribution, "host")

    def test_duplicate_requests_create_match_exactly_once(self):
        """Duplicate concurrent or serial swipe submissions cannot create duplicate matches."""
        session = Session.objects.create(code=uuid.uuid4().hex[:6].upper(), host=self.host, guest=self.guest)
        SessionStats.objects.create(session=session)
        movie = Movie.objects.create(tmdb_id=301, title="Deduplication Film")

        self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.SUPERLIKE},
            HTTP_AUTHORIZATION=f"Token {self.host_token.key}",
            content_type="application/json",
        )

        # Guest submits like
        res_g1 = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g1.status_code, 201)
        self.assertTrue(res_g1.json()["match"])

        # Guest retries same like -> 200 OK idempotent success
        res_g2 = self.client.post(
            "/api/swipes/",
            {"session": session.id, "movie": movie.id, "reaction": Swipe.LIKE},
            HTTP_AUTHORIZATION=f"Token {self.guest_token.key}",
            content_type="application/json",
        )
        self.assertEqual(res_g2.status_code, 200)
        self.assertTrue(res_g2.json()["success"])
        self.assertTrue(res_g2.json()["idempotent"])
        self.assertTrue(res_g2.json()["match"])

        # Exact match count in DB must be exactly 1
        self.assertEqual(Match.objects.filter(session=session, movie=movie).count(), 1)
