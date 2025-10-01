from django.urls import path, include
from main.views import *

app_name = 'main'

urlpatterns = [
    path('', main, name='show_main')
]