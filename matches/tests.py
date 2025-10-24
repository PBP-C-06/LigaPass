import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache

from matches.models import Match, Team, Venue, TicketPrice
from reviews.models import Review

User = get_user_model()


class MatchViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        uid_admin = uuid.uuid4().hex[:8]
        uid_user = uuid.uuid4().hex[:8]

        self.admin = User.objects.create_user(
            username=f"admin_{uid_admin}",
            email=f"admin_{uid_admin}@example.com",
            password="adminpass",
            role="admin"
        )

        self.user = User.objects.create_user(
            username=f"user_{uid_user}",
            email=f"user_{uid_user}@example.com",
            password="userpass",
            role="user"
        )

        self.home_team = Team.objects.create(name="Persija", league="liga_1")
        self.away_team = Team.objects.create(name="Persib", league="liga_1")
        self.venue = Venue.objects.create(name="Gelora Bung Karno", city="Jakarta")

        self.future_match = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() + timezone.timedelta(days=3)
        )
        self.past_match = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() - timezone.timedelta(days=5)
        )

        TicketPrice.objects.create(
            match=self.future_match, seat_category="REGULAR", price=100000, quantity_available=10
        )

    # --- match_calendar_view ---
    def test_match_calendar_view_renders(self):
        url = reverse("matches:calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/calendar.html")
        self.assertIn("venues", response.context)

    # --- api_match_list ---
    def test_api_match_list_grouping(self):
        url = reverse("matches:api_calendar")
        response = self.client.get(url)
        data = response.json()
        self.assertIn("grouped_matches", data)
        self.assertIn("Upcoming", data["grouped_matches"])
        self.assertIn("Past", data["grouped_matches"])

    def test_api_match_list_with_search_filter(self):
        url = reverse("matches:api_calendar") + "?q=Persija"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Persija", str(response.content))

    def test_api_match_list_with_date_range(self):
        url = reverse("matches:api_calendar")
        start = (timezone.now() - timezone.timedelta(days=10)).strftime("%Y-%m-%d")
        end = (timezone.now() + timezone.timedelta(days=10)).strftime("%Y-%m-%d")
        response = self.client.get(url, {"date_start": start, "date_end": end})
        self.assertEqual(response.status_code, 200)

    # --- match_details_view ---
    def test_match_details_future(self):
        url = reverse("matches:details", args=[self.future_match.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/details.html")
        self.assertIn("ticket_prices", response.context)

    def test_match_details_past_with_review(self):
        review = Review.objects.create(
            match=self.past_match, user=self.user, rating=4, comment="Bagus!"
        )
        url = reverse("matches:details", args=[self.past_match.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("reviews", response.context)
        self.assertIn(review, response.context["reviews"])

    # --- update_matches_view ---
    @patch("matches.views.sync_database_with_apis")
    def test_update_matches_admin_ajax(self, mock_sync):
        mock_sync.return_value = None
        self.client.force_login(self.admin)
        url = reverse("matches:update_from_api")
        response = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertJSONEqual(response.content, {"status": "success", "message": "Database pertandingan berhasil diperbarui dari API."})

    @patch("matches.views.sync_database_with_apis")
    def test_update_matches_admin_redirect(self, mock_sync):
        mock_sync.return_value = None
        self.client.force_login(self.admin)
        url = reverse("matches:update_from_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(list(get_messages(response.wsgi_request))), 1)

    def test_update_matches_non_admin_redirects(self):
        self.client.force_login(self.user)
        url = reverse("matches:update_from_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # --- live_score_api ---
    @patch("matches.views.requests.get")
    def test_live_score_api_cached(self, mock_get):
        cache_key = f"live_score_single_{self.future_match.api_id or 123}"
        cached_data = {"home_goals": 1, "away_goals": 2}
        cache.set(cache_key, cached_data, timeout=10)
        url = reverse("matches:live_score_api", args=[self.future_match.api_id or 123])
        response = self.client.get(url)
        self.assertEqual(response.json(), cached_data)
        mock_get.assert_not_called()
        cache.delete(cache_key)


    @patch("matches.views.requests.get")
    def test_live_score_api_external(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "response": {
                "match": {
                    "home": {"score": 2},
                    "away": {"score": 1},
                    "status": {"short": "FT", "long": "Full Time", "liveTime": {"long": "90:00"}}
                }
            }
        }
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp

        url = reverse("matches:live_score_api", args=[555])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("home_goals", response.json())

    # --- Team CRUD ---
    def test_team_list_view_admin(self):
        self.client.force_login(self.admin)
        url = reverse("matches:manage_teams")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/manage/team_list.html")

    def test_team_create_and_delete(self):
        self.client.force_login(self.admin)
        create_url = reverse("matches:add_team")
        post_data = {"name": "Bali United", "league": "liga_1"}
        self.client.post(create_url, post_data)
        team = Team.objects.get(name="Bali United")

        delete_url = reverse("matches:delete_team", args=[team.id])
        self.client.post(delete_url)
        self.assertFalse(Team.objects.filter(name="Bali United").exists())

    # --- Match CRUD ---
    def test_match_create_admin(self):
        self.client.force_login(self.admin)
        url = reverse("matches:add_match")
        post_data = {
            "home_team": self.home_team.id,
            "away_team": self.away_team.id,
            "venue": self.venue.id,
            "date": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "ticket_prices-TOTAL_FORMS": 1,
            "ticket_prices-INITIAL_FORMS": 0,
            "ticket_prices-MIN_NUM_FORMS": 0,
            "ticket_prices-MAX_NUM_FORMS": 1000,
            "ticket_prices-0-seat_category": "VIP",
            "ticket_prices-0-price": 250000,
            "ticket_prices-0-quantity_available": 5,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Match.objects.exists())
