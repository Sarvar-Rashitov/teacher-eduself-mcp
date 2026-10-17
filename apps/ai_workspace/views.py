"""
AI Workspace REST API Views.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import async_to_sync

from apps.quizzes.models import Question
from apps.ai_workspace.schemas import QuizRequirements
from apps.ai_workspace.generator import AIQuizGenerator
from apps.ai_workspace.tools import PlatformTools
from apps.ai_workspace.diff_engine import AIDiffEngine, QuestionLockedError


class GenerateQuizAPIView(APIView):
    """
    POST /api/ai/generate/
    Mavzu bo'yicha yangi test generatsiya qilish va draft sifatida saqlash.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            req = QuizRequirements(**request.data)
        except Exception as e:
            return Response({'error': f"Parametrlar xatosi: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            generated_quiz = async_to_sync(AIQuizGenerator.generate_quiz)(
                requirements=req,
                user=request.user
            )
            # Draft modelini yaratish
            quiz_instance = PlatformTools.create_quiz_draft(generated_quiz, author=request.user)

            return Response({
                'message': "Viktorina muvaffaqiyatli generatsiya qilindi va qoralama sifatida saqlandi.",
                'quiz_id': str(quiz_instance.id),
                'title': quiz_instance.title,
                'question_count': quiz_instance.questions.count(),
                'suggested_game_mode': generated_quiz.suggested_game_mode
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f"Generatsiyada xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReviseQuestionAPIView(APIView):
    """
    POST /api/ai/revise/
    Bitta savolni tahrirlash taklifini (Diff) tayyorlash.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        q_id = request.data.get('question_id')
        instruction = request.data.get('instruction')

        if not q_id or not instruction:
            return Response({'error': "question_id va instruction kiritilishi shart."}, status=status.HTTP_400_BAD_REQUEST)

        question = Question.objects.filter(id=q_id).first()
        if not question:
            return Response({'error': "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        try:
            AIDiffEngine.verify_not_locked(question)
        except QuestionLockedError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)

        q_dict = {
            "order": question.order_index,
            "prompt": question.prompt,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
            "points": question.points,
            "time_limit_seconds": question.time_limit_seconds
        }

        try:
            proposal = async_to_sync(AIQuizGenerator.revise_single_question)(
                current_question_dict=q_dict,
                instruction=instruction,
                user=request.user
            )

            # Diff hisoblash
            proposed_dict = proposal.new_question_data.model_dump()
            diff_res = AIDiffEngine.compute_question_diff(q_dict, proposed_dict)

            return Response({
                'proposal': proposal.model_dump(),
                'diff': diff_res
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f"Tahrirlashda xatolik: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplyRevisionAPIView(APIView):
    """
    POST /api/ai/apply-revision/
    O'qituvchi tasdiqlagan tahrirni savolga qo'llash.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        q_id = request.data.get('question_id')
        new_data = request.data.get('new_data', {})

        question = Question.objects.filter(id=q_id).first()
        if not question:
            return Response({'error': "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        try:
            updated = AIDiffEngine.apply_revision(question, new_data)
            return Response({
                'message': "Savol muvaffaqiyatli yangilandi.",
                'question_id': str(updated.id),
                'prompt': updated.prompt
            }, status=status.HTTP_200_OK)
        except QuestionLockedError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class SuggestGameModesAPIView(APIView):
    """
    GET /api/ai/suggest-modes/
    Dars parametrlariga qarab o'yin rejimlarini tavsiya etish.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student_count = int(request.query_params.get('student_count', 20))
        duration = int(request.query_params.get('duration_minutes', 15))
        goal = request.query_params.get('learning_goal', 'general')

        recommendations = PlatformTools.suggest_game_modes(student_count, duration, goal)
        return Response({'recommendations': recommendations})
