from django.urls import path
from profiles.views import *

app_name = 'profile'

urlpatterns = [
    path("json/", show_json, name="json_view"),
    path("user/", user_view, name="user_view"),
    path("admin/", admin_view, name="admin_view"),
    path("journalist/", journalist_view, name="journalist_view"),
    # path('<int:id>/edit/', edit_product, name='edit_product'), # draft untuk edit user
    # path('admin/<int:id>/', edit_product, name='edit_product'), #draft untuk admin to user
]