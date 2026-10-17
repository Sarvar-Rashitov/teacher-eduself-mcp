"""
API views for Quiz and Question management.
Provides CRUD, publishing snapshots, and zero-knowledge student preview endpoints.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.questions_registry.exceptions import QuestionValidationError, QuestionTypeNotFoundError
from .models import Quiz, Question
from .serializers import QuizSerializer, QuestionTeacherSerializer, QuizVersionSerializer
from .services import QuizService


class QuizListCreateView(APIView):
    """
    List user's quizzes or create a new quiz.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        quizzes = Quiz.objects.filter(owner=request.user)
        serializer = QuizSerializer(quizzes, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data
        title = data.get('title')
        subject = data.get('subject')

        if not title or not subject:
            return Response(
                {'error': "'title' va 'subject' maydonlari kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST
            )

        quiz = QuizService.create_quiz(
            owner=request.user,
            title=title,
            subject=subject,
            grade_level=data.get('grade_level', 7),
            locale=data.get('locale', 'uz-Latn'),
            description=data.get('description'),
            google_sheet_url=data.get('google_sheet_url'),
        )
        return Response(QuizSerializer(quiz).data, status=status.HTTP_201_CREATED)


class QuizDetailView(APIView):
    """
    Retrieve, update or delete a specific quiz.
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Quiz.objects.get(pk=pk, owner=user)
        except Quiz.DoesNotExist:
            return None

    def get(self, request, pk):
        quiz = self.get_object(pk, request.user)
        if not quiz:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(QuizSerializer(quiz).data)

    def put(self, request, pk):
        quiz = self.get_object(pk, request.user)
        if not quiz:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = QuizSerializer(quiz, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        quiz = self.get_object(pk, request.user)
        if not quiz:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        quiz.delete()
        return Response({'status': 'deleted'}, status=status.HTTP_204_NO_CONTENT)


class QuestionCreateView(APIView):
    """
    Add a new validated question to a quiz.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, quiz_id):
        try:
            quiz = Quiz.objects.get(pk=quiz_id, owner=request.user)
        except Quiz.DoesNotExist:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            question = QuizService.add_question(quiz, request.data)
            return Response(QuestionTeacherSerializer(question).data, status=status.HTTP_201_CREATED)
        except (QuestionValidationError, QuestionTypeNotFoundError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class QuestionDetailView(APIView):
    """
    Update or delete an individual question.
    """
    permission_classes = [IsAuthenticated]

    def get_object(self, quiz_id, pk, user):
        try:
            return Question.objects.get(pk=pk, quiz__id=quiz_id, quiz__owner=user)
        except Question.DoesNotExist:
            return None

    def put(self, request, quiz_id, pk):
        question = self.get_object(quiz_id, pk, request.user)
        if not question:
            return Response({'error': 'Savol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            updated_question = QuizService.update_question(question, request.data)
            return Response(QuestionTeacherSerializer(updated_question).data)
        except (QuestionValidationError, QuestionTypeNotFoundError) as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, quiz_id, pk):
        question = self.get_object(quiz_id, pk, request.user)
        if not question:
            return Response({'error': 'Savol topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            QuizService.delete_question(question)
            return Response({'status': 'deleted'}, status=status.HTTP_204_NO_CONTENT)
        except QuestionValidationError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class QuizPublishView(APIView):
    """
    Publish a new immutable version snapshot of the quiz.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            quiz = Quiz.objects.get(pk=pk, owner=request.user)
        except Quiz.DoesNotExist:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        version = QuizService.publish_quiz_version(quiz)
        return Response(QuizVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class QuizStudentPreviewView(APIView):
    """
    Zero-Knowledge student preview endpoint.
    Omits all correct answers, secret keys, and explanations.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            quiz = Quiz.objects.get(pk=pk, owner=request.user)
        except Quiz.DoesNotExist:
            return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)

        preview_data = QuizService.get_student_sanitized_quiz(quiz)
        return Response(preview_data)
