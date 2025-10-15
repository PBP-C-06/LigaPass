from django.db import models
from django.db import models
from django.conf import settings

# Profile
class Profile(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('banned', 'Banned'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.user.username

    @property 
    def full_name(self): 
        return self.user.get_full_name().strip().title()

# Profile untuk admin dan journalist
class AdminJournalistProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    profile_picture = models.URLField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.role} : {self.user.username}"

# TODO: JournalistData from news
# TODO: UserReviewsInfo from reviews