from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Movie
from .models import Swipe
from .models import Session
from .models import Genre
from .models import ConstraintExpansionProposal, ProposalOutboxMessage
from .services.affinity import calculate_session_statistics


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model = Genre
        fields = ['id','name']

class MovieSerializer(serializers.ModelSerializer):
    poster_url = serializers.SerializerMethodField()
    backdrop_url = serializers.SerializerMethodField()
    release_year = serializers.SerializerMethodField()
    trailer_url = serializers.SerializerMethodField()
    genres = serializers.SerializerMethodField()
    runtime = serializers.SerializerMethodField()

    class Meta:
        model = Movie
        fields = [
            "id",
            "tmdb_id",
            "title",
            "overview",
            "release_date",
            "release_year",
            "rating",
            "vote_count",        # direct model field — no method needed
            "original_language", # needed for Discover page language display
            "backdrop_url",
            "poster_url",
            "trailer_url",
            "genres",
            "runtime",
        ]

    def get_genres(self, obj):
        genres = [g.name for g in obj.genres.all() if g.name]
        if not genres and getattr(obj, "tmdb_genre_ids", None):
            from .services.recommendation_engine import TMDB_GENRE_MAP
            genres = [TMDB_GENRE_MAP[gid] for gid in obj.tmdb_genre_ids if gid in TMDB_GENRE_MAP]
        return genres

    def get_runtime(self, obj):
        val = getattr(obj, "runtime", None)
        if isinstance(val, (int, float)) and not isinstance(val, bool) and int(val) > 0:
            return int(val)
        return None
    
    def get_backdrop_url(self, obj):
        if obj.backdrop_path:
            return f"https://image.tmdb.org/t/p/w780{obj.backdrop_path}"
        return None

    def get_poster_url(self, obj):
        # FIXED: was incorrectly using obj.backdrop_path
        if obj.poster_path:
            return f"https://image.tmdb.org/t/p/w780{obj.poster_path}"
        return None

    def get_release_year(self, obj):
        if obj.release_date:
            return obj.release_date.year
        return None

    def get_trailer_url(self, obj):
        if obj.trailer_key:
            return f"https://www.youtube.com/watch?v={obj.trailer_key}"
        return None


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email'),
            password=validated_data['password']
        )
        return user
    
class SwipeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Swipe
        fields = ['id', 'session', 'movie', 'reaction']

    def validate_reaction(self, value):
        if value not in ['like', 'dislike', 'superlike']:
            raise serializers.ValidationError("Reaction must be 'like', 'dislike', or 'superlike'")
        return value

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ['id', 'code', 'host', 'guest', 'is_active']
        read_only_fields = ['code', 'host', 'guest']

class SessionDetailSerializer(serializers.ModelSerializer):
    genre = serializers.SerializerMethodField()
    host_joined = serializers.SerializerMethodField()
    guest_joined = serializers.SerializerMethodField()
    host_display_name = serializers.SerializerMethodField()
    guest_display_name = serializers.SerializerMethodField()
    ended = serializers.SerializerMethodField()
    quality_score = serializers.SerializerMethodField()
    highlights = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    user_preferences_set = serializers.SerializerMethodField()
    host_preferences_set = serializers.SerializerMethodField()
    guest_preferences_set = serializers.SerializerMethodField()
    user_preferences = serializers.SerializerMethodField()
    both_preferences_set = serializers.SerializerMethodField()
    preferences_set = serializers.SerializerMethodField()
    is_legacy = serializers.SerializerMethodField()
    reviewed_count = serializers.SerializerMethodField()
    matched_count = serializers.SerializerMethodField()
    affinity_percent = serializers.SerializerMethodField()

    def get_user_role(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        if obj.host_id == request.user.id:
            return "host"
        if obj.guest_id == request.user.id:
            return "guest"
        return None

    def get_user_preferences_set(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return False
        if obj.host_id == request.user.id:
            return bool(obj.host_preferences)
        if obj.guest_id == request.user.id:
            return bool(obj.guest_preferences)
        return False

    def get_host_preferences_set(self, obj):
        return bool(obj.host_preferences)

    def get_guest_preferences_set(self, obj):
        return bool(obj.guest_preferences)

    def get_user_preferences(self, obj):
        request = self.context.get("request")
        if not request or not getattr(request, "user", None) or not request.user.is_authenticated:
            return None
        if obj.host_id == request.user.id:
            return obj.host_preferences
        if obj.guest_id == request.user.id:
            return obj.guest_preferences
        return None

    def get_preferences_set(self, obj):
        return bool(obj.preferences_set or (obj.host_preferences and obj.guest_preferences))

    def get_both_preferences_set(self, obj):
        return self.get_preferences_set(obj)

    def get_is_legacy(self, obj):
        return getattr(obj, "is_legacy", False)

    def get_quality_score(self, obj):
        if hasattr(obj, "stats"):
            return obj.stats.quality_score
        return None

    def get_highlights(self, obj):
        if hasattr(obj, "stats"):
            return obj.stats.highlights
        return []

    def get_host_display_name(self, obj):
        if not obj.host:
            return None
        profile = getattr(obj.host, "profile", None)
        if profile and profile.display_name:
            return profile.display_name.strip()
        return obj.host.first_name.strip() or obj.host.username

    def get_guest_display_name(self, obj):
        if not obj.guest:
            return None
        profile = getattr(obj.guest, "profile", None)
        if profile and profile.display_name:
            return profile.display_name.strip()
        return obj.guest.first_name.strip() or obj.guest.username

    class Meta:
        model = Session
        fields = [
            "id",
            "code",
            "genre",
            "host_joined",
            "guest_joined",
            "host_display_name",
            "guest_display_name",
            "ended",
            "preferences_set",
            "user_role",
            "user_preferences_set",
            "host_preferences_set",
            "guest_preferences_set",
            "user_preferences",
            "both_preferences_set",
            "is_legacy",
            "quality_score",
            "highlights",
            "reviewed_count",
            "matched_count",
            "affinity_percent",
        ]

    def get_genre(self, obj):
        if obj.genre:
            return {
                "id": obj.genre.id,
                "name": obj.genre.name
            }
        first_genre = obj.genres.first()
        if first_genre:
            return {
                "id": first_genre.id,
                "name": first_genre.name
            }
        return None

    def get_host_joined(self, obj):
        return obj.host is not None

    def get_guest_joined(self, obj):
        return obj.guest is not None

    def get_ended(self, obj):
        return obj.ended_at is not None

    def _get_stats(self, obj):
        if not hasattr(obj, "_cached_session_stats"):
            request = self.context.get("request")
            user = getattr(request, "user", None) if request else None
            obj._cached_session_stats = calculate_session_statistics(obj, user=user)
        return obj._cached_session_stats

    def get_reviewed_count(self, obj):
        return self._get_stats(obj)["reviewed_count"]

    def get_matched_count(self, obj):
        return self._get_stats(obj)["matched_count"]

    def get_affinity_percent(self, obj):
        return self._get_stats(obj)["affinity_percent"]


class ConstraintExpansionProposalSerializer(serializers.ModelSerializer):
    is_expired = serializers.BooleanField(read_only=True)
    is_mutually_approved = serializers.BooleanField(read_only=True)
    initiated_by_username = serializers.CharField(source="initiated_by_user.username", read_only=True)

    class Meta:
        model = ConstraintExpansionProposal
        fields = [
            "id",
            "session_id",
            "status",
            "initiated_by_user_id",
            "initiated_by_username",
            "original_constraints",
            "proposed_constraints",
            "host_decision",
            "guest_decision",
            "created_at",
            "expires_at",
            "completed_at",
            "error_message",
            "is_expired",
            "is_mutually_approved",
        ]
        read_only_fields = fields


class ProposalOutboxMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalOutboxMessage
        fields = [
            "id",
            "proposal_id",
            "session_id",
            "topic",
            "status",
            "attempts",
            "max_attempts",
            "scheduled_at",
            "processed_at",
            "error_message",
            "created_at",
        ]
        read_only_fields = fields
