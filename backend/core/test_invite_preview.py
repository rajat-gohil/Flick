from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from core.models import Session, Genre

User = get_user_model()


class SessionInvitePreviewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.host = User.objects.create_user(username="rajat", password="password123")
        self.genre_scifi = Genre.objects.create(name="Sci-Fi", tmdb_id=878)
        self.genre_thriller = Genre.objects.create(name="Thriller", tmdb_id=53)

        self.session = Session.objects.create(
            code="CINE99",
            host=self.host,
            industry="bollywood",
        )
        self.session.genres.add(self.genre_scifi, self.genre_thriller)

    def test_whatsapp_crawler_receives_server_rendered_html_with_opengraph(self):
        """WhatsApp crawler must receive rich OpenGraph metadata, not a redirect."""
        response = self.client.get(
            "/j/CINE99/",
            HTTP_USER_AGENT="WhatsApp/2.21.12.21 A",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])

        content = response.content.decode("utf-8")
        self.assertIn('property="og:title"', content)
        self.assertIn("rajat invited you to Movie Night on Flick!", content)
        self.assertIn('property="og:description"', content)
        self.assertIn("Bollywood movies (Sci-Fi, Thriller)", content)
        self.assertIn('property="og:image"', content)
        self.assertIn("/og-invite.png", content)
        self.assertIn('property="og:url"', content)
        self.assertIn("/join/CINE99", content)

    def test_facebook_and_twitter_crawlers_receive_html(self):
        """Facebook and Twitter crawlers must also receive 200 HTML with metadata."""
        for ua in [
            "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
            "Twitterbot/1.0",
            "TelegramBot (like TwitterBot)",
        ]:
            response = self.client.get(f"/join/CINE99/", HTTP_USER_AGENT=ua)
            self.assertEqual(response.status_code, 200, f"Failed for {ua}")
            self.assertIn("text/html", response["Content-Type"])
            self.assertIn("rajat invited you", response.content.decode("utf-8"))

    def test_human_browser_receives_302_redirect_to_frontend(self):
        """Regular browser user is redirected immediately to the frontend join URL."""
        response = self.client.get(
            "/j/CINE99/",
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].endswith("/join/CINE99"))

    def test_nonexistent_session_gracefully_renders_fallback_metadata(self):
        """If session does not exist, crawlers still get clean fallback Flick metadata."""
        response = self.client.get(
            "/j/NONEXISTENT/",
            HTTP_USER_AGENT="WhatsApp/2.21.4 A",
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Join Movie Night on Flick", content)
        self.assertIn("/og-invite.png", content)

    def test_crawler_html_script_redirect_has_valid_js_quotes(self):
        """Script redirect must use valid JSON quotes, not HTML-escaped &quot;."""
        response = self.client.get(
            "/j/CINE99/",
            HTTP_USER_AGENT="WhatsApp/2.21.12.21 A",
        )
        content = response.content.decode("utf-8")
        self.assertIn('window.location.replace("', content)
        self.assertNotIn("window.location.replace(&quot;", content)

    def test_preview_metadata_api_returns_session_details(self):
        """Public preview metadata JSON API returns host, genres, and industry."""
        response = self.client.get("/api/sessions/CINE99/preview/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["found"])
        self.assertEqual(data["code"], "CINE99")
        self.assertEqual(data["host_name"], "rajat")
        self.assertEqual(data["industry"], "bollywood")
        self.assertIn("Sci-Fi", data["genres"])

    def test_preview_metadata_api_returns_404_for_missing_session(self):
        response = self.client.get("/api/sessions/MISSING/preview/")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()["found"])
