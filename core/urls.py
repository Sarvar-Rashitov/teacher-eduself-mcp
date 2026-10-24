from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls')),
    path('api/v1/quizzes/', include('quizzes.urls')),
    path('quizzes/', include('quizzes.urls')),
    path('api/v1/sessions/', include('live_sessions.urls')),
    path('sessions/', include('live_sessions.urls')),
    path('api/v1/ai/workspace/', include('ai_workspace.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
