import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# -------------------------------------------------
# Genre Model
# -------------------------------------------------

class Genre(models.Model):
    """
    TMDB genre reference.
    Stored once and reused across movies and sessions.
    """
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100)

    industry = models.CharField(
            max_length=50,
            choices=[
                ("bollywood", "Bollywood"),
                ("hollywood", "Hollywood"),
                ("mixed", "Mixed"),
            ],
            null=True,
            blank=True
        )

    def __str__(self):
        return self.name


# -------------------------------------------------
# Session Model
# -------------------------------------------------

class Session(models.Model):
    """
    A private swipe session between two users.
    Genre is fixed at creation time.
    """
    code = models.CharField(max_length=6, unique=True)

    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="hosted_sessions"
    )

    guest = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="joined_sessions"
    )

    # SINGLE genre per session (kept for backward compat, use genres M2M for new logic)
    genre = models.ForeignKey(
        Genre,
        on_delete=models.PROTECT,
        related_name="sessions",
        null=True,
        blank=True,
    )

    # MULTIPLE genres (new — supports multi-genre sessions)
    genres = models.ManyToManyField(
        Genre,
        blank=True,
        related_name="multi_sessions",
        help_text="All genres selected for this session (multi-select)"
    )

    industry = models.CharField(
        max_length=50,
        choices=[
            ("bollywood", "Bollywood"),
            ("hollywood", "Hollywood"),
            ("mixed", "Mixed"),
        ],
        null=True,  # ← CRITICAL: Must be nullable for existing sessions
        blank=True
    )

    selected_languages = models.JSONField(
        null=True,
        blank=True,
        help_text="User-selected languages like ['hi', 'gu', 'mr']"
    )
    
    host_preferences = models.JSONField(
        null=True,
        blank=True,
        help_text="Host's mood/vibe preferences"
    )
    
    guest_preferences = models.JSONField(
        null=True,
        blank=True,
        help_text="Guest's mood/vibe preferences"
    )
    
    preferences_set = models.BooleanField(
        default=False,
        help_text="Whether both users completed the questionnaire"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    def is_active(self):
        return self.ended_at is None

    def __str__(self):
        return f"Session {self.code} ({self.genre.name if self.genre else 'No genre'})"


# -------------------------------------------------
# Movie Model
# -------------------------------------------------

class MovieQuerySet(models.QuerySet):
    RESTRICTED_FIELDS = frozenset({'display_ready', 'recommendable', 'provenance'})

    def update(self, **kwargs):
        restricted = self.RESTRICTED_FIELDS.intersection(kwargs.keys())
        if restricted:
            raise RuntimeError(
                f"Direct bulk update of restricted field(s) {restricted} is prohibited on MovieQuerySet. "
                f"Use eligibility recalculation service or _trusted_update_eligibility."
            )
        return super().update(**kwargs)

    def _trusted_update_eligibility(self, movie_pk: int, display_ready: bool, recommendable: bool) -> int:
        return models.QuerySet.update(
            self.filter(pk=movie_pk),
            display_ready=display_ready,
            recommendable=recommendable,
        )


class MovieManager(models.Manager.from_queryset(MovieQuerySet)):
    def _trusted_update_eligibility(self, movie_pk: int, display_ready: bool, recommendable: bool) -> int:
        return self.get_queryset()._trusted_update_eligibility(
            movie_pk=movie_pk,
            display_ready=display_ready,
            recommendable=recommendable,
        )


class Movie(models.Model):
    """
    Movie synced from TMDB.
    """
    PROVENANCE_CHOICES = [
        ('needs_review', 'Needs Review'),
        ('tmdb_catalogue', 'TMDB Catalogue'),
        ('synthetic_fixture', 'Synthetic Fixture'),
        ('manual_curated', 'Manual Curated'),
    ]

    objects = MovieManager()

    tmdb_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    overview = models.TextField(blank=True)
    poster_path = models.CharField(max_length=255, blank=True, null=True)
    backdrop_path = models.CharField(max_length=255, blank=True, null=True)
    release_date = models.DateField(null=True, blank=True)

    # Raw TMDB genre IDs (used during sync)
    tmdb_genre_ids = models.JSONField(default=list)

    # Relational genres (used by app logic)
    genres = models.ManyToManyField(Genre, blank=True)

    rating = models.FloatField(null=True, blank=True)
    vote_count = models.IntegerField(null=True, blank=True)  # ← vote count from TMDB
    trailer_key = models.CharField(max_length=50, null=True, blank=True)  # ← YouTube key from TMDB

    created_at = models.DateTimeField(auto_now_add=True)
    tags = models.ManyToManyField(
        "MovieTag",
        blank=True,
        related_name="movies"
    )
    keywords = models.ManyToManyField(
        "MovieKeyword",
        blank=True,
        related_name="movies",
        help_text="TMDB human-curated keywords — backbone of smart scoring"
    )
    original_language = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        db_index=True
    )

    # Intelligence & catalogue qualification fields
    display_ready = models.BooleanField(default=False, db_index=True)
    recommendable = models.BooleanField(default=False, db_index=True)
    provenance = models.CharField(
        max_length=32,
        choices=PROVENANCE_CHOICES,
        default='needs_review',
        db_index=True,
    )
    field_provenance = models.JSONField(default=dict, blank=True)
    credits_summary = models.JSONField(default=dict, blank=True)
    last_enriched_at = models.DateTimeField(null=True, blank=True)
    metadata_content_hash = models.CharField(max_length=64, blank=True, default='')

    def recalculate_eligibility(self, commit: bool = False):
        from core.services.catalogue_eligibility import recalculate_movie_eligibility
        return recalculate_movie_eligibility(self, commit=commit)

    @property
    def runtime(self):
        if hasattr(self, "credits_summary") and isinstance(self.credits_summary, dict):
            return self.credits_summary.get("runtime")
        return None

    def __str__(self):
        return self.title


# -------------------------------------------------
# Swipe Model
# -------------------------------------------------

class Swipe(models.Model):
    """
    A user's swipe (like/dislike) on a movie within a session.
    """
    LIKE = "like"
    DISLIKE = "dislike"
    SUPERLIKE = "superlike"

    REACTION_CHOICES = [
        (LIKE, "Like"),
        (DISLIKE, "Dislike"),
        (SUPERLIKE, "Super Like"),
    ]

    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    reaction = models.CharField(max_length=10, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "session", "movie")

    def __str__(self):
        return f"{self.user.username} {self.reaction} {self.movie.title}"


# -------------------------------------------------
# Match Model
# -------------------------------------------------

class Match(models.Model):
    """
    Created when both users like the same movie in a session.
    """
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "movie"],
                name="unique_match_per_movie_per_session"
            )
        ]

    def __str__(self):
        return f"Match: {self.movie.title} ({self.session.code})"

    @property
    def superlike_attribution(self) -> str:
        """
        Derives Super-Like attribution directly from persisted Swipe records.
        Returns:
            'mutual': Both host and guest submitted Super-Like
            'host': Only host submitted Super-Like
            'guest': Only guest submitted Super-Like
            'none': Ordinary match (neither participant Super-Liked)
        """
        swipes = getattr(self, "_cached_swipes", None)
        if swipes is None:
            swipes = list(Swipe.objects.filter(session_id=self.session_id, movie_id=self.movie_id))

        host_id = self.session.host_id
        guest_id = self.session.guest_id

        host_rx = None
        guest_rx = None
        for s in swipes:
            if s.user_id == host_id:
                host_rx = s.reaction
            elif s.user_id == guest_id:
                guest_rx = s.reaction

        if host_rx == Swipe.SUPERLIKE and guest_rx == Swipe.SUPERLIKE:
            return "mutual"
        elif host_rx == Swipe.SUPERLIKE:
            return "host"
        elif guest_rx == Swipe.SUPERLIKE:
            return "guest"
        return "none"

    @property
    def match_type(self) -> str:
        """
        Returns:
            'mutual_superlike': Both participants superliked
            'superlike': Exactly one participant superliked
            'ordinary': Both participants liked
        """
        attr = self.superlike_attribution
        if attr == "mutual":
            return "mutual_superlike"
        elif attr in ("host", "guest"):
            return "superlike"
        return "ordinary"
    

    # Data Capture #

class MovieExposure(models.Model):
    movie = models.OneToOneField(Movie, on_delete=models.CASCADE)
    exposed_count = models.IntegerField(default=0)
    last_exposed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.movie.title} — {self.exposed_count}"


class SessionStats(models.Model):
    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name="stats"
    )
    total_swipes = models.PositiveIntegerField(default=0)
    total_matches = models.PositiveIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    ended_by = models.CharField(
        max_length=20,
        choices=[
            ("user", "User"),
            ("no_more_movies", "No More Movies"),
            ("disconnect", "Disconnect"),
        ],
        null=True,
        blank=True,
    )
        # --- Phase 2D ---
    quality_score = models.PositiveIntegerField(null=True, blank=True)
    highlights = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Stats for session {self.session.id}"

class MovieTag(models.Model):
    """
    Lightweight sub-genre / vibe tags (AI-generated or manual).
    Examples: 'unhinged', 'comfort watch', 'slow burn'
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class MovieKeyword(models.Model):
    """
    TMDB keyword synced per movie — human-curated descriptors.
    Examples: 'psychological thriller', 'obsession', 'ballet', 'superhero', 'family'
    These are the backbone of smart recommendation scoring — far more precise
    than scanning raw overview text.
    """
    tmdb_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=100, db_index=True)

    def __str__(self):
        return self.name

class UserTasteSignal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tag = models.ForeignKey("MovieTag", on_delete=models.CASCADE)

    like_count = models.PositiveIntegerField(default=0)
    dislike_count = models.PositiveIntegerField(default=0)

    last_interacted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "tag")

class SessionChemistry(models.Model):
    """
    Captures what works for a specific pair of users.
    """
    user_a = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chemistry_as_a"
    )
    user_b = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chemistry_as_b"
    )

    tag = models.CharField(max_length=64)

    match_count = models.PositiveIntegerField(default=0)
    swipe_count = models.PositiveIntegerField(default=0)

    last_matched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user_a", "user_b", "tag")

    def __str__(self):
        return f"{self.user_a} + {self.user_b} → {self.tag}"

class MovieTagRelation(models.Model):
    """
    Weighted relationship between vibe tags.
    Example: 'chaotic' -> 'dark humor'
    """
    from_tag = models.ForeignKey(
        "MovieTag",
        on_delete=models.CASCADE,
        related_name="outgoing_relations"
    )
    to_tag = models.ForeignKey(
        "MovieTag",
        on_delete=models.CASCADE,
        related_name="incoming_relations"
    )

    weight = models.FloatField(default=1.0)

    class Meta:
        unique_together = ("from_tag", "to_tag")

    def __str__(self):
        return f"{self.from_tag} → {self.to_tag} ({self.weight})"


class WatchlistItem(models.Model):
    """
    A movie saved to a user's watchlist from a match popup.
    Both users in a session can independently save matches.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="watchlist")
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="watchlisted_by")
    session = models.ForeignKey(
        Session, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Session in which this match was made"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    watched = models.BooleanField(default=False)
    watched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "movie")

    def __str__(self):
        return f"{self.user.username} → {self.movie.title}"


class UserProfile(models.Model):
    """
    Extended profile for each user.
    Created automatically on first access.
    Stores avatar, social login ID, display name, and any future profile fields.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )
    display_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="User's chosen display name for social and session interactions"
    )
    avatar_url = models.TextField(blank=True, default="")
    social_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        db_index=True,
        help_text="OAuth subject ID from Google/Apple"
    )
    social_provider = models.CharField(
        max_length=20,
        blank=True,
        default="",
        choices=[("google", "Google"), ("apple", "Apple"), ("", "Email")]
    )
    email_verified = models.BooleanField(
        default=False,
        help_text="True once the user has clicked the verification link"
    )
    fcm_token = models.TextField(
        blank=True,
        default="",
        help_text="Firebase Cloud Messaging token for push notifications"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile({self.user.username})"

    @property
    def effective_display_name(self):
        if self.display_name and self.display_name.strip():
            return self.display_name.strip()
        return self.user.first_name or self.user.username


class GuestProfile(models.Model):
    """
    Companion profile for persistent anonymous-first guest accounts.
    Decoupled from Session; persistent across discovery, journal, and multiple screening decks.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="guest_profile",
        help_text="Canonical Django User backing this persistent guest"
    )
    # Security & Recovery: Dual-Token Architecture
    recovery_lookup_digest = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default="",
        help_text="Keyed HMAC-SHA256 digest of recovery code for O(1) B-tree lookup"
    )
    recovery_verification_hash = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Salted PBKDF2/Argon2 verification hash of recovery code"
    )
    recovery_key_version = models.PositiveSmallIntegerField(
        default=1,
        help_text="HMAC secret key version for zero-downtime key rotation"
    )
    # Recovery Handoff State: Dual-validity window for retry-safe recovery handoff
    previous_recovery_lookup_digest = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default="",
        help_text="Keyed HMAC-SHA256 digest of previous recovery code during handoff window"
    )
    previous_recovery_verification_hash = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Salted PBKDF2/Argon2 verification hash of previous recovery code during handoff window"
    )
    previous_recovery_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when previous recovery code expires during handoff"
    )
    # Lifecycle & Status
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_claimed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="False while guest; True once converted to permanent registered account"
    )
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_claimed", "last_active_at"]),
            models.Index(fields=["recovery_lookup_digest", "is_claimed"]),
            models.Index(fields=["previous_recovery_lookup_digest", "previous_recovery_expires_at"]),
        ]

    def __str__(self):
        status = "Permanent" if self.is_claimed else "Guest"
        return f"GuestProfile({self.user.username}, {status})"

    @property
    def guest_uuid(self):
        """UUID alias for compatibility."""
        return self.id

    @property
    def is_converted(self):
        """Conversion status alias for compatibility."""
        return self.is_claimed

    @is_converted.setter
    def is_converted(self, value):
        self.is_claimed = bool(value)

    @property
    def converted_at(self):
        """Conversion timestamp alias for compatibility."""
        return self.claimed_at

    @converted_at.setter
    def converted_at(self, value):
        self.claimed_at = value


class StreamingProvider(models.Model):
    name = models.CharField(max_length=100)
    logo_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    country_code = models.CharField(max_length=10, default='IN')
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name

class MovieStreamingAvailability(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    provider = models.ForeignKey(StreamingProvider, on_delete=models.CASCADE)
    url = models.URLField(blank=True)
    monetization_type = models.CharField(max_length=20, choices=[
        ('flatrate', 'Subscription'),
        ('buy', 'Buy'),
        ('rent', 'Rent'),
    ])
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['movie', 'provider']


# -------------------------------------------------
# Unified Movie Intelligence Models (Phase 1)
# -------------------------------------------------

class UserTasteProfile(models.Model):
    """
    Tier A: Persistent Individual Taste Profile.
    1-to-1 with User. Initialized during first screening setup
    or voluntary profile configuration.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="taste_profile"
    )
    # Core aesthetic dimensions
    emotional_tonality = models.JSONField(default=list, blank=True, help_text="List of preferred mood tokens (max 3)")
    narrative_structures = models.JSONField(default=list, blank=True, help_text="List of preferred narrative forms (max 2)")
    thematic_interests = models.JSONField(default=list, blank=True, help_text="List of preferred thematic tokens (max 3)")
    viewing_rhythm = models.CharField(max_length=30, default="balanced", help_text="Preferred pacing/intensity")
    preferred_languages = models.JSONField(default=list, blank=True, help_text="List of ISO 639-1 language codes")

    # Persistent boundary defaults
    default_min_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Default minimum rating threshold (0.00 to 10.00)"
    )
    default_max_runtime = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Default maximum runtime in minutes"
    )
    default_eras = models.JSONField(default=list, blank=True, help_text="Default era envelope choices")
    hard_exclusions = models.JSONField(default=dict, blank=True, help_text="Explicit vetoes (e.g. excluded_genre_ids)")

    # Learned feedback weights
    learned_weights = models.JSONField(default=dict, blank=True, help_text="Accumulated taste weights from interaction logs")
    version = models.PositiveIntegerField(default=1, help_text="Profile mutation version counter")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"TasteProfile({self.user.username}, v{self.version})"


class SessionOccasionState(models.Model):
    """
    Tier B: Ephemeral Screening Preferences.
    1-to-1 with Session. Captures temporary requirements without
    mutating UserTasteProfile unless explicit consent is given.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name="occasion_state"
    )
    host_occasion = models.JSONField(default=dict, blank=True, help_text="Host's occasion questionnaire responses")
    guest_occasion = models.JSONField(default=dict, blank=True, help_text="Guest's occasion questionnaire responses")
    host_submitted_at = models.DateTimeField(null=True, blank=True)
    guest_submitted_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"OccasionState(Session {self.session.code})"


class ConstraintExpansionProposal(models.Model):
    """
    Formal proposal for relaxing hard constraints when candidate pool
    is exhausted (<16 candidates). Requires explicit dual approval.
    """
    STATUS_PENDING = "pending"
    STATUS_APPROVED_QUEUED = "approved_queued"
    STATUS_REPLENISHMENT_RUNNING = "replenishment_running"
    STATUS_REPLENISHMENT_COMPLETED = "replenishment_completed"
    STATUS_REPLENISHMENT_FAILED = "replenishment_failed"
    STATUS_REPLENISHMENT_INSUFFICIENT = "replenishment_insufficient"
    STATUS_DECLINED = "declined"
    STATUS_EXPIRED = "expired"
    STATUS_SUPERSEDED = "superseded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Decisions"),
        (STATUS_APPROVED_QUEUED, "Approved — Queued for Replenishment"),
        (STATUS_REPLENISHMENT_RUNNING, "Replenishment In Progress"),
        (STATUS_REPLENISHMENT_COMPLETED, "Replenishment Completed"),
        (STATUS_REPLENISHMENT_FAILED, "Replenishment Failed"),
        (STATUS_REPLENISHMENT_INSUFFICIENT, "Replenishment Insufficient (<16 Candidates)"),
        (STATUS_DECLINED, "Declined by Participant"),
        (STATUS_EXPIRED, "Proposal Expired"),
        (STATUS_SUPERSEDED, "Superseded by New Proposal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="expansion_proposals"
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    initiated_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_proposals"
    )
    original_constraints = models.JSONField(default=dict, help_text="Snapshot of constraints prior to proposal")
    proposed_constraints = models.JSONField(default=dict, help_text="Snapshot of proposed relaxed constraints")
    host_decision = models.JSONField(null=True, blank=True, help_text="{'decision': 'approve'|'decline', 'decided_at': ...}")
    guest_decision = models.JSONField(null=True, blank=True, help_text="{'decision': 'approve'|'decline', 'decided_at': ...}")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Proposal {self.id} ({self.session.code}, {self.status})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_mutually_approved(self):
        h = self.host_decision and self.host_decision.get("decision") == "approve"
        g = self.guest_decision and self.guest_decision.get("decision") == "approve"
        return bool(h and g)


class CollaborativeAgreement(models.Model):
    """
    Tier C: Synthesizes both participants' inputs into an execution contract.
    Maintains shared constraints, deterministic deck manifest, and independent
    participant delivery and resolution cursors.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session,
        on_delete=models.CASCADE,
        related_name="collaborative_agreement"
    )
    # Shared hard constraints
    shared_min_rating = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Arithmetic average of explicit participant thresholds"
    )
    shared_max_runtime = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Lower of explicit participant maximum runtime limits"
    )
    shared_eras = models.JSONField(
        default=list,
        blank=True,
        help_text="Intersection of explicit participant era envelopes"
    )
    shared_languages = models.JSONField(
        default=list,
        blank=True,
        help_text="Reconciled shared language filters"
    )
    mutual_hard_exclusions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Union of explicit participant vetoes (e.g. excluded_genre_ids)"
    )

    # Soft preferences (retained separately for balanced-turn scoring)
    host_soft_preferences = models.JSONField(default=dict, blank=True)
    guest_soft_preferences = models.JSONField(default=dict, blank=True)

    # Deterministic deck manifest: list of dicts [{'movie_id': ..., 'slot_type': ..., 'turn': ...}]
    deck_manifest = models.JSONField(default=list, blank=True)

    # Decoupled Delivery and Resolution Cursors
    host_card_index = models.PositiveIntegerField(default=0, help_text="Index of next card delivered to Host")
    guest_card_index = models.PositiveIntegerField(default=0, help_text="Index of next card delivered to Guest")
    resolved_card_index = models.PositiveIntegerField(default=0, help_text="Highest index where both users have swiped")

    # Active proposal pointer
    active_proposal = models.ForeignKey(
        ConstraintExpansionProposal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_agreements"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"CollaborativeAgreement(Session {self.session.code})"


class InteractionLog(models.Model):
    """
    Append-only audit log of raw interaction events for feedback scoring,
    learning loops, and half-life decay.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interaction_logs"
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interaction_logs"
    )
    movie = models.ForeignKey(
        Movie,
        on_delete=models.CASCADE,
        related_name="interaction_logs"
    )
    event_type = models.CharField(
        max_length=32,
        db_index=True,
        choices=[
            ("swipe_like", "Swipe Like"),
            ("swipe_dislike", "Swipe Dislike"),
            ("superlike", "Super Like"),
            ("match", "Match Formed"),
            ("watchlist_add", "Watchlist Addition"),
            ("modal_open", "Detail Modal Opened"),
            ("undo", "Swipe Undo"),
        ]
    )
    weight = models.FloatField(default=0.0, help_text="Assigned signal weight at event time")
    metadata = models.JSONField(default=dict, blank=True, help_text="Contextual details (turn, slot_type, client_ts)")
    processing_status = models.CharField(
        max_length=16,
        choices=[
            ("pending", "Pending Recomputation"),
            ("processed", "Processed into Taste Profile"),
        ],
        default="pending",
        db_index=True,
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    source_swipe_id = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        help_text="Primary key of originating core_swipe record for 1-to-1 traceability",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "movie", "event_type"]),
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "processing_status"]),
        ]

    def __str__(self):
        return f"Interaction({self.user.username}, {self.event_type}, movie={self.movie_id})"


class UserIdentityLink(models.Model):
    """
    Links canonical authenticated users to historical guest actor identities
    for attribution, taste signal recomputation, and session audit history.
    """
    class LinkType(models.TextChoices):
        GUEST_CONVERSION = "guest_conversion", "Guest Conversion"
        SESSION_CLAIM = "session_claim", "Session Claim"

    id = models.BigAutoField(primary_key=True)
    canonical_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="linked_guest_identities",
    )
    linked_actor_id = models.IntegerField(
        unique=True,
        db_index=True,
        help_text="Historical auth_user.id of the guest actor",
    )
    link_type = models.CharField(
        max_length=32,
        choices=LinkType.choices,
    )
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "User Identity Link"
        verbose_name_plural = "User Identity Links"

    def __str__(self):
        return f"UserIdentityLink(canonical={self.canonical_user_id}, linked_actor={self.linked_actor_id}, type={self.link_type})"


LinkType = UserIdentityLink.LinkType


class ProposalOutboxMessage(models.Model):
    """
    Transactional outbox for reliable, asynchronous replenishment dispatch.
    Inserted in the same database transaction as the proposal approval, then
    processed asynchronously by a durable background worker.
    """
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending Dispatch"),
        (STATUS_PROCESSING, "Processing Ingestion"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed (Exhausted Retries)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    proposal = models.ForeignKey(
        ConstraintExpansionProposal,
        on_delete=models.CASCADE,
        related_name="outbox_messages"
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="proposal_outbox_messages"
    )
    topic = models.CharField(max_length=64, default="proposal.replenishment")
    payload = models.JSONField(default=dict, help_text="Message payload for background worker")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self):
        return f"OutboxMessage({self.id}, proposal={self.proposal_id}, status={self.status})"


class CatalogueJob(models.Model):
    """
    Durable, PostgreSQL-backed asynchronous job queue for catalogue intelligence,
    TMDB metadata synchronization, and taste profile recomputations.
    
    Guarantees:
    - At-least-once execution with idempotent handlers and generation fencing tokens.
    - Transactional side-effect protection under row-level locks.
    - Active-job uniqueness and deduplication via conditional constraints.
    - Safe concurrency claiming using SELECT FOR UPDATE SKIP LOCKED.
    - Quota-partitioned fair scheduling to prevent priority starvation.
    """
    class JobType(models.TextChoices):
        ENRICH_MOVIE = "enrich_movie", "Enrich Movie Metadata"
        FETCH_KEYWORDS = "fetch_keywords", "Fetch TMDB Keywords"
        FETCH_CREDITS = "fetch_credits", "Fetch TMDB Credits"
        SYNC_CHANGES_FEED = "sync_changes_feed", "Sync TMDB Changes Feed"
        FULL_RECONCILIATION = "full_reconciliation", "Catalogue Reconciliation Sweep"
        RECOMPUTE_TASTE = "recompute_taste", "Recompute User Taste Profile"
        RECONCILE_INTERACTIONS = "reconcile_interactions", "Reconcile Historical Events"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        RETRY_WAIT = "retry_wait", "Awaiting Retry"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED_PERMANENT = "failed_permanent", "Permanently Failed"
        NEEDS_REVIEW = "needs_review", "Requires Manual Review"

    id = models.BigAutoField(primary_key=True)
    job_type = models.CharField(max_length=64, choices=JobType.choices, db_index=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    priority = models.IntegerField(default=100, db_index=True)  # Lower number = higher priority (50 High, 100 Normal, 200 Low)

    # Entity targeting: local database primary key vs. external provider ID
    entity_type = models.CharField(max_length=64, db_index=True)
    entity_id = models.CharField(max_length=128, db_index=True, help_text="Local database primary key (e.g. Movie.id or User.id)")
    external_id = models.CharField(max_length=128, null=True, blank=True, db_index=True, help_text="External identifier (e.g. TMDB ID)")
    payload = models.JSONField(default=dict, blank=True)
    needs_subsequent_pass = models.BooleanField(default=False, help_text="Dirty flag set when enqueue is called while job is in-flight")

    # Worker lease, fencing and ownership
    claimed_by_worker_id = models.CharField(max_length=128, null=True, blank=True)
    claim_generation = models.PositiveIntegerField(default=0, help_text="Monotonically incremented fencing token on each claim")
    lease_token = models.UUIDField(null=True, blank=True, help_text="Ephemeral unique token for current lease ownership")
    claimed_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)

    # Retry scheduling and diagnostics
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    scheduled_for = models.DateTimeField(default=timezone.now, db_index=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "scheduled_for"]
        indexes = [
            models.Index(fields=["status", "scheduled_for", "priority"], name="idx_catjob_poll"),
            models.Index(fields=["entity_type", "entity_id", "status"], name="idx_catjob_entity_status"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["job_type", "entity_type", "entity_id"],
                condition=models.Q(status__in=["pending", "in_progress", "retry_wait"]),
                name="uidx_active_catalogue_job"
            )
        ]

    def __str__(self):
        return f"CatalogueJob({self.id}, {self.job_type}, {self.entity_type}={self.entity_id}, status={self.status}, gen={self.claim_generation})"


class TmdbChangesCheckpoint(models.Model):
    """
    Durable cursor tracking TMDB Changes Feed polling.
    Guarantees that change ingestion can be resumed across restarts,
    crashes, or rate limit backoffs without skipping or duplicating events.
    """
    feed_name = models.CharField(max_length=64, unique=True, default="movie_changes")
    last_polled_at = models.DateTimeField(null=True, blank=True)
    window_start_date = models.DateField(null=True, blank=True)
    window_end_date = models.DateField(null=True, blank=True)
    current_page = models.PositiveIntegerField(default=1)
    total_pages = models.PositiveIntegerField(default=1)
    changes_detected_count = models.PositiveIntegerField(default=0)
    changes_enqueued_count = models.PositiveIntegerField(default=0)
    is_in_progress = models.BooleanField(default=False)
    lock_token = models.UUIDField(null=True, blank=True, help_text="Unique UUID identifying current poller ownership")
    lock_generation = models.PositiveIntegerField(default=0, help_text="Monotonically incremented fencing generation token")
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TMDB Changes Checkpoint"
        verbose_name_plural = "TMDB Changes Checkpoints"

    def __str__(self):
        return f"TmdbChangesCheckpoint({self.feed_name}, page {self.current_page}/{self.total_pages}, window={self.window_start_date}..{self.window_end_date})"


class StalenessSweepCheckpoint(models.Model):
    """
    Durable cursor tracking 90-day catalogue staleness sweeps.
    Ensures that long-running or interrupted sweeps resume cleanly from
    the last scanned primary key without reloading the full table into memory.
    """
    sweep_name = models.CharField(max_length=64, unique=True, default="90_day_movie_staleness")
    last_sweep_completed_at = models.DateTimeField(null=True, blank=True)
    last_scanned_id = models.PositiveIntegerField(default=0)
    is_in_progress = models.BooleanField(default=False)
    records_scanned = models.PositiveIntegerField(default=0)
    records_enqueued = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Staleness Sweep Checkpoint"
        verbose_name_plural = "Staleness Sweep Checkpoints"

    def __str__(self):
        return f"StalenessSweepCheckpoint({self.sweep_name}, last_id={self.last_scanned_id}, in_progress={self.is_in_progress})"


# -------------------------------------------------
# Wire Catalogue Eligibility Signals
# -------------------------------------------------
try:
    from core.services.catalogue_eligibility import register_eligibility_signals
    register_eligibility_signals()
except Exception:
    pass


