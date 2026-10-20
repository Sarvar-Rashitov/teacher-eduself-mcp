"""
URL configuration for EduSelf project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.quizzes.views import teacher_dashboard_view, quiz_editor_view, design_system_showcase_view
from apps.live_sessions.views import host_screen_view, student_game_view
from apps.authentication.views import login_page_view, profile_page_view

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Frontend MVT Pages
    path('', teacher_dashboard_view, name='home'),
    path('dashboard/', teacher_dashboard_view, name='dashboard'),
    path('login/', login_page_view, name='login-page'),
    path('profile/', profile_page_view, name='profile-page'),
    path('editor/new/', quiz_editor_view, name='editor-new'),
    path('editor/<uuid:quiz_id>/', quiz_editor_view, name='editor-detail'),
    path('live/<str:room_code>/', host_screen_view, name='host-screen'),
    path('play/', student_game_view, name='student-play-join'),
    path('play/<str:room_code>/', student_game_view, name='student-play-room'),
    path('design-system/', design_system_showcase_view, name='design-system'),

    # Backend APIs
    path('auth/', include('apps.authentication.urls')),
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/quizzes/', include('apps.quizzes.urls')),
    path('api/v1/sessions/', include('apps.live_sessions.urls')),
    path('api/v1/ai-workspace/', include('apps.ai_workspace.urls')),
    path('api/v1/sheets/', include('apps.sheets_sync.urls')),
    path('mcp/', include('apps.mcp_server.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

