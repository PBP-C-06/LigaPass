import uuid
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from news.models import News
from profiles.models import Profile, AdminJournalistProfile
from django.core.files.uploadedfile import SimpleUploadedFile
import json
from django.conf import settings
from authentication.models import User
from profiles.models import AdminJournalistProfile
from profiles.hardcode_admin_and_journalist import create_default_users, hardcode_admin, hardcode_journalist
from django.db.models import Sum

User = get_user_model()

# Test untuk views
class ProfileViewsTest(TestCase):
    def setUp(self):
        self.client = Client()

        # Buat tiga role user
        self.user = User.objects.create_user(
            username="user1", email="user1@example.com", password="password", role="user"
        )
        self.admin = User.objects.create_user(
            username="admin1", email="admin1@example.com", password="password", role="admin"
        )
        self.journalist = User.objects.create_user(
            username="journalist1", email="journalist1@example.com", password="password", role="journalist"
        )

        # Buat base profile
        self.profile = Profile.objects.create(user=self.user, status="active")

        # Buat admin/journalist profile
        self.admin_profile = AdminJournalistProfile.objects.create(user=self.admin)
        self.journalist_profile = AdminJournalistProfile.objects.create(user=self.journalist)

    # Test create profile
    # Test ke halaman create profile
    def test_create_profile_get(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse("profiles:create_profile"))
        self.assertEqual(response.status_code, 200)

    # Test sukses untuk membuat profile baru
    def test_create_profile_post_success(self):
        self.client.login(username="user1", password="password")
        self.user.profile.delete()  # supaya bisa create baru
        response = self.client.post(reverse("profiles:create_profile"), {
            "date_of_birth": "2000-01-01",
            "phone": "08123456789"
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn("Profil berhasil di daftarkan", response.json()["message"])

    # Test admin tidak boleh membuat profile 
    def test_create_profile_for_admin_denied(self):
        self.client.login(username="admin1", password="password")
        response = self.client.post(reverse("profiles:create_profile"), {})
        self.assertEqual(response.status_code, 400)

    # Test journalist tidak boleh membuat profile 
    def test_create_profile_duplicate_error(self):
        self.client.login(username="user1", password="password")
        response = self.client.post(reverse("profiles:create_profile"), {})
        self.assertEqual(response.status_code, 400)

    # User menghapus profil dirinya sendiri 
    def test_delete_profile_self(self):
        self.client.login(username="user1", password="password")
        
        response = self.client.post(
            reverse("profiles:delete_profile", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("berhasil dihapus", response.json()["message"])

    # User lain mencoba menghapus profil user lain 
    def test_delete_profile_other_user_forbidden(self):
        # Login use journalist dan coba hapus user1
        self.client.login(username="journalist1", password="password")
        
        response = self.client.post(
            reverse("profiles:delete_profile", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])
        self.assertIn("tidak memiliki izin", response.json()["message"])

    # Journalist mencoba menghapus profil 
    def test_delete_profile_journalist_forbidden(self):
        # journalist mencoba untuk hapus profile user1
        self.client.login(username="journalist1", password="password")
        
        response = self.client.post(
            reverse("profiles:delete_profile", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])

    # Admin menghapus profil siapa pun 
    def test_delete_profile_admin(self):
        self.client.login(username="admin1", password="password")
        
        response = self.client.post(
            reverse("profiles:delete_profile", args=[self.user.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertIn("berhasil dihapus", response.json()["message"])

    # Test show JSON 
    def test_show_json_returns_profiles(self):
        response = self.client.get(reverse("profiles:show_json"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(isinstance(data, list))
        self.assertIn("username", data[0])

    # Test show JSON 
    # Test show JSON by Id user biasa
    def test_show_json_by_id_user(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse("profiles:show_json_by_id", args=[self.user.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.json())

    # Test show JSON by Id admin
    def test_show_json_by_id_admin(self):
        response = self.client.get(reverse("profiles:show_json_by_id", args=[self.admin.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("profile_picture", response.json())

    # Test show JSON jika id tidak ditemukan 
    def test_show_json_by_id_not_found(self):
        fake_id = uuid.uuid4() 
        response = self.client.get(reverse("profiles:show_json_by_id", args=[fake_id]))
        self.assertEqual(response.status_code, 404)

    # Test show JSON admin 
    def test_show_json_admin(self):
        response = self.client.get(reverse("profiles:show_json_admin"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.json())

    # Test show JSON journalist
    def test_show_json_journalist(self):
        response = self.client.get(reverse("profiles:show_json_journalist"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("username", response.json())

    # Test user view
    # Test user view jika user sudah login 
    def test_user_view_authenticated(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse("profiles:user_view", args=[self.user.id]))
        self.assertEqual(response.status_code, 200)

    # Test user view jika user belum login 
    def test_user_view_anonymous(self):
        response = self.client.get(reverse("profiles:user_view", args=[self.user.id]))
        self.assertEqual(response.status_code, 200)

    # Test admin view
    def test_admin_view(self):
        response = self.client.get(reverse("profiles:admin_view"))
        self.assertEqual(response.status_code, 200)

    # Test journalist view
    def test_journalist_view(self):
        response = self.client.get(reverse("profiles:journalist_view"))
        self.assertEqual(response.status_code, 200)

    # Test edit profile
    def test_edit_profile_get(self):
        self.client.login(username="user1", password="password")
        response = self.client.get(reverse("profiles:edit_profile_for_user", args=[self.user.id]))
        self.assertEqual(response.status_code, 200)

    # Test sukses untuk edit profile user
    def test_edit_profile_post_success(self):
        self.client.login(username="user1", password="password")
        response = self.client.post(reverse("profiles:edit_profile_for_user", args=[self.user.id]), {
            "first_name": "New",
            "last_name": "Name",
            "username": "newuser1",
            "email": "new@example.com",
            "phone": "0811111111",
            "date_of_birth": "2000-02-02",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["ok"], True)

    # Test tdk bisa edit profile punya user lain 
    def test_edit_profile_forbidden(self):
        self.client.login(username="user1", password="password")
        response = self.client.post(reverse("profiles:edit_profile_for_user", args=[self.admin.id]), {})
        self.assertEqual(response.status_code, 403)

    # Test admin ubah status user
    def test_admin_change_status_success(self):
        self.client.login(username="admin1", password="password")
        data = json.dumps({"status": "banned"})
        response = self.client.post(
            reverse("profiles:admin_change_status", args=[self.user.id]),
            data,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("berhasil diubah", response.json()["message"])

    # Test ubah status user tapi invalid 
    def test_admin_change_status_invalid_status(self):
        self.client.login(username="admin1", password="password")
        data = json.dumps({"status": "wrong"})
        response = self.client.post(
            reverse("profiles:admin_change_status", args=[self.user.id]),
            data,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    # Test user biasa tidak bisa ubah status yang lain 
    def test_admin_change_status_permission_denied(self):
        self.client.login(username="user1", password="password")
        data = json.dumps({"status": "active"})
        response = self.client.post(
            reverse("profiles:admin_change_status", args=[self.user.id]),
            data,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)

    # Test ubah status tapi user tidak ditemukan 
    def test_admin_change_status_user_not_found(self):
        fake_id = uuid.uuid4() 
        self.client.login(username="admin1", password="password")
        data = json.dumps({"status": "active"})
        response = self.client.post(
            reverse("profiles:admin_change_status", args=[fake_id]),
            data,
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

# Test untuk hardcode admin dan journalist
class HardcodeUsersTest(TestCase):
    @override_settings(ADMIN_PASSWORD="admin123", JOURNALIST_PASSWORD="journalist123")
    def test_hardcode_admin_creates_user_and_profile(self):
        # Hapus admin lama 
        User.objects.filter(username="admin").delete()
        self.assertFalse(User.objects.filter(username="admin").exists())

        # Jalankan hardcode
        hardcode_admin()

        # Cek  user admin berhasil dibuat dengan sesuai 
        admin_user = User.objects.get(username="admin")
        self.assertEqual(admin_user.email, "l1gapass@outlook.com")
        self.assertEqual(admin_user.role, "admin")

        # Cek profile admin berhasil dibuat dengan sesuai 
        profile = AdminJournalistProfile.objects.get(user=admin_user)
        self.assertEqual(profile.profile_picture, "images/Admin.png")

        # Cek  password admin berhasil dibuat dengan sesuai 
        self.assertTrue(admin_user.check_password(settings.ADMIN_PASSWORD))

    # Test fungsi tidak menduplikat jika dijalankan 2 kali
    @override_settings(ADMIN_PASSWORD="admin123")
    def test_hardcode_admin_does_not_duplicate(self):
        hardcode_admin()
        count_before = User.objects.count()
        hardcode_admin()
        self.assertEqual(User.objects.count(), count_before)

    # Test hardcode journalist
    @override_settings(JOURNALIST_PASSWORD="journalist123")
    def test_hardcode_journalist_creates_user_and_profile(self):
        # Hapus journalist lama
        User.objects.filter(username="journalist").delete()
        self.assertFalse(User.objects.filter(username="journalist").exists())

        # Jalankan hardcode
        hardcode_journalist()

        # Cek user journalist berhasil dibuat dengan sesuai 
        journalist_user = User.objects.get(username="journalist")
        self.assertEqual(journalist_user.email, "journalistLigaPass@gmail.com")
        self.assertEqual(journalist_user.role, "journalist")

        # Cek profile journalist berhasil dibuat dengan sesuai 
        profile = AdminJournalistProfile.objects.get(user=journalist_user)
        self.assertEqual(profile.profile_picture, "images/Journalist.png")

        # Cek password journalist berhasil dibuat dengan sesuai 
        self.assertTrue(journalist_user.check_password(settings.JOURNALIST_PASSWORD))

    # Test memanggil kedua fungsi 
    def test_create_default_users_calls_both(self):
        create_default_users(sender=None)
        self.assertTrue(User.objects.filter(username="admin").exists())
        self.assertTrue(User.objects.filter(username="journalist").exists())

# Test untuk model Profile
class ProfileModelTest(TestCase):
    # Buat user dan profile 
    def setUp(self):
        self.user = User.objects.create_user(
            username="user1",
            first_name="nadia",
            last_name="aisyah",
            password="test123",
            email="nadia@example.com"
        )
        self.profile = Profile.objects.create(user=self.user)

    # Test str return username 
    def test_str_returns_username(self):
        self.assertEqual(str(self.profile), "user1")

    # Test property full name (menggabungkan nama depan dan nama belakang)
    def test_full_name_property(self):
        self.assertEqual(self.profile.full_name, "Nadia Aisyah")

    # Test status default nya active
    def test_status_default_is_active(self):
        self.assertEqual(self.profile.status, "active")

# Test untuk model AdminJournalistProfile
class AdminJournalistProfileModelTest(TestCase):
    # Buat user dan AdminJournalistProfile 
    def setUp(self):
        self.user = User.objects.create_user(
            username="jurnal",
            first_name="jurnal",
            last_name="ist",
            password="pass123",
            email="journalist@example.com",
            role="journalist"
        )
        self.profile = AdminJournalistProfile.objects.create(
            user=self.user,
            profile_picture="images/journalist.png"
        )

    # Test str return username 
    def test_str_returns_role_and_username(self):
        self.assertEqual(str(self.profile), "journalist : jurnal")

    # Test hitung jumlah berita
    def test_news_count_returns_correct_value(self):
        # Bikin dua news punya user lalu hitung ada berapa jumlah newsnya
        News.objects.create(author=self.user, title="News1", content="Isi berita 1", news_views=5)
        News.objects.create(author=self.user, title="News2", content="Isi berita 2", news_views=7)
        self.assertEqual(self.profile.news_count, 2)

    # Test hitung jumlah news
    def test_total_news_views_returns_sum(self):
        # Bikin dua news punya user lalu hitung ada berapa total jumlah viewsnya
        News.objects.create(author=self.user, title="News1", content="Isi berita 1", news_views=5)
        News.objects.create(author=self.user, title="News2", content="Isi berita 2", news_views=7)
        total_views = self.user.news_set.aggregate(total_views=Sum('news_views'))['total_views']
        self.assertEqual(self.profile.total_news_views, total_views)

    # Test jika belum ada berita maka viewsnya 0
    def test_total_news_views_returns_zero_if_no_news(self):
        self.assertEqual(self.profile.total_news_views, 0)