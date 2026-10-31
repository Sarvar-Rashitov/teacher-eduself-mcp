"""
Root URL configuration for EduSelf Teacher platform.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    home_view,
    dashboard_view,
    quiz_editor_view,
    host_screen_view,
    student_game_view,
    profile_view,
    robots_txt,
    sitemap_xml,
)


def health_check(request):
    """Basic health check endpoint."""
    return JsonResponse({"status": "healthy", "service": "EduSelf Teacher Core"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("deploy.health.urls", namespace="health")),
    # SEO Endpoints
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    # Frontend MVT Views (Phase 08)
    path("", home_view, name="home"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("auth/profile/", profile_view, name="profile"),
    path("editor/new/", quiz_editor_view, name="quiz_editor_new"),
    path("editor/<uuid:quiz_id>/", quiz_editor_view, name="quiz_editor"),
    path("live/<str:room_code>/", host_screen_view, name="host_screen"),
    path("play/", student_game_view, name="student_game_join"),
    path("play/<str:room_code>/", student_game_view, name="student_game"),
    # Modular APIs
    path("auth/", include("apps.authentication.urls", namespace="auth")),
    path("api/quizzes/", include("apps.quizzes.urls", namespace="quizzes")),
    path("api/sessions/", include("apps.live_sessions.urls", namespace="live_sessions")),
    path("api/ai/", include("apps.ai_workspace.urls", namespace="ai_workspace")),
    path("mcp/", include("apps.mcp_server.urls", namespace="mcp_server")),
    path("api/sheets/", include("apps.sheets_sync.urls", namespace="sheets_sync")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
