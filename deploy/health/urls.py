"""
Health check endpoints for load balancers and container orchestrators.
"""

from django.urls import path
from deploy.health.views import liveness_check, readiness_check

app_name = "health"

urlpatterns = [
    path("", liveness_check, name="index"),
    path("live/", liveness_check, name="live"),
    path("ready/", readiness_check, name="ready"),
]
