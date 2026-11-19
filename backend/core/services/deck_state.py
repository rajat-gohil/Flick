import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction, IntegrityError
from django.db.models import F

from decimal import Decimal

from core.models import (
    CollaborativeAgreement,
    InteractionLog,
    Match,
    Movie,
    Session,
    SessionOccasionState,
    SessionStats,
    Swipe,
)
from core.services.manifest import ManifestCompilerService

logger = logging.getLogger(__name__)
matching_logger = logging.getLogger("flick.matching")

# Centrally configurable provisional defaults (Architecture Section 10)
DEFAULT_MAX_UNPARTNERED_BUFFER = getattr(settings, "MAX_UNPARTNERED_BUFFER", 5)


# -------------------------------------------------------------------
# Custom State Machine Exceptions
# -------------------------------------------------------------------

class DeckStateError(Exception):
    """Base exception for deck state machine operations."""
    pass


class InvalidCardIndexError(DeckStateError):
    """Raised when card index is outside manifest bounds or mismatched."""
    pass


class OutOfOrderResponseError(DeckStateError):
    """Raised when participant submits a response out of sequential delivery order."""
    pass


class StaleManifestError(DeckStateError):
    """Raised when submitted card does not match the active deck manifest."""
    pass


class UndoNotPermittedError(DeckStateError):
    """Raised when attempting an invalid undo (e.g. matched movie or out of window)."""
    pass


class ConflictingResponseError(DeckStateError):
    """Raised when participant submits a conflicting reaction for an already processed card."""
    pass


# -------------------------------------------------------------------
# Deck Advancement Service
# -------------------------------------------------------------------

class DeckAdvancementService:
    """
    Manages the collaborative screening card delivery, response persistence,
    and joint resolution state machine.
    
    Guarantees:
    - Decoupled Delivery: Host and Guest have independent delivery positions.
    - Idempotent Responses: Duplicate submissions do not duplicate state or re-trigger matches.
    - Atomic Joint Resolution: Cards become jointly resolved iff both participants respond.
    - PostgreSQL Concurrency: Uses select_for_update() row locking to serialize state transitions.
    """

    MAX_UNPARTNERED_BUFFER: int = DEFAULT_MAX_UNPARTNERED_BUFFER

    @classmethod
    def _get_locked_agreement(cls, session: Session) -> CollaborativeAgreement:
        """
        Retrieves CollaborativeAgreement with database row-level locking on PostgreSQL.
        """
        if connection.vendor == "postgresql":
            return CollaborativeAgreement.objects.select_for_update().get(session=session)
        return CollaborativeAgreement.objects.get(session=session)

    @classmethod
    def sync_agreement_from_session(
        cls,
        session: Session,
        agreement: CollaborativeAgreement,
    ) -> CollaborativeAgreement:
        """
        Synchronizes collaborative agreement hard constraints and soft preferences
        from the session configuration, occasion state, and participant profiles.
        Guarantees that user-selected filters (languages, genres, eras, min rating, max runtime)
        are materialized on the agreement so candidate retrieval enforces them strictly.
        """
        changed = False

        # 1. Shared Languages
        # If participants explicitly updated preferences in their taste questionnaire, prioritize them
        h_langs = session.host_preferences.get("languages", []) if session.host_preferences else []
        g_langs = session.guest_preferences.get("languages", []) if session.guest_preferences else []
        if h_langs and g_langs:
            common = [l for l in h_langs if l in g_langs]
            session_langs = common if common else (h_langs or g_langs)
        elif h_langs or g_langs:
            session_langs = h_langs or g_langs
        else:
            session_langs = list(session.selected_languages or [])
            if not session_langs and hasattr(session, "occasion_state"):
                occ = session.occasion_state
                h_occ = occ.host_occasion.get("languages", []) if occ else []
                g_occ = occ.guest_occasion.get("languages", []) if occ else []
                if h_occ and g_occ:
                    session_langs = list(set(h_occ) & set(g_occ))
                else:
                    session_langs = h_occ or g_occ

        if session_langs and agreement.shared_languages != session_langs:
            agreement.shared_languages = session_langs
            changed = True

        # 2. Required and Excluded Genres
        mutual_exclusions = dict(agreement.mutual_hard_exclusions or {})
        req_genre_ids = set()
        for p in (session.host_preferences, session.guest_preferences):
            if p and isinstance(p, dict) and p.get("genre_id"):
                try:
                    req_genre_ids.add(int(p["genre_id"]))
                except (ValueError, TypeError):
                    pass
        if not req_genre_ids:
            if hasattr(session, "genres") and session.genres.exists():
                for g in session.genres.all():
                    if g.tmdb_id:
                        req_genre_ids.add(g.tmdb_id)
            elif getattr(session, "genre", None) and session.genre and session.genre.tmdb_id:
                req_genre_ids.add(session.genre.tmdb_id)

        if req_genre_ids:
            sorted_req = sorted(list(req_genre_ids))
            if mutual_exclusions.get("required_genre_ids") != sorted_req:
                mutual_exclusions["required_genre_ids"] = sorted_req
                agreement.mutual_hard_exclusions = mutual_exclusions
                changed = True

        # 3. Shared Eras
        # Reconcile from host_preferences, guest_preferences, and occasion_state
        host_eras = []
        guest_eras = []
        if session.host_preferences:
            h_era = session.host_preferences.get("era", [])
            host_eras = h_era if isinstance(h_era, list) else ([h_era] if h_era else [])
        if session.guest_preferences:
            g_era = session.guest_preferences.get("era", [])
            guest_eras = g_era if isinstance(g_era, list) else ([g_era] if g_era else [])

        if host_eras and guest_eras:
            # Intersection of explicit participant era envelopes
            shared_eras = [e for e in host_eras if e in guest_eras]
            if not shared_eras:
                shared_eras = list(dict.fromkeys(host_eras + guest_eras))
        else:
            shared_eras = host_eras or guest_eras

        if shared_eras and agreement.shared_eras != shared_eras:
            agreement.shared_eras = shared_eras
            changed = True

        # 4. Shared Min Rating & Max Runtime
        ratings = []
        runtimes = []
        for prefs in (session.host_preferences, session.guest_preferences):
            if prefs and isinstance(prefs, dict):
                mr = prefs.get("min_rating")
                if mr is not None:
                    if isinstance(mr, (list, tuple)):
                        mr = mr[0] if mr else None
                    if mr is not None:
                        mr_clean = str(mr).strip().rstrip("+").strip()
                        try:
                            ratings.append(Decimal(mr_clean))
                        except Exception:
                            pass
                rt = prefs.get("max_runtime")
                if rt is not None:
                    if isinstance(rt, (list, tuple)):
                        rt = rt[0] if rt else None
                    if rt is not None:
                        try:
                            runtimes.append(int(rt))
                        except Exception:
                            pass

        if ratings:
            avg_rating = sum(ratings) / Decimal(len(ratings))
            if agreement.shared_min_rating != avg_rating:
                agreement.shared_min_rating = avg_rating
                changed = True

        if runtimes:
            min_runtime = min(runtimes)
            if agreement.shared_max_runtime != min_runtime:
                agreement.shared_max_runtime = min_runtime
                changed = True

        # 5. Soft Preferences
        if session.host_preferences and agreement.host_soft_preferences != session.host_preferences:
            agreement.host_soft_preferences = session.host_preferences
            changed = True
        if session.guest_preferences and agreement.guest_soft_preferences != session.guest_preferences:
            agreement.guest_soft_preferences = session.guest_preferences
            changed = True

        if changed:
            if agreement.host_card_index == 0 and agreement.guest_card_index == 0:
                agreement.deck_manifest = []
                if agreement.active_proposal:
                    agreement.active_proposal = None
            agreement.save()

        return agreement

    @classmethod
    def get_or_initialize_agreement(cls, session: Session) -> CollaborativeAgreement:
        """
        Ensures a CollaborativeAgreement exists and has an active compiled manifest.
        """
        agreement, created = CollaborativeAgreement.objects.get_or_create(session=session)
        cls.sync_agreement_from_session(session, agreement)
        if not agreement.deck_manifest:
            ManifestCompilerService.compile_and_persist_manifest(session=session, agreement=agreement)
            agreement.refresh_from_db()
        return agreement

    @classmethod
    def _build_card_payload(cls, manifest: List[Dict[str, Any]], index: int) -> Optional[Dict[str, Any]]:
        """
        Constructs a read-only card delivery payload for a given manifest index.
        Returns None if index is out of bounds or movie does not exist.
        """
        if index < 0 or index >= len(manifest):
            return None
        card_meta = manifest[index]
        movie_id = card_meta.get("movie_id")
        if not movie_id:
            return None
        movie = Movie.objects.filter(id=movie_id).first()
        if not movie:
            return None
        return {
            "card_index": index,
            "movie_id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "overview": movie.overview,
            "poster_path": movie.poster_path,
            "backdrop_path": movie.backdrop_path,
            "rating": movie.rating,
            "vote_count": movie.vote_count,
            "release_date": str(movie.release_date) if movie.release_date else None,
            "slot_type": card_meta.get("slot_type"),
            "turn": card_meta.get("turn"),
            "scores": card_meta.get("scores", {}),
        }

    @classmethod
    def get_current_delivery_card(
        cls,
        session: Session,
        user: Any,
    ) -> Dict[str, Any]:
        """
        Delivers the active card for the requesting participant based on their independent cursor,
        along with the prefetched next_card to enable instant, zero-placeholder optimistic swiping.
        Guarantees:
        - Host advancing does NOT advance or invalidate Guest cursor.
        - Reconnecting or refreshing resumes cleanly from persisted cursor.
        - Calculates partner lag and flags when buffer limit is exceeded.
        - Delivery is read-only and does not consume cards or advance cursors.
        """
        if user not in (session.host, session.guest):
            raise PermissionDenied("User is not a participant in this screening session.")

        agreement = cls.get_or_initialize_agreement(session)
        manifest = agreement.deck_manifest or []
        total_cards = len(manifest)

        is_host = (user == session.host)
        current_index = agreement.host_card_index if is_host else agreement.guest_card_index
        partner_index = agreement.guest_card_index if is_host else agreement.host_card_index

        partner_lag = max(0, current_index - partner_index)
        waiting_for_partner = (partner_lag >= cls.MAX_UNPARTNERED_BUFFER)
        is_completed = (current_index >= total_cards)

        if is_completed:
            return {
                "session_id": session.id,
                "card_index": current_index,
                "total_cards": total_cards,
                "has_more": False,
                "is_completed": True,
                "card": None,
                "next_card": None,
                "resolved_card_index": agreement.resolved_card_index,
                "host_card_index": agreement.host_card_index,
                "guest_card_index": agreement.guest_card_index,
                "partner_lag": partner_lag,
                "waiting_for_partner": False,
            }

        card_payload = cls._build_card_payload(manifest, current_index)
        if not card_payload:
            raise StaleManifestError(f"Movie referenced in manifest card {current_index} not found.")

        next_card_payload = cls._build_card_payload(manifest, current_index + 1)

        return {
            "session_id": session.id,
            "card_index": current_index,
            "total_cards": total_cards,
            "has_more": (current_index + 1 < total_cards),
            "is_completed": False,
            "card": card_payload,
            "next_card": next_card_payload,
            "resolved_card_index": agreement.resolved_card_index,
            "host_card_index": agreement.host_card_index,
            "guest_card_index": agreement.guest_card_index,
            "partner_lag": partner_lag,
            "waiting_for_partner": waiting_for_partner,
        }

    @classmethod
    def record_swipe_response(
        cls,
        session_id: int,
        user: Any,
        card_index: int,
        movie_id: int,
        reaction: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records a participant's swipe response for a card in the manifest.
        
        State-Machine Invariants:
        1. Atomic Row Lock: PostgreSQL select_for_update() on Session and Agreement.
        2. Idempotency: Duplicate submissions for an already-swiped card or matching
           idempotency_key return consistent success without duplicating Swipe records,
           re-evaluating matches, or re-dispatching WebSocket events.
        3. Sequential Ordering: Out-of-order submissions (skipping cards) raise OutOfOrderResponseError.
        4. Independent Cursors: Host's response only advances host_card_index; does not affect guest_card_index.
        5. Joint Resolution: Card transitions to JOINTLY_RESOLVED iff both participants have submitted.
        6. Resolution Cursor: resolved_card_index advances to min(host_card_index, guest_card_index).
        """
        if reaction not in {Swipe.LIKE, Swipe.DISLIKE, Swipe.SUPERLIKE}:
            raise ValidationError(f"Invalid swipe reaction: '{reaction}'.")

        idemp_cache_key = f"idemp:swipe:{session_id}:{user.id}:{idempotency_key}" if idempotency_key else None
        if idemp_cache_key:
            cached_entry = cache.get(idemp_cache_key)
            if cached_entry:
                if isinstance(cached_entry, dict) and "payload" in cached_entry:
                    if (
                        cached_entry.get("card_index") != card_index
                        or cached_entry.get("movie_id") != movie_id
                        or cached_entry.get("reaction") != reaction
                    ):
                        matching_logger.warning(
                            "Idempotency key payload mismatch: session=%s user=%s key=%s",
                            session_id, user.id, idempotency_key
                        )
                        raise ConflictingResponseError(
                            f"Idempotency key '{idempotency_key}' was already used with different swipe parameters."
                        )
                    cached_copy = dict(cached_entry["payload"])
                else:
                    cached_copy = dict(cached_entry)
                cached_copy["idempotent"] = True
                return cached_copy

        with transaction.atomic():
            # 1. Lock session and agreement
            if connection.vendor == "postgresql":
                try:
                    session = Session.objects.select_for_update().get(id=session_id)
                except Session.DoesNotExist:
                    raise ValidationError(f"Session {session_id} not found.")
            else:
                try:
                    session = Session.objects.get(id=session_id)
                except Session.DoesNotExist:
                    raise ValidationError(f"Session {session_id} not found.")

            if session.ended_at:
                raise ValidationError("Screening session has ended.")

            if user not in (session.host, session.guest):
                raise PermissionDenied("You are not part of this screening session.")

            agreement = cls._get_locked_agreement(session)
            manifest = agreement.deck_manifest or []
            total_cards = len(manifest)

            if not manifest:
                raise StaleManifestError("Session does not have an active deck manifest.")

            if card_index < 0 or card_index >= total_cards:
                raise InvalidCardIndexError(f"Card index {card_index} is out of bounds (0 to {total_cards - 1}).")

            # Validate card matches manifest entry
            expected_card = manifest[card_index]
            if expected_card["movie_id"] != movie_id:
                raise StaleManifestError(
                    f"Submitted movie_id {movie_id} does not match manifest card {card_index} (expected {expected_card['movie_id']})."
                )

            is_host = (user == session.host)
            current_cursor = agreement.host_card_index if is_host else agreement.guest_card_index
            partner_cursor = agreement.guest_card_index if is_host else agreement.host_card_index

            # 2. Idempotency & Conflict Check: Already swiped this card
            existing_swipe = Swipe.objects.filter(session=session, user=user, movie_id=movie_id).first()
            if existing_swipe:
                if existing_swipe.reaction != reaction:
                    matching_logger.warning(
                        "Conflicting deck swipe rejected: session=%s card_idx=%s movie=%s user=%s new_reaction=%s persisted_reaction=%s",
                        session.id,
                        card_index,
                        movie_id,
                        user.id,
                        reaction,
                        existing_swipe.reaction,
                    )
                    raise ConflictingResponseError(
                        f"Conflicting reaction '{reaction}' submitted for already processed card {card_index} "
                        f"(persisted reaction is '{existing_swipe.reaction}')."
                    )
                match_obj = Match.objects.filter(session=session, movie_id=movie_id).first()
                match_formed = match_obj is not None
                partner_lag = max(0, current_cursor - partner_cursor)
                waiting_for_partner = (partner_lag >= cls.MAX_UNPARTNERED_BUFFER)
                idemp_payload = {
                    "success": True,
                    "idempotent": True,
                    "card_index": card_index,
                    "current_card_index": current_cursor,
                    "jointly_resolved": (card_index < agreement.resolved_card_index),
                    "match_formed": match_formed,
                    "superlike_attribution": match_obj.superlike_attribution if match_formed else None,
                    "match_type": match_obj.match_type if match_formed else None,
                    "resolved_card_index": agreement.resolved_card_index,
                    "host_card_index": agreement.host_card_index,
                    "guest_card_index": agreement.guest_card_index,
                    "partner_lag": partner_lag,
                    "waiting_for_partner": waiting_for_partner,
                    "is_completed": (current_cursor >= total_cards),
                }
                if idemp_cache_key:
                    cache.set(idemp_cache_key, {
                        "payload": idemp_payload,
                        "card_index": card_index,
                        "movie_id": movie_id,
                        "reaction": reaction,
                    }, timeout=86400)
                cache.set(f"idemp:swipe:{session_id}:{user.id}:{card_index}:{movie_id}", idemp_payload, timeout=86400)
                return idemp_payload

            # 3. Out-of-Order Check: Attempting to skip ahead or respond out of sequence
            if card_index != current_cursor:
                raise OutOfOrderResponseError(
                    f"Out of order response. Expected card_index={current_cursor}, received {card_index}."
                )

            # 4. Record participant swipe (with concurrency safety)
            try:
                swipe = Swipe.objects.create(
                    session=session,
                    user=user,
                    movie_id=movie_id,
                    reaction=reaction,
                )
            except IntegrityError:
                # Concurrent duplicate insert resolved
                existing_swipe = Swipe.objects.filter(session=session, user=user, movie_id=movie_id).first()
                if existing_swipe:
                    if existing_swipe.reaction != reaction:
                        raise ConflictingResponseError(
                            f"Conflicting reaction '{reaction}' submitted for already processed card {card_index} "
                            f"(persisted reaction is '{existing_swipe.reaction}')."
                        )
                    match_obj = Match.objects.filter(session=session, movie_id=movie_id).first()
                    match_formed = match_obj is not None
                    partner_lag = max(0, current_cursor - partner_cursor)
                    waiting_for_partner = (partner_lag >= cls.MAX_UNPARTNERED_BUFFER)
                    idemp_payload = {
                        "success": True,
                        "idempotent": True,
                        "card_index": card_index,
                        "current_card_index": current_cursor,
                        "jointly_resolved": (card_index < agreement.resolved_card_index),
                        "match_formed": match_formed,
                        "superlike_attribution": match_obj.superlike_attribution if match_formed else None,
                        "match_type": match_obj.match_type if match_formed else None,
                        "resolved_card_index": agreement.resolved_card_index,
                        "host_card_index": agreement.host_card_index,
                        "guest_card_index": agreement.guest_card_index,
                        "partner_lag": partner_lag,
                        "waiting_for_partner": waiting_for_partner,
                        "is_completed": (current_cursor >= total_cards),
                        "card": cls._build_card_payload(manifest, current_cursor) if (current_cursor < total_cards and not waiting_for_partner) else None,
                        "next_card": cls._build_card_payload(manifest, current_cursor + 1) if (current_cursor + 1 < total_cards and not waiting_for_partner) else None,
                    }
                    if idemp_cache_key:
                        cache.set(idemp_cache_key, idemp_payload, timeout=86400)
                    cache.set(f"idemp:swipe:{session_id}:{user.id}:{card_index}:{movie_id}", idemp_payload, timeout=86400)
                    return idemp_payload

            # 5. Log interaction event for feedback/audit
            w_val = 3.0 if reaction == Swipe.SUPERLIKE else (1.0 if reaction == Swipe.LIKE else -1.2)
            InteractionLog.objects.create(
                user=user,
                session=session,
                movie_id=movie_id,
                event_type=f"swipe_{reaction}" if reaction in {Swipe.LIKE, Swipe.DISLIKE} else reaction,
                weight=w_val,
            )

            # Update session stats total swipes atomically
            SessionStats.objects.filter(session=session).update(total_swipes=F("total_swipes") + 1)

            # 6. Advance participant cursor
            new_cursor = current_cursor + 1
            if is_host:
                agreement.host_card_index = new_cursor
            else:
                agreement.guest_card_index = new_cursor

            # 7. Joint Resolution Evaluation
            partner = session.guest if is_host else session.host
            partner_swipe = Swipe.objects.filter(session=session, user=partner, movie_id=movie_id).first()

            jointly_resolved = False
            match_formed = False
            superlike_attr = None
            match_type_str = None

            if partner_swipe is not None:
                # Both participants have submitted responses for this card!
                jointly_resolved = True

                # Evaluate match conditions:
                # Both participants must have submitted positive reactions (LIKE or SUPERLIKE)
                is_my_positive = reaction in (Swipe.LIKE, Swipe.SUPERLIKE)
                is_partner_positive = partner_swipe.reaction in (Swipe.LIKE, Swipe.SUPERLIKE)

                if is_my_positive and is_partner_positive:
                    match, match_created = Match.objects.get_or_create(session=session, movie_id=movie_id)
                    match_formed = True
                    superlike_attr = match.superlike_attribution
                    match_type_str = match.match_type
                    if match_created:
                        SessionStats.objects.filter(session=session).update(total_matches=F("total_matches") + 1)
                        # Log match interaction
                        InteractionLog.objects.create(
                            user=user,
                            session=session,
                            movie_id=movie_id,
                            event_type="match",
                            weight=2.5,
                        )

                # Advance joint resolution cursor: highest contiguous resolved card index
                agreement.resolved_card_index = min(agreement.host_card_index, agreement.guest_card_index)

            # 8. Persist agreement updates atomically
            agreement.save(update_fields=["host_card_index", "guest_card_index", "resolved_card_index", "updated_at"])

            partner_lag = abs(agreement.host_card_index - agreement.guest_card_index)
            waiting_for_partner = (partner_lag >= cls.MAX_UNPARTNERED_BUFFER)
            is_completed = (agreement.host_card_index >= total_cards and agreement.guest_card_index >= total_cards)

            participant_role = "host" if is_host else "guest"
            resolution_outcome = "matched" if match_formed else ("pending" if partner_swipe is None else "no_match")
            matching_logger.info(
                "Deck swipe processed: session=%s card_idx=%s movie=%s role=%s reaction=%s partner_rx=%s outcome=%s match_formed=%s attribution=%s",
                session.id,
                card_index,
                movie_id,
                participant_role,
                reaction,
                partner_swipe.reaction if partner_swipe else None,
                resolution_outcome,
                match_formed,
                superlike_attr if match_formed else None,
            )

            active_card_payload = cls._build_card_payload(manifest, new_cursor) if (new_cursor < total_cards and not waiting_for_partner) else None
            next_card_payload = cls._build_card_payload(manifest, new_cursor + 1) if (new_cursor + 1 < total_cards and not waiting_for_partner) else None

            fresh_payload = {
                "success": True,
                "idempotent": False,
                "card_index": card_index,
                "next_card_index": new_cursor,
                "jointly_resolved": jointly_resolved,
                "match_formed": match_formed,
                "superlike_attribution": superlike_attr,
                "match_type": match_type_str,
                "resolved_card_index": agreement.resolved_card_index,
                "host_card_index": agreement.host_card_index,
                "guest_card_index": agreement.guest_card_index,
                "partner_lag": partner_lag,
                "waiting_for_partner": waiting_for_partner,
                "is_completed": is_completed,
                "card": active_card_payload,
                "next_card": next_card_payload,
            }
            if idemp_cache_key:
                cache.set(idemp_cache_key, {
                    "payload": fresh_payload,
                    "card_index": card_index,
                    "movie_id": movie_id,
                    "reaction": reaction,
                }, timeout=86400)
            cache.set(f"idemp:swipe:{session_id}:{user.id}:{card_index}:{movie_id}", fresh_payload, timeout=86400)
            return fresh_payload

    @classmethod
    def undo_card_response(
        cls,
        session_id: int,
        user: Any,
        card_index: int,
        movie_id: int,
    ) -> Dict[str, Any]:
        """
        Reverses a participant's most recent swipe response within the undo window.
        Guarantees:
        - Can only undo the immediately preceding card for that participant.
        - Cannot undo if a mutual match was already formed for this movie.
        - Regresses participant cursor and joint resolution cursor safely.
        - Logs an undo event in InteractionLog.
        """
        with transaction.atomic():
            if connection.vendor == "postgresql":
                try:
                    session = Session.objects.select_for_update().get(id=session_id)
                except Session.DoesNotExist:
                    raise ValidationError(f"Session {session_id} not found.")
            else:
                try:
                    session = Session.objects.get(id=session_id)
                except Session.DoesNotExist:
                    raise ValidationError(f"Session {session_id} not found.")

            agreement = cls._get_locked_agreement(session)
            is_host = (user == session.host)
            current_cursor = agreement.host_card_index if is_host else agreement.guest_card_index

            expected_undo_index = current_cursor - 1
            if card_index != expected_undo_index:
                raise UndoNotPermittedError(
                    f"Can only undo the most recent card (expected index {expected_undo_index}, got {card_index})."
                )

            # Block undo if a match already exists for this movie
            if Match.objects.filter(session=session, movie_id=movie_id).exists():
                raise UndoNotPermittedError("Cannot undo a swipe once a mutual match has been formed.")

            # Delete the user's swipe
            Swipe.objects.filter(session=session, user=user, movie_id=movie_id).delete()

            # Record undo interaction
            InteractionLog.objects.create(
                user=user,
                session=session,
                movie_id=movie_id,
                event_type="undo",
                weight=0.0,
            )

            # Regress cursor
            if is_host:
                agreement.host_card_index = card_index
            else:
                agreement.guest_card_index = card_index

            # Re-evaluate resolution cursor
            agreement.resolved_card_index = min(agreement.host_card_index, agreement.guest_card_index)
            agreement.save(update_fields=["host_card_index", "guest_card_index", "resolved_card_index", "updated_at"])

            manifest = agreement.deck_manifest or []
            return {
                "success": True,
                "card_index": card_index,
                "host_card_index": agreement.host_card_index,
                "guest_card_index": agreement.guest_card_index,
                "resolved_card_index": agreement.resolved_card_index,
                "card": cls._build_card_payload(manifest, card_index),
                "next_card": cls._build_card_payload(manifest, card_index + 1),
            }
