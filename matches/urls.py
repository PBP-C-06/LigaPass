from django.urls import path
from .views import match_calendar_view

app_name = 'matches'

urlpatterns = [
    path('', match_calendar_view, name='calendar'),
]