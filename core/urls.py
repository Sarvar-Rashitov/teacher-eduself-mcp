"""
URL configuration for EduSelf Teacher project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('apps.authentication.urls')),
    path('api/v1/quizzes/', include('apps.quizzes.urls')),
]
