from django.urls import path
from .views import (
    GenerateQuizAPIView,
    ReviseQuestionAPIView,
    ApplyDiffAPIView,
    LockQuestionAPIView,
    ValidateQuizAPIView,
    GameModesAPIView,
)

app_name = "ai_workspace"

urlpatterns = [
    path("generate/", GenerateQuizAPIView.as_view(), name="generate"),
    path("revise-question/", ReviseQuestionAPIView.as_view(), name="revise-question"),
    path("apply-diff/", ApplyDiffAPIView.as_view(), name="apply-diff"),
    path("lock-question/", LockQuestionAPIView.as_view(), name="lock-question"),
    path("validate/", ValidateQuizAPIView.as_view(), name="validate"),
    path("game-modes/", GameModesAPIView.as_view(), name="game-modes"),
]
