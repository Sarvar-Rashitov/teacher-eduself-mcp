# deploy/health/urls.py
from django.urls import path
from deploy.health import views

app_name = 'health'

urlpatterns = [
    path('live/', views.health_live_view, name='health_live'),
    path('ready/', views.health_ready_view, name='health_ready'),
]
