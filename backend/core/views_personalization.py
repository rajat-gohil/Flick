"""
Views for Personalization Surfaces, Curators Selection, Your Archive Shelves,
and Complete Unpersonalized Catalogue.

Endpoints:
- CuratorsSelectionView: /api/curators-selection/
- YourArchiveView: /api/your-archive/
- CompleteCatalogueView: /api/catalogue/
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Set

from django.db import models
from django.db.models import Q
from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Genre, Movie
from core.serializers import MovieSerializer
from core.services.archive_shelves import TMDB_GENRE_MAP, ArchiveShelvesService

logger = logging.getLogger(__name__)


class CuratorsSelectionView(APIView):
    """
    Curator's Selection endpoint.
    GET /api/curators-selection/

    - Authenticated or guest session user.
    - Returns 5-10 high-confidence personalized movies with rich explanations.
    - Honest cold-start fallback if confidence is COLD_START.
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        limit_param = request.query_params.get("limit", "10")
        try:
            limit = max(5, min(int(limit_param), 20))
        except (ValueError, TypeError):
            limit = 10

        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None

        movies_out: List[Dict[str, Any]] = []
        confidence = "COLD_START"

        if user:
            try:
                from core.services.recommendation_engine import (
                    PersonalizedRecommendationEngine,
                )

                rec_res = PersonalizedRecommendationEngine.get_recommendations(
                    user=user,
                    limit=limit,
                    offset=0,
                    min_quality=0.0,
                    apply_diversity=True,
                    shelf_context="curators_selection",
                )
                confidence = rec_res.get("confidence", "COLD_START")
                raw_movies = rec_res.get("movies", [])
                for m in raw_movies:
                    m_expl = getattr(m, "explanation", None) if not isinstance(m, dict) else m.get("explanation")
                    movies_out.append(ArchiveShelvesService._format_movie(m, explanation=m_expl))
                    if len(movies_out) >= limit:
                        break
            except Exception as e:
                logger.warning(f"[CuratorsSelectionView] RecommendationEngine fallback: {e}")

        # Fallback if engine unavailable or cold-start/unauthenticated
        if len(movies_out) < limit:
            remaining = limit - len(movies_out)
            seen_ids = {m.get("id") for m in movies_out if m.get("id")}
            candidates = ArchiveShelvesService._get_candidate_pool(exclude_movie_ids=seen_ids)
            fallback_items = candidates.order_by("-rating", "-vote_count", "-id")[:remaining]

            for m in fallback_items:
                expl = {
                    "reason": "Editorial Selection: Highly rated in the Flick collection",
                    "matched_signals": ["high_rating", "editorial"],
                    "confidence": "COLD_START",
                }
                movies_out.append(ArchiveShelvesService._format_movie(m, explanation=expl))

        return Response(
            {
                "success": True,
                "confidence": confidence,
                "user_id": user.id if user else None,
                "count": len(movies_out),
                "movies": movies_out,
            },
            status=status.HTTP_200_OK,
        )


class YourArchiveView(APIView):
    """
    Your Archive endpoint.
    GET /api/your-archive/

    - Authenticated users only.
    - Returns the 5 distinct, cross-shelf deduplicated archive shelves:
      1. recommended_for_you
      2. because_you_liked
      3. explore_your_genres
      4. explore_by_era
      5. outside_your_comfort_zone
    """

    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        max_shelf_param = request.query_params.get("max_per_shelf", "8")
        try:
            max_per_shelf = max(1, min(int(max_shelf_param), 20))
        except (ValueError, TypeError):
            max_per_shelf = 8

        shelves_data = ArchiveShelvesService.get_archive_shelves(
            user=request.user,
            max_per_shelf=max_per_shelf,
        )

        return Response(
            {
                "success": True,
                **shelves_data,
            },
            status=status.HTTP_200_OK,
        )


class CompleteCatalogueView(APIView):
    """
    Complete Catalogue endpoint.
    GET /api/catalogue/

    - Completely UNPERSONALIZED: Zero user taste vector bias.
    - Filtering: genre, era, language, min_rating, search.
    - Sorting: rating, popularity, release_date, title.
    - Standard pagination metadata: count, page, page_size, total_pages, results.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        # Base candidate pool: completely unpersonalized, strictly authentic catalogue
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

        # 1. Search Query
        search = request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(overview__icontains=search)
            )

        # 2. Genre Filter
        genre_param = request.query_params.get("genre", "").strip()
        if genre_param and genre_param.lower() not in ("all", "any"):
            if genre_param.isdigit():
                gid = int(genre_param)
                # Check both Genre model pk and TMDB genre id
                qs = qs.filter(
                    Q(genres__id=gid)
                    | Q(genres__tmdb_id=gid)
                ).distinct()
            else:
                canon_tid = None
                for tid, name in TMDB_GENRE_MAP.items():
                    if name.lower() == genre_param.lower():
                        canon_tid = tid
                        break
                genre_q = Q(genres__name__iexact=genre_param)
                if canon_tid:
                    genre_q |= Q(genres__tmdb_id=canon_tid)
                qs = qs.filter(genre_q).distinct()

        # 3. Era Filter
        era_param = request.query_params.get("era", "").strip().lower()
        if era_param and era_param not in ("any", "all"):
            if era_param in ("classic", "before_1990", "pre_1990"):
                qs = qs.filter(release_date__lte=date(1989, 12, 31))
            elif era_param == "90s":
                qs = qs.filter(
                    release_date__range=(date(1990, 1, 1), date(1999, 12, 31))
                )
            elif era_param == "2000s":
                qs = qs.filter(
                    release_date__range=(date(2000, 1, 1), date(2009, 12, 31))
                )
            elif era_param == "2010s":
                qs = qs.filter(
                    release_date__range=(date(2010, 1, 1), date(2019, 12, 31))
                )
            elif era_param == "recent":
                qs = qs.filter(release_date__gte=date(2020, 1, 1))

        # 4. Language Filter
        lang_param = request.query_params.get("language", "").strip().lower()
        if lang_param and lang_param not in ("all", "any"):
            qs = qs.filter(original_language__iexact=lang_param)

        # 5. Min Rating Filter
        min_rating_param = request.query_params.get("min_rating", "").strip()
        if min_rating_param and min_rating_param not in ("any", "all"):
            try:
                min_rating = float(min_rating_param)
                qs = qs.filter(rating__gte=min_rating)
            except (ValueError, TypeError):
                pass

        # 6. Streaming Provider Filter
        provider_param = (
            request.query_params.get("watch_provider_id")
            or request.query_params.get("provider")
            or ""
        ).strip()
        if provider_param:
            import re
            from core.services.retrieval import resolve_streaming_provider_ids
            provider_ids = [int(p) for p in re.split(r"[,|+]", str(provider_param)) if p.strip().isdigit()]
            if provider_ids:
                matched_pks = resolve_streaming_provider_ids(provider_ids)
                if matched_pks:
                    qs = qs.filter(moviestreamingavailability__provider_id__in=matched_pks)
                else:
                    qs = qs.none()

        # Sorting: rating, popularity, release_date, title
        sort_param = (
            request.query_params.get("sort")
            or request.query_params.get("sort_by")
            or "rating.desc"
        ).strip().lower()

        if sort_param in ("rating.desc", "-rating", "rating_desc"):
            qs = qs.order_by("-rating", "-vote_count", "-id")
        elif sort_param in ("rating.asc", "rating", "rating_asc", "+rating"):
            qs = qs.order_by("rating", "-vote_count", "id")
        elif sort_param in ("popularity.desc", "-popularity", "popularity", "popularity_desc"):
            qs = qs.order_by("-vote_count", "-rating", "-id")
        elif sort_param in ("popularity.asc", "+popularity", "popularity_asc"):
            qs = qs.order_by("vote_count", "-rating", "id")
        elif sort_param in ("release_date.desc", "-release_date", "release_date", "release_date_desc"):
            qs = qs.order_by("-release_date", "-rating", "-id")
        elif sort_param in ("release_date.asc", "+release_date", "release_date_asc"):
            qs = qs.order_by("release_date", "-rating", "id")
        elif sort_param in ("title.asc", "title", "+title", "title_asc"):
            qs = qs.order_by("title", "-rating", "id")
        elif sort_param in ("title.desc", "-title", "title_desc"):
            qs = qs.order_by("-title", "-rating", "-id")
        else:
            qs = qs.order_by("-rating", "-vote_count", "-id")

        # Standard Pagination
        count = qs.count()
        page_param = request.query_params.get("page", "1")
        page_size_param = request.query_params.get("page_size", "20")

        try:
            page = max(1, int(page_param))
        except (ValueError, TypeError):
            page = 1

        try:
            page_size = max(1, min(int(page_size_param), 100))
        except (ValueError, TypeError):
            page_size = 20

        total_pages = max(1, (count + page_size - 1) // page_size) if page_size > 0 else 1
        start = (page - 1) * page_size
        end = start + page_size

        page_results = list(qs[start:end])
        serialized = MovieSerializer(page_results, many=True).data

        return Response(
            {
                "count": count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_more": page < total_pages,
                "results": serialized,
                "movies": serialized,
            },
            status=status.HTTP_200_OK,
        )
