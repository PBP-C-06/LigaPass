from django.db import models
from django.conf import settings

CATEGORY_CHOICES = [
    ('transfer', 'Transfer'),
    ('update', 'Update'),
    ('exclusive', 'Exclusive'),
    ('match', 'Match'),
    ('rumor', 'Rumor'),
    ('analysis', 'Analysis'),
]

class News(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='update')
    thumbnail = models.ImageField(upload_to='news_thumbnails/', blank=True, null=True, default='default.jpg')
    is_featured = models.BooleanField(default=False)
    news_views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    news_views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title
    
    @classmethod
    def published_count(cls):
        return cls.objects.filter(is_published=True).count()