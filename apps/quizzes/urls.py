"""
URL routes for Quizzes API endpoints.
"""

from django.urls import path
from . import views

app_name = 'quizzes'

urlpatterns = [
    path('', views.QuizListCreateView.as_view(), name='quiz_list_create'),
    path('<uuid:pk>/', views.QuizDetailView.as_view(), name='quiz_detail'),
    path('<uuid:quiz_id>/questions/', views.QuestionCreateView.as_view(), name='question_create'),
    path('<uuid:quiz_id>/questions/<uuid:pk>/', views.QuestionDetailView.as_view(), name='question_detail'),
    path('<uuid:pk>/publish/', views.QuizPublishView.as_view(), name='quiz_publish'),
    path('<uuid:pk>/student-preview/', views.QuizStudentPreviewView.as_view(), name='quiz_student_preview'),
]
