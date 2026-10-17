from django.urls import path
from apps.ai_workspace.views import (
    GenerateQuizAPIView,
    ReviseQuestionAPIView,
    ApplyRevisionAPIView,
    SuggestGameModesAPIView
)

app_name = 'ai_workspace'

urlpatterns = [
    path('generate/', GenerateQuizAPIView.as_view(), name='generate_quiz'),
    path('revise/', ReviseQuestionAPIView.as_view(), name='revise_question'),
    path('apply-revision/', ApplyRevisionAPIView.as_view(), name='apply_revision'),
    path('suggest-modes/', SuggestGameModesAPIView.as_view(), name='suggest_modes'),
]
