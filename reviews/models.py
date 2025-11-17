from django.db import models
from django.conf import settings
from matches.models import Match
from profiles.models import Profile
from django.utils.timezone import now

class Review(models.Model):
    SENTIMENT_CHOICES = [
        ('POSITIVE', 'Positive'),
        ('NEUTRAL', 'Neutral'),
        ('NEGATIVE', 'Negative'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()  # 1–5
    comment = models.TextField(blank=True, null=True)
    sentiment = models.CharField(max_length=8, choices=SENTIMENT_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Satu user cuma boleh review satu kali per pertandingan
        unique_together = ('user', 'match')

    def __str__(self):
        return f"{self.user.username} - {self.match} - {self.rating}★"


class ReviewReply(models.Model):
    review = models.OneToOneField(Review, on_delete=models.CASCADE, related_name='reply')
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='review_replies')
    reply_text = models.TextField()

    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"Reply to {self.review.id} by {self.admin}"
