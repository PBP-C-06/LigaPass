from django.urls import path
from . import views

app_name = 'news'

urlpatterns = [
    path('', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),
    path('news/create/', views.news_create, name='news_create'),
    path('news/edit/<int:pk>/', views.news_edit, name='news_edit'),
    path('news/delete/<int:pk>/', views.news_delete, name='news_delete'),
    path('comment/<int:comment_id>/like/', views.like_comment, name='like_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    
    path('api/news/', views.api_news_list, name='api_news_list'),
    path('api/news/<int:pk>/', views.api_news_detail, name='api_news_detail'),
    path('api/news/create-json/', views.api_news_create_json, name='api_news_create_json'),
    path('api/news/<int:pk>/edit-json/', views.api_news_edit_json, name='api_news_edit_json'),
    path('api/news/<int:pk>/delete/', views.api_news_delete, name='api_news_delete'),
    path('api/news/<int:pk>/comments/', views.api_news_comments, name='api_news_comments'),
    path("api/news/<int:pk>/recommendations/", views.api_news_recommendations, name="api_news_recommendations"),
    path("api/comment/<int:comment_id>/like/", views.api_like_comment, name="api_like_comment"),
    path('api/comment/<int:comment_id>/delete/', views.api_delete_comment, name='api_delete_comment'),
    path('api/user/', views.api_current_user, name='api_current_user'),
]