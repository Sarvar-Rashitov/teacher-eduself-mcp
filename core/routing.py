"""
WebSocket URL routing for EduSelf Teacher project.
Maps WebSocket connection endpoints to Daphne ASGI consumers.
"""

from django.urls import re_path
from apps.live_sessions.consumers import ClassroomGameConsumer, HostGameConsumer

websocket_urlpatterns = [
    re_path(r'^ws/session/(?P<room_code>[0-9a-zA-Z]+)/?$', ClassroomGameConsumer.as_asgi()),
    re_path(r'^ws/host/(?P<room_code>[0-9a-zA-Z]+)/?$', HostGameConsumer.as_asgi()),
]
