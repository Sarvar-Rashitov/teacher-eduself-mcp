from django.urls import path
from .views import (
    session_create_view,
    session_join_view,
    session_reconnect_view,
    session_state_view,
    session_start_view,
)

app_name = "live_sessions"

urlpatterns = [
    path("create/", session_create_view, name="session_create"),
    path("join/", session_join_view, name="session_join"),
    path("reconnect/", session_reconnect_view, name="session_reconnect"),
    path("<str:room_code>/state/", session_state_view, name="session_state"),
    path("<str:room_code>/start/", session_start_view, name="session_start"),
]
