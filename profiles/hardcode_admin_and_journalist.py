from django.conf import settings
from authentication.models import User
from profiles.models import AdminJournalistProfile

def create_default_users(sender, **kwargs):
    hardcode_admin()
    hardcode_journalist()
    
def hardcode_admin():
    try:
        if not (User.objects.filter(username="admin").exists()):
            user = User.objects.create(
                username="admin",
                role="admin",
                email="l1gapass@outlook.com"
            )
            user.set_password(settings.ADMIN_PASSWORD)
            user.save()
            AdminJournalistProfile.objects.create(
                user=user,
                profile_picture="static/images/Admin.png"
            )
    except Exception:
        pass

def hardcode_journalist():
    try:
        if not (User.objects.filter(username="journalist").exists()):
                user = User.objects.create(
                    username="journalist",
                    role="journalist",
                    email="journalistLigaPass@gmail.com"
                )
                user.set_password(settings.JOURNALIST_PASSWORD)
                user.save()
                AdminJournalistProfile.objects.create(
                    user=user,
                    profile_picture="static/images/Journalist.png"
                )
    except Exception:
        pass