from django.conf import settings
from authentication.models import User
from profiles.models import AdminJournalistProfile

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
                profile_picture="static/image/Admin.png"
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
                    profile_picture="static/image/Journalist.png"
                )
    except Exception:
        pass