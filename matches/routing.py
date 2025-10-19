from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/match/(?P<match_api_id>\w+)/$', consumers.MatchConsumer.as_asgi()),
]