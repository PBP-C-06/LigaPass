# news/tests.py
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import News, Comment
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image
from django.utils import timezone

User = get_user_model()

# Hardcoded journalist credentials (sesuai info kamu)
HARDCODED_JOURNALIST_USERNAME = "journalist"
HARDCODED_JOURNALIST_PASSWORD = "journalist12345journalistligapass"

def create_user(username="user", password="pass", role="reader"):
    return User.objects.create_user(username=username, password=password, role=role)

def create_journalist(username=HARDCODED_JOURNALIST_USERNAME, password=HARDCODED_JOURNALIST_PASSWORD):
    return create_user(username=username, password=password, role="journalist")

def get_image_file(name='test.png', size=(100, 100), color=(255, 0, 0)):
    """
    Return SimpleUploadedFile with a small PNG image (via Pillow) suitable for ImageField tests.
    """
    file_obj = BytesIO()
    image = Image.new("RGB", size=size, color=color)
    image.save(file_obj, 'PNG')
    file_obj.seek(0)
    return SimpleUploadedFile(name, file_obj.read(), content_type='image/png')


class NewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # create the journalist with the exact hardcoded credentials
        self.journalist = create_journalist()
        # another regular reader user
        self.reader = create_user(username="reader", password="readerpass", role="reader")
        # create a sample news item authored by journalist
        self.news = News.objects.create(
            title="Sample News",
            content="<p>Some content here</p>",
            category="update",
            is_featured=True,
            author=self.journalist
        )

    def test_news_list_view_requires_login_and_shows_news(self):
        # unauthenticated should redirect to login
        response = self.client.get(reverse('news:news_list'))
        self.assertEqual(response.status_code, 302)
        # login as reader
        logged = self.client.login(username=self.reader.username, password="readerpass")
        self.assertTrue(logged)
        response = self.client.get(reverse('news:news_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sample News")

    def test_news_list_search_filter_sort(self):
        self.client.login(username=self.reader.username, password="readerpass")
        response = self.client.get(reverse('news:news_list'), {
            'search': 'Sample',
            'category': 'update',
            'is_featured': 'true',
            'sort': 'created_at'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sample News")

    def test_news_detail_view_increments_view_count(self):
        self.client.login(username=self.reader.username, password="readerpass")
        response = self.client.get(reverse('news:news_detail', args=[self.news.pk]))
        self.assertEqual(response.status_code, 200)
        self.news.refresh_from_db()
        self.assertEqual(self.news.news_views, 1)

    def test_create_comment_ajax(self):
        self.client.login(username=self.reader.username, password="readerpass")
        response = self.client.post(
            reverse('news:news_detail', args=[self.news.pk]),
            {'content': 'Test comment'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        # view returns JsonResponse on successful AJAX POST -> status 200
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(news=self.news, content='Test comment').exists())

    def test_reply_comment_ajax(self):
        self.client.login(username=self.reader.username, password="readerpass")
        parent = Comment.objects.create(news=self.news, user=self.reader, content="Parent")
        response = self.client.post(
            reverse('news:news_detail', args=[self.news.pk]),
            {'content': 'Child reply', 'parent_id': parent.id},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(parent=parent, content='Child reply').exists())

    def test_like_comment_ajax_and_toggle(self):
        self.client.login(username=self.reader.username, password="readerpass")
        comment = Comment.objects.create(news=self.news, user=self.journalist, content="A comment")
        # like
        response = self.client.post(
            reverse('news:like_comment', args=[comment.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertTrue(comment.likes.filter(id=self.reader.id).exists())
        # unlike (same endpoint toggles)
        response = self.client.post(
            reverse('news:like_comment', args=[comment.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        comment.refresh_from_db()
        self.assertFalse(comment.likes.filter(id=self.reader.id).exists())

    def test_delete_comment_ajax_by_owner(self):
        self.client.login(username=self.reader.username, password="readerpass")
        comment = Comment.objects.create(news=self.news, user=self.reader, content="To delete")
        response = self.client.post(
            reverse('news:delete_comment', args=[comment.id]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(id=comment.id).exists())

    def test_news_create_view_by_journalist_with_thumbnail(self):
        # login as the hardcoded journalist
        logged = self.client.login(username=HARDCODED_JOURNALIST_USERNAME, password=HARDCODED_JOURNALIST_PASSWORD)
        self.assertTrue(logged)
        thumbnail = get_image_file()
        response = self.client.post(
            reverse('news:news_create'),
            {
                'title': 'New News',
                # Note: in your form the 'content' field is a HiddenInput; tests can send plain string
                'content': '<p>Content News</p>',
                'category': 'match',
                'is_featured': 'on',  # checkbox present
                'thumbnail': thumbnail
            },
            follow=True
        )
        # after successful create the view redirects (follow=True -> final 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(News.objects.filter(title='New News').exists())

    def test_news_edit_view_updates_and_respects_delete_thumbnail_flag(self):
        # ensure the news has a thumbnail first
        dummy_thumb = get_image_file(name="thumb.png")
        self.news.thumbnail = dummy_thumb
        self.news.save()
        # login as journalist
        self.client.login(username=HARDCODED_JOURNALIST_USERNAME, password=HARDCODED_JOURNALIST_PASSWORD)
        response = self.client.post(
            reverse('news:news_edit', args=[self.news.pk]),
            {
                'title': 'Edited Title',
                'content': '<p>Edited content</p>',
                'category': 'transfer',
                # simulate ticking/unticking checkbox; using 'is_featured': False might not be accepted by forms,
                # so we omit it to default to False in this test pattern; still we'll assert title changed.
                'delete_thumbnail': 'true',
            },
            follow=True
        )
        # should redirect / render final page with 200
        self.assertEqual(response.status_code, 200)
        self.news.refresh_from_db()
        self.assertEqual(self.news.title, 'Edited Title')
        # If delete_thumbnail is processed, thumbnail should be None
        # (note: since we used save=False delete in views, thumbnail deletion should take effect)
        # Depending on storage backend, the file may still be present on filesystem in test env; ensure field cleared:
        self.assertTrue(self.news.thumbnail in [None, ""]) or self.assertIsNone(self.news.thumbnail)

    def test_news_delete_by_journalist_ajax(self):
        # login as journalist
        self.client.login(username=HARDCODED_JOURNALIST_USERNAME, password=HARDCODED_JOURNALIST_PASSWORD)
        response = self.client.post(
            reverse('news:news_delete', args=[self.news.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(News.objects.filter(pk=self.news.pk).exists())

    def test_non_journalist_cannot_access_create_view(self):
        # login as regular reader
        self.client.login(username=self.reader.username, password="readerpass")
        response = self.client.get(reverse('news:news_create'), follow=False)
        # behavior can be redirect (302) or forbidden (403) depending on decorator config;
        # assert it's not 200 and is either 302 or 403
        self.assertNotEqual(response.status_code, 200)
        self.assertIn(response.status_code, (302, 403))

    def test_detail_post_fallback_non_ajax_comment_redirect(self):
        # non-ajax POST should fallback to redirect
        self.client.login(username=self.reader.username, password="readerpass")
        response = self.client.post(
            reverse('news:news_detail', args=[self.news.pk]),
            {'content': 'Non AJAX comment'},
            follow=True
        )
        # After fallback it redirects back to detail page (follow=True -> final 200)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Comment.objects.filter(content='Non AJAX comment').exists())