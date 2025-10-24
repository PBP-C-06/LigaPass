# Ganti nama file ini menjadi tests.py di dalam app 'reviews' kamu
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.timezone import now
from matches.models import Match, Team, Venue
from reviews.models import Review, ReviewReply
from bookings.models import Booking, Ticket, TicketPrice

User = get_user_model()


class FixedReviewAndAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # === BUAT USERS ===
        self.user = User.objects.create(username="user", email="user@example.com", role="user")
        self.user.set_password("12345")
        self.user.save()

        self.user2 = User.objects.create(username="user2", email="user2@example.com", role="user")
        self.user2.set_password("12345")
        self.user2.save()

        self.admin = User.objects.create(username="admin", email="admin@example.com", role="admin")
        self.admin.set_password("12345")
        self.admin.save()

        # === BUAT MATCH & TICKET ===
        self.home = Team.objects.create(name="Team A", league="liga_1")
        self.away = Team.objects.create(name="Team B", league="liga_1")
        self.venue = Venue.objects.create(name="GBK", city="Jakarta")

        # Match 1 (Data utama untuk tes)
        self.match = Match.objects.create(
            id=uuid.uuid4(), home_team=self.home, away_team=self.away, venue=self.venue, date=now()
        )
        self.ticket_price = TicketPrice.objects.create(
            match=self.match, seat_category="REGULAR", price=100000, quantity_available=100
        )
        self.ticket_price_vip = TicketPrice.objects.create(
            match=self.match, seat_category="VIP", price=500000, quantity_available=50
        )
        self.booking = Booking.objects.create(
            user=self.user, status="CONFIRMED", total_price=100000, created_at=now()
        )
        self.ticket = Ticket.objects.create(booking=self.booking, ticket_type=self.ticket_price)

        # Match 2 (Untuk tes user tidak punya tiket)
        self.match2 = Match.objects.create(
            id=uuid.uuid4(), home_team=self.home, away_team=self.away, venue=self.venue, date=now() + timedelta(days=1)
        )
        self.ticket_price2 = TicketPrice.objects.create(
            match=self.match2, seat_category="REGULAR", price=120000, quantity_available=100
        )
        
        # URL yang sering dipakai
        self.user_review_url = reverse("reviews:user_review_page", args=[self.match.id])
        self.create_review_url = reverse("reviews:api_create_review", args=[self.match.id])
        self.update_review_url = reverse("reviews:api_update_review", args=[self.match.id])
        self.admin_review_url = reverse("reviews:admin_review_page", args=[self.match.id])

    # ==================================
    # HELPER UNTUK MEMBUAT BOOKING
    # ==================================
    def _create_booking(self, user, amount, created_at_time, status="CONFIRMED", seat_category="REGULAR"):
        price_obj = self.ticket_price if seat_category == "REGULAR" else self.ticket_price_vip
        
        booking = Booking.objects.create(
            user=user,
            status=status,
            total_price=amount,
            created_at=created_at_time
        )
        Ticket.objects.create(booking=booking, ticket_type=price_obj)
        return booking

    # ==================================
    # TES USER REVIEW PAGE
    # ==================================
    def test_user_review_page_with_ticket(self):
        self.client.login(username="user", password="12345")
        res = self.client.get(self.user_review_url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "user_review_page.html")
        self.assertContains(res, "Review")

    def test_user_review_page_denied_without_ticket(self):
        """
        FIX: Tes ini sebelumnya mengecek 302 atau 403.
        View kamu secara eksplisit mengembalikan 403, jadi kita tes 403.
        """
        self.client.login(username="user", password="12345")
        # Hapus tiket user, pastikan dia tidak punya akses
        Ticket.objects.filter(booking__user=self.user).delete()
        
        res = self.client.get(self.user_review_url)
        self.assertEqual(res.status_code, 403)
        self.assertJSONEqual(
            res.content,
            {"ok": False, "message": "Kamu belum membeli tiket untuk pertandingan ini."}
        )

    def test_user_review_page_not_logged_in(self):
        res = self.client.get(self.user_review_url)
        self.assertEqual(res.status_code, 302) # Redirect ke login
        self.assertIn("/accounts/login/", res.url)

    # ==================================
    # TES CREATE & UPDATE REVIEW
    # ==================================
    def test_user_can_create_review(self):
        self.client.login(username="user", password="12345")
        res = self.client.post(self.create_review_url, {"rating": 5, "comment": "Keren banget"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Review.objects.filter(user=self.user, match=self.match).exists())
        self.assertIn("Review berhasil ditambahkan", res.json()["message"])

    def test_user_cannot_create_review_twice(self):
        Review.objects.create(user=self.user, match=self.match, rating=4, comment="Bagus")
        self.client.login(username="user", password="12345")
        res = self.client.post(self.create_review_url, {"rating": 5})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Kamu sudah pernah mereview", res.json()["message"])

    def test_user_cannot_create_review_without_ticket(self):
        self.client.login(username="user", password="12345")
        # User mencoba review match 2, yang dia tidak punya tiketnya
        url = reverse("reviews:api_create_review", args=[self.match2.id])
        res = self.client.post(url, {"rating": 5, "comment": "Mau nonton"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("hanya bisa mereview pertandingan yang sudah kamu beli", res.json()["message"])

    def test_api_create_review_invalid_rating(self):
        self.client.login(username="user", password="12345")
        res = self.client.post(self.create_review_url, {"rating": 6, "comment": "Invalid"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Rating harus 1–5", res.json()["message"])

    def test_api_create_review_invalid_method(self):
        self.client.login(username="user", password="12345")
        res = self.client.get(self.create_review_url) # Method GET
        self.assertEqual(res.status_code, 400) # Sesuai view: HttpResponseBadRequest

    def test_user_can_update_review_formdata(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=2, comment="meh")
        self.client.login(username="user", password="12345")
        res = self.client.post(self.update_review_url, {"rating": 4, "comment": "Better"})
        self.assertEqual(res.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, "Better")
        self.assertIn("Review berhasil diperbarui", res.json()["message"])

    def test_user_can_update_review_json(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=1, comment="jelek")
        self.client.login(username="user", password="12345")
        payload = json.dumps({"rating": 3, "comment": "Lumayan lah"})
        res = self.client.post(self.update_review_url, payload, content_type="application/json")
        
        self.assertEqual(res.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.comment, "Lumayan lah")

    def test_user_update_invalid_json(self):
        Review.objects.create(user=self.user, match=self.match, rating=2, comment="meh")
        self.client.login(username="user", password="12345")
        res = self.client.post(self.update_review_url, "{invalid json}", content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Invalid JSON format", res.json()["message"])

    def test_user_cannot_update_others_review(self):
        # Review dibuat oleh user2
        review = Review.objects.create(user=self.user2, match=self.match, rating=5, comment="Mantap")
        # Login sebagai user1
        self.client.login(username="user", password="12345")
        
        # user1 mencoba update review milik user2
        res = self.client.post(self.update_review_url, {"rating": 1, "comment": "Hack"})
        
        # View menggunakan get_object_or_404(Review, match=match, user=request.user)
        # Ini akan gagal menemukan review, sehingga mengembalikan 404
        self.assertEqual(res.status_code, 404)

    # ==================================
    # TES ADMIN REVIEW & REPLY
    # ==================================
    def test_admin_review_page_loads(self):
        self.client.login(username="admin", password="12345")
        res = self.client.get(self.admin_review_url)
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, "admin_review_page.html")

    def test_admin_review_page_denied_for_user(self):
        self.client.login(username="user", password="12345")
        res = self.client.get(self.admin_review_url)
        self.assertEqual(res.status_code, 302) # @user_passes_test me-redirect
        self.assertIn("/accounts/login/", res.url)

    def test_admin_can_add_reply(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=5, comment="Suka")
        self.client.login(username="admin", password="12345")
        
        url = reverse("reviews:api_add_reply", args=[review.id])
        res = self.client.post(url, {"reply_text": "Terima kasih atas reviewnya!"})
        
        self.assertEqual(res.status_code, 200)
        self.assertTrue(ReviewReply.objects.filter(review=review, admin=self.admin).exists())
        self.assertIn("Balasan berhasil disimpan", res.json()["message"])

    def test_admin_cannot_reply_twice(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=5, comment="Suka")
        ReviewReply.objects.create(review=review, admin=self.admin, reply_text="Balasan pertama")
        
        self.client.login(username="admin", password="12345")
        url = reverse("reviews:api_add_reply", args=[review.id])
        res = self.client.post(url, {"reply_text": "Balasan kedua"})
        
        self.assertEqual(res.status_code, 400)
        self.assertIn("Review ini sudah memiliki balasan", res.json()["message"])

    def test_admin_cannot_add_empty_reply(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=5, comment="Suka")
        self.client.login(username="admin", password="12345")
        
        url = reverse("reviews:api_add_reply", args=[review.id])
        res = self.client.post(url, {"reply_text": "  "}) # Empty string
        
        self.assertEqual(res.status_code, 400)
        self.assertIn("Balasan tidak boleh kosong", res.json()["message"])

    def test_user_cannot_add_reply(self):
        review = Review.objects.create(user=self.user, match=self.match, rating=5, comment="Suka")
        self.client.login(username="user", password="12345") # Login sebagai user
        
        url = reverse("reviews:api_add_reply", args=[review.id])
        res = self.client.post(url, {"reply_text": "Saya user, mau reply"})
        
        self.assertEqual(res.status_code, 302) # Redirect by @user_passes_test
        self.assertFalse(ReviewReply.objects.filter(review=review).exists())

    # ==================================
    # TES ANALYTICS - AUTH
    # ==================================
    def test_analytics_pages_redirect_anon(self):
        res = self.client.get(reverse("reviews:admin_analytics_page"))
        self.assertIn("/accounts/login/", res.url)
        res = self.client.get(reverse("reviews:api_admin_analytics_data"))
        self.assertIn("/accounts/login/", res.url)
        res = self.client.get(reverse("reviews:user_analytics_page"))
        self.assertIn("/accounts/login/", res.url)
        res = self.client.get(reverse("reviews:api_user_analytics_data"))
        self.assertIn("/accounts/login/", res.url)

    def test_admin_analytics_denied_for_user(self):
        self.client.login(username="user", password="12345")
        res = self.client.get(reverse("reviews:admin_analytics_page"))
        self.assertIn("/accounts/login/", res.url) # Redirect
        res = self.client.get(reverse("reviews:api_admin_analytics_data"))
        self.assertIn("/accounts/login/", res.url) # Redirect

    def test_user_analytics_denied_for_admin(self):
        self.client.login(username="admin", password="12345")
        res = self.client.get(reverse("reviews:user_analytics_page"))
        self.assertIn("/accounts/login/", res.url) # Redirect
        res = self.client.get(reverse("reviews:api_user_analytics_data"))
        self.assertIn("/accounts/login/", res.url) # Redirect

    # ==================================
    # TES ANALYTICS - ADMIN DATA
    # ==================================
    
    @patch('django.utils.timezone.now')
    def test_admin_analytics_daily(self, mock_now):
        # Tentukan waktu "sekarang"
        TODAY = now().replace(hour=10, minute=0, second=0, microsecond=0)
        YESTERDAY = TODAY - timedelta(days=1)
        mock_now.return_value = TODAY
        
        # Buat data
        self._create_booking(self.admin, 100000, TODAY)
        self._create_booking(self.user, 50000, TODAY.replace(hour=8))
        self._create_booking(self.user, 25000, YESTERDAY) # Data kemarin
        
        self.client.login(username="admin", password="12345")
        res = self.client.get(reverse("reviews:api_admin_analytics_data"), {"period": "daily"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Hanya data HARI INI yang boleh muncul
        expected_revenue = [{"date": TODAY.strftime("%d/%m/%Y"), "total_revenue": 150000.0}]
        expected_tickets = [{"date": TODAY.strftime("%d/%m/%Y"), "tickets_sold": 2}]
        
        self.assertEqual(data["revenueData"], expected_revenue)
        self.assertEqual(data["ticketsData"], expected_tickets)

    @patch('django.utils.timezone.now')
    def test_admin_analytics_weekly(self, mock_now):
        # Tentukan "sekarang" adalah hari Rabu
        WEDNESDAY = now().replace(day=15, month=10, year=2025, hour=12) # Asumsi Rabu
        while WEDNESDAY.weekday() != 2: # 2 = Rabu
            WEDNESDAY += timedelta(days=1)
        
        MONDAY = WEDNESDAY - timedelta(days=2)
        FRIDAY = WEDNESDAY + timedelta(days=2)
        LAST_WEEK = WEDNESDAY - timedelta(days=7)
        mock_now.return_value = WEDNESDAY

        # Buat data
        self._create_booking(self.user, 100000, MONDAY)
        self._create_booking(self.admin, 50000, MONDAY)
        self._create_booking(self.user, 200000, FRIDAY)
        self._create_booking(self.user, 10000, LAST_WEEK) # Data minggu lalu
        
        self.client.login(username="admin", password="12345")
        res = self.client.get(reverse("reviews:api_admin_analytics_data"), {"period": "weekly"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Cek data revenue
        self.assertEqual(len(data["revenueData"]), 7) # Harus ada 7 hari
        self.assertEqual(data["revenueData"][0]["date"], "Senin")
        self.assertEqual(data["revenueData"][0]["total_revenue"], 150000.0) # 100k + 50k
        self.assertEqual(data["revenueData"][1]["date"], "Selasa")
        self.assertEqual(data["revenueData"][1]["total_revenue"], 0.0)
        self.assertEqual(data["revenueData"][4]["date"], "Jumat")
        self.assertEqual(data["revenueData"][4]["total_revenue"], 200000.0)
        
        # Cek data tiket
        self.assertEqual(len(data["ticketsData"]), 7)
        self.assertEqual(data["ticketsData"][0]["tickets_sold"], 2)
        self.assertEqual(data["ticketsData"][1]["tickets_sold"], 0)
        self.assertEqual(data["ticketsData"][4]["tickets_sold"], 1)

    @patch('django.utils.timezone.now')
    def test_admin_analytics_monthly(self, mock_now):
        # Tentukan "sekarang" di minggu ke-3
        TODAY = now().replace(day=17, month=10, year=2025)
        WEEK_1 = TODAY.replace(day=3)
        WEEK_3 = TODAY.replace(day=16)
        LAST_MONTH = TODAY.replace(month=9)
        mock_now.return_value = TODAY

        self._create_booking(self.user, 100000, WEEK_1) # Minggu 1
        self._create_booking(self.admin, 50000, WEEK_1) # Minggu 1
        self._create_booking(self.user, 200000, WEEK_3) # Minggu 3
        self._create_booking(self.user, 10000, LAST_MONTH) # Bulan lalu

        self.client.login(username="admin", password="12345")
        res = self.client.get(reverse("reviews:api_admin_analytics_data"), {"period": "monthly"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Asumsi view kamu membagi 4 minggu
        self.assertEqual(len(data["revenueData"]), 4)
        # Asumsi TruncWeek menempatkan WEEK_1 di index 0
        self.assertEqual(data["revenueData"][0]["total_revenue"], 150000.0) 
        self.assertEqual(data["revenueData"][1]["total_revenue"], 0.0)
        # Asumsi TruncWeek menempatkan WEEK_3 di index 2
        self.assertEqual(data["revenueData"][2]["total_revenue"], 200000.0)
        self.assertEqual(data["revenueData"][3]["total_revenue"], 0.0)
        
        self.assertEqual(len(data["ticketsData"]), 4)
        self.assertEqual(data["ticketsData"][0]["tickets_sold"], 2)
        self.assertEqual(data["ticketsData"][1]["tickets_sold"], 0)
        self.assertEqual(data["ticketsData"][2]["tickets_sold"], 1)
        self.assertEqual(data["ticketsData"][3]["tickets_sold"], 0)

    def test_admin_analytics_ignores_pending_booking(self):
        self._create_booking(self.user, 999999, now(), status="PENDING")
        
        self.client.login(username="admin", password="12345")
        res = self.client.get(reverse("reviews:api_admin_analytics_data"), {"period": "daily"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Revenue dan tiket harus 0 karena satu-satunya booking berstatus PENDING
        self.assertEqual(data["revenueData"][0]["total_revenue"], 0.0)
        self.assertEqual(data["ticketsData"][0]["tickets_sold"], 0)

    # ==================================
    # TES ANALYTICS - USER DATA
    # ==================================

    def test_user_analytics_data_isolation(self):
        # Buat booking untuk user1 (total 100k)
        # (sudah ada di setUp)
        
        # Buat booking untuk user2 (total 500k)
        self._create_booking(self.user2, 500000, now())
        
        # Login sebagai user1
        self.client.login(username="user", password="12345")
        res = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": "daily"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Data spending HARUS HANYA 100k (milik user1), BUKAN 600k
        self.assertEqual(data["spendingData"][0]["total_spent"], 100000.0)

    def test_user_analytics_seat_count(self):
        # user1 punya 1 tiket REGULAR (dari setUp)
        
        # Tambah 2 tiket VIP untuk user1
        booking_vip = Booking.objects.create(
            user=self.user, status="CONFIRMED", total_price=1000000, created_at=now()
        )
        Ticket.objects.create(booking=booking_vip, ticket_type=self.ticket_price_vip)
        Ticket.objects.create(booking=booking_vip, ticket_type=self.ticket_price_vip)
        
        self.client.login(username="user", password="12345")
        res = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": "daily"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Urutkan hasilnya untuk perbandingan yang konsisten
        seat_count = sorted(data["seatCount"], key=lambda x: x["ticket_type__seat_category"])
        
        expected = [
            {"ticket_type__seat_category": "REGULAR", "count": 1},
            {"ticket_type__seat_category": "VIP", "count": 2}
        ]
        self.assertEqual(seat_count, expected)

    def test_user_analytics_attendance(self):
        self.client.login(username="user", password="12345")

        # 1. User punya 1 tiket (dari setUp), 0 review
        res1 = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": "daily"})
        data1 = res1.json()
        self.assertEqual(data1["attendance"], {"hadir": 0, "tidak_hadir": 1})
        
        # 2. User membuat 1 review
        Review.objects.create(user=self.user, match=self.match, rating=5, comment="Hadir")
        res2 = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": "daily"})
        data2 = res2.json()
        self.assertEqual(data2["attendance"], {"hadir": 1, "tidak_hadir": 0})
        
        # 3. User beli tiket match 2 (total 2 tiket), tapi review tetap 1
        booking2 = Booking.objects.create(user=self.user, status="CONFIRMED", total_price=120000, created_at=now())
        Ticket.objects.create(booking=booking2, ticket_type=self.ticket_price2)

        res3 = self.client.get(reverse("reviews:api_user_analytics_data"), {"period": "daily"})
        data3 = res3.json()
        # View kamu menghitung "total_matches" berdasarkan tiket, jadi sekarang ada 2
        self.assertEqual(data3["attendance"], {"hadir": 1, "tidak_hadir": 1})