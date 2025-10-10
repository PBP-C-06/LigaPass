from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import Profile, JournalistData

User = settings.AUTH_USER_MODEL

# Handling create user
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

        # Buat JournalistData hanya ketika role adalah journalist
        if instance.role == 'journalist':
            JournalistData.objects.create(user=instance)

# Handling edit user
@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
