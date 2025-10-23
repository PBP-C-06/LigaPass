from django.urls import path, include
from main import views
from main.views import *

app_name = 'main'

urlpatterns = [
    path("current_user_json/", views.current_user_json, name="current_user_json"),
]