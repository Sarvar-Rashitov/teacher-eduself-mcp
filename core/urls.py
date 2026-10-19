"""
URL configuration for EduSelf Teacher project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('apps.authentication.urls')),
    path('api/v1/quizzes/', include('apps.quizzes.urls')),
    path('api/v1/sessions/', include('apps.live_sessions.urls')),
    path('api/v1/ai-workspace/', include('apps.ai_workspace.urls')),
    path('mcp/', include('apps.mcp_server.urls')),
]
