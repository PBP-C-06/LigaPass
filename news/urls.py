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
]