from django.db import models
from django.conf import settings
from match.models import Match
from phonenumber_field.modelfields import PhoneNumberField
import uuid

User = settings.AUTH_USER_MODEL 

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.user.username
    
    @property 
    def full_name(self): 
        return f"{self.user.first_name} {self.user.last_name}".strip().title()
    
    @property 
    def username(self): 
        return self.user.username
    
    @property
    def email(self): 
        return self.user.email
    
    @property
    def phone_number(self): 
        return self.user.phone

    @property
    def role(self): 
        return self.user.role

    @property
    def total_journalist_views(self):
        if hasattr(self.user, 'journalistdata'):
            return self.user.journalistdata.total_views
        return 0 

    @property
    def total_journalist_news(self):
        if hasattr(self.user, 'journalistdata'):
            return self.user.journalistdata.total_news
        return 0 

class JournalistData(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    total_views = models.IntegerField(default=0)
    total_news = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Data"
    
class TicketPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ticket_purchases')
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField()
    seat_plan = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.user.username} - {self.match}"

class MatchReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_reviews')
    match = models.ForeignKey(Match, on_delete=models.CASCADE)
    review_date = models.DateTimeField()
    comment = models.TextField()

    def __str__(self):
        return f"{self.user.username} - {self.match}"