import re
import random
import string
import secrets
import logging
import time
import uuid
from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone
from django.db import IntegrityError, OperationalError, models, transaction
from django.db.models import F, Q
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.cache import cache
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.template.loader import render_to_string
from django.contrib.auth import authenticate
from django.conf import settings

logger = logging.getLogger(__name__)
matching_logger = logging.getLogger("flick.matching")
from core.logging import SecretRedactionFilter


from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .consumers import broadcast_credential_revocation

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework import status


from .models import (
    Movie, Swipe, Match, Session, Genre, MovieExposure,
    SessionStats, UserTasteSignal, SessionChemistry,
    MovieTagRelation, MovieTag, WatchlistItem, UserProfile,
    StreamingProvider, MovieStreamingAvailability, GuestProfile
)
from .serializers import MovieSerializer, RegisterSerializer, SwipeSerializer, SessionDetailSerializer
from .pagination import StandardResultsSetPagination, SwipeHistoryPagination
from .throttling import (
    AuthRateThrottle, PasswordResetRateThrottle,
    GuestProvisionThrottle, GuestRecoverThrottle
)
from .guest_security import (
    generate_recovery_code,
    canonicalize_recovery_code,
    compute_recovery_lookup_digest,
    hash_recovery_code,
    verify_recovery_code,
    dummy_verify_recovery_code,
)
from .services.tmdb import (
    get_movie_watch_providers,
    TMDBServiceError,
    TMDBTimeoutError,
    TMDBAPIError,
)


# -------------------------------------------------------------------
# Recommendation shaping constants (Phase 2)
# -------------------------------------------------------------------

RECENT_EXPOSURE_COOLDOWN_MINUTES = 30
MAX_GLOBAL_EXPOSURE = 100
CANDIDATE_POOL_SIZE = 120
FINAL_DECK_SIZE = 40
MIN_DECK_SIZE = 16
MAX_DECK_SIZE = 50
INDIAN_LANGUAGES = ["hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa"]
User = get_user_model()

# -------------------------------------------------------------------
# Utility helpers
# -------------------------------------------------------------------

SESSION_CODE_ALPHABET = string.ascii_uppercase + string.digits
MAX_SESSION_CODE_RETRIES = 5

def generate_session_code(length=6):
    """
    Generate a short, cryptographically secure human-readable session code.
    """
    return ''.join(secrets.choice(SESSION_CODE_ALPHABET) for _ in range(length))

def normalize_pair(user1, user2):
    """
    Ensures user pair ordering is consistent.
    """
    return (user1, user2) if user1.id < user2.id else (user2, user1)

def calculate_preference_score(movie, preferences):
    """
    Calculate how well a movie matches user preferences.
    STRICT filtering with proper era handling.
    """
    score = 0
    overview_lower = movie.overview.lower()
    title_lower = movie.title.lower()
    
    # Mood keywords
    mood_keywords = {
        "happy": ["comedy", "fun", "laugh", "joy", "light", "cheerful", "humorous", "hilarious", "amusing", "witty"],
        "intense": ["thriller", "suspense", "intense", "dark", "serious", "gripping", "tense", "dramatic", "noir"],
        "emotional": ["drama", "emotional", "moving", "heartfelt", "touching", "tear", "powerful", "profound", "poignant"],
        "exciting": ["action", "adventure", "exciting", "fast-paced", "thrilling", "explosive", "dynamic", "spectacular"],
    }
    
    pace_keywords = {
        "fast": ["action", "fast", "intense", "quick", "thrilling", "explosive", "adrenaline", "rush", "rapid"],
        "slow": ["slow", "deliberate", "thoughtful", "contemplative", "meditative", "quiet", "introspective", "patient"],
        "balanced": ["balanced", "mix", "variety", "blend", "diverse", "moderate"],
    }
    
    vibe_keywords = {
        "feel-good": ["uplifting", "inspiring", "heartwarming", "positive", "hopeful", "optimistic", "joyful", "warm"],
        "mind-bending": ["twist", "complex", "mystery", "puzzle", "psychological", "surreal", "enigmatic", "cryptic"],
        "escapist": ["fantasy", "adventure", "magical", "world", "epic", "mythical", "otherworldly", "imaginative"],
        "realistic": ["real", "authentic", "true", "based on", "documentary", "life", "actual", "gritty"],
    }
    
    # Check moods
    for mood in preferences.get("mood", []):
        keywords = mood_keywords.get(mood, [])
        for keyword in keywords:
            if keyword in overview_lower or keyword in title_lower:
                score += 8  # ✅ INCREASED
                break
    
    # Check pace
    for pace in preferences.get("pace", []):
        keywords = pace_keywords.get(pace, [])
        for keyword in keywords:
            if keyword in overview_lower:
                score += 6  # ✅ INCREASED
                break
    
    # Check vibe
    for vibe in preferences.get("vibe", []):
        keywords = vibe_keywords.get(vibe, [])
        for keyword in keywords:
            if keyword in overview_lower:
                score += 6  # ✅ INCREASED
                break
    
    # ✅ FIX: Strict era filtering with proper logic
    era_match = False
    if movie.release_date:
        release_year = movie.release_date.year
        
        for era in preferences.get("era", []):
            era_lower = str(era).lower()
            if era_lower in ("before_1990", "pre_1990") and movie.release_date <= date(1989, 12, 31):
                score += 15
                era_match = True
            elif era_lower == "classic" and release_year < 2000:
                score += 15  # ✅ HUGE bonus for era match
                era_match = True
            elif era_lower == "90s" and 1990 <= release_year <= 1999:
                score += 15
                era_match = True
            elif era_lower == "2000s" and 2000 <= release_year < 2010:
                score += 15
                era_match = True
            elif era_lower == "2010s" and 2010 <= release_year < 2020:
                score += 15
                era_match = True
            elif era_lower == "recent" and release_year >= 2020:
                score += 15
                era_match = True
            elif era_lower == "any":
                score += 5  # Small bonus for flexibility
                era_match = True
    
    # ✅ CRITICAL: Penalize movies that don't match era preference
    if not era_match and preferences.get("era") and "any" not in preferences.get("era", []):
        score -= 20  # Heavy penalty for wrong era
    
    return score

# -------------------------------------------------------------------
# Movie APIs
# -------------------------------------------------------------------

class MovieListView(generics.ListAPIView):
    """
    Public list of movies with standard pagination and optimized genre prefetching.
    """
    queryset = Movie.objects.all().prefetch_related("genres").order_by("-rating", "-id")
    serializer_class = MovieSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [AllowAny]


class MovieDetailView(generics.RetrieveAPIView):
    """
    Retrieve details for a single movie.
    """
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    permission_classes = [AllowAny]


class MovieCreateView(generics.CreateAPIView):
    """
    Create a new movie (admin required).
    """
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]


class MovieUpdateView(generics.UpdateAPIView):
    """
    Update an existing movie (admin required).
    """
    queryset = Movie.objects.all()
    serializer_class = MovieSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]


class MovieDeleteView(generics.DestroyAPIView):
    """
    Delete a movie (admin required).
    """
    queryset = Movie.objects.all()
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]


# -------------------------------------------------------------------
# Authentication APIs
# -------------------------------------------------------------------

class RegisterView(APIView):
    """
    Register a new user account with email and password.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        # Check if data exists
        if not request.data:
            return Response({
                "success": False,
                "error": "No registration data received. Please check your internet connection and try again."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not isinstance(request.data, dict):
            return Response({
                "success": False,
                "error": "Invalid data format received."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract fields
        email = request.data.get('email')
        password = request.data.get('password')
        display_name = request.data.get('display_name')
        
        # Validate required fields
        if email is None:
            return Response({
                "success": False,
                "error": "Email field is missing from request."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if password is None:
            return Response({
                "success": False,
                "error": "Password field is missing from request."
            }, status=status.HTTP_400_BAD_REQUEST)

        if display_name is None:
            return Response({
                "success": False,
                "error": "Display name field is missing from request."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Convert to strings if needed
        if not isinstance(email, str):
            email = str(email)
        
        if not isinstance(password, str):
            password = str(password)

        if not isinstance(display_name, str):
            display_name = str(display_name)
        
        email = email.strip()
        display_name = display_name.strip()

        if not display_name:
            return Response({
                "success": False,
                "error": "Display name cannot be blank."
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(display_name) < 2:
            return Response({
                "success": False,
                "error": "Display name must be at least 2 characters long."
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(display_name) > 50:
            return Response({
                "success": False,
                "error": "Display name cannot exceed 50 characters."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate email format
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            return Response({
                "success": False,
                "error": f"Invalid email format: '{email}'. Please enter a valid email address."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate password
        if len(password) < 6:
            return Response({
                "success": False,
                "error": f"Password must be at least 6 characters long. Yours is {len(password)} characters."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check user existence
        try:
            if User.objects.filter(email=email).exists():
                return Response({
                    "success": False,
                    "error": "An account with this email already exists. Please try logging in instead."
                }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            pass
        
        # Try to create user
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=display_name,
                )
                UserProfile.objects.update_or_create(
                    user=user,
                    defaults={"display_name": display_name, "email_verified": True}
                )
            return Response({
                "success": True,
                "message": "Account created successfully! Welcome to Flick.",
                "user_id": user.id,
                "display_name": display_name,
            }, status=status.HTTP_201_CREATED)
            
        except IntegrityError as e:
            return Response({
                "success": False,
                "error": "An account with this email already exists. Please try logging in."
            }, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            return Response({
                "success": False,
                "error": f"Registration failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(ObtainAuthToken):
    """
    Authenticate a user and return a token.
    Can login with either username or email.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request, *args, **kwargs):
        try:
            # Extract login credentials - accept both username and email
            username_input = request.data.get('username') or request.data.get('email', '')
            password = request.data.get('password', '')
            
            if not username_input or not password:
                return Response({
                    "success": False,
                    "error": "Username/email and password are required."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Use Django's authenticate - our custom backend handles both
            user = authenticate(request, username=username_input, password=password)
            
            if user is not None:
                # Create or get token
                token, created = Token.objects.get_or_create(user=user)
                profile = getattr(user, "profile", None)
                display_name = ""
                if profile and profile.display_name:
                    display_name = profile.display_name.strip()
                if not display_name:
                    display_name = user.first_name.strip() or user.username
                
                return Response({
                    "success": True,
                    "token": token.key,
                    "user_id": user.id,
                    "username": user.username,
                    "display_name": display_name,
                    "email": user.email,
                    "message": "Login successful!"
                })
            else:
                return Response({
                    "success": False,
                    "error": "Invalid credentials. Please check your username/email and password."
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            return Response({
                "success": False,
                "error": f"Login failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuestProvisionView(APIView):
    """
    Initialize an anonymous persistent guest account.
    Creates a User with unusable password, companion GuestProfile, UserProfile, and DRF Token.
    Returns single-exposure Crockford Base32 recovery credential.
    """
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]
    throttle_classes = [GuestProvisionThrottle]

    def post(self, request):
        if request.user and request.user.is_authenticated:
            return Response({
                "success": False,
                "error": "Authenticated users cannot create a new guest account."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Optional display_name provided in request body
        display_name = ""
        if isinstance(request.data, dict):
            raw_name = request.data.get("display_name", "")
            if isinstance(raw_name, str):
                display_name = raw_name.strip()[:50]

        User = get_user_model()
        recovery_code = generate_recovery_code()
        digest = compute_recovery_lookup_digest(recovery_code)
        v_hash = hash_recovery_code(recovery_code)

        try:
            with transaction.atomic():
                username = None
                for _ in range(5):
                    candidate = f"guest_{uuid.uuid4().hex[:12]}"
                    if not User.objects.filter(username=candidate).exists():
                        username = candidate
                        break
                if not username:
                    username = f"guest_{uuid.uuid4().hex}"

                user = User(username=username)
                user.set_unusable_password()
                user.save()

                if not display_name:
                    display_name = f"Cinephile #{user.id}"

                user.first_name = display_name
                user.save(update_fields=["first_name"])

                UserProfile.objects.create(
                    user=user,
                    display_name=display_name
                )

                guest_profile = GuestProfile.objects.create(
                    user=user,
                    recovery_lookup_digest=digest,
                    recovery_verification_hash=v_hash,
                    recovery_key_version=1,
                    recovery_code=recovery_code,
                )

                token = Token.objects.create(user=user)

            return Response({
                "success": True,
                "token": token.key,
                "recovery_code": recovery_code,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "display_name": display_name,
                    "guest_uuid": str(guest_profile.id),
                    "is_guest": True,
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Failed to provision anonymous guest account")
            return Response({
                "success": False,
                "error": "Failed to create guest account. Please try again."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class GuestRecoverView(APIView):
    """
    Recover an anonymous guest account using a Crockford Base32 recovery code.
    Rotates the active DRF auth token and establishes a retry-safe recovery handoff window.
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [GuestRecoverThrottle]

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({
                "success": False,
                "error": "Invalid request format."
            }, status=status.HTTP_400_BAD_REQUEST)

        raw_code = request.data.get("recovery_code")
        if not raw_code or not isinstance(raw_code, str) or not raw_code.strip():
            return Response({
                "success": False,
                "error": "Recovery code is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            canonical_code = canonicalize_recovery_code(raw_code)
        except (ValueError, TypeError):
            dummy_verify_recovery_code()
            return Response({
                "success": False,
                "error": "Invalid recovery code."
            }, status=status.HTTP_400_BAD_REQUEST)

        digest = compute_recovery_lookup_digest(canonical_code)
        now = timezone.now()

        max_retries = 5
        backoff_sec = 0.05

        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Query candidate profile locking row for concurrency safety
                    profile = GuestProfile.objects.select_for_update().select_related("user", "user__profile").filter(
                        Q(recovery_lookup_digest=digest) |
                        Q(previous_recovery_lookup_digest=digest, previous_recovery_expires_at__gt=now)
                    ).first()

                    if not profile:
                        dummy_verify_recovery_code()
                        return Response({
                            "success": False,
                            "error": "Invalid recovery code."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    if profile.is_claimed:
                        return Response({
                            "success": False,
                            "error": "This account has already been registered with email and password. Please sign in with your credentials."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Determine which hash matched
                    if profile.recovery_lookup_digest == digest:
                        target_hash = profile.recovery_verification_hash
                        matched_role = "primary"
                    else:
                        target_hash = profile.previous_recovery_verification_hash
                        matched_role = "previous"

                    if not verify_recovery_code(canonical_code, target_hash):
                        return Response({
                            "success": False,
                            "error": "Invalid recovery code."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Generate replacement recovery credential
                    new_code = generate_recovery_code()
                    new_digest = compute_recovery_lookup_digest(new_code)
                    new_hash = hash_recovery_code(new_code)

                    # Setup or refresh handoff grace period (15 minutes)
                    if matched_role == "primary":
                        profile.previous_recovery_lookup_digest = profile.recovery_lookup_digest
                        profile.previous_recovery_verification_hash = profile.recovery_verification_hash
                        profile.previous_recovery_expires_at = now + timedelta(minutes=15)
                    else:
                        # In previous retry: extend handoff window to allow new recovery receipt
                        profile.previous_recovery_expires_at = now + timedelta(minutes=15)

                    profile.recovery_lookup_digest = new_digest
                    profile.recovery_verification_hash = new_hash
                    profile.recovery_code = new_code
                    profile.last_active_at = now
                    profile.save()

                    # Rotate DRF Token (Strictly delete + create, not get_or_create)
                    Token.objects.filter(user=profile.user).delete()
                    new_token = Token.objects.create(user=profile.user)

                    # Dispatch WebSocket revocation after successful transaction commit
                    user_id = profile.user.id
                    transaction.on_commit(lambda uid=user_id: broadcast_credential_revocation(uid))

                # Successfully completed transaction
                break

            except OperationalError as exc:
                is_lock = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if is_lock and attempt < max_retries - 1:
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                    continue
                logger.exception("Database lock contention exhausted during guest recovery")
                return Response({
                    "success": False,
                    "error": "Database is temporarily busy. Please retry shortly."
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception as e:
                logger.exception("Unexpected error during guest recovery")
                return Response({
                    "success": False,
                    "error": "An error occurred during account recovery. Please try again."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        display_name = ""
        if hasattr(profile.user, "profile") and profile.user.profile.display_name:
            display_name = profile.user.profile.display_name.strip()
        if not display_name:
            display_name = profile.user.first_name or profile.user.username

        return Response({
            "success": True,
            "token": new_token.key,
            "recovery_code": new_code,
            "user": {
                "id": profile.user.id,
                "username": profile.user.username,
                "display_name": display_name,
                "guest_uuid": str(profile.id),
                "is_guest": True,
            },
            "handoff_pending": True
        }, status=status.HTTP_200_OK)



class GuestRecoveryAckView(APIView):
    """
    Acknowledge receipt and safe storage of the replacement recovery credential.
    Instantly retires the previous recovery credential before the 15-minute grace period expires.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        profile = getattr(request.user, "guest_profile", None)
        if not profile:
            return Response({
                "success": False,
                "error": "Guest profile not found."
            }, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            profile = GuestProfile.objects.select_for_update().get(pk=profile.pk)
            profile.previous_recovery_lookup_digest = ""
            profile.previous_recovery_verification_hash = ""
            profile.previous_recovery_expires_at = None
            profile.save(update_fields=[
                "previous_recovery_lookup_digest",
                "previous_recovery_verification_hash",
                "previous_recovery_expires_at"
            ])

        return Response({
            "success": True,
            "message": "Recovery credential handoff acknowledged. Previous credential retired."
        }, status=status.HTTP_200_OK)


class GuestRotateCodeView(APIView):
    """
    Generate and return a new recovery code for the authenticated guest user.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        guest_profile = getattr(request.user, "guest_profile", None)
        if not guest_profile or guest_profile.is_claimed:
            return Response({"success": False, "error": "Only active guest accounts have recovery codes."}, status=status.HTTP_400_BAD_REQUEST)

        new_code = generate_recovery_code()
        guest_profile.recovery_code = new_code
        guest_profile.recovery_lookup_digest = compute_recovery_lookup_digest(new_code)
        guest_profile.recovery_verification_hash = hash_recovery_code(new_code)
        guest_profile.save(update_fields=["recovery_code", "recovery_lookup_digest", "recovery_verification_hash"])

        return Response({
            "success": True,
            "recovery_code": new_code,
            "message": "New recovery code generated successfully."
        }, status=status.HTTP_200_OK)


class GuestConvertView(APIView):
    """
    In-place conversion of an authenticated guest account into a permanent registered account.
    Mutates the existing auth.User row (email, username, password) and marks GuestProfile.is_claimed = True.
    Preserves User.pk and all associated data (sessions, swipes, matches, watchlists, etc.).
    Retires all guest recovery credentials permanently.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({
                "success": False,
                "error": "Invalid request format."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. Authorization: user must have an unconverted GuestProfile
        profile = getattr(request.user, "guest_profile", None)
        if not profile:
            return Response({
                "success": False,
                "error": "Only guest accounts can be converted."
            }, status=status.HTTP_400_BAD_REQUEST)

        if profile.is_claimed:
            return Response({
                "success": False,
                "error": "This guest account has already been converted."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. Extract inputs
        email = request.data.get("email")
        password = request.data.get("password")
        username = request.data.get("username")
        display_name = request.data.get("display_name")

        # 3. Validation: email
        if not email or not isinstance(email, str):
            return Response({
                "success": False,
                "error": "Email is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        email = email.strip().lower()
        if not email or "@" not in email or "." not in email.split("@")[-1]:
            return Response({
                "success": False,
                "error": f"Invalid email format: '{email}'. Please enter a valid email address."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 4. Validation: password
        if not password or not isinstance(password, str):
            return Response({
                "success": False,
                "error": "Password is required."
            }, status=status.HTTP_400_BAD_REQUEST)

        if len(password) < 6:
            return Response({
                "success": False,
                "error": f"Password must be at least 6 characters long. Yours is {len(password)} characters."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 5. Validation: username & display_name
        if username and isinstance(username, str):
            username = username.strip()
        else:
            username = email  # Default username to email per Flick convention

        if not username:
            return Response({
                "success": False,
                "error": "Username cannot be blank."
            }, status=status.HTTP_400_BAD_REQUEST)

        if display_name and isinstance(display_name, str):
            display_name = display_name.strip()[:50]
        else:
            display_name = None

        # 6. Uniqueness pre-checks
        User = get_user_model()
        if User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
            return Response({
                "success": False,
                "error": "An account with this email already exists."
            }, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exclude(pk=request.user.pk).exists():
            return Response({
                "success": False,
                "error": "An account with this username already exists."
            }, status=status.HTTP_400_BAD_REQUEST)

        # 7. Atomic in-place conversion with retry for SQLite contention
        max_retries = 5
        backoff_sec = 0.05

        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Lock rows
                    user = User.objects.select_for_update().get(pk=request.user.pk)
                    profile = GuestProfile.objects.select_for_update().get(user=user)

                    if profile.is_claimed:
                        return Response({
                            "success": False,
                            "error": "This guest account has already been converted."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Re-verify uniqueness within transaction
                    if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                        return Response({
                            "success": False,
                            "error": "An account with this email already exists."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    if User.objects.filter(username=username).exclude(pk=user.pk).exists():
                        return Response({
                            "success": False,
                            "error": "An account with this username already exists."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # In-place user update
                    user.email = email
                    user.username = username
                    user.set_password(password)

                    if display_name:
                        user.first_name = display_name

                    user.save()

                    # Update UserProfile if exists or display_name provided
                    user_profile, _ = UserProfile.objects.get_or_create(user=user)
                    user_profile.email_verified = True
                    if display_name:
                        user_profile.display_name = display_name
                        user_profile.save(update_fields=["display_name", "email_verified"])
                    else:
                        user_profile.save(update_fields=["email_verified"])

                    # Retire all guest recovery credentials permanently
                    profile.is_claimed = True
                    profile.claimed_at = timezone.now()
                    profile.recovery_lookup_digest = ""
                    profile.recovery_verification_hash = ""
                    profile.previous_recovery_lookup_digest = ""
                    profile.previous_recovery_verification_hash = ""
                    profile.previous_recovery_expires_at = None
                    profile.save()

                    # Preserve existing token or create if missing
                    token, _ = Token.objects.get_or_create(user=user)

                break

            except OperationalError as exc:
                is_lock = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                if is_lock and attempt < max_retries - 1:
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                    continue
                logger.exception("Database lock contention exhausted during guest conversion")
                return Response({
                    "success": False,
                    "error": "Database is temporarily busy. Please retry shortly."
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception as e:
                logger.exception("Unexpected error during guest conversion")
                return Response({
                    "success": False,
                    "error": "An error occurred during account conversion. Please try again."
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        effective_name = user_profile.effective_display_name if hasattr(user_profile, "effective_display_name") else (user.first_name or user.username)

        return Response({
            "success": True,
            "message": "Account successfully converted to permanent registered account.",
            "token": token.key,
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": effective_name,
                "guest_uuid": str(profile.id),
                "is_guest": False,
            }
        }, status=status.HTTP_200_OK)




# -------------------------------------------------------------------
# Session APIs
# -------------------------------------------------------------------

class SessionCreateView(APIView):
    """
    Create a new collaborative session with collision-resistant session codes.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        for attempt in range(MAX_SESSION_CODE_RETRIES):
            code = generate_session_code()
            try:
                with transaction.atomic():
                    session = Session.objects.create(
                        host=request.user,
                        code=code
                    )
                return Response(
                    {
                        "success": True,
                        "id": session.id,
                        "session_id": session.id,
                        "code": session.code,
                    },
                    status=status.HTTP_201_CREATED
                )
            except IntegrityError:
                logger.warning(
                    "Session code collision on '%s' (attempt %d/%d). Retrying...",
                    code, attempt + 1, MAX_SESSION_CODE_RETRIES
                )
                continue

        logger.error(
            "Exhausted %d retries generating a unique session code for user_id=%s",
            MAX_SESSION_CODE_RETRIES, request.user.id
        )
        return Response(
            {
                "success": False,
                "error": "Failed to generate a unique session code. Please try again."
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    
class SessionSetGenreView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        genre_id = request.data.get("genre_id")
        industry = request.data.get("industry")
        languages = request.data.get("languages")  # ✅ ADD THIS

        if not session_id or not genre_id or not industry:
            return Response(
                {"success": False, "error": "session_id, genre_id, and industry required"},
                status=400
            )

        if industry not in ["bollywood", "hollywood", "mixed"]:  # ✅ ADD mixed
            return Response(
                {"success": False, "error": "Invalid industry"},
                status=400
            )

        # ✅ Validate languages
        if not languages or not isinstance(languages, list):
            return Response(
                {"success": False, "error": "languages must be a non-empty list"},
                status=400
            )

        try:
            session = Session.objects.get(id=session_id)
            genre = Genre.objects.get(id=genre_id)
        except (Session.DoesNotExist, Genre.DoesNotExist):
            return Response(
                {"success": False, "error": "Invalid session or genre"},
                status=404
            )

        if not session.host or request.user.id != session.host.id:
            return Response(
                {"success": False, "error": "Only host can set genre"},
                status=403
            )

        session.genre = genre
        session.industry = industry
        session.selected_languages = languages

        update_fields = ["genre", "industry", "selected_languages"]
        streaming_provider_ids = request.data.get("streaming_provider_ids", [])
        if streaming_provider_ids and isinstance(streaming_provider_ids, list):
            prefs = dict(session.host_preferences or {})
            prefs["streaming_provider_ids"] = [int(p) for p in streaming_provider_ids if str(p).isdigit()]
            session.host_preferences = prefs
            update_fields.append("host_preferences")

        session.save(update_fields=update_fields)

        # Also populate ManyToMany genres if passed
        genre_ids = request.data.get("genre_ids", [])
        if genre_ids and isinstance(genre_ids, list):
            session.genres.set(Genre.objects.filter(id__in=genre_ids))
        else:
            session.genres.set([genre])

        return Response(
            {
                "success": True,
                "session_id": session.id,
                "genre": {"id": genre.id, "name": genre.name},
                "genres": [{"id": g.id, "name": g.name} for g in session.genres.all()],
                "industry": industry,
                "languages": languages,
            },
            status=200
        )
    
class SessionSetPreferencesView(APIView):
    """
    Store user's mood/vibe preferences for the session.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        preferences = request.data.get("preferences")

        if not session_id or not preferences:
            return Response(
                {"success": False, "error": "session_id and preferences required"},
                status=400
            )

        with transaction.atomic():
            try:
                session = Session.objects.select_for_update().get(id=session_id)
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Session not found"},
                    status=404
                )

            if request.user not in [session.host, session.guest]:
                return Response(
                    {"success": False, "error": "Not part of this session"},
                    status=403
                )

            user_role = "host" if request.user == session.host else "guest"

            # Store preferences (merging with any session creation parameters like streaming_provider_ids)
            if user_role == "host":
                host_prefs = dict(session.host_preferences or {})
                host_prefs.update(preferences)
                session.host_preferences = host_prefs
            else:
                guest_prefs = dict(session.guest_preferences or {})
                guest_prefs.update(preferences)
                session.guest_preferences = guest_prefs

            # Check if both submitted
            both_ready = False
            overlap_score = 0

            if session.host_preferences and session.guest_preferences:
                session.preferences_set = True
                both_ready = True

                from core.services.affinity import calculate_questionnaire_similarity
                overlap_score = calculate_questionnaire_similarity(
                    session.host_preferences,
                    session.guest_preferences,
                )

            session.save(update_fields=["host_preferences", "guest_preferences", "preferences_set"])

            # Sync Tier B SessionOccasionState
            try:
                from core.models import SessionOccasionState
                occasion_state, _ = SessionOccasionState.objects.get_or_create(session=session)
                if user_role == "host":
                    occasion_state.host_occasion = preferences
                    occasion_state.host_submitted_at = timezone.now()
                else:
                    occasion_state.guest_occasion = preferences
                    occasion_state.guest_submitted_at = timezone.now()
                occasion_state.save()
            except Exception as e:
                logger.warning(f"Failed to persist SessionOccasionState for session {session.id}: {e}")

            # Sync Tier C CollaborativeAgreement
            try:
                from core.models import CollaborativeAgreement
                from core.services.deck_state import DeckAdvancementService
                agreement, _ = CollaborativeAgreement.objects.get_or_create(session=session)
                DeckAdvancementService.sync_agreement_from_session(session, agreement)
            except Exception as e:
                logger.warning(f"Failed to sync CollaborativeAgreement for session {session.id}: {e}")

            # Supersede any pending constraint expansion proposals for this session
            try:
                from core.models import ConstraintExpansionProposal
                ConstraintExpansionProposal.objects.filter(
                    session=session,
                    status=ConstraintExpansionProposal.STATUS_PENDING,
                ).update(status=ConstraintExpansionProposal.STATUS_SUPERSEDED)
            except Exception as e:
                logger.warning(f"Failed to supersede pending proposals on preference update: {e}")

            def notify_preferences():
                try:
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            f"session_{session.id}",
                            {
                                "type": "preferences_event",
                                "session_id": session.id,
                                "user_id": request.user.id,
                                "role": user_role,
                                "host_preferences_set": bool(session.host_preferences),
                                "guest_preferences_set": bool(session.guest_preferences),
                                "preferences_set": bool(session.preferences_set or (session.host_preferences and session.guest_preferences)),
                                "both_ready": both_ready,
                                "overlap_score": overlap_score,
                                "questionnaire_similarity": overlap_score,
                            }
                        )
                except Exception:
                    pass

            transaction.on_commit(notify_preferences)

        return Response(
            {
                "success": True,
                "both_ready": both_ready,
                "overlap_score": overlap_score,
                "questionnaire_similarity": overlap_score,
                "user_role": user_role,
                "user_preferences_set": True,
                "host_preferences_set": bool(session.host_preferences),
                "guest_preferences_set": bool(session.guest_preferences),
                "preferences_set": bool(session.preferences_set),
            },
            status=200
        )

class SessionJoinView(APIView):
    """
    Join an existing session using a session code.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw_code = request.data.get("code")

        if not raw_code:
            return Response(
                {"success": False, "error": "Session code required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        code = str(raw_code).strip().upper()

        with transaction.atomic():
            try:
                session = Session.objects.select_for_update().get(code__iexact=code)
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Invalid session code"},
                    status=status.HTTP_404_NOT_FOUND
                )

            if session.host == request.user:
                return Response(
                    {"success": False, "error": "Host cannot join own session"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if session.guest:
                if session.guest == request.user:
                    return Response(
                        {
                            "success": True,
                            "message": "Already joined session",
                            "session_id": session.id,
                            "code": session.code,
                            "host_joined": True,
                            "guest_joined": True,
                            "preferences_set": bool(session.preferences_set or (session.host_preferences and session.guest_preferences)),
                            "user_role": "guest",
                            "user_preferences_set": bool(session.guest_preferences),
                            "host_preferences_set": bool(session.host_preferences),
                            "guest_preferences_set": bool(session.guest_preferences),
                        },
                        status=status.HTTP_200_OK
                    )
                return Response(
                    {"success": False, "error": "Session already full"},
                    status=status.HTTP_409_CONFLICT
                )

            session.guest = request.user
            session.save(update_fields=["guest"])

            def notify_partner():
                try:
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        profile = getattr(request.user, "profile", None)
                        disp_name = profile.display_name if profile and profile.display_name else (request.user.first_name or request.user.username)
                        async_to_sync(channel_layer.group_send)(
                            f"session_{session.id}",
                            {
                                "type": "partner_joined_event",
                                "session_id": session.id,
                                "username": request.user.username,
                                "display_name": disp_name,
                            }
                        )
                except Exception:
                    pass

            transaction.on_commit(notify_partner)

        return Response(
            {
                "success": True,
                "message": "Joined session",
                "session_id": session.id,
                "code": session.code,
                "host_joined": True,
                "guest_joined": True,
                "preferences_set": bool(session.preferences_set or (session.host_preferences and session.guest_preferences)),
                "user_role": "guest",
                "user_preferences_set": bool(session.guest_preferences),
                "host_preferences_set": bool(session.host_preferences),
                "guest_preferences_set": bool(session.guest_preferences),
            },
            status=status.HTTP_200_OK
        )


def serialize_session_matches(session):
    """
    Serializes all matches for a given session into the standard Match format.
    """
    matches = (
        Match.objects.filter(session=session)
        .select_related("movie", "session")
        .prefetch_related("movie__genres")
        .order_by("-created_at")
    )
    match_list = list(matches)
    session_ids = {m.session_id for m in match_list}
    movie_ids = {m.movie_id for m in match_list}
    swipes_by_pair = defaultdict(list)
    if session_ids and movie_ids:
        for sw in Swipe.objects.filter(session_id__in=session_ids, movie_id__in=movie_ids):
            swipes_by_pair[(sw.session_id, sw.movie_id)].append(sw)

    for m in match_list:
        m._cached_swipes = swipes_by_pair.get((m.session_id, m.movie_id), [])

    data = []
    for match in match_list:
        movie = match.movie
        poster_url = None
        if movie.poster_path:
            poster_url = f"https://image.tmdb.org/t/p/w780{movie.poster_path}"

        data.append({
            "session_id": match.session.id,
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "movie_title": movie.title,
            "matched_at": match.created_at,
            "poster_url": poster_url,
            "rating": movie.rating,
            "vote_count": movie.vote_count,
            "release_year": movie.release_date.year if movie.release_date else None,
            "overview": movie.overview or "",
            "genres": [g.name for g in movie.genres.all()],
            "original_language": movie.original_language or "",
            "superlike_attribution": match.superlike_attribution,
            "match_type": match.match_type,
        })
    return data


def compute_session_statistics(session, user=None):
    """
    Computes authoritative session statistics using the canonical Affinity service.
    Guarantees:
    - reviewed_count: distinct movies reviewed (always >= matched_count)
    - matched_count: mutual matches formed in session
    - affinity_percent: percentage (matched / reviewed * 100), bounded [0, 100]%
    - total_swipes: total distinct movies reviewed in session
    """
    from core.services.affinity import calculate_session_statistics
    return calculate_session_statistics(session, user=user)


class SessionEndView(APIView):
    """
    End an active session manually.
    Protected with transaction and row lock; idempotent if already ended.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")

        with transaction.atomic():
            try:
                session = Session.objects.select_for_update().get(id=session_id)
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            if request.user not in [session.host, session.guest]:
                return Response(
                    {"success": False, "error": "Not allowed: You are not a participant in this screening room"},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Idempotent: If session is already ended, both participants receive 200 gracefully
            if session.ended_at:
                stats, _ = SessionStats.objects.get_or_create(session=session)
                total_swipes = Swipe.objects.filter(session=session).count()
                total_matches = Match.objects.filter(session=session).count()
                needs_stat_save = False
                update_fields = []
                if stats.total_swipes == 0 and total_swipes > 0:
                    stats.total_swipes = total_swipes
                    needs_stat_save = True
                    update_fields.append("total_swipes")
                if stats.total_matches != total_matches:
                    stats.total_matches = total_matches
                    needs_stat_save = True
                    update_fields.append("total_matches")
                if needs_stat_save:
                    stats.save(update_fields=update_fields)

                stats_dict = compute_session_statistics(session, user=request.user)
                matches_data = serialize_session_matches(session)
                return Response(
                    {
                        "success": True,
                        "message": "Session already ended",
                        "ended": True,
                        "matches": matches_data,
                        "reviewed_count": stats_dict["reviewed_count"],
                        "matched_count": stats_dict["matched_count"],
                        "affinity_percent": stats_dict["affinity_percent"],
                    },
                    status=status.HTTP_200_OK
                )

            # Both host and guest have shared permission to end the screening room for both participants
            ended_by = "host" if request.user == session.host else "guest"
            session.ended_at = timezone.now()
            session.save(update_fields=["ended_at"])

            stats, _ = SessionStats.objects.get_or_create(session=session)

            # Ensure total_swipes and total_matches in SessionStats are accurately synchronized
            stats.total_swipes = Swipe.objects.filter(session=session).count()
            stats.total_matches = Match.objects.filter(session=session).count()

            if session.created_at:
                duration = timezone.now() - session.created_at
                stats.duration_ms = int(duration.total_seconds() * 1000)

            stats.ended_by = ended_by

            # --- Session Quality Score ---
            swipes = stats.total_swipes
            matches = stats.total_matches
            duration_minutes = (stats.duration_ms or 0) / 60000

            score = 0
            highlights = []

            # Match efficiency (core signal)
            if swipes > 0:
                match_ratio = matches / swipes
                score += min(int(match_ratio * 100), 40)

                if match_ratio > 0.2:
                    highlights.append("Strong agreement")
                elif match_ratio < 0.05:
                    highlights.append("Low alignment")

            # Absolute matches
            score += min(matches * 15, 30)
            if matches >= 2:
                highlights.append("Multiple matches")

            # Session depth
            if duration_minutes > 5:
                score += 10
                highlights.append("Good session flow")

            # Penalize dead sessions
            if swipes < 10:
                score -= 15
                highlights.append("Ended too early")

            # Clamp score
            stats.quality_score = max(0, min(score, 100))
            stats.highlights = highlights
            stats.save(update_fields=["quality_score", "highlights", "duration_ms", "ended_by", "total_swipes", "total_matches"])

        # Post-transaction broadcast
        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"session_{session.id}",
                    {
                        "type": "session_ended_event",
                        "session_id": session.id,
                        "ended_by": ended_by,
                    }
                )
            except Exception:
                pass

        stats_dict = compute_session_statistics(session, user=request.user)
        matches_data = serialize_session_matches(session)

        return Response(
            {
                "success": True,
                "message": "Session ended",
                "ended": True,
                "matches": matches_data,
                "reviewed_count": stats_dict["reviewed_count"],
                "matched_count": stats_dict["matched_count"],
                "affinity_percent": stats_dict["affinity_percent"],
            },
            status=status.HTTP_200_OK
        )


class SessionLeaveView(APIView):
    """
    Allows a participant (particularly guest) to leave an active screening session
    without unilaterally terminating the session for the other participant.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        if not session_id:
            return Response(
                {"success": False, "error": "session_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            try:
                session = Session.objects.select_for_update().get(id=session_id)
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            if request.user not in [session.host, session.guest]:
                return Response(
                    {"success": False, "error": "Not a participant in this session"},
                    status=status.HTTP_403_FORBIDDEN
                )

            is_guest = (request.user == session.guest)
            role = "guest" if is_guest else "host"

        channel_layer = get_channel_layer()
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"session_{session.id}",
                    {
                        "type": "partner_left_event",
                        "session_id": session.id,
                        "user_id": request.user.id,
                        "role": role,
                    }
                )
            except Exception:
                pass

        return Response(
            {
                "success": True,
                "left": True,
                "role": role,
                "session_active": session.ended_at is None,
                "message": f"{role.capitalize()} exited screening session.",
            },
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# Swipe APIs
# -------------------------------------------------------------------

def _update_analytics_after_commit(user_id, session_id, host_id, guest_id, movie_id, reaction, match_created):
    """
    Background analytics and chemistry aggregation deferred outside of the
    critical atomic transaction to prevent SQLite/PostgreSQL lock contention.
    """
    for attempt in range(3):
        try:
            from core.models import UserTasteSignal, SessionChemistry, Movie, Session
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.filter(id=user_id).first()
            host = User.objects.filter(id=host_id).first()
            guest = User.objects.filter(id=guest_id).first()
            movie = Movie.objects.prefetch_related("tags").filter(id=movie_id).first()
            if not user or not host or not guest or not movie:
                return

            user_a, user_b = normalize_pair(host, guest)
            tags = list(movie.tags.all())

            with transaction.atomic():
                for tag in tags:
                    signal, _ = UserTasteSignal.objects.get_or_create(user=user, tag=tag)
                    if reaction in (Swipe.LIKE, Swipe.SUPERLIKE):
                        UserTasteSignal.objects.filter(id=signal.id).update(like_count=F("like_count") + 1)
                    else:
                        UserTasteSignal.objects.filter(id=signal.id).update(dislike_count=F("dislike_count") + 1)

                    chemistry, _ = SessionChemistry.objects.get_or_create(
                        user_a=user_a,
                        user_b=user_b,
                        tag=tag.name,
                    )
                    SessionChemistry.objects.filter(id=chemistry.id).update(swipe_count=F("swipe_count") + 1)

                if match_created:
                    for tag in tags:
                        chemistry, _ = SessionChemistry.objects.get_or_create(
                            user_a=user_a,
                            user_b=user_b,
                            tag=tag.name,
                        )
                        SessionChemistry.objects.filter(id=chemistry.id).update(
                            match_count=F("match_count") + 1,
                            last_matched_at=timezone.now(),
                        )
            break
        except Exception as e:
            if isinstance(e, OperationalError) and "locked" in str(e).lower() and attempt < 2:
                time.sleep(0.05 * (attempt + 1))
                continue
            logger.warning(
                "Failed background analytics update after commit for session=%s user=%s movie=%s rx=%s attempt=%d: %s",
                session_id, user_id, movie_id, reaction, attempt + 1, e,
                exc_info=True,
            )
            break


def _safe_analytics_callback(user_id, session_id, host_id, guest_id, movie_id, reaction, match_created):
    """
    Safely executes deferred analytics callback without allowing any uncaught exception
    to bubble up to Django's on_commit runner, which would turn a committed 201 into 500.
    """
    try:
        _update_analytics_after_commit(
            user_id=user_id,
            session_id=session_id,
            host_id=host_id,
            guest_id=guest_id,
            movie_id=movie_id,
            reaction=reaction,
            match_created=match_created,
        )
    except Exception as exc:
        logger.error(
            "Uncaught exception in background analytics callback (session=%s user=%s movie=%s reaction=%s): %s",
            session_id, user_id, movie_id, reaction, exc,
            exc_info=True,
        )


class SwipeCreateView(APIView):
    """
    Records a swipe for a movie inside a session.
    - Enforces session rules
    - Prevents duplicate swipes
    - Detects matches
    - Emits WebSocket event on match
    - Hardened against database lock contention with bounded retry and deferred analytics
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        match_created = False
        should_notify_match = False
        superlike_attr = "none"
        match_type_str = "ordinary"
        session = None

        max_attempts = 5
        backoff_sec = 0.05

        for attempt in range(max_attempts):
            try:
                serializer = SwipeSerializer(data=request.data)

                # 1. Validate request payload (inside retry loop to absorb lock on related lookups)
                if not serializer.is_valid():
                    return Response(
                        {"success": False, "errors": serializer.errors},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                session_obj = serializer.validated_data["session"]
                movie = serializer.validated_data["movie"]
                reaction = serializer.validated_data["reaction"]

                # All DB mutations and match checks inside atomic transaction
                with transaction.atomic():
                    try:
                        from django.db import connection
                        if connection.vendor == "postgresql":
                            session = Session.objects.select_for_update().select_related("host", "guest").get(id=session_obj.id)
                        else:
                            session = Session.objects.select_related("host", "guest").get(id=session_obj.id)
                    except Session.DoesNotExist:
                        return Response(
                            {"success": False, "error": "Session not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    # 2. Session state checks
                    if session.ended_at:
                        return Response(
                            {"success": False, "error": "Session has ended"},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    if not session.host or not session.guest:
                        return Response(
                            {"success": False, "error": "Session is not ready yet"},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    # 3. Membership check
                    if request.user not in (session.host, session.guest):
                        return Response(
                            {"success": False, "error": "You are not part of this session"},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    # 4. Idempotency & Conflict Check: Already swiped this movie
                    existing_swipe = Swipe.objects.filter(session=session, user=request.user, movie=movie).first()
                    if existing_swipe:
                        if existing_swipe.reaction != reaction:
                            matching_logger.warning(
                                "Conflicting swipe rejected: session=%s movie=%s user=%s new_reaction=%s persisted_reaction=%s",
                                session.id,
                                movie.id,
                                request.user.id,
                                reaction,
                                existing_swipe.reaction,
                            )
                            return Response(
                                {
                                    "success": False,
                                    "error": f"Conflicting reaction '{reaction}' submitted for already processed movie (persisted reaction is '{existing_swipe.reaction}')."
                                },
                                status=status.HTTP_409_CONFLICT
                            )
                        # Same user, same session, same movie, same reaction:
                        # Return SUCCESSFUL idempotent response (HTTP 200 OK)
                        match_obj = Match.objects.filter(session=session, movie=movie).first()
                        match_formed = match_obj is not None
                        return Response(
                            {
                                "success": True,
                                "idempotent": True,
                                "match": match_formed,
                                "ask_to_end": match_formed,
                                "message": "Swipe already recorded (idempotent retry)",
                                "reaction": existing_swipe.reaction,
                                "superlike_attribution": match_obj.superlike_attribution if match_formed else "none",
                                "match_type": match_obj.match_type if match_formed else "ordinary",
                            },
                            status=status.HTTP_200_OK
                        )

                    # 5. Block swipes if movie already matched (sanity guard)
                    if Match.objects.filter(session=session, movie=movie).exists():
                        return Response(
                            {"success": False, "error": "This movie is already matched"},
                            status=status.HTTP_409_CONFLICT
                        )

                    # 6. Create swipe (unique constraint enforced at DB level)
                    try:
                        swipe = Swipe.objects.create(
                            user=request.user,
                            session=session,
                            movie=movie,
                            reaction=reaction
                        )
                    except IntegrityError:
                        return Response(
                            {"success": False, "error": "Already swiped on this movie"},
                            status=status.HTTP_409_CONFLICT
                        )

                    # Update stats safely using atomic F() expressions
                    SessionStats.objects.get_or_create(session=session)
                    SessionStats.objects.filter(session=session).update(
                        total_swipes=F("total_swipes") + 1
                    )

                    # 7. Match detection: Both participants must submit positive reactions (LIKE or SUPERLIKE)
                    partner = session.guest if request.user == session.host else session.host
                    partner_swipe = Swipe.objects.filter(session=session, user=partner, movie=movie).first()

                    match_created = False
                    should_notify_match = False
                    superlike_attr = "none"
                    match_type_str = "ordinary"

                    if partner_swipe is not None:
                        # Both participants have submitted responses for this movie
                        my_positive = reaction in (Swipe.LIKE, Swipe.SUPERLIKE)
                        partner_positive = partner_swipe.reaction in (Swipe.LIKE, Swipe.SUPERLIKE)

                        if my_positive and partner_positive:
                            match, created = Match.objects.get_or_create(session=session, movie=movie)
                            match_created = True
                            superlike_attr = match.superlike_attribution
                            match_type_str = match.match_type
                            if created:
                                SessionStats.objects.filter(session=session).update(
                                    total_matches=F("total_matches") + 1
                                )
                                should_notify_match = True

                    participant_role = "host" if request.user == session.host else "guest"
                    resolution_outcome = "matched" if match_created else ("pending" if partner_swipe is None else "no_match")
                    matching_logger.info(
                        "Swipe processed: session=%s movie=%s role=%s reaction=%s partner_rx=%s outcome=%s match_created=%s attribution=%s",
                        session.id,
                        movie.id,
                        participant_role,
                        reaction,
                        partner_swipe.reaction if partner_swipe else None,
                        resolution_outcome,
                        match_created,
                        superlike_attr if match_created else None,
                    )

                    # Defer expensive analytics (up to 40 queries) to post-commit to minimize write-lock duration
                    user_id_val = request.user.id
                    session_id_val = session.id
                    host_id_val = session.host.id
                    guest_id_val = session.guest.id
                    movie_id_val = movie.id
                    rx_val = reaction
                    m_created_val = match_created

                    transaction.on_commit(
                        lambda: _safe_analytics_callback(
                            user_id=user_id_val,
                            session_id=session_id_val,
                            host_id=host_id_val,
                            guest_id=guest_id_val,
                            movie_id=movie_id_val,
                            reaction=rx_val,
                            match_created=m_created_val,
                        )
                    )

                # Transaction succeeded cleanly
                break

            except (OperationalError, Exception) as exc:
                is_lock = isinstance(exc, OperationalError) and ("locked" in str(exc).lower() or "busy" in str(exc).lower())
                if is_lock and attempt < max_attempts - 1:
                    logger.warning(
                        "Database lock contention in SwipeCreateView (attempt %d/%d): %s. Retrying in %fs",
                        attempt + 1,
                        max_attempts,
                        exc,
                        backoff_sec,
                    )
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                    continue
                elif is_lock:
                    logger.error(
                        "Database lock contention exhausted in SwipeCreateView after %d attempts: %s",
                        max_attempts,
                        exc,
                    )
                    return Response(
                        {
                            "success": False,
                            "error": "Screening room is temporarily busy processing votes. Please retry.",
                            "retryable": True,
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                else:
                    raise exc

        # Post-transaction broadcast
        channel_layer = get_channel_layer()
        if channel_layer and session:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"session_{session.id}",
                    {
                        "type": "swipe_event",
                        "user_id": request.user.id,
                    }
                )
            except Exception:
                pass

            if should_notify_match:
                poster_url = None
                if movie.poster_path:
                    poster_url = f"https://image.tmdb.org/t/p/w780{movie.poster_path}"
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"session_{session.id}",
                        {
                            "type": "match_event",
                            "session_id": session.id,
                            "movie_id": movie.id,
                            "movie_title": movie.title or "Unknown Movie",
                            "poster_url": poster_url or "",
                            "release_year": movie.release_date.year if movie.release_date else None,
                            "rating": movie.rating,
                            "superlike_attribution": superlike_attr,
                            "match_type": match_type_str,
                        }
                    )
                except Exception:
                    pass

        # 8. Final response
        return Response(
            {
                "success": True,
                "idempotent": False,
                "match": match_created,
                "ask_to_end": match_created,
                "message": "It's a match!" if match_created else "Swipe recorded",
                "reaction": reaction,
                "superlike_attribution": superlike_attr if match_created else "none",
                "match_type": match_type_str if match_created else "ordinary",
            },
            status=status.HTTP_201_CREATED
        )


class SwipeUndoView(APIView):
    """
    Undo a swipe within a 10-second window if no match exists.
    Protected with transaction and session-level row locking to prevent undo/match races.
    Includes bounded lock retry protection.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        session_id = request.data.get("session_id")
        movie_id = request.data.get("movie_id")

        if not session_id or not movie_id:
            return Response(
                {"success": False, "error": "session_id and movie_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        max_attempts = 5
        backoff_sec = 0.05

        for attempt in range(max_attempts):
            try:
                with transaction.atomic():
                    try:
                        from django.db import connection
                        if connection.vendor == "postgresql":
                            session = Session.objects.select_for_update(of=('self',)).select_related("host", "guest").get(id=session_id)
                        else:
                            session = Session.objects.select_related("host", "guest").get(id=session_id)
                    except Session.DoesNotExist:
                        return Response(
                            {"success": False, "error": "Session not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    if session.ended_at:
                        return Response(
                            {"success": False, "error": "Session has ended"},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    if request.user not in (session.host, session.guest):
                        return Response(
                            {"success": False, "error": "Not part of this session"},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    try:
                        from django.db import connection
                        if connection.vendor == "postgresql":
                            swipe = Swipe.objects.select_for_update().select_related("movie").get(
                                user=request.user,
                                session=session,
                                movie_id=movie_id
                            )
                        else:
                            swipe = Swipe.objects.select_related("movie").get(
                                user=request.user,
                                session=session,
                                movie_id=movie_id
                            )
                    except Swipe.DoesNotExist:
                        return Response(
                            {"success": False, "error": "Swipe not found"},
                            status=status.HTTP_404_NOT_FOUND
                        )

                    if Match.objects.filter(session=session, movie_id=movie_id).exists():
                        return Response(
                            {"success": False, "error": "Cannot undo after match"},
                            status=status.HTTP_409_CONFLICT
                        )

                    if timezone.now() - swipe.created_at > timedelta(seconds=10):
                        return Response(
                            {"success": False, "error": "Undo window expired"},
                            status=status.HTTP_403_FORBIDDEN
                        )

                    # Revert swipe count safely
                    SessionStats.objects.filter(session=session, total_swipes__gt=0).update(
                        total_swipes=F("total_swipes") - 1
                    )

                    try:
                        for tag in swipe.movie.tags.all():
                            if swipe.reaction in (Swipe.LIKE, Swipe.SUPERLIKE):
                                UserTasteSignal.objects.filter(user=request.user, tag=tag, like_count__gt=0).update(
                                    like_count=F("like_count") - 1
                                )
                            else:
                                UserTasteSignal.objects.filter(user=request.user, tag=tag, dislike_count__gt=0).update(
                                    dislike_count=F("dislike_count") - 1
                                )
                    except Exception:
                        pass

                    from .models import InteractionLog
                    undo_weight = 0.0
                    if swipe.reaction == Swipe.LIKE:
                        undo_weight = -1.0
                    elif swipe.reaction == Swipe.DISLIKE:
                        undo_weight = 1.2
                    elif swipe.reaction == Swipe.SUPERLIKE:
                        undo_weight = -3.0

                    InteractionLog.objects.create(
                        user=request.user,
                        session=session,
                        movie=swipe.movie,
                        event_type='undo',
                        weight=undo_weight,
                        processing_status='pending',
                        metadata={'undone_swipe_id': swipe.id, 'undone_reaction': swipe.reaction},
                    )

                    swipe.delete()

                # Success
                break

            except (OperationalError, Exception) as exc:
                is_lock = isinstance(exc, OperationalError) and ("locked" in str(exc).lower() or "busy" in str(exc).lower())
                if is_lock and attempt < max_attempts - 1:
                    logger.warning(
                        "Database lock contention in SwipeUndoView (attempt %d/%d): %s. Retrying in %fs",
                        attempt + 1,
                        max_attempts,
                        exc,
                        backoff_sec,
                    )
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                    continue
                elif is_lock:
                    logger.error(
                        "Database lock contention exhausted in SwipeUndoView after %d attempts: %s",
                        max_attempts,
                        exc,
                    )
                    return Response(
                        {
                            "success": False,
                            "error": "Screening room is temporarily busy. Please retry.",
                            "retryable": True,
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                else:
                    raise exc

        return Response(
            {"success": True, "message": "Swipe undone"},
            status=status.HTTP_200_OK
        )


class SwipeHistoryView(APIView):
    """
    Paginated swipe history for the logged-in user.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = SwipeHistoryPagination

    def get(self, request):
        session_id = request.query_params.get("session_id")

        swipes = Swipe.objects.filter(
            user=request.user
        ).select_related(
            "movie", "session"
        ).order_by("-created_at")

        if session_id:
            swipes = swipes.filter(session_id=session_id)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(swipes, request)

        data = [
            {
                "session_id": swipe.session.id,
                "movie_id": swipe.movie.id,
                "movie_title": swipe.movie.title,
                "reaction": swipe.reaction,
                "swiped_at": swipe.created_at,
            }
            for swipe in page
        ]

        return paginator.get_paginated_response({
            "success": True,
            "swipes": data,
        })


# -------------------------------------------------------------------
# Match APIs
# -------------------------------------------------------------------

class MatchListView(APIView):
    """
    List match history for the logged-in user.
    When ?session_id= is supplied, strictly validates session existence and user membership.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        session_id_param = request.query_params.get("session_id")

        if session_id_param is not None:
            try:
                session_id = int(session_id_param)
            except (ValueError, TypeError):
                return Response(
                    {"success": False, "error": "Invalid session_id parameter"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                session = Session.objects.get(id=session_id)
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Strict authorization: user must be host or guest of requested session
            if session.host_id != user.id and session.guest_id != user.id:
                return Response(
                    {"success": False, "error": "You are not authorized to view matches for this session"},
                    status=status.HTTP_403_FORBIDDEN
                )

            matches = Match.objects.filter(session=session)
        else:
            matches = Match.objects.filter(
                models.Q(session__host=user) | models.Q(session__guest=user)
            ).distinct()

        matches = matches.select_related("movie", "session").prefetch_related("movie__genres").order_by("-created_at")

        match_list = list(matches)
        session_ids = {m.session_id for m in match_list}
        movie_ids = {m.movie_id for m in match_list}
        swipes_by_pair = defaultdict(list)
        if session_ids and movie_ids:
            for sw in Swipe.objects.filter(session_id__in=session_ids, movie_id__in=movie_ids):
                swipes_by_pair[(sw.session_id, sw.movie_id)].append(sw)

        for m in match_list:
            m._cached_swipes = swipes_by_pair.get((m.session_id, m.movie_id), [])

        data = []
        for match in match_list:
            movie = match.movie
            poster_url = None
            if movie.poster_path:
                poster_url = f"https://image.tmdb.org/t/p/w780{movie.poster_path}"

            data.append({
                "session_id": match.session.id,
                "movie_id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "movie_title": movie.title,
                "matched_at": match.created_at,
                "poster_url": poster_url,
                "rating": movie.rating,
                "vote_count": movie.vote_count,
                "release_year": movie.release_date.year if movie.release_date else None,
                "overview": movie.overview or "",
                "genres": [g.name for g in movie.genres.all()],
                "original_language": movie.original_language or "",
                "superlike_attribution": match.superlike_attribution,
                "match_type": match.match_type,
            })

        response_data = {
            "success": True,
            "matches": data,
        }
        if session_id_param is not None:
            stats_dict = compute_session_statistics(session, user=user)
            response_data.update(stats_dict)

        return Response(
            response_data,
            status=status.HTTP_200_OK
        )

class MovieSyncTMDBView(APIView):
    """
    Sync popular movies from TMDB into local database.
    Safe to run multiple times.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        from .services.tmdb import get_popular_movies

        movies_created = 0
        tmdb_data = get_popular_movies(page=1)

        for item in tmdb_data.get("results", []):
            movie, created = Movie.objects.update_or_create(
                tmdb_id=item["id"],
                defaults={
                    "title": item["title"],
                    "overview": item.get("overview", ""),
                    "poster_path": item.get("poster_path", ""),
                    "backdrop_path": item.get("backdrop_path", ""),
                    "release_date": item.get("release_date") or None,
                    "rating": item.get("vote_average"),
                    "vote_count": item.get("vote_count"),
                    "original_language": item.get("original_language"),
                    "tmdb_genre_ids": tmdb_genre_ids,
                }

            )

            # ✅ Correct genre linking
            tmdb_genre_ids = item.get("genre_ids", [])
            genre_objects = Genre.objects.filter(tmdb_id__in=tmdb_genre_ids)

            movie.genres.set(genre_objects)

            if created:
                movies_created += 1

        return Response(
            {
                "success": True,
                "created": movies_created,
                "total_fetched": len(tmdb_data.get("results", [])),
            },
            status=status.HTTP_200_OK
        )

class RecommendationView(APIView):
    """
    Returns swipeable movie recommendations
    filtered by the session's selected genre.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        session_id = request.query_params.get("session_id")
        
        if not session_id:
            return Response(
                {"success": False, "error": "session_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            session = Session.objects.select_related("genre", "host", "guest").get(id=session_id)
        except Session.DoesNotExist:
            return Response(
                {"success": False, "error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.user not in [session.host, session.guest]:
            return Response(
                {"success": False, "error": "Not part of this session"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if not session.genre:
            first_genre = session.genres.first()
            if first_genre:
                session.genre = first_genre
                session.save(update_fields=["genre"])
            else:
                return Response(
                    {"success": False, "error": "Genre not selected yet"},
                    status=400
                )

        # Get already swiped movies FOR THIS USER in this session (independent participant voting state)
        swiped_movie_ids = list(Swipe.objects.filter(
            session=session,
            user=request.user
        ).values_list("movie_id", flat=True))

        # Movies already matched in this session are excluded for both participants
        matched_movie_ids = list(Match.objects.filter(
            session=session
        ).values_list("movie_id", flat=True))

        # ✅ STEP 1: Start with ALL movies in selected genre(s)
        session_genres = list(session.genres.all())
        if not session_genres and session.genre:
            session_genres = [session.genre]

        if session_genres:
            base_qs = Movie.objects.filter(genres__in=session_genres)
        else:
            base_qs = Movie.objects.all()

        # ✅ STEP 2: Apply language / industry filtering
        if session.selected_languages:
            base_qs = base_qs.filter(original_language__in=session.selected_languages)
        else:
            # Fallback to industry if no languages set
            if session.industry == "bollywood":
                base_qs = base_qs.filter(original_language__in=INDIAN_LANGUAGES)
            elif session.industry == "hollywood":
                base_qs = base_qs.filter(original_language="en")
            # mixed = no language filter

        # ✅ STEP 3: Extract combined preferences from host and guest (or whichever has submitted)
        combined_prefs = {}
        host_prefs = session.host_preferences or {}
        guest_prefs = session.guest_preferences or {}

        if host_prefs and guest_prefs:
            # Soft preferences: mood, pace, vibe (intersection if common ground, else union for discovery)
            h_mood = set(host_prefs.get("mood", []))
            g_mood = set(guest_prefs.get("mood", []))
            h_pace = set(host_prefs.get("pace", []))
            g_pace = set(guest_prefs.get("pace", []))
            h_vibe = set(host_prefs.get("vibe", []))
            g_vibe = set(guest_prefs.get("vibe", []))

            combined_prefs = {
                "mood": list(h_mood & g_mood) or list(h_mood | g_mood),
                "pace": list(h_pace & g_pace) or list(h_pace | g_pace),
                "vibe": list(h_vibe & g_vibe) or list(h_vibe | g_vibe),
                "min_rating": list(set(host_prefs.get("min_rating", [])) & set(guest_prefs.get("min_rating", []))),
            }
            if not combined_prefs["min_rating"]:
                combined_prefs["min_rating"] = list(set(host_prefs.get("min_rating", [])) | set(guest_prefs.get("min_rating", [])))

            # Hard constraints: era (Architecture v1.2.2 Section 2.2 Table 1: intersection of era envelopes)
            h_eras = set(e for e in host_prefs.get("era", []) if e != "any")
            g_eras = set(e for e in guest_prefs.get("era", []) if e != "any")
            if h_eras and g_eras:
                common_eras = list(h_eras & g_eras)
                # If disjoint, envelope is contradictory: 0 movies can satisfy both without silent relaxation
                combined_prefs["era"] = common_eras if common_eras else ["__CONTRADICTORY_EMPTY_ERA__"]
            elif h_eras:
                combined_prefs["era"] = list(h_eras)
            elif g_eras:
                combined_prefs["era"] = list(g_eras)
            else:
                combined_prefs["era"] = []
        elif host_prefs:
            combined_prefs = dict(host_prefs)
        elif guest_prefs:
            combined_prefs = dict(guest_prefs)

        # ✅ STEP 4: Apply strict era and rating filtering if specified in preferences
        preferred_eras = [e for e in combined_prefs.get("era", []) if e != "any"]
        if preferred_eras:
            if "__CONTRADICTORY_EMPTY_ERA__" in preferred_eras:
                base_qs = base_qs.none()
            else:
                era_q = models.Q()
                for e in preferred_eras:
                    e_lower = str(e).lower()
                    if e_lower in ("before_1990", "pre_1990"):
                        era_q |= models.Q(release_date__lte="1989-12-31")
                    elif e_lower == "classic":
                        era_q |= models.Q(release_date__year__lt=2000)
                    elif e_lower == "90s":
                        era_q |= models.Q(release_date__year__gte=1990, release_date__year__lte=1999)
                    elif e_lower == "2000s":
                        era_q |= models.Q(release_date__year__gte=2000, release_date__year__lte=2009)
                    elif e_lower == "2010s":
                        era_q |= models.Q(release_date__year__gte=2010, release_date__year__lte=2019)
                    elif e_lower == "recent":
                        era_q |= models.Q(release_date__year__gte=2020)
                base_qs = base_qs.filter(era_q)

        min_rating_vals = []
        for mr in combined_prefs.get("min_rating", []):
            if mr and mr != "any":
                val = str(mr).replace("+", "").strip()
                try:
                    min_rating_vals.append(float(val))
                except (ValueError, TypeError):
                    pass
        if min_rating_vals:
            base_qs = base_qs.filter(rating__gte=min(min_rating_vals))

        # ✅ STEP 5: Get ALL candidates (excluding already swiped/matched)
        all_candidate_ids = list(
            base_qs
            .exclude(id__in=swiped_movie_ids)
            .exclude(id__in=matched_movie_ids)
            .values_list("id", flat=True)
            .distinct()
        )

        # If candidates are empty, attempt on-demand TMDB sync WITH the era and rating criteria
        if not all_candidate_ids:
            try:
                from core.services.tmdb import sync_tmdb_movies_for_criteria
                sync_era = preferred_eras[0] if preferred_eras else None
                sync_min_rating = min(min_rating_vals) if min_rating_vals else None
                sync_tmdb_movies_for_criteria(
                    genres=session_genres,
                    industry=session.industry,
                    languages=session.selected_languages,
                    max_pages=3,
                    era=sync_era,
                    min_rating=sync_min_rating,
                )
                all_candidate_ids = list(
                    base_qs
                    .exclude(id__in=swiped_movie_ids)
                    .exclude(id__in=matched_movie_ids)
                    .values_list("id", flat=True)
                    .distinct()
                )
            except Exception as e:
                logger.warning("On-demand TMDB sync failed: %s", SecretRedactionFilter.redact_text(e))

        # ✅ CHECK: If still no movies left after sync attempt, return exhausted
        if not all_candidate_ids:
            genre_name = session.genre.name if session.genre else (session_genres[0].name if session_genres else "")
            return Response(
                {
                    "success": True,
                    "session_id": session.id,
                    "genre": genre_name,
                    "movies": [],
                    "exhausted": True,
                    "total_swiped": len(swiped_movie_ids),
                    "total_matched": len(matched_movie_ids),
                },
                status=status.HTTP_200_OK
            )

        candidate_movies = Movie.objects.filter(id__in=all_candidate_ids)

        # ✅ STEP 6: Score ALL candidate movies
        scored_movies = []

        for movie in candidate_movies:
            score = 0
            
            # Preference matching (ranking signal)
            if combined_prefs:
                pref_score = calculate_preference_score(movie, combined_prefs)
                score += pref_score
            
            # Taste signal (user history)
            for tag in movie.tags.all():
                try:
                    signal = UserTasteSignal.objects.get(user=request.user, tag=tag)
                    score += (signal.like_count - signal.dislike_count) * 2
                except UserTasteSignal.DoesNotExist:
                    pass
            
            # Chemistry signal (pair history)
            user_a, user_b = normalize_pair(session.host, session.guest)
            for tag in movie.tags.all():
                try:
                    chem = SessionChemistry.objects.get(
                        user_a=user_a, user_b=user_b, tag=tag.name
                    )
                    score += chem.match_count * 3
                except SessionChemistry.DoesNotExist:
                    pass

            # Penalize overexposed movies
            try:
                exposure = MovieExposure.objects.get(movie=movie)
                if exposure.exposed_count > 50:
                    score -= 5
            except MovieExposure.DoesNotExist:
                pass

            scored_movies.append((score, movie))

        # ✅ STEP 6: Sort by score (best first)
        scored_movies.sort(key=lambda x: x[0], reverse=True)

        # ✅ STEP 7: Return top 30 movies (adaptive batch)
        stats, _ = SessionStats.objects.get_or_create(session=session)
        
        if stats.total_swipes < 10:
            batch_size = 40  # Larger batch early
        elif stats.total_matches >= 3:
            batch_size = 20  # Smaller batch if matching well
        else:
            batch_size = 30  # Default

        movies = [m for (score, m) in scored_movies[:batch_size]]

        # Update exposure
        for movie in movies:
            try:
                exposure, _ = MovieExposure.objects.get_or_create(movie=movie)
                exposure.exposed_count += 1
                exposure.last_exposed_at = timezone.now()
                exposure.save(update_fields=["exposed_count", "last_exposed_at"])
            except Exception:
                pass

        serializer = MovieSerializer(movies, many=True)

        genre_name = session.genre.name if session.genre else (session_genres[0].name if session_genres else "")
        remaining_candidates = max(0, len(all_candidate_ids) - len(movies))

        return Response(
            {
                "success": True,
                "session_id": session.id,
                "genre": genre_name,
                "movies": serializer.data,
                "exhausted": False,
                "remaining_candidates": remaining_candidates,
            },
            status=status.HTTP_200_OK
        )


DEFAULT_CANONICAL_GENRES = [
    (28, "Action"),
    (12, "Adventure"),
    (16, "Animation"),
    (35, "Comedy"),
    (80, "Crime"),
    (99, "Documentary"),
    (18, "Drama"),
    (10751, "Family"),
    (14, "Fantasy"),
    (36, "History"),
    (27, "Horror"),
    (10402, "Music"),
    (9648, "Mystery"),
    (10749, "Romance"),
    (878, "Science Fiction"),
    (10770, "TV Movie"),
    (53, "Thriller"),
    (10752, "War"),
    (37, "Western"),
]

def ensure_default_genres():
    """Ensure standard canonical genres exist in database."""
    if not Genre.objects.exists():
        for tmdb_id, name in DEFAULT_CANONICAL_GENRES:
            Genre.objects.get_or_create(tmdb_id=tmdb_id, defaults={"name": name})


class GenreListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        industry = request.query_params.get("industry")
        
        if not industry:
            return Response(
                {"success": False, "error": "industry param required"},
                status=400
            )

        if industry not in ["bollywood", "hollywood", "mixed"]:
            return Response(
                {"success": False, "error": "Invalid industry"},
                status=400
            )

        ensure_default_genres()

        if industry == "mixed":
            genres = Genre.objects.all().order_by("name")
        elif industry == "bollywood":
            languages = ["hi", "ta", "te", "bn", "mr", "gu", "kn", "ml", "pa"]
            movie_genres = Genre.objects.filter(movie__original_language__in=languages).distinct()
            if movie_genres.exists():
                genres = movie_genres.order_by("name")
            else:
                genres = Genre.objects.filter(
                    models.Q(industry="bollywood") | models.Q(industry__isnull=True) | models.Q(industry="")
                ).order_by("name")
        else:  # hollywood
            languages = ["en"]
            movie_genres = Genre.objects.filter(movie__original_language__in=languages).distinct()
            if movie_genres.exists():
                genres = movie_genres.order_by("name")
            else:
                genres = Genre.objects.filter(
                    models.Q(industry="hollywood") | models.Q(industry__isnull=True) | models.Q(industry="")
                ).order_by("name")

        return Response(
            {
                "success": True,
                "genres": [{"id": g.id, "tmdb_id": g.tmdb_id, "name": g.name} for g in genres]
            },
            status=200
        )


    
class SessionDetailView(APIView):
    """
    Get session state for frontend polling.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        max_attempts = 5
        backoff_sec = 0.05
        for attempt in range(max_attempts):
            try:
                session = Session.objects.select_related(
                    "host__profile", "guest__profile", "genre", "stats"
                ).prefetch_related("genres").get(id=session_id)

                if request.user not in [session.host, session.guest]:
                    return Response(
                        {"success": False, "error": "Not allowed"},
                        status=status.HTTP_403_FORBIDDEN
                    )

                serializer = SessionDetailSerializer(session, context={"request": request})
                return Response(
                    {"success": True, "session": serializer.data},
                    status=status.HTTP_200_OK
                )
            except Session.DoesNotExist:
                return Response(
                    {"success": False, "error": "Session not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except (OperationalError, Exception) as exc:
                is_lock = isinstance(exc, OperationalError) and ("locked" in str(exc).lower() or "busy" in str(exc).lower())
                if is_lock and attempt < max_attempts - 1:
                    time.sleep(backoff_sec)
                    backoff_sec *= 2
                    continue
                elif is_lock:
                    return Response(
                        {"success": False, "error": "Database is temporarily busy. Please retry."},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
                raise exc

class SessionStatusView(APIView):
    """
    Public session status lookup by code.
    Used before joining a session.
    """

    def get(self, request):
        raw_code = request.query_params.get("code")

        if not raw_code:
            return Response(
                {"success": False, "error": "Session code required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        code = str(raw_code).strip().upper()

        try:
            session = Session.objects.get(code__iexact=code)
        except Session.DoesNotExist:
            return Response(
                {"success": False, "exists": False},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "success": True,
                "exists": True,
                "session": {
                    "id": session.id,
                    "code": session.code,
                    "host_joined": True,
                    "guest_joined": session.guest is not None,
                    "ended": session.ended_at is not None,
                    "preferences_set": bool(session.preferences_set),
                    "genre": {
                        "id": session.genre.id,
                        "name": session.genre.name
                    } if session.genre else None,
                },
            },
            status=status.HTTP_200_OK
        )
    
class GenreSyncTMDBView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request):
        from .services.tmdb import get_tmdb_genres

        created = 0
        updated = 0

        tmdb_genres = get_tmdb_genres()

        for g in tmdb_genres:
            genre, was_created = Genre.objects.update_or_create(
                tmdb_id=g["id"],
                defaults={
                    "name": g["name"],
                    # TEMP default – you will refine later
                    "industry": "hollywood",
                }
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return Response({
            "success": True,
            "created": created,
            "updated": updated,
        })


class UserProfileView(APIView):
    """
    Get or update current user's profile information.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "profile", None)
        guest_profile = getattr(user, "guest_profile", None)
        is_guest = bool(guest_profile and not guest_profile.is_claimed)
        recovery_code = ""
        if is_guest and guest_profile:
            if not guest_profile.recovery_code:
                new_code = generate_recovery_code()
                guest_profile.recovery_code = new_code
                guest_profile.recovery_lookup_digest = compute_recovery_lookup_digest(new_code)
                guest_profile.recovery_verification_hash = hash_recovery_code(new_code)
                guest_profile.save(update_fields=["recovery_code", "recovery_lookup_digest", "recovery_verification_hash"])
            recovery_code = guest_profile.recovery_code

        # For activated registered / converted members, mark email_verified = True so they are recognized as activated
        email_verified = True
        if is_guest:
            email_verified = False
        elif profile:
            if not profile.email_verified:
                profile.email_verified = True
                profile.save(update_fields=["email_verified"])
            email_verified = True
        else:
            UserProfile.objects.create(user=user, email_verified=True)
            email_verified = True

        display_name = ""
        if profile and profile.display_name:
            display_name = profile.display_name.strip()
        if not display_name:
            display_name = user.first_name.strip() or user.username

        return Response({
            "success": True,
            "user": {
                "id": user.id,
                "username": user.username,
                "display_name": display_name,
                "email": user.email,
                "email_verified": email_verified,
                "date_joined": user.date_joined,
                "is_staff": user.is_staff,
                "is_guest": is_guest,
                "recovery_code": recovery_code if is_guest else None,
            }
        })

    def patch(self, request):
        user = request.user
        display_name = request.data.get("display_name")
        if display_name is not None:
            display_name = str(display_name).strip()
            if len(display_name) < 2 or len(display_name) > 50:
                return Response(
                    {"success": False, "error": "Display name must be between 2 and 50 characters."},
                    status=400
                )
            user.first_name = display_name
            user.save(update_fields=["first_name"])
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.display_name = display_name
            profile.save(update_fields=["display_name"])
            return Response({"success": True, "display_name": display_name})
        return Response({"success": False, "error": "No display_name provided"}, status=400)


class UpdateUsernameView(APIView):
    """
    Update current authenticated user's username.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user  # ✅ Use authenticated user, not user_id
        new_username = request.data.get("username")

        if not new_username:
            return Response({
                "success": False,
                "error": "Username is required"
            }, status=400)

        # Check if username is taken by another user
        if User.objects.filter(username=new_username).exclude(id=user.id).exists():
            return Response({
                "success": False,
                "error": "Username is already taken"
            }, status=400)

        # Update username only
        old_username = user.username
        user.username = new_username
        user.save(update_fields=['username'])

        return Response({
            "success": True,
            "message": f"Username updated from '{old_username}' to '{new_username}'",
            "username": new_username,
        })


class DeleteAccountView(APIView):
    """
    Permanently delete the authenticated user's account with GDPR/CCPA privacy tombstoning.
    DELETE /api/users/delete-account/

    Contract:
    - Requires authentication via Token or Session.
    - Requires password confirmation in request payload: {"password": "<password>"}.
    - Rejects system tombstone actor.
    - Invokes TombstoneService.anonymize_and_delete_user to reassign interaction logs
      to system_deleted_actor, purge identity links, delete taste/user profiles, and remove the auth_user row.
    - Returns HTTP 200 with {"success": True, "message": "Account deleted successfully."}.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        user = request.user
        password = request.data.get("password") if isinstance(request.data, dict) else None

        from core.services.tombstone import TombstoneService

        # 1. Prevent deletion of system tombstone actor
        if user.username == TombstoneService.TOMBSTONE_USERNAME:
            return Response(
                {"success": False, "error": "Cannot delete system tombstone actor."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 2. Require and verify password for registered users with usable passwords
        if user.has_usable_password():
            if not password:
                return Response(
                    {"success": False, "error": "Please enter your password to confirm."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not user.check_password(str(password)):
                return Response(
                    {"success": False, "error": "Invalid password."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 3. Anonymize and delete user via TombstoneService
        try:
            metrics = TombstoneService.anonymize_and_delete_user(user)
            logger.info("Account deleted successfully for user_id=%s: %s", getattr(user, "id", None), metrics)
            return Response(
                {
                    "success": True,
                    "message": "Account deleted successfully.",
                    "metrics": metrics,
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error("Failed to delete account for user: %s", e)
            return Response(
                {"success": False, "error": "Failed to delete account. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



class PasswordResetRequestView(APIView):
    """
    Request password reset - sends email with reset link.
    Never exposes tokens or reset links in API responses.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        email = request.data.get("email")
        
        if not email:
            return Response({
                "success": False,
                "error": "Email is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists - return generic success message
            return Response({
                "success": True,
                "message": "If this email exists, you will receive a password reset link."
            }, status=status.HTTP_200_OK)

        # Generate token & uid
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        
        frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
        reset_link = f"{frontend_url}/reset-password?uid={uid}&token={token}"
        
        try:
            send_mail(
                subject="Password Reset Request - Flick",
                message=(
                    f"Hello,\n\n"
                    f"You requested a password reset for your Flick account.\n"
                    f"Please click the link below to reset your password:\n\n"
                    f"{reset_link}\n\n"
                    f"If you did not request this, please ignore this email.\n"
                ),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@flickapp.com"),
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception as exc:
            logger.error("Failed to send password reset email to %s: %s", user.email, exc)

        return Response({
            "success": True,
            "message": "If this email exists, you will receive a password reset link."
        }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """
    Reset password with token.
    Validates token, enforces password complexity, and invalidates existing auth tokens.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not all([uidb64, token, new_password]):
            return Response({
                "success": False,
                "error": "Missing required parameters"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({
                "success": False,
                "error": "Invalid reset link"
            }, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({
                "success": False,
                "error": "Invalid or expired reset link"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except ValidationError as err:
            return Response({
                "success": False,
                "error": " ".join(err.messages)
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Invalidate existing auth tokens on password reset
        Token.objects.filter(user=user).delete()

        return Response({
            "success": True,
            "message": "Password reset successful"
        }, status=status.HTTP_200_OK)

class MovieStreamingOptionsView(APIView):
    """
    Get streaming options for a movie with regional availability.
    Fetches official TMDB watch provider data with region-aware caching
    and JustWatch attribution.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, movie_id):
        # 1. Resolve movie by Django PK or TMDB ID
        movie = Movie.objects.filter(
            models.Q(id=movie_id) | models.Q(tmdb_id=movie_id)
        ).first()

        # If not stored locally, attempt on-demand creation from TMDB
        if not movie:
            from core.services.tmdb import get_or_create_movie_from_tmdb
            try:
                movie, _ = get_or_create_movie_from_tmdb(movie_id)
            except Exception:
                movie = None

        if not movie:
            return Response(
                {"success": False, "error": "Movie not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2. Resolve target region (defaults to settings.DEFAULT_STREAMING_REGION or 'IN')
        region_param = request.query_params.get("region")
        default_region = getattr(settings, "DEFAULT_STREAMING_REGION", "IN")
        region = (region_param or default_region or "IN").strip().upper()
        if not region or len(region) != 2 or not region.isalpha():
            region = "IN"

        # 3. Check region-aware cache
        cache_key = f"movie_streaming_providers:{movie.id}:{region}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data, status=status.HTTP_200_OK)

        # 4. If movie has no tmdb_id, return empty providers list
        if not movie.tmdb_id:
            payload = {
                "success": True,
                "movie_title": movie.title,
                "movie_id": movie.id,
                "tmdb_id": None,
                "region": region,
                "link": None,
                "attribution": "Streaming data provided by JustWatch via TMDB",
                "providers": [],
            }
            cache.set(cache_key, payload, timeout=86400)
            return Response(payload, status=status.HTTP_200_OK)

        # 5. Fetch watch providers from TMDB
        try:
            raw_providers = get_movie_watch_providers(movie.tmdb_id, region=region)
        except (TMDBTimeoutError, TMDBAPIError, TMDBServiceError) as e:
            # Distinguish 404 (unavailable upstream provider data) from operational errors
            if isinstance(e, TMDBAPIError) and "404" in str(e):
                logger.info(
                    f"Watch provider data unavailable (404) for movie={movie.id} "
                    f"(tmdb_id={movie.tmdb_id}, region={region}); returning empty provider list."
                )
                payload = {
                    "success": True,
                    "movie_title": movie.title,
                    "movie_id": movie.id,
                    "tmdb_id": movie.tmdb_id,
                    "region": region,
                    "link": None,
                    "attribution": "Streaming data provided by JustWatch via TMDB",
                    "providers": [],
                }
                cache.set(cache_key, payload, timeout=86400)
                return Response(payload, status=status.HTTP_200_OK)

            logger.warning(
                f"Error fetching watch providers for movie={movie.id} "
                f"(tmdb_id={movie.tmdb_id}, region={region}): {e}"
            )
            # Check if database has cached records for this movie and region as fallback
            db_avail = MovieStreamingAvailability.objects.filter(
                movie=movie,
                provider__country_code=region
            ).select_related("provider")

            if db_avail.exists():
                fallback_providers = [
                    {
                        "id": opt.provider.id,
                        "name": opt.provider.name,
                        "provider_name": opt.provider.name,
                        "logo_url": opt.provider.logo_url,
                        "logo_path": "",
                        "url": opt.url or opt.provider.website_url,
                        "link": opt.url or opt.provider.website_url,
                        "type": opt.monetization_type,
                    }
                    for opt in db_avail
                ]
                return Response({
                    "success": True,
                    "movie_title": movie.title,
                    "movie_id": movie.id,
                    "tmdb_id": movie.tmdb_id,
                    "region": region,
                    "link": None,
                    "attribution": "Streaming data provided by JustWatch via TMDB",
                    "providers": fallback_providers,
                }, status=status.HTTP_200_OK)

            # Do not cache error responses
            return Response({
                "success": False,
                "error": "Failed to retrieve streaming availability from upstream provider. Please retry.",
                "error_code": "UPSTREAM_TIMEOUT" if isinstance(e, TMDBTimeoutError) else "UPSTREAM_ERROR",
            }, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e:
            logger.error("Unexpected error retrieving streaming options for movie=%s: %s", movie.id, SecretRedactionFilter.redact_text(e))
            return Response({
                "success": False,
                "error": "Failed to load streaming options. Please retry.",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 6. Parse and format provider categories
        providers_data = []
        link = raw_providers.get("link")

        for category in ["flatrate", "free", "ads", "rent", "buy"]:
            for p in raw_providers.get(category, []):
                logo_path = p.get("logo_path") or ""
                logo_url = f"https://image.tmdb.org/t/p/original{logo_path}" if logo_path else ""
                providers_data.append({
                    "id": p.get("provider_id"),
                    "name": p.get("provider_name", ""),
                    "provider_name": p.get("provider_name", ""),
                    "logo_url": logo_url,
                    "logo_path": logo_path,
                    "url": link or "",
                    "link": link or "",
                    "type": category,
                    "display_priority": p.get("display_priority", 999),
                })

        # 7. Persist to local database models (StreamingProvider & MovieStreamingAvailability)
        for p in providers_data:
            try:
                db_provider, _ = StreamingProvider.objects.update_or_create(
                    name=p["name"],
                    country_code=region,
                    defaults={
                        "logo_url": p["logo_url"],
                        "website_url": p["url"],
                        "is_active": True,
                    }
                )
                m_type = p["type"] if p["type"] in ["flatrate", "buy", "rent"] else "flatrate"
                MovieStreamingAvailability.objects.update_or_create(
                    movie=movie,
                    provider=db_provider,
                    defaults={
                        "url": p["url"],
                        "monetization_type": m_type,
                    }
                )
            except Exception as db_err:
                logger.debug(f"Error persisting streaming option: {db_err}")

        # 8. Build response and cache
        response_data = {
            "success": True,
            "movie_title": movie.title,
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "region": region,
            "link": link,
            "attribution": "Streaming data provided by JustWatch via TMDB",
            "providers": providers_data,
        }

        # Cache with 24h TTL
        cache.set(cache_key, response_data, timeout=86400)

        return Response(response_data, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# Email Verification Views
# -------------------------------------------------------------------

class SendVerificationEmailView(APIView):
    """
    Send or resend email verification link.
    Supports authenticated users, or takes 'email' in request body.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        user = request.user if (request.user and request.user.is_authenticated) else None

        if not user:
            email = request.data.get("email")
            if not email:
                return Response(
                    {"success": False, "error": "Authentication or email required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response(
                    {"success": True, "message": "If the email is registered, a verification link has been sent."},
                    status=status.HTTP_200_OK
                )

        profile, _ = UserProfile.objects.get_or_create(user=user)
        if profile.email_verified:
            return Response(
                {"success": True, "message": "Email is already verified", "already_verified": True},
                status=status.HTTP_200_OK
            )

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        verify_url = f"/verify-email?uid={uid}&token={token}"

        email_sent = False
        try:
            send_mail(
                subject="Verify your Flick email",
                message=f"Hi {user.username},\n\nPlease click the link below to verify your email address:\n\n{verify_url}\n\nThank you,\nFlick Team",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@flickapp.in"),
                recipient_list=[user.email],
                fail_silently=False,
            )
            email_sent = True
        except Exception:
            pass

        return Response(
            {
                "success": True,
                "message": "Verification email sent" if email_sent else "Verification link generated",
                "email_sent": email_sent,
                "verify_url": verify_url if getattr(settings, "DEBUG", False) else None,
            },
            status=status.HTTP_200_OK
        )


class VerifyEmailConfirmView(APIView):
    """
    Confirm email verification using uid and token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")

        if not uidb64 or not token:
            return Response(
                {"success": False, "error": "Missing uid or token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response(
                {"success": False, "error": "Invalid verification link"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if default_token_generator.check_token(user, token):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])
            return Response(
                {"success": True, "message": "Email verified successfully"},
                status=status.HTTP_200_OK
            )

        return Response(
            {"success": False, "error": "Verification link has expired or is invalid"},
            status=status.HTTP_400_BAD_REQUEST
        )


# -------------------------------------------------------------------
# Recent Sessions View
# -------------------------------------------------------------------

class SessionRecentListView(APIView):
    """
    Returns recent sessions for the logged-in user.
    Optimized with select_related, prefetch_related, and Count annotation to eliminate N+1 queries.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sessions = (
            Session.objects.filter(models.Q(host=user) | models.Q(guest=user))
            .select_related("host", "guest", "genre", "collaborative_agreement")
            .prefetch_related("genres")
            .annotate(match_count=models.Count("match", distinct=True))
            .order_by("-created_at")[:30]
        )

        data = []
        for s in sessions:
            prefetched_genres = list(s.genres.all())
            if s.genre:
                name = f"{s.genre.name} Night"
            elif prefetched_genres:
                name = f"{prefetched_genres[0].name} Night"
            else:
                name = f"Movie Night #{s.code}"

            participants = [
                {
                    "username": s.host.username,
                    "initials": s.host.username[:2].upper() if s.host.username else "HO",
                }
            ]
            if s.guest:
                participants.append({
                    "username": s.guest.username,
                    "initials": s.guest.username[:2].upper() if s.guest.username else "GU",
                })

            is_host = (s.host_id == user.id)
            user_role = "host" if is_host else "guest"
            if s.ended_at is None:
                session_status = "active"
            else:
                is_completed = False
                if hasattr(s, "collaborative_agreement") and s.collaborative_agreement:
                    manifest_len = len(s.collaborative_agreement.deck_manifest or [])
                    is_completed = manifest_len > 0 and s.collaborative_agreement.resolved_card_index >= manifest_len
                session_status = "completed" if is_completed else "ended_by_host"

            data.append({
                "id": s.id,
                "code": s.code,
                "name": name,
                "date": s.created_at.strftime("%b %d, %Y") if s.created_at else "",
                "matches": s.match_count,
                "ended": s.ended_at is not None,
                "status": session_status,
                "is_host": is_host,
                "user_role": user_role,
                "participants": participants,
            })

        return Response(
            {"success": True, "sessions": data},
            status=status.HTTP_200_OK
        )


class SessionHistoryView(APIView):
    """
    Returns screening history for the authenticated user with details required
    by the Screening Archives UI: session code, partner username, genre tags,
    match and swipe counts, and the top-rated matched movie.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sessions = (
            Session.objects.filter(models.Q(host=user) | models.Q(guest=user))
            .select_related("host", "guest", "genre")
            .prefetch_related(
                "genres",
                models.Prefetch(
                    "match_set",
                    queryset=Match.objects.select_related("movie").order_by("-movie__rating", "-created_at"),
                    to_attr="prefetched_matches"
                ),
                models.Prefetch(
                    "swipe_set",
                    queryset=Swipe.objects.all(),
                    to_attr="prefetched_swipes"
                ),
            )
            .order_by("-created_at")[:50]
        )

        history = []
        for s in sessions:
            if user == s.host:
                partner_username = s.guest.username if s.guest else "Waiting for partner"
            else:
                partner_username = s.host.username if s.host else ""

            genres = [g.name for g in s.genres.all()]
            if not genres and s.genre:
                genres = [s.genre.name]

            matches = getattr(s, "prefetched_matches", [])
            match_count = len(matches)

            top_match = None
            if matches and matches[0].movie:
                best = matches[0].movie
                poster_url = f"https://image.tmdb.org/t/p/w780{best.poster_path}" if best.poster_path else None
                top_match = {
                    "movie_id": best.id,
                    "movie_title": best.title,
                    "poster_url": poster_url,
                }

            from .services.affinity import calculate_session_statistics
            stats_dict = calculate_session_statistics(s, user=user)
            match_count = stats_dict["matched_count"]
            swipe_count = stats_dict["reviewed_count"]
            affinity_percent = stats_dict["affinity_percent"]

            history.append({
                "session_id": s.id,
                "session_code": s.code,
                "partner_username": partner_username,
                "genres": genres,
                "match_count": match_count,
                "swipe_count": swipe_count,
                "affinity_percent": affinity_percent,
                "top_match": top_match,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else "",
            })

        return Response(
            {"success": True, "history": history},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# Watchlist Views
# -------------------------------------------------------------------

class WatchlistView(APIView):
    """
    List user's watchlist or add movie to watchlist.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit_str = request.query_params.get("limit") or request.query_params.get("page_size")
        try:
            limit = min(max(1, int(limit_str)), 100) if limit_str else 100
        except (ValueError, TypeError):
            limit = 100

        offset_str = request.query_params.get("offset")
        try:
            offset = max(0, int(offset_str)) if offset_str else 0
        except (ValueError, TypeError):
            offset = 0

        qs = (
            WatchlistItem.objects.filter(user=request.user)
            .select_related("movie", "session")
            .order_by("-added_at")
        )

        total_count = qs.count()
        items = list(qs[offset : offset + limit])

        data = [
            {
                "id": item.id,
                "movie_id": item.movie.id,
                "movie_title": item.movie.title,
                "poster_url": (
                    f"https://image.tmdb.org/t/p/w780{item.movie.poster_path}"
                    if item.movie.poster_path else None
                ),
                "rating": item.movie.rating,
                "release_year": item.movie.release_date.year if item.movie.release_date else None,
                "trailer_url": (
                    f"https://www.youtube.com/watch?v={item.movie.trailer_key}"
                    if item.movie.trailer_key else None
                ),
                "session_id": item.session_id,
                "added_at": item.added_at.isoformat() if item.added_at else "",
                "watched": item.watched,
            }
            for item in items
        ]

        return Response(
            {
                "success": True,
                "watchlist": data,
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
            },
            status=status.HTTP_200_OK
        )

    def post(self, request):
        movie_id = request.data.get("movie_id")
        tmdb_id = request.data.get("tmdb_id")
        session_id = request.data.get("session_id")

        if not movie_id and not tmdb_id:
            return Response(
                {"success": False, "error": "movie_id or tmdb_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        movie = None

        # 1. If explicit tmdb_id provided, resolve or create via TMDB
        if tmdb_id:
            try:
                tmdb_int = int(tmdb_id)
                movie = Movie.objects.filter(tmdb_id=tmdb_int).first()
                if not movie:
                    from core.services.tmdb import get_or_create_movie_from_tmdb
                    movie, _ = get_or_create_movie_from_tmdb(tmdb_int)
            except (ValueError, TypeError):
                pass

        # 2. If movie not yet resolved, check movie_id (local Django PK or TMDB ID)
        if not movie and movie_id:
            try:
                mid_int = int(movie_id)
                movie = Movie.objects.filter(
                    models.Q(id=mid_int) | models.Q(tmdb_id=mid_int)
                ).first()
                if not movie:
                    from core.services.tmdb import get_or_create_movie_from_tmdb
                    movie, _ = get_or_create_movie_from_tmdb(mid_int)
            except (ValueError, TypeError):
                pass

        if not movie:
            return Response(
                {"success": False, "error": "Movie not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        session = Session.objects.filter(id=session_id).first() if session_id else None

        item, created = WatchlistItem.objects.get_or_create(
            user=request.user,
            movie=movie,
            defaults={"session": session}
        )

        return Response(
            {
                "success": True,
                "created": created,
                "item": {
                    "id": item.id,
                    "movie_id": movie.id,
                    "tmdb_id": movie.tmdb_id,
                    "movie_title": movie.title,
                    "watched": item.watched,
                }
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )


class WatchlistDetailView(APIView):
    """
    Update or delete a movie in user's watchlist.
    Supports either local movie_id or tmdb_id.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, movie_id):
        item = WatchlistItem.objects.filter(user=request.user).filter(
            models.Q(movie_id=movie_id) | models.Q(movie__tmdb_id=movie_id)
        ).first()
        if not item:
            return Response(
                {"success": False, "error": "Item not found in watchlist"},
                status=status.HTTP_404_NOT_FOUND
            )

        watched = request.data.get("watched")
        if watched is not None:
            item.watched = bool(watched)
            item.watched_at = timezone.now() if item.watched else None
            item.save(update_fields=["watched", "watched_at"])

        return Response(
            {"success": True, "watched": item.watched},
            status=status.HTTP_200_OK
        )

    def delete(self, request, movie_id):
        item = WatchlistItem.objects.filter(user=request.user).filter(
            models.Q(movie_id=movie_id) | models.Q(movie__tmdb_id=movie_id)
        ).first()
        if item:
            item.delete()

        return Response(
            {"success": True, "message": "Removed from watchlist"},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------------------
# Movie Discover View (Dynamic TMDB + Hybrid Redis Caching + Local Fallback)
# -------------------------------------------------------------------

class DiscoverView(APIView):
    """
    Discover movies dynamically from the full TMDB catalogue with hybrid Redis caching.
    Supports categories (trending, popular, top_rated, now_playing, upcoming, discover),
    filters (genre, language, era, min_rating), full pagination, keyword search,
    and automatic graceful fallback to the local catalogue.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        category = request.query_params.get("category", "").strip().lower()
        search = request.query_params.get("search", "").strip()
        genre = request.query_params.get("genre")
        language = request.query_params.get("language")
        era = request.query_params.get("era")
        min_rating = request.query_params.get("min_rating")
        sort_by = request.query_params.get("sort_by", "popularity.desc")
        watch_provider_id = request.query_params.get("watch_provider_id")
        region = request.query_params.get("region", getattr(settings, "DEFAULT_STREAMING_REGION", "IN") or "IN")

        page_str = request.query_params.get("page", "1")
        try:
            page = max(1, int(page_str))
        except (ValueError, TypeError):
            page = 1

        # Resolve genre to canonical TMDB IDs
        genre_id = None
        target_tmdb_ids = []
        if genre:
            raw_delimiter = "|" if "|" in str(genre) else ","
            parts = [p.strip() for p in re.split(r"[,|+]", str(genre)) if p.strip()]
            for p in parts:
                if p.isdigit():
                    iv = int(p)
                    canonical_ids = [tid for tid, _ in DEFAULT_CANONICAL_GENRES]
                    if iv in canonical_ids:
                        target_tmdb_ids.append(iv)
                    else:
                        g = Genre.objects.filter(id=iv).first()
                        if g and g.tmdb_id:
                            target_tmdb_ids.append(g.tmdb_id)
                        else:
                            g_tmdb = Genre.objects.filter(tmdb_id=iv).first()
                            if g_tmdb and g_tmdb.tmdb_id:
                                target_tmdb_ids.append(g_tmdb.tmdb_id)
                            else:
                                target_tmdb_ids.append(iv)
                else:
                    g = Genre.objects.filter(name__iexact=p).first()
                    if g and g.tmdb_id:
                        target_tmdb_ids.append(g.tmdb_id)
                    else:
                        canon = {name.lower(): tid for tid, name in DEFAULT_CANONICAL_GENRES}
                        if p.lower() in canon:
                            target_tmdb_ids.append(canon[p.lower()])

            if target_tmdb_ids:
                if len(target_tmdb_ids) == 1:
                    genre_id = target_tmdb_ids[0]
                else:
                    genre_id = raw_delimiter.join(str(tid) for tid in target_tmdb_ids)

        # Attempt dynamic TMDB discovery via cached service
        from core.services.tmdb import (
            get_trending_movies,
            get_popular_movies,
            get_top_rated_movies,
            get_now_playing_movies,
            get_upcoming_movies,
            search_movies,
            discover_movies,
            get_genres_map,
            format_tmdb_movie,
        )

        if not getattr(settings, "TMDB_API_KEY", None):
            logger.info("TMDB_API_KEY unconfigured; serving discovery from local database.")
            return self._local_fallback(request, page)

        try:
            if search:
                raw_data, source = search_movies(query=search, page=page)
                # When filters are combined with search, filter search results accordingly
                if target_tmdb_ids or (language and language != "all") or (era and era != "any") or (min_rating and str(min_rating) != "any"):
                    filtered_results = []
                    results_list = raw_data.get("results", [])
                    t_set = set(target_tmdb_ids)
                    for item in results_list:
                        if not isinstance(item, dict):
                            continue
                        if t_set:
                            item_gids = set(item.get("genre_ids", []))
                            if "|" in str(genre):
                                if not item_gids.intersection(t_set):
                                    continue
                            else:
                                if not t_set.issubset(item_gids):
                                    continue
                        if language and language != "all" and item.get("original_language") != language:
                            continue
                        if min_rating and str(min_rating) != "any":
                            try:
                                if float(item.get("vote_average", 0)) < float(min_rating):
                                    continue
                            except (ValueError, TypeError):
                                pass
                        if era and era != "any":
                            era_lower = str(era).lower()
                            rdate = item.get("release_date", "")
                            ryear = int(rdate[:4]) if rdate and len(rdate) >= 4 and rdate[:4].isdigit() else None
                            if ryear is not None:
                                if era_lower in ("before_1990", "pre_1990") and ryear >= 1990:
                                    continue
                                elif era_lower == "recent" and ryear < 2020:
                                    continue
                                elif era_lower == "2010s" and not (2010 <= ryear <= 2019):
                                    continue
                                elif era_lower == "2000s" and not (2000 <= ryear <= 2009):
                                    continue
                                elif era_lower == "90s" and not (1990 <= ryear <= 1999):
                                    continue
                                elif era_lower == "classic" and ryear >= 1990:
                                    continue
                        filtered_results.append(item)
                    raw_data["results"] = filtered_results
                    raw_data["total_results"] = len(filtered_results)
            elif category == "trending":
                time_window = request.query_params.get("time_window", "day")
                raw_data, source = get_trending_movies(time_window=time_window, page=page)
            elif category == "top_rated":
                raw_data, source = get_top_rated_movies(page=page)
            elif category == "now_playing":
                raw_data, source = get_now_playing_movies(page=page)
            elif category == "upcoming":
                raw_data, source = get_upcoming_movies(page=page)
            elif category == "popular":
                raw_data, source = get_popular_movies(page=page)
            else:
                # Default discover with filters
                has_filters = bool(
                    genre_id
                    or (language and language != "all")
                    or (era and era != "any")
                    or (min_rating and str(min_rating) != "any")
                    or watch_provider_id
                )
                if not has_filters and not category:
                    # Default browse shelf
                    raw_data, source = get_popular_movies(page=page)
                else:
                    raw_data, source = discover_movies(
                        page=page,
                        language=language,
                        genre_id=genre_id,
                        sort_by=sort_by,
                        era=era,
                        min_rating=min_rating,
                        region=region,
                        watch_provider_id=watch_provider_id,
                        watch_region=region,
                    )

            results = raw_data.get("results", [])
            if era and era != "any":
                era_lower = str(era).lower()
                filtered_results = []
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    rdate = item.get("release_date", "")
                    ryear = int(rdate[:4]) if rdate and len(rdate) >= 4 and rdate[:4].isdigit() else None
                    if ryear is not None:
                        if era_lower in ("before_1990", "pre_1990", "classic") and ryear >= 1990:
                            continue
                        elif era_lower == "90s" and not (1990 <= ryear <= 1999):
                            continue
                        elif era_lower == "2000s" and not (2000 <= ryear <= 2009):
                            continue
                        elif era_lower == "2010s" and not (2010 <= ryear <= 2019):
                            continue
                        elif era_lower == "recent" and ryear < 2020:
                            continue
                    elif era_lower != "any":
                        continue
                    filtered_results.append(item)
                results = filtered_results
            tmdb_ids = [item["id"] for item in results if isinstance(item, dict) and item.get("id")]

            # Map existing local IDs
            local_movies_map = {}
            if tmdb_ids:
                local_movies_map = {
                    m.tmdb_id: m.id
                    for m in Movie.objects.filter(tmdb_id__in=tmdb_ids)
                }

            # Map user watchlist state
            user_watchlist_tmdb_ids = set()
            if request.user and request.user.is_authenticated and tmdb_ids:
                user_watchlist_tmdb_ids = set(
                    WatchlistItem.objects.filter(
                        user=request.user,
                        movie__tmdb_id__in=tmdb_ids
                    ).values_list("movie__tmdb_id", flat=True)
                )

            genres_map = get_genres_map()
            formatted_movies = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                tid = item.get("id")
                if not tid:
                    continue
                formatted = format_tmdb_movie(
                    item,
                    local_movie_id=local_movies_map.get(tid),
                    genres_map=genres_map,
                )
                formatted["is_in_watchlist"] = tid in user_watchlist_tmdb_ids
                formatted_movies.append(formatted)

            total_pages = min(int(raw_data.get("total_pages", 1)), 500)
            total_results = int(raw_data.get("total_results", len(formatted_movies)))
            has_more = page < total_pages

            return Response(
                {
                    "success": True,
                    "movies": formatted_movies,
                    "has_more": has_more,
                    "page": page,
                    "total_pages": total_pages,
                    "total_results": total_results,
                    "source": source,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.warning("TMDB dynamic discovery fallback to local database: %s", SecretRedactionFilter.redact_text(e))
            return self._local_fallback(request, page)

    def _local_fallback(self, request, page):
        """
        Graceful local fallback: queries local PostgreSQL records if TMDB is offline,
        unconfigured, or experiencing network errors.
        """
        qs = (
            Movie.objects.exclude(provenance="synthetic_fixture")
            .exclude(title__istartswith="Deck Movie")
            .exclude(title__istartswith="Bench Movie")
            .exclude(title__istartswith="Matrix Movie")
            .exclude(title__istartswith="Repro Movie")
            .exclude(title__icontains="SciFi Test")
            .prefetch_related("genres")
        )

        if qs.filter(display_ready=True).exists():
            qs = qs.filter(display_ready=True).exclude(poster_path__isnull=True).exclude(poster_path="").exclude(poster_path="/p1.jpg")

        genre = request.query_params.get("genre")
        language = request.query_params.get("language")
        era = request.query_params.get("era")
        min_rating = request.query_params.get("min_rating")
        search = request.query_params.get("search")
        watch_provider_id = request.query_params.get("watch_provider_id")

        if watch_provider_id:
            from core.services.retrieval import resolve_streaming_provider_ids
            provider_ids = [int(p) for p in re.split(r"[,|+]", str(watch_provider_id)) if p.strip().isdigit()]
            if provider_ids:
                matched_pks = resolve_streaming_provider_ids(provider_ids)
                if matched_pks:
                    qs = qs.filter(moviestreamingavailability__provider_id__in=matched_pks)
                else:
                    qs = qs.none()

        if min_rating and min_rating != "any":
            try:
                qs = qs.filter(rating__gte=float(min_rating))
            except (ValueError, TypeError):
                pass

        if language and language != "all":
            qs = qs.filter(original_language=language)

        if era and era != "any":
            era_lower = str(era).lower()
            if era_lower in ("before_1990", "pre_1990", "classic"):
                qs = qs.filter(release_date__lte="1989-12-31")
            elif era_lower == "recent":
                qs = qs.filter(release_date__year__gte=2020)
            elif era_lower == "2010s":
                qs = qs.filter(release_date__year__gte=2010, release_date__year__lte=2019)
            elif era_lower == "2000s":
                qs = qs.filter(release_date__year__gte=2000, release_date__year__lte=2009)
            elif era_lower == "90s":
                qs = qs.filter(release_date__year__gte=1990, release_date__year__lte=1999)

        if genre:
            parts = [p.strip() for p in re.split(r"[,|+]", str(genre)) if p.strip()]
            genre_queries = []
            for p in parts:
                if p.isdigit():
                    iv = int(p)
                    genre_queries.append(models.Q(genres__id=iv) | models.Q(genres__tmdb_id=iv))
                else:
                    canon = {name.lower(): tid for tid, name in DEFAULT_CANONICAL_GENRES}
                    canon_id = canon.get(p.lower())
                    if canon_id:
                        genre_queries.append(models.Q(genres__name__iexact=p) | models.Q(genres__tmdb_id=canon_id))
                    else:
                        genre_queries.append(models.Q(genres__name__iexact=p))

            if genre_queries:
                if "|" in str(genre):
                    or_q = genre_queries[0]
                    for gq in genre_queries[1:]:
                        or_q |= gq
                    qs = qs.filter(or_q)
                else:
                    for gq in genre_queries:
                        qs = qs.filter(gq)

        if search:
            qs = qs.filter(
                models.Q(title__icontains=search) | models.Q(overview__icontains=search)
            )

        qs = qs.distinct().order_by("-rating", "-vote_count", "-id")

        page_size = 20
        total_count = qs.count()
        offset = (page - 1) * page_size
        page_movies = list(qs[offset : offset + page_size])
        has_more = (offset + page_size) < total_count
        total_pages = max(1, (total_count + page_size - 1) // page_size)

        serializer = MovieSerializer(page_movies, many=True)
        return Response(
            {
                "success": True,
                "movies": serializer.data,
                "has_more": has_more,
                "page": page,
                "total_pages": total_pages,
                "total_results": total_count,
                "source": "fallback",
            },
            status=status.HTTP_200_OK,
        )


class HealthCheckView(APIView):
    """
    Lightweight, unauthenticated health check endpoint for reverse proxies,
    load balancers, and orchestrators (e.g. Render, AWS, Kubernetes).
    """
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return Response({"status": "healthy"}, status=status.HTTP_200_OK)


# -------------------------------------------------------------------
# Collaborative Screening Deck State Machine Endpoints (Workstream 5)
# -------------------------------------------------------------------

class DeckCardDeliveryView(APIView):
    """
    Delivers the active card for the requesting participant based on their independent cursor.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "Not a participant in this session"}, status=status.HTTP_403_FORBIDDEN)

        if getattr(session, "is_legacy", False):
            return Response(
                {"success": False, "is_legacy": True, "error": "Legacy session mode"},
                status=status.HTTP_200_OK
            )

        from core.services.deck_state import DeckAdvancementService, DeckStateError
        from core.services.manifest import (
            InsufficientCandidatesError,
            TransientReplenishmentError,
            ReplenishmentInProgressError,
        )
        try:
            payload = DeckAdvancementService.get_current_delivery_card(session=session, user=request.user)
            return Response({"success": True, **payload}, status=status.HTTP_200_OK)
        except TransientReplenishmentError as e:
            return Response(
                {
                    "success": False,
                    "transient_error": True,
                    "error": str(e),
                },
                status=status.HTTP_200_OK,
            )
        except ReplenishmentInProgressError as e:
            return Response(
                {
                    "success": False,
                    "replenishing": True,
                    "error": str(e),
                },
                status=status.HTTP_200_OK,
            )
        except InsufficientCandidatesError as e:
            return Response(
                {
                    "success": False,
                    "exhausted": True,
                    "proposal_required": True,
                    "error": "Eligible candidate pool exhausted (< 16). Constraint expansion required.",
                },
                status=status.HTTP_200_OK,
            )
        except DeckStateError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeckSwipeResponseView(APIView):
    """
    Records a participant's swipe response for a card in the manifest.
    Guarantees independent advancement, idempotency, and atomic joint resolution.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        card_index = request.data.get("card_index")
        movie_id = request.data.get("movie_id")
        reaction = request.data.get("reaction")

        if card_index is None or movie_id is None or reaction is None:
            return Response(
                {"success": False, "error": "card_index, movie_id, and reaction are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            card_index = int(card_index)
            movie_id = int(movie_id)
        except (ValueError, TypeError):
            return Response(
                {"success": False, "error": "card_index and movie_id must be integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.services.deck_state import (
            ConflictingResponseError,
            DeckAdvancementService,
            DeckStateError,
            InvalidCardIndexError,
            OutOfOrderResponseError,
            StaleManifestError,
        )
        from django.core.exceptions import PermissionDenied, ValidationError

        idempotency_key = (
            request.headers.get("Idempotency-Key")
            or request.headers.get("X-Idempotency-Key")
            or request.data.get("idempotency_key")
        )
        if idempotency_key:
            idempotency_key = str(idempotency_key).strip()

        try:
            result = DeckAdvancementService.record_swipe_response(
                session_id=session_id,
                user=request.user,
                card_index=card_index,
                movie_id=movie_id,
                reaction=reaction,
                idempotency_key=idempotency_key,
            )

            # Post-transaction WebSocket broadcast - only on fresh operations, never on idempotent retries
            if not result.get("idempotent"):
                channel_layer = get_channel_layer()
                if channel_layer:
                    try:
                        async_to_sync(channel_layer.group_send)(
                            f"session_{session_id}",
                            {
                                "type": "swipe_event",
                                "user_id": request.user.id,
                            }
                        )
                    except Exception as e:
                        logger.error("Failed to broadcast deck swipe event for session %s: %s", session_id, e)

                    if result.get("match_formed"):
                        movie = Movie.objects.filter(id=movie_id).first()
                        if movie:
                            poster_url = None
                            if movie.poster_path:
                                poster_url = f"https://image.tmdb.org/t/p/w780{movie.poster_path}" if not movie.poster_path.startswith("http") else movie.poster_path
                            try:
                                async_to_sync(channel_layer.group_send)(
                                    f"session_{session_id}",
                                    {
                                        "type": "match_event",
                                        "session_id": session_id,
                                        "movie_id": movie.id,
                                        "movie_title": movie.title or "Unknown Movie",
                                        "poster_url": poster_url or "",
                                        "release_year": movie.release_date.year if movie.release_date else None,
                                        "rating": movie.rating,
                                        "superlike_attribution": result.get("superlike_attribution") or "none",
                                        "match_type": result.get("match_type") or "ordinary",
                                    }
                                )
                            except Exception as e:
                                logger.error("Failed to broadcast deck match event for session %s: %s", session_id, e)

            return Response(result, status=status.HTTP_200_OK)
        except ConflictingResponseError as e:
            logger.warning(
                "Deck swipe conflict session=%s user=%s card_idx=%s movie=%s: %s",
                session_id, request.user.id, card_index, movie_id, e
            )
            return Response({"success": False, "error": str(e)}, status=status.HTTP_409_CONFLICT)
        except PermissionDenied as e:
            logger.warning(
                "Deck swipe forbidden session=%s user=%s card_idx=%s movie=%s: %s",
                session_id, request.user.id, card_index, movie_id, e
            )
            return Response({"success": False, "error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except (OutOfOrderResponseError, InvalidCardIndexError, StaleManifestError, ValidationError) as e:
            logger.warning(
                "Deck swipe rejected session=%s user=%s card_idx=%s movie=%s: %s",
                session_id, request.user.id, card_index, movie_id, e
            )
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DeckStateError as e:
            logger.warning(
                "Deck swipe error session=%s user=%s card_idx=%s movie=%s: %s",
                session_id, request.user.id, card_index, movie_id, e
            )
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class DeckSwipeUndoView(APIView):
    """
    Reverses the participant's most recent swipe response within the undo window.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        card_index = request.data.get("card_index")
        movie_id = request.data.get("movie_id")

        if card_index is None or movie_id is None:
            return Response(
                {"success": False, "error": "card_index and movie_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            card_index = int(card_index)
            movie_id = int(movie_id)
        except (ValueError, TypeError):
            return Response(
                {"success": False, "error": "card_index and movie_id must be integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        from core.services.deck_state import DeckAdvancementService, DeckStateError, UndoNotPermittedError
        from django.core.exceptions import ValidationError

        try:
            result = DeckAdvancementService.undo_card_response(
                session_id=session_id,
                user=request.user,
                card_index=card_index,
                movie_id=movie_id,
            )
            return Response(result, status=status.HTTP_200_OK)
        except (UndoNotPermittedError, ValidationError) as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except DeckStateError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# -----------------------------------------------------------------------------
# Workstream 6: Constraint Expansion Proposal & Outbox Background Worker Views
# -----------------------------------------------------------------------------

class SessionExpandConstraintsView(APIView):
    """
    Unified Endpoint for Constraint Expansion Proposals (Section 15).
    POST /api/sessions/<int:session_id>/expand-constraints/
    GET /api/sessions/<int:session_id>/expand-constraints/
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_session(self, session_id):
        try:
            return Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return None

    def get(self, request, session_id):
        session = self._get_session(session_id)
        if not session:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "You are not an authorized participant"}, status=status.HTTP_403_FORBIDDEN)

        from core.services.proposals import ProposalService
        ProposalService.reap_expired_proposals()

        from core.models import CollaborativeAgreement
        agreement = CollaborativeAgreement.objects.filter(session=session).first()
        active_prop = agreement.active_proposal if agreement else None

        from core.serializers import ConstraintExpansionProposalSerializer
        if active_prop:
            return Response({
                "success": True,
                "active_proposal": ConstraintExpansionProposalSerializer(active_prop).data
            }, status=status.HTTP_200_OK)

        from core.models import ConstraintExpansionProposal
        latest_prop = ConstraintExpansionProposal.objects.filter(session=session).first()
        return Response({
            "success": True,
            "active_proposal": None,
            "latest_proposal": ConstraintExpansionProposalSerializer(latest_prop).data if latest_prop else None
        }, status=status.HTTP_200_OK)

    def post(self, request, session_id):
        session = self._get_session(session_id)
        if not session:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "You are not an authorized participant in this session"}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get("action")
        if not action:
            return Response({"success": False, "error": "Field 'action' is required ('propose' or 'respond')"}, status=status.HTTP_400_BAD_REQUEST)

        from core.services.proposals import (
            ProposalService,
            ProposalExpiredError,
            ProposalSupersededError,
            ProposalInvalidStateError,
            ProposalPermissionDeniedError,
            ProposalNotFoundError,
        )

        try:
            if action == "propose":
                proposed_constraints = request.data.get("proposed_constraints")
                auto_approve = bool(request.data.get("auto_approve", False) or request.data.get("approve", False))
                prop = ProposalService.create_proposal(
                    session=session,
                    user=request.user,
                    proposed_constraints=proposed_constraints,
                    auto_approve=auto_approve,
                )
                return Response({
                    "success": True,
                    "proposal_id": str(prop.id),
                    "status": prop.status,
                    "expires_at": prop.expires_at.isoformat(),
                    "message": "Proposal created. Awaiting partner approval.",
                }, status=status.HTTP_201_CREATED)

            elif action == "respond":
                proposal_id = request.data.get("proposal_id")
                decision = request.data.get("decision")
                if not proposal_id or not decision:
                    return Response({"success": False, "error": "proposal_id and decision are required"}, status=status.HTTP_400_BAD_REQUEST)

                if decision == "reject":
                    decision = "decline"

                prop, queued = ProposalService.record_decision(
                    session=session,
                    user=request.user,
                    proposal_id=proposal_id,
                    decision=decision,
                )
                if queued:
                    try:
                        from core.services.outbox import ProposalExecutionWorker
                        worker = ProposalExecutionWorker()
                        worker.process_batch(max_messages=1)
                    except Exception as e:
                        logger.warning(f"Synchronous proposal outbox execution failed for {prop.id}: {e}")

                    return Response({
                        "success": True,
                        "proposal_id": str(prop.id),
                        "status": "approved_queued",
                        "message": "Dual approval confirmed. Asynchronous candidate replenishment queued.",
                    }, status=status.HTTP_200_OK)
                else:
                    msg = "Proposal declined." if decision == "decline" else "Approval recorded. Awaiting partner approval."
                    return Response({
                        "success": True,
                        "proposal_id": str(prop.id),
                        "status": prop.status,
                        "message": msg,
                    }, status=status.HTTP_200_OK)
            else:
                return Response({"success": False, "error": f"Unknown action '{action}'"}, status=status.HTTP_400_BAD_REQUEST)

        except ProposalExpiredError as e:
            return Response({"success": False, "error": str(e), "status": "expired"}, status=status.HTTP_409_CONFLICT)
        except ProposalSupersededError as e:
            return Response({"success": False, "error": str(e), "status": "superseded"}, status=status.HTTP_409_CONFLICT)
        except ProposalInvalidStateError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_409_CONFLICT)
        except ProposalPermissionDeniedError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ProposalNotFoundError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProposalListCreateView(APIView):
    """
    GET /api/sessions/<int:session_id>/proposals/
    POST /api/sessions/<int:session_id>/proposals/
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from core.services.proposals import ProposalService
        ProposalService.reap_expired_proposals()

        from core.models import ConstraintExpansionProposal
        from core.serializers import ConstraintExpansionProposalSerializer
        proposals = ConstraintExpansionProposal.objects.filter(session=session)
        serializer = ConstraintExpansionProposalSerializer(proposals, many=True)
        return Response({"success": True, "proposals": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        from core.services.proposals import ProposalService, ProposalPermissionDeniedError, ProposalInvalidStateError
        proposed_constraints = request.data.get("proposed_constraints")
        auto_approve = bool(request.data.get("auto_approve", False) or request.data.get("approve", False))

        try:
            prop = ProposalService.create_proposal(
                session=session,
                user=request.user,
                proposed_constraints=proposed_constraints,
                auto_approve=auto_approve,
            )
            from core.serializers import ConstraintExpansionProposalSerializer
            return Response({
                "success": True,
                "proposal": ConstraintExpansionProposalSerializer(prop).data,
            }, status=status.HTTP_201_CREATED)
        except ProposalPermissionDeniedError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ProposalInvalidStateError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProposalDetailView(APIView):
    """
    GET /api/sessions/<int:session_id>/proposals/<uuid:proposal_id>/
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id, proposal_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        from core.models import ConstraintExpansionProposal
        from core.serializers import ConstraintExpansionProposalSerializer
        try:
            proposal = ConstraintExpansionProposal.objects.get(id=proposal_id, session=session)
        except ConstraintExpansionProposal.DoesNotExist:
            return Response({"success": False, "error": "Proposal not found"}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "proposal": ConstraintExpansionProposalSerializer(proposal).data,
        }, status=status.HTTP_200_OK)


class ProposalDecideView(APIView):
    """
    POST /api/sessions/<int:session_id>/proposals/<uuid:proposal_id>/decide/
    POST /api/sessions/<int:session_id>/proposals/<uuid:proposal_id>/approve/
    POST /api/sessions/<int:session_id>/proposals/<uuid:proposal_id>/reject/
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    default_decision = None

    def post(self, request, session_id, proposal_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "Forbidden: You are not a session member"}, status=status.HTTP_403_FORBIDDEN)

        decision = self.default_decision or request.data.get("decision")
        if not decision:
            return Response({"success": False, "error": "Field 'decision' is required ('approve' or 'decline')"}, status=status.HTTP_400_BAD_REQUEST)

        if decision == "reject":
            decision = "decline"

        from core.services.proposals import (
            ProposalService,
            ProposalExpiredError,
            ProposalSupersededError,
            ProposalInvalidStateError,
            ProposalPermissionDeniedError,
            ProposalNotFoundError,
        )
        from core.serializers import ConstraintExpansionProposalSerializer

        try:
            prop, queued = ProposalService.record_decision(
                session=session,
                user=request.user,
                proposal_id=proposal_id,
                decision=decision,
            )
            return Response({
                "success": True,
                "proposal": ConstraintExpansionProposalSerializer(prop).data,
                "is_queued": queued,
            }, status=status.HTTP_200_OK)
        except ProposalExpiredError as e:
            return Response({"success": False, "error": str(e), "status": "expired"}, status=status.HTTP_409_CONFLICT)
        except ProposalSupersededError as e:
            return Response({"success": False, "error": str(e), "status": "superseded"}, status=status.HTTP_409_CONFLICT)
        except ProposalInvalidStateError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_409_CONFLICT)
        except ProposalPermissionDeniedError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ProposalNotFoundError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProposalApproveView(ProposalDecideView):
    default_decision = "approve"


class ProposalRejectView(ProposalDecideView):
    default_decision = "decline"


class ProposalOutboxProcessBatchView(APIView):
    """
    POST /api/sessions/<int:session_id>/proposals/process-outbox/
    Runs a batch of outbox replenishment tasks.
    Restricted to administrative/staff users only.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id=None):
        if not request.user.is_staff and not request.user.is_superuser:
            return Response(
                {"success": False, "error": "Administrative permissions required to process outbox"},
                status=status.HTTP_403_FORBIDDEN
            )
        from core.services.outbox import ProposalExecutionWorker
        max_messages = int(request.data.get("max_messages", 10))
        worker = ProposalExecutionWorker()
        summary = worker.process_batch(max_messages=max_messages)
        return Response({"success": True, "summary": summary}, status=status.HTTP_200_OK)


class SessionResetPreferencesView(APIView):
    """
    POST /api/sessions/<int:session_id>/reset-preferences/
    Resets taste questionnaire preferences for an active screening session,
    allowing participants to redefine their preferences.
    """
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = Session.objects.get(id=session_id)
        except Session.DoesNotExist:
            return Response({"success": False, "error": "Session not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user not in (session.host, session.guest):
            return Response({"success": False, "error": "Not a participant in this session"}, status=status.HTTP_403_FORBIDDEN)

        with transaction.atomic():
            session.preferences_set = False
            session.host_preferences = {}
            session.guest_preferences = {}
            session.save(update_fields=["preferences_set", "host_preferences", "guest_preferences"])

            from core.models import CollaborativeAgreement, ConstraintExpansionProposal
            agreement = CollaborativeAgreement.objects.filter(session=session).first()
            if agreement:
                if agreement.host_card_index == 0 and agreement.guest_card_index == 0:
                    agreement.deck_manifest = []
                agreement.active_proposal = None
                agreement.save()

            ConstraintExpansionProposal.objects.filter(
                session=session,
                status=ConstraintExpansionProposal.STATUS_PENDING,
            ).update(status=ConstraintExpansionProposal.STATUS_SUPERSEDED)

            def notify():
                try:
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            f"session_{session.id}",
                            {
                                "type": "preferences_event",
                                "session_id": session.id,
                                "user_id": request.user.id,
                                "preferences_set": False,
                                "host_preferences_set": False,
                                "guest_preferences_set": False,
                                "both_ready": False,
                            }
                        )
                except Exception:
                    pass

            transaction.on_commit(notify)

        return Response({"success": True, "message": "Taste parameters reset successfully."}, status=status.HTTP_200_OK)



