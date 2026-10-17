# apps/quizzes/views.py
from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.authentication.permissions import IsTeacher
from .models import Quiz, Question, QuizVersion
from .serializers import (
    QuizSerializer,
    QuizDetailSerializer,
    QuestionSerializer,
    StudentQuestionSerializer,
    QuizVersionSerializer
)
from .services import QuizService


class QuizViewSet(viewsets.ModelViewSet):
    """
    O'qituvchi viktorinalarini boshqarish (CRUD).
    """
    permission_classes = [IsAuthenticated, IsTeacher]

    def get_queryset(self):
        # O'qituvchi faqat o'ziga tegishli yoki ommaviy quizlarni ko'radi
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return Quiz.objects.none()
        return Quiz.objects.filter(owner=user).annotate(
            annotated_question_count=Count('questions')
        ).order_by('-created_at')

    def get_serializer_class(self):
        if self.action in ['retrieve', 'update', 'partial_update']:
            return QuizDetailSerializer
        return QuizSerializer

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['post'], url_path='snapshot')
    def create_snapshot(self, request, pk=None):
        """
        Quizning joriy holatidan versiya snapshotini yaratish.
        QUIZ_ENGINE.md §4: Immutability & Snapshotting.
        """
        quiz = self.get_object()
        version = QuizService.create_version_snapshot(quiz)
        return Response(
            QuizVersionSerializer(version).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'], url_path='student-preview')
    def student_preview(self, request, pk=None):
        """
        Zero-Knowledge ko'rinishida savollar ro'yxatini olish (Test qilib ko'rish uchun).
        """
        quiz = self.get_object()
        sanitized_questions = QuizService.get_sanitized_questions_for_student(quiz)
        return Response({
            'quiz_id': str(quiz.id),
            'title': quiz.title,
            'question_count': len(sanitized_questions),
            'questions': sanitized_questions
        })


class QuestionViewSet(viewsets.ModelViewSet):
    """
    Savollarni alohida yaratish, tahrirlash va o'chirish.
    """
    permission_classes = [IsAuthenticated, IsTeacher]
    serializer_class = QuestionSerializer

    def get_queryset(self):
        user = self.request.user
        if getattr(self, 'swagger_fake_view', False):
            return Question.objects.none()
        quiz_id = self.request.query_params.get('quiz_id')
        qs = Question.objects.filter(quiz__owner=user)
        if quiz_id:
            qs = qs.filter(quiz_id=quiz_id)
        return qs.order_by('order_index')

    def perform_create(self, serializer):
        question = serializer.save()
        # Quiz versiyasini oshirish
        question.quiz.current_version += 1
        question.quiz.save(update_fields=['current_version', 'updated_at'])

    def perform_update(self, serializer):
        question = self.get_object()
        # AI orqali o'zgartirish bo'lsa va is_locked bo'lsa bloklanadi
        is_ai = self.request.data.get('is_ai_action', False)
        if question.is_locked and is_ai:
            raise ValidationError("Savol qulflangan, AI tomonidan o'zgartirib bo'lmaydi.")
        updated_q = serializer.save()
        updated_q.quiz.current_version += 1
        updated_q.quiz.save(update_fields=['current_version', 'updated_at'])

    @action(detail=True, methods=['post'], url_path='toggle-lock')
    def toggle_lock(self, request, pk=None):
        """
        Savolni AI tahriridan qulflash yoki ochish (is_locked bayrog'i).
        """
        question = self.get_object()
        question.is_locked = not question.is_locked
        question.save(update_fields=['is_locked', 'updated_at'])
        return Response({
            'id': str(question.id),
            'is_locked': question.is_locked,
            'message': f"Savol {'qulflandi' if question.is_locked else 'ochildi'}."
        })
