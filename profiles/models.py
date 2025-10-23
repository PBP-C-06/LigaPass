from django.db import models
from django.db import models
from django.conf import settings
from django.db.models import Sum

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
    
    # Menambahkan property untuk menghitung jumlah news dan view untuk journalist
    @property
    def news_count(self):
        return self.user.news_set.count()

    @property
    def total_news_views(self):
        # Count jumlah views news dengan aggregate(sum) supaya perhitungan langsung dilakukan di database (lebih efisien)
        total = self.user.news_set.aggregate(total_views=Sum('news_views'))['total_views'] 
        return total or 0 # Return 0 jika tidak memiliki news