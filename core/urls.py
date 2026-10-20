from django.contrib import admin
from django.urls import path, include
from core import views_ui

urlpatterns = [
    path('admin/', admin.site.urls),

    # UI Web Routes ("EduPlay 3D" Frontend MVT)
    path('', views_ui.index_view, name='ui_index'),
    path('login/', views_ui.login_view, name='ui_login'),
    path('logout/', views_ui.logout_view, name='ui_logout'),
    path('profile/', views_ui.profile_view, name='ui_profile'),
    path('dashboard/', views_ui.dashboard_view, name='ui_dashboard'),
    path('editor/new/', views_ui.quiz_editor_view, name='ui_quiz_editor_new'),
    path('editor/<uuid:quiz_id>/', views_ui.quiz_editor_view, name='ui_quiz_editor'),
    path('live/launch/<uuid:quiz_id>/', views_ui.launch_live_view, name='ui_live_launch'),
    path('live/<str:room_code>/', views_ui.host_screen_view, name='ui_host_screen'),
    path('play/', views_ui.student_game_view, name='ui_student_play'),
    path('play/<str:room_code>/', views_ui.student_game_view, name='ui_student_play_room'),

    # APIs & MCP
    path('api/auth/', include('apps.authentication.urls')),
    path('api/quizzes/', include('apps.quizzes.urls')),
    path('api/sessions/', include('apps.live_sessions.urls')),
    path('api/ai/', include('apps.ai_workspace.urls')),
    path('api/sheets/', include('apps.sheets_sync.urls')),
    path('mcp/', include('apps.mcp_server.urls')),
    path('oauth/', include('apps.mcp_server.oauth_urls')),
    path('health/', include('deploy.health.urls')),
]
