from django.apps import AppConfig

class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'

    def ready(self):
        from .hardcode_admin_and_journalist import hardcode_admin, hardcode_journalist
        hardcode_admin()
        hardcode_journalist()