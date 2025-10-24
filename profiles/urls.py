from django.urls import path
from profiles.views import admin_change_status, admin_search_filter, admin_view, create_profile, edit_profile_for_user, journalist_view, show_json_admin, show_json_by_id, show_json_journalist, user_view, show_json, current_user_json, user_tickets_page, user_tickets_json

app_name = 'profiles'

urlpatterns = [
    # Untuk create profile
    path('user/create-profile/', create_profile, name='create_profile'),

    # Untuk endpoints
    path('json/admin/', show_json_admin, name='show_json_admin'),
    path('json/journalist/', show_json_journalist, name='show_json_journalist'),
    path('json/admin/search-filter/', admin_search_filter, name='admin_search_and_filter'),
    path('json/<uuid:id>/', show_json_by_id, name='show_json_by_id'),
    path('json/', show_json, name='show_json'),

    # Untuk view pages
    path("user/<uuid:id>/", user_view, name="user_view"),
    path("admin/", admin_view, name="admin_view"),
    path("journalist/", journalist_view, name="journalist_view"),
    path('user/<uuid:id>/edit/', edit_profile_for_user, name='edit_profile_for_user'), 

    # Untuk admin edit status user
    path("admin/edit/<uuid:id>/", admin_change_status, name="admin_change_status"),
    
    path("current_user_json/", current_user_json, name="current_user_json"),
    path("<uuid:id>/tickets/", user_tickets_page, name="user_tickets_page"),
    path("<uuid:id>/tickets/json/", user_tickets_json, name="user_tickets_json"),
]