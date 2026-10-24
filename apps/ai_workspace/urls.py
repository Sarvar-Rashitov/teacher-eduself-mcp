from django.urls import path
from apps.ai_workspace.views import (
    GenerateQuizView,
    ReviseQuestionView,
    ApplyDiffView,
    LockQuestionView,
    SuggestGameModesView,
)

app_name = "ai_workspace"

urlpatterns = [
    path("generate-quiz/", GenerateQuizView.as_view(), name="generate-quiz"),
    path("revise-question/", ReviseQuestionView.as_view(), name="revise-question"),
    path("diff-apply/", ApplyDiffView.as_view(), name="diff-apply"),
    path("tools/lock/", LockQuestionView.as_view(), name="tools-lock"),
    path("tools/suggest-game-modes/", SuggestGameModesView.as_view(), name="suggest-game-modes"),
]
