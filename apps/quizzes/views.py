"""
API views for Quiz and Question management.
Provides CRUD, publishing snapshots, and zero-knowledge student preview endpoints.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import json
from apps.questions_registry.registry import question_type_registry
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


class QuizSaveFullView(APIView):
    """
    Atomic bulk save/update endpoint for Quiz Editor.
    Creates or updates Quiz and synchronizes all questions with QuestionTypeRegistry validation.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data = request.data
        quiz_id = data.get('id')
        title = (data.get('title') or '').strip()
        subject = (data.get('subject') or 'Fizika').strip()
        grade_level = data.get('grade_level', 7)
        status_val = data.get('status', 'draft')
        description = data.get('description', '')
        questions_data = data.get('questions', [])

        if not title:
            return Response({'error': "Viktorina nomi ('title') bo‘sh bo‘lishi mumkin emas."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Fetch existing quiz or create new
        if quiz_id:
            try:
                quiz = Quiz.objects.select_for_update().get(id=quiz_id, owner=request.user)
                quiz.title = title
                quiz.subject = subject
                quiz.grade_level = grade_level
                quiz.status = status_val
                quiz.description = description
                quiz.save()
            except Quiz.DoesNotExist:
                return Response({'error': 'Viktorina topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            quiz = QuizService.create_quiz(
                owner=request.user,
                title=title,
                subject=subject,
                grade_level=grade_level,
                description=description
            )
            quiz.status = status_val
            quiz.save()

        # 2. Synchronize questions
        existing_questions = {str(q.id): q for q in quiz.questions.all()}
        processed_ids = set()

        for idx, q_item in enumerate(questions_data):
            q_id = q_item.get('id')
            q_type = q_item.get('type', 'single_choice')
            prompt = q_item.get('prompt', '')
            options = q_item.get('options', [])
            correct_answer = q_item.get('correct_answer')
            accepted_alternatives = q_item.get('accepted_alternatives', [])
            explanation = q_item.get('explanation', '')
            points = q_item.get('points', 1000)
            time_limit = q_item.get('time_limit_seconds', 30)
            difficulty = q_item.get('difficulty', 'medium')
            is_locked = q_item.get('is_locked', False)
            media_url = q_item.get('media_url')
            media_type = q_item.get('media_type')

            # Plugin validation
            try:
                plugin = question_type_registry.get(q_type)
                plugin.validate_payload(options=options, correct_answer=correct_answer)
            except (QuestionValidationError, QuestionTypeNotFoundError) as exc:
                transaction.set_rollback(True)
                return Response({'error': f"{idx + 1}-savol xatosi: {str(exc)}"}, status=status.HTTP_400_BAD_REQUEST)

            if q_id and str(q_id) in existing_questions:
                q_obj = existing_questions[str(q_id)]
                q_obj.type = q_type
                q_obj.prompt = prompt
                q_obj.options = options
                q_obj.correct_answer = correct_answer
                q_obj.accepted_alternatives = accepted_alternatives
                q_obj.explanation = explanation
                q_obj.points = points
                q_obj.time_limit_seconds = time_limit
                q_obj.difficulty = difficulty
                q_obj.order_index = idx
                q_obj.is_locked = is_locked
                q_obj.media_url = media_url
                q_obj.media_type = media_type
                q_obj.save()
                processed_ids.add(str(q_id))
            else:
                new_q = Question.objects.create(
                    quiz=quiz,
                    type=q_type,
                    prompt=prompt,
                    options=options,
                    correct_answer=correct_answer,
                    accepted_alternatives=accepted_alternatives,
                    explanation=explanation,
                    points=points,
                    time_limit_seconds=time_limit,
                    difficulty=difficulty,
                    order_index=idx,
                    is_locked=is_locked,
                    media_url=media_url,
                    media_type=media_type
                )
                processed_ids.add(str(new_q.id))

        # Delete removed questions
        for old_id, old_q in existing_questions.items():
            if old_id not in processed_ids:
                old_q.delete()

        # 3. If published, snapshot version
        if quiz.status == 'published':
            QuizService.publish_quiz_version(quiz)

        return Response({
            'status': 'ok',
            'quiz_id': str(quiz.id),
            'message': 'Viktorina muvaffaqiyatli saqlandi! 💾',
            'quiz': QuizSerializer(quiz).data
        }, status=status.HTTP_200_OK if quiz_id else status.HTTP_201_CREATED)


def teacher_dashboard_view(request):
    """
    Renders the teacher dashboard with Bento Grid quizzes and quick actions.
    All statistics and quizzes are dynamically queried from the SQLite database.
    """
    from django.shortcuts import render
    from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission

    quizzes = []
    quizzes_count = 0
    completed_sessions_count = 0
    active_students_count = 0
    average_accuracy = 0

    if request.user.is_authenticated:
        quizzes = Quiz.objects.filter(owner=request.user).prefetch_related('questions').order_by('-created_at')
        quizzes_count = quizzes.count()
        completed_sessions_count = LiveSession.objects.filter(host=request.user).count()
        active_students_count = Participant.objects.filter(session__host=request.user).values('nickname').distinct().count()

        submissions = AnswerSubmission.objects.filter(session__host=request.user)
        total_subs = submissions.count()
        if total_subs > 0:
            correct_subs = submissions.filter(is_correct=True).count()
            average_accuracy = round((correct_subs / total_subs) * 100)
    else:
        # For public demo view, show recent published quizzes
        quizzes = Quiz.objects.filter(status='published').prefetch_related('questions').order_by('-created_at')[:6]
        quizzes_count = quizzes.count()

    return render(request, 'dashboard/teacher_home.html', {
        'quizzes': quizzes,
        'quizzes_count': quizzes_count,
        'completed_sessions_count': completed_sessions_count,
        'active_students_count': active_students_count,
        'average_accuracy': average_accuracy,
        'user': request.user,
    })


def quiz_editor_view(request, quiz_id=None):
    """
    Renders the universal 3-column quiz editor.
    Requires authentication: unauthenticated users are redirected to login.
    Passes serialized quiz data for interactive client-side editing.
    """
    from django.shortcuts import render, redirect

    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    quiz = None
    quiz_json = 'null'
    if quiz_id:
        try:
            quiz = Quiz.objects.filter(pk=quiz_id, owner=request.user).first()
            if not quiz:
                quiz = Quiz.objects.filter(pk=quiz_id).first()
            if quiz:
                quiz_json = json.dumps(QuizSerializer(quiz).data)
        except Exception:
            quiz = None

    return render(request, 'editor/quiz_editor.html', {
        'quiz': quiz,
        'quiz_json': quiz_json,
        'user': request.user,
    })



def leaderboard_page_view(request):
    """
    Renders the public & national 3D Leaderboard Podium and Rankings page.
    """
    from django.shortcuts import render
    top_3 = [
        {"rank": 1, "nickname": "Aziza Karimova", "school": "7-Maktab (Toshkent)", "score": 3450, "streak": 8, "accolade": "Humo Qanoti"},
        {"rank": 2, "nickname": "Jasur Aliyev", "school": "14-Prezident Maktabi (Samarqand)", "score": 3120, "streak": 6, "accolade": "Qanotli Tulpor"},
        {"rank": 3, "nickname": "Madina Shokirova", "school": "1-IDUM (Farg'ona)", "score": 2890, "streak": 5, "accolade": "Uchqur Lochin"},
    ]
    rankings = [
        {"rank": 4, "nickname": "Otabek Rustamov", "school": "21-Maktab (Buxoro)", "score": 2650, "accuracy": "94%"},
        {"rank": 5, "nickname": "Zilola Yusupova", "school": "5-Gimnaziya (Andijon)", "score": 2420, "accuracy": "91%"},
        {"rank": 6, "nickname": "Bobur Mirzayev", "school": "32-Maktab (Namangan)", "score": 2280, "accuracy": "89%"},
        {"rank": 7, "nickname": "Dilnoza Saidova", "school": "8-Maktab (Xorazm)", "score": 2150, "accuracy": "88%"},
        {"rank": 8, "nickname": "Sardor Ahmedov", "school": "19-Maktab (Qashqadaryo)", "score": 2040, "accuracy": "85%"},
    ]
    return render(request, 'leaderboard/leaderboard_page.html', {
        'user': request.user,
        'top_3': top_3,
        'rankings': rankings,
    })


