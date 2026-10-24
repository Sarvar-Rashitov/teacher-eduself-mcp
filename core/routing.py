from django.urls import path
# pyrefly: ignore[missing-import]
from live_sessions.consumers import ClassroomGameConsumer, HostGameConsumer

websocket_urlpatterns = [
    path("ws/session/<str:room_code>/", ClassroomGameConsumer.as_asgi()),
    path("ws/host/<str:room_code>/", HostGameConsumer.as_asgi()),
]
