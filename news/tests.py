import uuid
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.contrib.auth import get_user_model
from news.models import News, CATEGORY_CHOICES

User = get_user_model()


class NewsViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Buat akun user
        uid_journalist = uuid.uuid4().hex[:8]
        uid_user = uuid.uuid4().hex[:8]

        self.journalist = User.objects.create_user(
            username=f"journalist_{uid_journalist}",
            email=f"j{uid_journalist}@example.com",
            password="journalistpass",
            role="journalist"
        )

        self.user = User.objects.create_user(
            username=f"user_{uid_user}",
            email=f"u{uid_user}@example.com",
            password="userpass",
            role="user"
        )

        # Gambar dummy valid 1x1 px
        img_bytes = BytesIO()
        image = Image.new("RGB", (1, 1), color="white")
        image.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        self.image_file = SimpleUploadedFile("thumb.jpg", img_bytes.read(), content_type="image/jpeg")

        # Buat berita dummy
        self.news = News.objects.create(
            title="Berita Lama",
            content="Isi berita lama",
            category="update",
            thumbnail=self.image_file,
            author=self.journalist,
            is_featured=False
        )

    def test_news_list_renders(self):
        url = reverse("news:news_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/news_list.html")
        self.assertIn("news_list", response.context)

    def test_news_detail_increments_views(self):
        old_views = self.news.news_views
        url = reverse("news:news_detail", args=[self.news.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.news.refresh_from_db()
        self.assertEqual(self.news.news_views, old_views + 1)
        self.assertTemplateUsed(response, "news/news_detail.html")

    def test_news_list_with_search_filter(self):
        url = reverse("news:news_list") + "?search=Berita"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Berita Lama")

    def test_news_list_with_category_filter(self):
        url = reverse("news:news_list") + "?category=update"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Berita Lama")

    def test_news_list_with_sorting(self):
        url = reverse("news:news_list") + "?sort=created_at"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("news_list", response.context)

    def test_news_create_by_journalist(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_create")

        # Buat gambar valid
        img_bytes = BytesIO()
        image = Image.new("RGB", (1, 1), color="white")
        image.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        valid_image = SimpleUploadedFile("thumb.jpg", img_bytes.read(), content_type="image/jpeg")

        post_data = {
            "title": "Berita Baru",
            "content": "Isi berita baru",
            "category": "update",
            "thumbnail": valid_image,
            "is_featured": False,
        }

        response = self.client.post(url, post_data, follow=True)
        if hasattr(response, "context") and "form" in response.context:
            print("Form errors:", response.context["form"].errors)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            News.objects.filter(title__icontains="Berita Baru").exists(),
            "Form gagal menyimpan berita baru karena thumbnail invalid",
        )

    def test_news_create_requires_journalist_role(self):
        self.client.force_login(self.user)
        url = reverse("news:news_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    def test_news_edit_updates_content(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_edit", args=[self.news.pk])

        post_data = {
            "title": "Berita Lama (Edit)",
            "content": "Konten diperbarui",
            "category": "update",
        }

        response = self.client.post(url, post_data, follow=True)
        self.news.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.news.content, "Konten diperbarui")

    def test_news_edit_with_delete_thumbnail_flag(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_edit", args=[self.news.pk])

        post_data = {
            "title": "Berita Lama (No Thumbnail)",
            "content": "Isi update",
            "category": "update",
            "delete_thumbnail": "true",
        }

        response = self.client.post(url, post_data, follow=True)
        self.news.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(bool(self.news.thumbnail)) 

    def test_news_delete_by_author(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(News.objects.filter(pk=self.news.pk).exists())

    def test_news_delete_not_author_forbidden(self):
        self.client.force_login(self.user)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    def test_news_delete_ajax_returns_json(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True})
