from django.urls import path
from profiles.views import *
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

    # Untuk delete profile user
    path("delete/<uuid:id>/", delete_profile, name="delete_profile"),
    
    # Untuk base profile
    path("current_user_json/", current_user_json, name="current_user_json"),

    # Untuk ticket
    path("<uuid:id>/tickets/", user_tickets_page, name="user_tickets_page"),
    path("<uuid:id>/tickets/json/", user_tickets_json, name="user_tickets_json"),

    # Untuk flutter
    path('flutter-create-profile/', create_profile_flutter, name='create_profile_flutter'),
    path("admin/flutter-edit/<uuid:id>/", admin_change_status_flutter, name="admin_change_status_flutter"),
    path("flutter-delete/<uuid:id>/", delete_profile_flutter, name="delete_profile_flutter"),
    # path("flutter-edit/<uuid:id>/", edit_profile_flutter, name="edit_profile_flutter"),
]