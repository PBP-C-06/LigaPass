import uuid
import json
import os
import requests
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.core.exceptions import ValidationError

from matches.models import Match, Team, Venue, TicketPrice
from reviews.models import Review
from bookings.models import Booking, Ticket
from matches import services
from matches.forms import MatchForm, TicketPriceFormSet

User = get_user_model()


class MatchModelsTests(TestCase):
    def setUp(self):
        self.home_team = Team.objects.create(name="Persija", league="liga_1")
        self.away_team = Team.objects.create(name="Persib", league="liga_1")
        self.venue = Venue.objects.create(name="GBK", city="Jakarta")
        self.match = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now()
        )
        self.ticket_price = TicketPrice.objects.create(
            match=self.match, seat_category="VIP", price=100.00
        )

    def test_model_str_methods(self):
        self.assertEqual(str(self.home_team), "Persija")
        self.assertEqual(str(self.venue), "GBK, Jakarta")
        self.assertIn("Persija vs Persib", str(self.match))
        self.assertIn("VIP - Persija vs Persib", str(self.ticket_price))

    def test_team_display_logo_url(self):
        team_with_url = Team.objects.create(name="Tim URL", logo_url="http://example.com/logo.png")
        self.assertEqual(team_with_url.display_logo_url, "http://example.com/logo.png")

        team_no_url = Team.objects.create(name="Tim Static", league="liga_1")
        self.assertIn("matches/images/team_logos/liga_1/tim_static.png", team_no_url.display_logo_url)
        
        team_no_name = Team.objects.create(name="", league="liga_1")
        self.assertEqual(team_no_name.static_logo_filename, "default.png")


class MatchFormsTests(TestCase):
    def setUp(self):
        self.home_team = Team.objects.create(name="Persija", league="liga_1")
        self.away_team = Team.objects.create(name="Persib", league="liga_1")
        self.venue = Venue.objects.create(name="GBK", city="Jakarta")

    def test_match_form_clean_same_team(self):
        form_data = {
            "home_team": self.home_team.id,
            "away_team": self.home_team.id,
            "venue": self.venue.id,
            "date": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        }
        form = MatchForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn("tidak boleh sama", str(form.errors))

    def test_ticket_price_formset_duplicate_category(self):
        match = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now()
        )
        formset_data = {
            'ticket_prices-TOTAL_FORMS': '2',
            'ticket_prices-INITIAL_FORMS': '0',
            'ticket_prices-0-seat_category': 'VIP',
            'ticket_prices-0-price': '100',
            'ticket_prices-0-quantity_available': '10',
            'ticket_prices-1-seat_category': 'VIP',
            'ticket_prices-1-price': '200',
            'ticket_prices-1-quantity_available': '20',
        }
        formset = TicketPriceFormSet(data=formset_data, instance=match)
        self.assertFalse(formset.is_valid())
        self.assertIn("Perbaiki data ganda", str(formset.non_form_errors()))


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
            date=timezone.now() + timezone.timedelta(days=3),
            api_id=101010
        )
        self.past_match = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() - timezone.timedelta(days=5),
            api_id=202020
        )

        self.future_ticket_price = TicketPrice.objects.create(
            match=self.future_match, seat_category="REGULAR", price=100000, quantity_available=10
        )
        
        self.past_ticket_price = TicketPrice.objects.create(
            match=self.past_match, seat_category="REGULAR", price=100000, quantity_available=10
        )

    def test_match_calendar_view_renders(self):
        url = reverse("matches:calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/calendar.html")
        self.assertIn("venues", response.context)
        self.assertIn("teams", response.context)

    def test_api_match_list_returns_paginated_list(self):
        url = reverse("matches:api_calendar")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("matches", data)
        self.assertIn("pagination", data)
        self.assertIsInstance(data["matches"], list)
        self.assertGreater(len(data["matches"]), 0)
        self.assertNotIn("grouped_matches", data)

        first_match = data["matches"][0]
        self.assertIn("id", first_match)
        self.assertIn("home_team_name", first_match)
        self.assertIn("away_team_name", first_match)
        self.assertIn("details_url", first_match)
        self.assertIn("status_key", first_match)

    def test_api_match_list_with_search_filter(self):
        url = reverse("matches:api_calendar") + "?q=Persija"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("Persija", str(response.content))
        self.assertTrue(all("Persija" in m["home_team_name"] or "Persija" in m["away_team_name"] for m in data["matches"]))

    def test_api_match_list_with_date_range(self):
        url = reverse("matches:api_calendar")
        start = (timezone.now() - timezone.timedelta(days=10)).strftime("%Y-%m-%d")
        end = (timezone.now() + timezone.timedelta(days=10)).strftime("%Y-%m-%d")
        response = self.client.get(url, {"date_start": start, "date_end": end})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["matches"]), 2)

    def test_api_match_list_with_venue_filter(self):
        url = reverse("matches:api_calendar") + f"?venue={self.venue.id}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["matches"]), 2)

    def test_api_match_list_with_status_filter(self):
        url = reverse("matches:api_calendar") + "?status=Upcoming"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["id"], str(self.future_match.id))

    def test_match_details_future(self):
        url = reverse("matches:details", args=[self.future_match.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "matches/details.html")
        self.assertIn("ticket_prices", response.context)
        self.assertFalse(response.context["can_review"])

    def test_match_details_past_with_review(self):
        review = Review.objects.create(
            match=self.past_match, user=self.user, rating=4, comment="Bagus!"
        )
        url = reverse("matches:details", args=[self.past_match.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("reviews", response.context)
        self.assertIn(review, response.context["reviews"])
        self.assertIn("avg_rating", response.context)
        self.assertEqual(response.context["avg_rating"], 4.0)

    def test_match_details_past_can_review_with_ticket(self):
        booking = Booking.objects.create(
            user=self.user,
            status="CONFIRMED",
            total_price=100000
        )
        Ticket.objects.create(
            booking=booking,
            ticket_type=self.past_ticket_price
        )
        
        self.client.force_login(self.user)
        url = reverse("matches:details", args=[self.past_match.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("can_review", response.context)
        self.assertTrue(response.context["can_review"])

    def test_match_details_past_cannot_review_no_ticket(self):
        self.client.force_login(self.user)
        url = reverse("matches:details", args=[self.past_match.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("can_review", response.context)
        self.assertFalse(response.context["can_review"])
        
    def test_match_details_past_cannot_review_not_logged_in(self):
        url = reverse("matches:details", args=[self.past_match.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("can_review", response.context)
        self.assertFalse(response.context["can_review"])

    @patch("matches.views.sync_database_with_apis")
    def test_update_matches_admin_ajax(self, mock_sync):
        mock_sync.return_value = ("Database berhasil diperbarui dari API.", "api_live")
        self.client.force_login(self.admin)
        url = reverse("matches:update_from_api")
        response = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content, 
            {"status": "success", "message": "Database berhasil diperbarui dari API.", "sync_source": "api_live"}
        )

    @patch("matches.views.sync_database_with_apis")
    def test_update_matches_admin_redirect(self, mock_sync):
        mock_sync.return_value = ("Database berhasil diperbarui.", "api_cache")
        self.client.force_login(self.admin)
        url = reverse("matches:update_from_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("matches:calendar"))
        self.assertEqual(len(list(get_messages(response.wsgi_request))), 1)

    def test_update_matches_non_admin_redirects(self):
        self.client.force_login(self.user)
        url = reverse("matches:update_from_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        
        expected_url = f'{reverse("authentication:login")}?next={reverse("matches:update_from_api")}'
        self.assertEqual(response.url, expected_url)
    
    @patch("matches.views.requests.get")
    def test_live_score_api_cached(self, mock_get):
        cache_key = f"live_score_single_{self.future_match.api_id}"
        cached_data = {"home_goals": 1, "away_goals": 2}
        cache.set(cache_key, cached_data, timeout=10)
        
        url = reverse("matches:live_score_api", args=[self.future_match.api_id])
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
        self.assertEqual(response.json()["home_goals"], 2)

    @patch("matches.views.requests.get")
    def test_live_score_api_not_found(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": {"match": None}}
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp
        
        url = reverse("matches:live_score_api", args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertIn("Match not found", response.json()["error"])

    @patch("matches.views.requests.get")
    def test_live_score_api_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("API down")
        
        url = reverse("matches:live_score_api", args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 500)
        self.assertIn("API down", response.json()["error"])
        
    def test_admin_views_redirect_non_admin(self):
        self.client.force_login(self.user)
        admin_urls = [
            reverse("matches:manage_matches"),
            reverse("matches:add_match"),
            reverse("matches:edit_match", args=[self.future_match.id]),
            reverse("matches:delete_match", args=[self.future_match.id]),
            reverse("matches:manage_teams"),
            reverse("matches:add_team"),
            reverse("matches:edit_team", args=[self.home_team.id]),
            reverse("matches:delete_team", args=[self.home_team.id]),
            reverse("matches:manage_venues"),
            reverse("matches:add_venue"),
            reverse("matches:edit_venue", args=[self.venue.id]),
            reverse("matches:delete_venue", args=[self.venue.id]),
        ]
        for url in admin_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403, f"Failed for URL: {url}")

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
        response_create = self.client.post(create_url, post_data, follow=True)
        self.assertEqual(response_create.status_code, 200)
        self.assertTrue(Team.objects.filter(name="Bali United").exists())
        team = Team.objects.get(name="Bali United")

        delete_url = reverse("matches:delete_team", args=[team.id])
        response_delete = self.client.post(delete_url, follow=True)
        self.assertEqual(response_delete.status_code, 200)
        self.assertFalse(Team.objects.filter(name="Bali United").exists())

    def test_venue_crud_views(self):
        self.client.force_login(self.admin)
        
        create_url = reverse("matches:add_venue")
        response = self.client.post(create_url, {"name": "Stadion Baru", "city": "Kota Baru"}, follow=True)
        self.assertContains(response, "berhasil ditambahkan")
        venue = Venue.objects.get(name="Stadion Baru")
        
        update_url = reverse("matches:edit_venue", args=[venue.id])
        response = self.client.post(update_url, {"name": "Stadion Update", "city": "Kota Update"}, follow=True)
        self.assertContains(response, "berhasil diperbarui")
        
        delete_url = reverse("matches:delete_venue", args=[venue.id])
        response = self.client.post(delete_url, follow=True)
        self.assertContains(response, "berhasil dihapus")
        self.assertFalse(Venue.objects.filter(name="Stadion Update").exists())

    def test_team_update_view(self):
        self.client.force_login(self.admin)
        url = reverse("matches:edit_team", args=[self.home_team.id])
        response = self.client.post(url, {"name": "Persija Updated", "league": "liga_1"}, follow=True)
        self.assertContains(response, "berhasil diperbarui")
        self.home_team.refresh_from_db()
        self.assertEqual(self.home_team.name, "Persija Updated")

    def test_match_create_admin(self):
        self.client.force_login(self.admin)
        url = reverse("matches:add_match")
        
        new_team_1 = Team.objects.create(name="RANS", league="liga_1")
        new_team_2 = Team.objects.create(name="PSIS", league="liga_1")

        post_data = {
            "home_team": new_team_1.id,
            "away_team": new_team_2.id,
            "venue": self.venue.id,
            "date": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            
            "ticket_prices-TOTAL_FORMS": 1,
            "ticket_prices-INITIAL_FORMS": 0,
            "ticket_prices-MIN_NUM_FORMS": 0,
            "ticket_prices-MAX_NUM_FORMS": 1000,
            "ticket_prices-0-seat_category": "VIP",
            "ticket_prices-0-price": 250000,
            "ticket_prices-0-quantity_available": 5,
            "ticket_prices-0-id": "",
            "ticket_prices-0-match": "",
        }
        
        response = self.client.post(url, post_data)
        
        self.assertEqual(response.status_code, 302) 
        self.assertEqual(response.url, reverse("matches:manage_matches"))
        
        new_match = Match.objects.filter(home_team=new_team_1, away_team=new_team_2)
        self.assertTrue(new_match.exists())
        self.assertTrue(TicketPrice.objects.filter(match=new_match.first(), seat_category="VIP").exists())

    def test_match_update_view(self):
        self.client.force_login(self.admin)
        url = reverse("matches:edit_match", args=[self.future_match.id])
        post_data = {
            "home_team": self.home_team.id,
            "away_team": self.away_team.id,
            "venue": self.venue.id,
            "date": self.future_match.date.strftime("%Y-%m-%dT%H:%M"),
            "home_goals": 1,
            "away_goals": 0,
            
            "ticket_prices-TOTAL_FORMS": 1,
            "ticket_prices-INITIAL_FORMS": 1,
            "ticket_prices-0-id": self.future_ticket_price.id,
            "ticket_prices-0-match": self.future_match.id,
            "ticket_prices-0-seat_category": "REGULAR",
            "ticket_prices-0-price": 150000,
            "ticket_prices-0-quantity_available": 20,
        }
        response = self.client.post(url, post_data, follow=True)
        self.assertContains(response, "berhasil diperbarui")
        self.future_match.refresh_from_db()
        self.assertEqual(self.future_match.home_goals, 1)
        self.future_ticket_price.refresh_from_db()
        self.assertEqual(self.future_ticket_price.price, 150000)

    def test_match_delete_view(self):
        self.client.force_login(self.admin)
        url = reverse("matches:delete_match", args=[self.future_match.id])
        response = self.client.post(url, follow=True)
        self.assertContains(response, "berhasil dihapus")
        self.assertFalse(Match.objects.filter(id=self.future_match.id).exists())

    def test_match_create_invalid_formset(self):
        self.client.force_login(self.admin)
        url = reverse("matches:add_match")
        post_data = {
            "home_team": self.home_team.id,
            "away_team": self.away_team.id, 
            "venue": self.venue.id,
            "date": (timezone.now() + timezone.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M"),
            "ticket_prices-TOTAL_FORMS": 1,
            "ticket_prices-INITIAL_FORMS": 0,
            "ticket_prices-0-seat_category": "VIP",
            "ticket_prices-0-price": "",
            "ticket_prices-0-quantity_available": 5,
        }
        response = self.client.post(url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gagal menambahkan harga tiket")


@override_settings(RAPID_API_KEY="test_key")
class MatchServicesTests(TestCase):
    def setUp(self):
        self.mock_json_dir = Path("./temp_test_json_dir")
        self.mock_api_cache_file = self.mock_json_dir / 'matches_backup.json'
        self.mock_db_fixture_file = self.mock_json_dir / 'db_backup.json'
        
        self.patcher_json_dir = patch.object(services, 'JSON_DIR', self.mock_json_dir)
        self.patcher_api_cache = patch.object(services, 'API_CACHE_FILE_PATH', self.mock_api_cache_file)
        self.patcher_db_fixture = patch.object(services, 'DB_FIXTURE_PATH', self.mock_db_fixture_file)
        
        self.patcher_json_dir.start()
        self.patcher_api_cache.start()
        self.patcher_db_fixture.start()
        
        os.makedirs(self.mock_json_dir, exist_ok=True)
        
        self.sample_normalized_data = [{
            'id': 123, 'date_str': '2025-10-10T10:00:00+00:00',
            'home_team': 'Persija Jakarta', 'away_team': 'Persib Bandung',
            'home_goals': None, 'away_goals': None,
            'venue': 'GBK', 'city': 'Jakarta',
            'home_team_api_id': 1, 'away_team_api_id': 2
        }]
        
        self.sample_db_fixture_data = [
            {"model": "matches.team", "pk": 1, "fields": {"name": "Persija Jakarta", "api_id": 1}},
            {"model": "matches.team", "pk": 2, "fields": {"name": "Persib Bandung", "api_id": 2}},
            {"model": "matches.venue", "pk": 1, "fields": {"name": "GBK", "city": "Jakarta"}},
            {"model": "matches.match", "pk": 1, "fields": {
                "api_id": 123, "date": "2025-10-10T10:00:00+00:00",
                "home_team": 1, "away_team": 2, "venue": 1,
                "home_goals": None, "away_goals": None
            }}
        ]
        
        self.sample_raw_api_data = [{
            'id': 123, 'status': {'utcTime': '2025-10-10T10:00:00+00:00'},
            'home': {'name': 'Persija Jakarta', 'id': 1, 'score': None},
            'away': {'name': 'Persib Bandung', 'id': 2, 'score': None},
            'venue': 'GBK', 'city': 'Jakarta'
        }]

    def tearDown(self):
        self.patcher_json_dir.stop()
        self.patcher_api_cache.stop()
        self.patcher_db_fixture.stop()
        
        if self.mock_api_cache_file.exists():
            os.remove(self.mock_api_cache_file)
        if self.mock_db_fixture_file.exists():
            os.remove(self.mock_db_fixture_file)
        if self.mock_json_dir.exists():
            os.rmdir(self.mock_json_dir)

    def test_clean_team_name(self):
        self.assertEqual(services._clean_team_name("persija jakarta"), "Persija Jakarta")
        self.assertEqual(services._clean_team_name("AREMA"), "Arema FC")
        self.assertEqual(services._clean_team_name("Unknown Team"), "Unknown Team")

    def test_normalize_match_data(self):
        normalized = services._normalize_match_data(self.sample_raw_api_data[0])
        self.assertEqual(normalized['id'], 123)
        self.assertEqual(normalized['home_team'], "Persija Jakarta")
        self.assertEqual(normalized['home_goals'], None)

    def test_normalize_match_data_with_score(self):
        raw_data = self.sample_raw_api_data[0].copy()
        raw_data['home']['score'] = 2
        raw_data['away']['score'] = '1'
        normalized = services._normalize_match_data(raw_data)
        self.assertEqual(normalized['home_goals'], 2)
        self.assertEqual(normalized['away_goals'], 1)

    def test_api_cache_save_and_load(self):
        result = services._save_to_api_cache(self.sample_normalized_data)
        self.assertTrue(result)
        self.assertTrue(self.mock_api_cache_file.exists())
        
        loaded_data = services._load_from_api_cache()
        self.assertEqual(loaded_data, self.sample_normalized_data)

    def test_load_from_api_cache_not_found(self):
        self.assertIsNone(services._load_from_api_cache())

    def test_load_from_fixture_json(self):
        with open(self.mock_db_fixture_file, 'w', encoding='utf-8') as f:
            json.dump(self.sample_db_fixture_data, f)
        
        loaded_data = services._load_from_fixture_json()
        self.assertEqual(len(loaded_data), 1)
        self.assertEqual(loaded_data[0]['id'], 123)
        self.assertEqual(loaded_data[0]['home_team'], "Persija Jakarta")

    def test_load_from_fixture_json_not_found(self):
        self.assertIsNone(services._load_from_fixture_json())

    @patch('matches.services.requests.get')
    def test_fetch_freeapi_matches_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'success', 'response': {'matches': self.sample_raw_api_data}}
        mock_resp.raise_for_status = lambda: None
        mock_get.return_value = mock_resp
        
        data = services._fetch_freeapi_matches()
        self.assertEqual(data, self.sample_raw_api_data)

    @patch('matches.services.requests.get')
    def test_fetch_freeapi_matches_http_error(self, mock_get):
        mock_resp = MagicMock(status_code=429)
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_resp)
        data = services._fetch_freeapi_matches()
        self.assertEqual(data, [])

    @patch('matches.services.requests.get')
    def test_fetch_freeapi_matches_request_exception(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException()
        data = services._fetch_freeapi_matches()
        self.assertEqual(data, [])

    @patch('matches.services._fetch_freeapi_matches')
    def test_get_sync_data_from_api(self, mock_fetch):
        mock_fetch.return_value = self.sample_raw_api_data
        data, source = services._get_sync_data()
        self.assertEqual(source, "api_live")
        self.assertEqual(data[0]['id'], 123)
        self.assertTrue(self.mock_api_cache_file.exists())

    @patch('matches.services._fetch_freeapi_matches')
    def test_get_sync_data_from_api_cache(self, mock_fetch):
        mock_fetch.return_value = []
        services._save_to_api_cache(self.sample_normalized_data)
        
        data, source = services._get_sync_data()
        self.assertEqual(source, "api_cache")
        self.assertEqual(data, self.sample_normalized_data)

    @patch('matches.services._fetch_freeapi_matches')
    def test_get_sync_data_from_db_fixture(self, mock_fetch):
        mock_fetch.return_value = []
        with open(self.mock_db_fixture_file, 'w', encoding='utf-8') as f:
            json.dump(self.sample_db_fixture_data, f)
        
        data, source = services._get_sync_data()
        self.assertEqual(source, "db_fixture")
        self.assertEqual(data[0]['id'], 123)
        self.assertTrue(self.mock_api_cache_file.exists())

    @patch('matches.services._fetch_freeapi_matches')
    def test_get_sync_data_no_source(self, mock_fetch):
        mock_fetch.return_value = []
        data, source = services._get_sync_data()
        self.assertEqual(source, "error_no_source")
        self.assertEqual(data, [])

    @patch('matches.services._get_sync_data')
    def test_sync_database_with_apis(self, mock_get_sync_data):
        mock_get_sync_data.return_value = (self.sample_normalized_data, "api_live")
        
        message, source = services.sync_database_with_apis()
        
        self.assertEqual(source, "api_live")
        self.assertIn("berhasil disinkronkan", message)
        self.assertTrue(Team.objects.filter(name="Persija Jakarta").exists())
        self.assertTrue(Team.objects.filter(name="Persib Bandung").exists())
        self.assertTrue(Venue.objects.filter(name="GBK").exists())
        self.assertTrue(Match.objects.filter(api_id=123).exists())
        
        match = Match.objects.get(api_id=123)
        self.assertEqual(match.ticket_prices.count(), 3)
        self.assertTrue(TicketPrice.objects.filter(match=match, seat_category='VVIP').exists())

    @patch('matches.services._get_sync_data')
    def test_sync_database_update_existing(self, mock_get_sync_data):
        Team.objects.create(name="Persija Jakarta", api_id=1, league='n/a')
        self.assertEqual(Team.objects.count(), 1)
        
        mock_get_sync_data.return_value = (self.sample_normalized_data, "api_live")
        services.sync_database_with_apis()
        
        self.assertEqual(Team.objects.count(), 2)
        updated_team = Team.objects.get(name="Persija Jakarta")
        self.assertEqual(updated_team.league, 'liga_1')