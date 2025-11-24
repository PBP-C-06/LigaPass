from django.urls import path
from authentication.views import *

app_name = 'authentication'

urlpatterns = [
    path("register/", register_user, name="register"),
    path("login/", login_user, name="login"),
    path("logout/", logout_user, name="logout"),
    path("google-login/", google_login, name="google_login"),
    path("flutter-login/", flutter_login, name="flutter_login"),
    path("flutter-google-login/", flutter_google_login, name="flutter_google_login"),
    path("flutter-register/", flutter_register, name="flutter_register"),
    path("flutter-logout/", flutter_logout, name="flutter_logout"),
]