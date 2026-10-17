# ============================================================
# EduSelf Teacher — core/routing.py
# Django Channels WebSocket URL routing
# Backend.md §1.1 va REALTIME_PROTOCOL.md §1 asosida
# ============================================================
from django.urls import re_path
from apps.live_sessions.consumers import ClassroomGameConsumer, HostGameConsumer

websocket_urlpatterns = [
    # O'quvchilar ulanishi: wss://<domain>/ws/session/<room_code>/?token=<token>
    re_path(r'^ws/session/(?P<room_code>[A-Za-z0-9]{6})/$', ClassroomGameConsumer.as_asgi()),

    # O'qituvchi boshqaruv pulti: wss://<domain>/ws/host/<room_code>/
    re_path(r'^ws/host/(?P<room_code>[A-Za-z0-9]{6})/$', HostGameConsumer.as_asgi()),
]
