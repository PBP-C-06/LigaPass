from django.urls import path
from . import views, views_analytics

app_name = "reviews"

urlpatterns = [
    # Entry tanpa match_id → akan redirect ke match terakhir / match terakhir dari tim terpilih
    path("user/", views.user_review_entry, name="user_review_entry"),
    # Halaman user untuk 1 match tertentu
    path("user/<int:match_id>/", views.user_review_page, name="user_review_page"),

    # API AJAX
    path("api/<int:match_id>/create/", views.api_create_review, name="api_create_review"),
    path("api/<int:match_id>/update/", views.api_update_review, name="api_update_review"),
    path('admin/', views.admin_review_page, name='admin_review_page'),
    path('api/reply/<int:review_id>/', views.api_add_reply, name='api_add_reply'),

    # Analytics URLs
    path("analytics/admin/", views_analytics.admin_analytics_page, name="admin_analytics_page"),
    path("analytics/admin/data/", views_analytics.api_admin_analytics_data, name="api_admin_analytics_data"),
    path("analytics/user/", views_analytics.user_analytics_page, name="user_analytics_page"),
    path("analytics/user/data/", views_analytics.api_user_analytics_data, name="api_user_analytics_data"),
]