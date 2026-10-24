from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LiveSessionViewSet, JoinSessionAPIView

router = DefaultRouter()
router.register(r"", LiveSessionViewSet, basename="live-session")

urlpatterns = [
    path("join/", JoinSessionAPIView.as_view(), name="session-join"),
    path("", include(router.urls)),
]
