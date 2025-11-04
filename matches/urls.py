from django.urls import path
from .views import (
    MatchCreateView,
    MatchDeleteView,
    MatchListView,
    MatchUpdateView,
    api_match_list,
    live_score_api,
    match_calendar_view, 
    match_details_view,
    update_matches_view,
    TeamListView, TeamCreateView, TeamUpdateView, TeamDeleteView,
    VenueListView, VenueCreateView, VenueUpdateView, VenueDeleteView,
    ManageBaseView,
)

app_name = 'matches'

urlpatterns = [
    # Read data
    path('', match_calendar_view, name='calendar'),
    path('details/<uuid:match_id>/', match_details_view, name='details'),

    # APIs
    # URL untuk admin memicu update
    path('update-from-api/', update_matches_view, name='update_from_api'),

    # URL untuk live score update
    path('api/live-score/<int:match_api_id>/', live_score_api, name='live_score_api'),

    # Read match list ajax
    path('api/calendar/', api_match_list, name='api_calendar'),

    # URL untuk Manajemen Admin (CUD)
    # Base Management URL
    path('manage/', ManageBaseView.as_view(), name='manage_base'),

    # Teams
    path('manage/teams/', TeamListView.as_view(), name='manage_teams'),
    path('manage/teams/add/', TeamCreateView.as_view(), name='add_team'),
    path('manage/teams/edit/<uuid:pk>/', TeamUpdateView.as_view(), name='edit_team'),
    path('manage/teams/delete/<uuid:pk>/', TeamDeleteView.as_view(), name='delete_team'),

    # Matches
    path('manage/matches/', MatchListView.as_view(), name='manage_matches'),
    path('manage/matches/add/', MatchCreateView.as_view(), name='add_match'),
    path('manage/matches/edit/<uuid:pk>/', MatchUpdateView.as_view(), name='edit_match'), 
    path('manage/matches/delete/<uuid:pk>/', MatchDeleteView.as_view(), name='delete_match'),
    
    # Venues
    path('manage/venues/', VenueListView.as_view(), name='manage_venues'),
    path('manage/venues/add/', VenueCreateView.as_view(), name='add_venue'),
    path('manage/venues/edit/<uuid:pk>/', VenueUpdateView.as_view(), name='edit_venue'),
    path('manage/venues/delete/<uuid:pk>/', VenueDeleteView.as_view(), name='delete_venue'),
]