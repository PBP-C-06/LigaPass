from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from matches.models import Match, Team, Venue
from reviews.models import Review, ReviewReply
from bookings.models import Booking, Ticket, TicketPrice
import uuid

User = get_user_model()

class ReviewAndAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Buat user & admin dengan role tersimpan
        self.user = User.objects.create(username="user", email="user@example.com", role="user")
        self.user.set_password("12345")
        self.user.save()

        self.admin = User.objects.create(username="adming", email="admin@example.com", role="admin")
        self.admin.set_password("12345")
        self.admin.save()

        # Match setup
        self.home = Team.objects.create(name="Team A", league="liga_1")
        self.away = Team.objects.create(name="Team B", league="liga_1")
        self.venue = Venue.objects.create(name="GBK", city="Jakarta")
        self.match = Match.objects.create(
            id=uuid.uuid4(),
            home_team=self.home,
            away_team=self.away,
            venue=self.venue,
            date=now(),
        )

        self.ticket_price = TicketPrice.objects.create(
            match=self.match, seat_category="REGULAR", price=100000, quantity_available=100
        )
        self.booking = Booking.objects.create(
            user=self.user, status="CONFIRMED", total_price=100000, created_at=now()
        )
        self.ticket = Ticket.objects.create(booking=self.booking, ticket_type=self.ticket_price)

    # ======================
    # USER REVIEW PAGE
    # ======================
    def test_user_review_page_with_ticket(self):
        self.client.login(username="user", password="12345")
        url = reverse("reviews:user_review_page", args=[self.match.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "user_review_page.html")
        self.assertContains(res, "Review")

    def test_user_review_page_denied_without_ticket(self):
        self.client.login(username="user", password="12345")
        Ticket.objects.all().delete()
        url = reverse("reviews:user_review_page", args=[self.match.id])
        res = self.client.get(url)
        self.assertIn(res.status_code, [302, 403])

    # ======================
    # CREATE & UPDATE REVIEW
    # ======================
    def test_user_can_create_review(self):
        self.client.login(username="user", password="12345")
        url = reverse("reviews:api_create_review", args=[self.match.id])
        res = self.client.post(url, {"rating": 5, "comment": "Keren banget"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Review.objects.filter(user=self.user, match=self.match).exists())

    def test_user_cannot_review_twice(self):
        Review.objects.create(user=self.user, match=self.match, rating=4, comment="Bagus")
        self.client.login(username="user", password="12345")
        url = reverse("reviews:api_create_review", args=[self.match.id])
        res = self.client.post(url, {"rating": 5})
        self.assertEqual(res.status_code, 400)

    def test_user_can_update_review(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=2, comment="meh")
        self.client.login(username="user", password="12345")
        url = reverse("reviews:api_update_review", args=[self.match.id])
        res = self.client.post(url, {"rating": 4, "comment": "Better"})
        self.assertEqual(res.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)

    def test_user_update_invalid_json(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=2, comment="meh")
        self.client.login(username="user", password="12345")
        url = reverse("reviews:api_update_review", args=[self.match.id])
        res = self.client.post(url, "{invalid}", content_type="application/json")
        self.assertEqual(res.status_code, 400)

    # ======================
    # ADMIN REVIEW PAGE
    # ======================
    def test_admin_review_page_loads(self):
        self.client.login(username="adming", password="12345")
        url = reverse("reviews:admin_review_page", args=[self.match.id])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "admin_review_page.html")

    def test_admin_review_page_denied_for_user(self):
        self.client.login(username="user", password="12345")
        url = reverse("reviews:admin_review_page", args=[self.match.id])
        res = self.client.get(url)
        self.assertIn(res.status_code, [302, 403])

    # ======================
    # ANALYTICS ADMIN
    # ======================
    def test_admin_analytics_all_periods(self):
        self.client.login(username="adming", password="12345")
        for period in ["daily", "weekly", "monthly"]:
            res = self.client.get(reverse("reviews:api_admin_analytics_data"), {"period": period})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("revenueData", data)
            self.assertIn("ticketsData", data)

    def test_admin_analytics_page_loads(self):
        self.client.login(username="adming", password="12345")
        res = self.client.get(reverse("reviews:admin_analytics_page"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "admin_analytics.html")

    # ======================
    # ANALYTICS USER
    # ======================
    def test_user_analytics_all_periods(self):
        self.client.login(username="user", password="12345")
        for period in ["daily", "weekly", "monthly"]:
            res = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": period})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("spendingData", data)
            self.assertIn("attendance", data)
            self.assertIn("seatCount", data)

    def test_user_analytics_page_loads(self):
        self.client.login(username="user", password="12345")
        res = self.client.get(reverse("reviews:user_analytics_page"))
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "user_analytics.html")