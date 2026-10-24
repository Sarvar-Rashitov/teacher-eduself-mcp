"""
WebSocket routing configuration for EduSelf Teacher.
Routes incoming WebSocket connections to Channels consumers.
"""

from django.urls import path
from apps.live_sessions.consumers import ClassroomGameConsumer

websocket_urlpatterns = [
    path("ws/session/<str:room_code>/", ClassroomGameConsumer.as_asgi()),
]
