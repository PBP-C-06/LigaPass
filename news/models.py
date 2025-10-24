from django.db import models
from django.utils.timesince import timesince
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
    thumbnail = models.ImageField(upload_to='news_thumbnails/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    news_views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return self.title
    
    @classmethod
    def published_count(cls):
        return cls.objects.filter(is_published=True).count()
    
class Comment(models.Model):
    news = models.ForeignKey('News', on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='comment_likes', blank=True)

    def __str__(self):
        return f"{self.user.username}: {self.content[:30]}"
    
    def is_reply(self):
        return self.parent is not None
    
    @property
    def like_count(self):
        return self.likes.count()
    
    def is_liked_by(self, user):
        return self.likes.filter(id=user.id).exists()
    
    def time_since_created(self):
        return timesince(self.created_at)