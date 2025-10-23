from django.urls import path, include
from main import views
from main.views import *

app_name = 'main'

urlpatterns = [
    path("", views.home, name="home"),
]