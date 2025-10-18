from django.urls import path
from .views import (
    match_calendar_view, 
    match_detail_view,
    TeamListView, TeamCreateView, TeamUpdateView, TeamDeleteView,
    update_matches_view
)

app_name = 'matches'

urlpatterns = [
    # Read data
    path('', match_calendar_view, name='calendar'),
    path('detail/<int:match_api_id>/', match_detail_view, name='detail'),

    # URL untuk admin memicu update
    path('update-from-api/', update_matches_view, name='update_from_api'),

    # URL untuk Manajemen Admin (CUD)
    path('manage/teams/', TeamListView.as_view(), name='manage_teams'),
    path('manage/teams/add/', TeamCreateView.as_view(), name='add_team'),
    path('manage/teams/edit/<int:pk>/', TeamUpdateView.as_view(), name='edit_team'),
    path('manage/teams/delete/<int:pk>/', TeamDeleteView.as_view(), name='delete_team'),
]