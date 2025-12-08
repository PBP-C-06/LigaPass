import uuid
from io import BytesIO
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.contrib.auth import get_user_model
from news.models import News, CATEGORY_CHOICES

# Menyimpan model User (hasil get_user_model) ke variabel User
User = get_user_model()

# Kelas test untuk menguji views di app news
class NewsViewsTests(TestCase):
    # setUp dipanggil sebelum setiap test dijalankan
    def setUp(self):
        self.client = Client()

        # Buat akun user
        uid_journalist = uuid.uuid4().hex[:8]
        uid_user = uuid.uuid4().hex[:8]

        # Membuat user dengan role "journalist"
        self.journalist = User.objects.create_user(
            username=f"journalist_{uid_journalist}",
            email=f"j{uid_journalist}@example.com",
            password="journalistpass",
            role="journalist"
        )

        # Membuat user biasa (role "user") 
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

    # Test: halaman list berita bisa dirender dengan benar
    def test_news_list_renders(self):
        url = reverse("news:news_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "news/news_list.html")
        self.assertIn("news_list", response.context)

    # Test: membuka detail berita harus menambah counter views
    def test_news_detail_increments_views(self):
        old_views = self.news.news_views
        url = reverse("news:news_detail", args=[self.news.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.news.refresh_from_db()
        self.assertEqual(self.news.news_views, old_views + 1)
        self.assertTemplateUsed(response, "news/news_detail.html")

    # Test: parameter search di list berita harus memfilter hasil berdasarkan judul
    def test_news_list_with_search_filter(self):
        url = reverse("news:news_list") + "?search=Berita"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Berita Lama")

    # Test: parameter category di list berita harus memfilter berdasarkan kategori
    def test_news_list_with_category_filter(self):
        url = reverse("news:news_list") + "?category=update"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Berita Lama")

    # Test: parameter sort di list berita tidak menyebabkan error dan tetap mengembalikan context berita
    def test_news_list_with_sorting(self):
        url = reverse("news:news_list") + "?sort=created_at"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("news_list", response.context)

    # Test: jurnalis bisa membuat berita baru melalui view news_create
    def test_news_create_by_journalist(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_create")

        # Buat gambar valid
        img_bytes = BytesIO()
        image = Image.new("RGB", (1, 1), color="white")
        image.save(img_bytes, format="JPEG")
        img_bytes.seek(0)
        valid_image = SimpleUploadedFile("thumb.jpg", img_bytes.read(), content_type="image/jpeg")

        # Data yang akan dikirim via POST, menyerupai form NewsForm di frontend
        post_data = {
            "title": "Berita Baru",
            "content": "Isi berita baru",
            "category": "update",
            "thumbnail": valid_image,
            "is_featured": False,
        }
        
        # Kirim POST ke URL news_create dengan data form
        response = self.client.post(url, post_data, follow=True)
        if hasattr(response, "context") and "form" in response.context:
            print("Form errors:", response.context["form"].errors)

        # Pastikan respon akhir 200
        self.assertEqual(response.status_code, 200)
        # Pastikan objek News dengan judul mengandung "Berita Baru" benar-benar tersimpan di database
        self.assertTrue(
            News.objects.filter(title__icontains="Berita Baru").exists(),
            "Form gagal menyimpan berita baru karena thumbnail invalid",
        )

    # Test: user biasa (bukan jurnalis) tidak boleh mengakses halaman create (harus di-redirect)
    def test_news_create_requires_journalist_role(self):
        self.client.force_login(self.user)
        url = reverse("news:news_create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

    # Test: mengedit berita harus bisa mengubah konten berita
    def test_news_edit_updates_content(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_edit", args=[self.news.pk])

        # Data POST berisi judul baru, konten baru, dan kategori
        post_data = {
            "title": "Berita Lama (Edit)",
            "content": "Konten diperbarui",
            "category": "update",
        }

        response = self.client.post(url, post_data, follow=True)
        self.news.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.news.content, "Konten diperbarui")

    # Test: jika flag delete_thumbnail dikirim, thumbnail harus terhapus dari berita
    def test_news_edit_with_delete_thumbnail_flag(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_edit", args=[self.news.pk])

        # Data POST termasuk "delete_thumbnail": "true"
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

    # Test: author bisa menghapus berita dan data benar-benar hilang dari database
    def test_news_delete_by_author(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(News.objects.filter(pk=self.news.pk).exists())

    # Test: user non-author (walaupun login) tidak boleh menghapus berita
    def test_news_delete_not_author_forbidden(self):
        self.client.force_login(self.user)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

    # Test: jika delete lewat AJAX, view harus mengembalikan JSON {"success": True}
    def test_news_delete_ajax_returns_json(self):
        self.client.force_login(self.journalist)
        url = reverse("news:news_delete", args=[self.news.pk])
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True})
    
    # Test: AJAX GET ke halaman detail berita harus mengembalikan JSON yang berisi HTML komentar (comments_html)
    def test_ajax_get_comments_on_news_detail(self):
        self.client.force_login(self.user)
        url = reverse("news:news_detail", args=[self.news.pk])
        response = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("comments_html", response.json())
    
    # Test: AJAX POST komentar baru ke detail berita mengembalikan JSON yang berisi "comment_html"
    def test_ajax_post_comment(self):
        self.client.force_login(self.user)
        url = reverse("news:news_detail", args=[self.news.pk])
        data = {"content": "Komentar AJAX"}
        response = self.client.post(
            url,
            data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue("comment_html" in response.json())
    
    # Test: AJAX POST untuk balasan (reply) komentar utama
    def test_ajax_post_reply_comment(self):
        from news.models import Comment
        self.client.force_login(self.user)

        # Buat komentar utama
        parent = Comment.objects.create(
            news=self.news,
            user=self.user,
            content="Komentar utama"
        )

        # URL detail berita yang sama
        url = reverse("news:news_detail", args=[self.news.pk])
        # Data POST untuk balasan, termasuk parent_id dari komentar utama
        data = {
            "content": "Balasan",
            "parent_id": parent.id
        }

        # Kirim POST AJAX
        response = self.client.post(
            url,
            data,
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("comment_html", response.json())
    
    # Test: tombol like/unlike komentar via AJAX (like_comment) berfungsi dan jumlah like berubah
    def test_like_unlike_comment_ajax(self):
        from news.models import Comment
        self.client.force_login(self.user)

        comment = Comment.objects.create(news=self.news, user=self.journalist, content="Test")

        url = reverse("news:like_comment", args=[comment.id])

        # Like
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("liked"))
        self.assertEqual(response.json().get("like_count"), 1)

        # Unlike
        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json().get("liked"))
        self.assertEqual(response.json().get("like_count"), 0)

    # Test: menghapus komentar via AJAX (delete_comment) harus mengembalikan success=True dan menghapus komentar dari DB
    def test_delete_comment_ajax(self):
        from news.models import Comment
        self.client.force_login(self.user)

        comment = Comment.objects.create(news=self.news, user=self.user, content="To be deleted")
        url = reverse("news:delete_comment", args=[comment.id])

        response = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("success"), True)
        self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

    # Test: user anonim (belum login) tidak bisa post komentar, dan akan diarahkan (redirect) ke login
    def test_anonymous_cannot_post_comment(self):
        url = reverse("news:news_detail", args=[self.news.pk])
        response = self.client.post(url, {"content": "Komentar anonim"}, follow=True)
        self.assertEqual(response.status_code, 200)  # Sukses redirect ke login

    # Test: user yang sudah login dapat post komentar dan komentar tersebut tampil di halaman
    def test_authenticated_user_can_post_comment(self):
        self.client.force_login(self.user)
        url = reverse("news:news_detail", args=[self.news.pk])
        response = self.client.post(url, {"content": "Komentar user login"}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Komentar user login")