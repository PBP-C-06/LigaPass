from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.templatetags.static import static

from matches.models import Match, Team, Venue
from news.models import News

User = get_user_model()


class HomeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("main:home")

        # Dummy user untuk News.author
        self.user = User.objects.create_user(
            username="testing", email="testing@example.com", password="12345"
        )

        # Dummy teams & venue
        self.home_team = Team.objects.create(
            name="Home FC", logo_url="https://example.com/home.png"
        )
        self.away_team = Team.objects.create(
            name="Away FC", logo_url="https://example.com/away.png"
        )
        self.venue = Venue.objects.create(name="National Stadium", city="Jakarta")

    def test_render_without_data(self):
        """Halaman tetap bisa diakses walau tanpa data."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("hero_slides", response.context)
        self.assertEqual(list(response.context["upcoming_matches"]), [])
        self.assertEqual(response.context["latest_news"], [])

    def test_only_future_matches_displayed(self):
        """Past match tidak muncul di upcoming_matches."""
        Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() - timezone.timedelta(days=1),
        )
        future = Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() + timezone.timedelta(days=2),
        )

        response = self.client.get(self.url)
        matches = list(response.context["upcoming_matches"])
        self.assertIn(future, matches)
        self.assertTrue(all(m.date > timezone.now() for m in matches))

    def test_latest_news_featured_priority(self):
        """Berita featured diprioritaskan dan maksimal 6 total."""
        featured_news = [
            News.objects.create(
                title=f"Featured {i}",
                content="X",
                is_featured=True,
                author=self.user,
            )
            for i in range(4)
        ]
        normal_news = [
            News.objects.create(
                title=f"News {i}",
                content="Y",
                is_featured=False,
                author=self.user,
            )
            for i in range(5)
        ]

        response = self.client.get(self.url)
        latest = response.context["latest_news"]

        # total maksimal 6 (3 featured + 3 non-featured)
        self.assertLessEqual(len(latest), 6)
        # featured muncul di awal
        self.assertTrue(all(n.is_featured for n in latest[:3]))

    def test_hero_slides_integrity(self):
        """Pastikan hero slides punya struktur lengkap."""
        response = self.client.get(self.url)
        slides = response.context["hero_slides"]

        self.assertEqual(len(slides), 3)
        for slide in slides:
            self.assertIn("title", slide)
            self.assertIn("description", slide)
            self.assertIn("image", slide)
            self.assertIn("cta_text", slide)
            self.assertIn("cta_link", slide)
            self.assertTrue(slide["image"].startswith(static("images/")))

    def test_context_keys_complete(self):
        """Semua context utama tersedia dan lengkap."""
        News.objects.create(
            title="Test News",
            content="abc",
            is_featured=True,
            author=self.user,
        )
        Match.objects.create(
            home_team=self.home_team,
            away_team=self.away_team,
            venue=self.venue,
            date=timezone.now() + timezone.timedelta(days=1),
        )

        response = self.client.get(self.url)
        ctx = response.context
        self.assertIn("hero_slides", ctx)
        self.assertIn("upcoming_matches", ctx)
        self.assertIn("latest_news", ctx)
        self.assertEqual(response.status_code, 200)