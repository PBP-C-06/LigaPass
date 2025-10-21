from django.urls import path
from authentication.views import *

app_name = 'authentication'

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
    path("google-login/", google_login, name="google_login"),
]