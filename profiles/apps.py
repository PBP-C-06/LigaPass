from django.apps import AppConfig
from django.db.models.signals import post_migrate

class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profiles'

    def ready(self):
        from . import hardcode_admin_and_journalist 
        post_migrate.connect(
            hardcode_admin_and_journalist.create_default_users,
            sender=self
        )