from django.urls import path
from profiles.views import admin_view, create_profile, journalist_view, show_json_admin_journalist, show_json_by_id, user_view

app_name = 'profiles'

urlpatterns = [
    path('user/create-profile/', create_profile, name='create_profile'),
    path('json/<uuid:id>/', show_json_by_id, name='show_json_by_id'),
    path('adminJournalistJson/', show_json_admin_journalist, name='show_json_admin_journalist'),
    path("user/<uuid:id>/", user_view, name="user_view"),
    path("admin/", admin_view, name="admin_view"),
    path("journalist/", journalist_view, name="journalist_view"),
    # TODO: Lanjutkan yang dibawah
    # path('admin/<uuid:id>/', admin_to_user_view, name='admin_user_edit'),
    # path('user/<uuid:id>/edit/', user_edit, name='user_edit'), # Draft untuk edit user profile
]