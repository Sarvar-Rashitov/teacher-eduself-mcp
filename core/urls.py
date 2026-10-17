from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/quizzes/', include('apps.quizzes.urls')),
    path('api/sessions/', include('apps.live_sessions.urls')),
    path('api/ai/', include('apps.ai_workspace.urls')),
]
