from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
from django.conf import settings
from authentication.forms import RegisterForm

User = get_user_model()

class AuthenticationViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse("authentication:register")
        self.login_url = reverse("authentication:login")
        self.logout_url = reverse("authentication:logout")
        self.google_login_url = reverse("authentication:google_login")

        # Buat user normal
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
            role="user",
        )

    # ---------- REGISTER ----------
    def test_register_success(self):
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("redirect_url", json_data)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_register_invalid_password(self):
        data = {
            "username": "weakuser",
            "email": "weak@example.com",
            "password1": "123",
            "password2": "456",
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 400)
        json_data = response.json()
        self.assertEqual(json_data["status"], "error")
        self.assertIn("password2", json_data["errors"])

    def test_register_redirect_if_authenticated(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("matches:calendar"), response.url)

    # ---------- LOGIN ----------
    def test_login_success(self):
        response = self.client.post(self.login_url, {
            "username": "testuser",
            "password": "password123",
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("redirect_url", json_data)

    def test_login_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            "username": "testuser",
            "password": "wrongpass",
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.json()
        self.assertEqual(json_data["status"], "error")

    def test_login_redirect_if_authenticated(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("main:home"), response.url)

    # ---------- LOGOUT ----------
    def test_logout_get(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("matches:calendar"), response.url)

    def test_logout_post(self):
        self.client.login(username="testuser", password="password123")
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("redirect_url", json_data)

    # ---------- GOOGLE LOGIN ----------
    @patch("authentication.views.id_token.verify_oauth2_token")
    def test_google_login_success(self, mock_verify):
        mock_verify.return_value = {
            "email": "google@example.com",
            "sub": "1234567890",
            "given_name": "Google",
            "family_name": "User",
        }
        response = self.client.post(self.google_login_url, {"credential": "mocktoken"})
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "success")
        self.assertIn("redirect_url", json_data)
        self.assertTrue(User.objects.filter(email="google@example.com").exists())

    def test_google_login_missing_token(self):
        response = self.client.post(self.google_login_url, {})
        self.assertEqual(response.status_code, 400)
        json_data = response.json()
        self.assertEqual(json_data["status"], "error")
        self.assertIn("Missing credential", json_data["message"])

    def test_google_login_invalid_method(self):
        response = self.client.get(self.google_login_url)
        self.assertEqual(response.status_code, 405)
        json_data = response.json()
        self.assertEqual(json_data["status"], "error")
        self.assertIn("Invalid request method", json_data["message"])

    @patch("authentication.views.id_token.verify_oauth2_token", side_effect=ValueError("Bad Token"))
    def test_google_login_invalid_token(self, mock_verify):
        response = self.client.post(self.google_login_url, {"credential": "badtoken"})
        self.assertEqual(response.status_code, 401)
        json_data = response.json()
        self.assertEqual(json_data["status"], "error")
        self.assertIn("Invalid token", json_data["message"])

class RegisterFormTests(TestCase):
    def setUp(self):
        self.user_google = User.objects.create_user(
            username="guser",
            email="guser@example.com",
            password="pass123",
            is_google_account=True,
        )
        self.user_normal = User.objects.create_user(
            username="nuser",
            email="nuser@example.com",
            password="pass123",
        )

    def test_clean_email_valid(self):
        form = RegisterForm(data={
            "username": "newbie",
            "email": "unique@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!"
        })
        self.assertTrue(form.is_valid())  # tidak error

    def test_clean_email_already_exists(self):
        form = RegisterForm(data={
            "username": "someone",
            "email": "nuser@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!"
        })
        self.assertFalse(form.is_valid())
        self.assertIn("User with this email already exists.", form.errors["email"][0])

    def test_clean_email_google_account(self):
        form = RegisterForm(data={
            "username": "someoneelse",
            "email": "guser@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!"
        })
        self.assertFalse(form.is_valid())
        self.assertIn("registered with Google", form.errors["email"][0])