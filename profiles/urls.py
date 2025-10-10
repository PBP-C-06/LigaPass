from django.urls import path
from profiles.views import *

app_name = 'profile'

urlpatterns = [
    path("user/<uuid:id>/", user_view, name="user_view"),
    path("admin/", admin_view, name="admin_view"),
    path("journalist/", journalist_view, name="journalist_view"),
    path('admin/<uuid:id>/', admin_user_edit, name='admin_user_edit'),
    # path('user/<uuid:id>/edit/', user_edit, name='user_edit'), # Draft untuk edit user profile
]