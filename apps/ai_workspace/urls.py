"""
URL Configuration for AI Workspace.
"""

from django.urls import path
from .views import (
    GenerateQuizAPIView,
    ReviseQuestionAPIView,
    ApplyProposalAPIView,
    LockQuestionAPIView,
)

urlpatterns = [
    path('generate/', GenerateQuizAPIView.as_view(), name='ai_generate_quiz'),
    path('revise/', ReviseQuestionAPIView.as_view(), name='ai_revise_question'),
    path('apply-proposal/', ApplyProposalAPIView.as_view(), name='ai_apply_proposal'),
    path('lock-question/', LockQuestionAPIView.as_view(), name='ai_lock_question'),
]
