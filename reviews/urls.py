from django.urls import path
from . import views, views_analytics

app_name = "reviews"

urlpatterns = [
    # === USER REVIEWS ===
    path("user/<uuid:match_id>/", views.user_review_page, name="user_review_page"),
    path("api/<uuid:match_id>/create/", views.api_create_review, name="api_create_review"),
    path("api/<uuid:match_id>/update/", views.api_update_review, name="api_update_review"),

    # === ADMIN REVIEWS ===
    # Halaman detail review untuk 1 pertandingan (include di detail tiket admin)
    path("admin/<uuid:match_id>/", views.admin_review_page, name="admin_review_page"),

    # API untuk membalas review user
    path("api/reply/<int:review_id>/", views.api_add_reply, name="api_add_reply"),

    # === ANALYTICS ===
    path("analytics/admin/", views_analytics.admin_analytics_page, name="admin_analytics_page"),
    path("analytics/admin/data/", views_analytics.api_admin_analytics_data, name="api_admin_analytics_data"),
    path("analytics/user/", views_analytics.user_analytics_page, name="user_analytics_page"),
    path("analytics/user/data/", views_analytics.api_user_analytics_data, name="api_user_analytics_data"),
]
