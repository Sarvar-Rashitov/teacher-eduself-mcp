from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import QuizViewSet, QuestionViewSet

router = DefaultRouter()
router.register(r"questions", QuestionViewSet, basename="question")
router.register(r"", QuizViewSet, basename="quiz")

urlpatterns = [
    path("", include(router.urls)),
]
