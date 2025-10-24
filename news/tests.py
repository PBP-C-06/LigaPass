from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from news.models import News

User = get_user_model()

class NewsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Buat user dengan role 'journalist' dan login
        self.journalist = User.objects.create_user(
            username='journalist1',
            password='password123',
            role='journalist'
        )

        # Buat satu berita
        self.news = News.objects.create(
            title='Judul Uji',
            content='Isi konten uji',
            category='update',
            author=self.journalist
        )

    def test_news_list_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('news:news_list'))
        login_url = reverse('authentication:login')
        self.assertRedirects(response, f'{login_url}?next={reverse("news:news_list")}')

    def test_news_detail_view(self):
        self.client.login(username='journalist1', password='password123')
        response = self.client.get(reverse('news:news_detail', kwargs={'pk': self.news.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Isi konten uji')

    def test_news_list_redirects_if_not_logged_in(self):
        response = self.client.get(reverse('news:news_list'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login'))