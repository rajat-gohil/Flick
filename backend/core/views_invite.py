import json
import os
import re
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.views import View
from django.utils.html import escape
from core.models import Session

CRAWLER_USER_AGENTS = re.compile(
    r"(whatsapp|facebookexternalhit|twitterbot|telegrambot|applebot|discordbot|slackbot|linkedinbot|skypeuripreview|bingpreview|googlebot)",
    re.IGNORECASE,
)

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://flick-kappa.vercel.app").rstrip("/")


class SessionInvitePreviewView(View):
    """
    Server-rendered OpenGraph metadata handler for session invite links (/j/{code} or /join/{code}).
    
    Why:
    WhatsApp, iMessage, and social messaging platforms scrape HTML directly without executing JS.
    A pure Single Page Application yields a blank preview card.
    
    This view:
    1. Returns server-rendered HTML with full OpenGraph tags to messaging crawlers.
    2. Immediately 302-redirects real human browsers to the frontend React app.
    """

    def get(self, request, code, *args, **kwargs):
        session_code = (code or "").strip().upper()
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        target_url = f"{FRONTEND_URL}/join/{session_code}"

        is_crawler = bool(CRAWLER_USER_AGENTS.search(user_agent))

        # Query session details
        session = (
            Session.objects.filter(code=session_code)
            .select_related("host")
            .prefetch_related("genres")
            .first()
        )

        if session:
            host_name = session.host.username if session.host else "A friend"
            genres = [g.name for g in session.genres.all()[:3]]
            genre_desc = f" ({', '.join(genres)})" if genres else ""
            industry = f" {session.industry.capitalize()}" if session.industry else ""

            og_title = f"🎬 {host_name} invited you to Movie Night on Flick!"
            og_description = (
                f"Swipe through{industry} movies{genre_desc} together. "
                "Match on what to watch tonight in under 3 minutes — no sign-up needed!"
            )
        else:
            og_title = "🎬 Join Movie Night on Flick"
            og_description = (
                "Swipe through movies with your partner or friends. "
                "Match on what to watch tonight in under 3 minutes!"
            )

        og_image = f"{FRONTEND_URL}/og-invite.png"

        # If regular browser, redirect to frontend join route immediately
        if not is_crawler:
            return HttpResponseRedirect(target_url)

        # For crawlers (WhatsApp, Facebook, Twitter, Telegram, etc.): return rich HTML
        html_content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{escape(og_title)}</title>
    <meta name="description" content="{escape(og_description)}">

    <!-- OpenGraph Metadata -->
    <meta property="og:site_name" content="Flick">
    <meta property="og:title" content="{escape(og_title)}">
    <meta property="og:description" content="{escape(og_description)}">
    <meta property="og:image" content="{escape(og_image)}">
    <meta property="og:image:secure_url" content="{escape(og_image)}">
    <meta property="og:image:type" content="image/png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="Flick Cinema Salon Admission Pass">
    <meta property="og:url" content="{escape(target_url)}">
    <meta property="og:type" content="website">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{escape(og_title)}">
    <meta name="twitter:description" content="{escape(og_description)}">
    <meta name="twitter:image" content="{escape(og_image)}">

    <!-- Fallback Redirect -->
    <meta http-equiv="refresh" content="0;url={escape(target_url)}">
    <script>
        window.location.replace({json.dumps(target_url)});
    </script>
</head>
<body style="background:#0c100e;color:#F5F2EB;font-family:sans-serif;text-align:center;padding:40px;">
    <h2>{escape(og_title)}</h2>
    <p>{escape(og_description)}</p>
    <p><a href="{escape(target_url)}" style="color:#C5A880;font-weight:bold;">Click here to join if not redirected...</a></p>
</body>
</html>"""

        return HttpResponse(html_content, content_type="text/html; charset=utf-8")


class SessionInviteMetadataAPIView(View):
    """Lightweight public JSON metadata endpoint for edge/serverless invite link previews."""

    def get(self, request, code, *args, **kwargs):
        session_code = (code or "").strip().upper()
        session = (
            Session.objects.filter(code=session_code)
            .select_related("host")
            .prefetch_related("genres")
            .first()
        )

        if not session:
            return JsonResponse({"found": False, "code": session_code}, status=404)

        return JsonResponse({
            "found": True,
            "code": session_code,
            "host_name": session.host.username if session.host else "A friend",
            "genres": [g.name for g in session.genres.all()[:3]],
            "industry": session.industry or "",
        })
