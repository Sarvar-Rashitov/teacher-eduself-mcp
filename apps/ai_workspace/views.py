import asyncio
from asgiref.sync import async_to_sync
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.ai_workspace.schemas import GenerateQuizRequest
from apps.ai_workspace.generator import AIQuizGenerator
from apps.ai_workspace.diff_engine import AIDiffEngine
from apps.ai_workspace.tools import lock_question, suggest_game_modes


class GenerateQuizView(APIView):
    """
    POST /api/ai/generate-quiz/
    Generates structured quiz according to teacher specifications.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            req_data = GenerateQuizRequest.model_validate(request.data)
        except Exception as e:
            return Response({"error": f"Invalid request payload: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        generator = AIQuizGenerator()
        try:
            quiz = async_to_sync(generator.generate_quiz)(req_data, user=request.user)
            return Response(quiz.model_dump(), status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ReviseQuestionView(APIView):
    """
    POST /api/ai/revise-question/
    Generates a structured revision proposal for a specific question.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        existing_question = request.data.get("existing_question")
        instruction = request.data.get("instruction")

        if not existing_question or not instruction:
            return Response(
                {"error": "Both 'existing_question' and 'instruction' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        generator = AIQuizGenerator()
        try:
            proposal = async_to_sync(generator.revise_question)(existing_question, instruction, user=request.user)
            return Response(proposal.model_dump(), status=status.HTTP_200_OK)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": f"Revision failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplyDiffView(APIView):
    """
    POST /api/ai/diff-apply/
    Applies approved changes to existing questions while protecting locked questions.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        original = request.data.get("original_questions", [])
        proposed = request.data.get("proposed_questions", [])
        accepted_orders = request.data.get("accepted_orders")
        if accepted_orders is not None:
            accepted_orders = set(accepted_orders)

        diff_summary = AIDiffEngine.compute_diff(original, proposed)
        merged = AIDiffEngine.apply_diff(original, proposed, accepted_orders=accepted_orders)

        return Response({
            "diff_summary": diff_summary,
            "merged_questions": merged,
        }, status=status.HTTP_200_OK)


class LockQuestionView(APIView):
    """
    POST /api/ai/tools/lock/
    Locks or unlocks a question to prevent AI overrides.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = str(request.data.get("quiz_id", ""))
        question_id = str(request.data.get("question_id", ""))
        is_locked = bool(request.data.get("is_locked", True))

        if not quiz_id or not question_id:
            return Response({"error": "quiz_id and question_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        success = lock_question(quiz_id, question_id, is_locked)
        return Response({"success": success, "is_locked": is_locked}, status=status.HTTP_200_OK)


class SuggestGameModesView(APIView):
    """
    GET /api/ai/tools/suggest-game-modes/?students=20&duration=15
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        students = int(request.query_params.get("students", 20))
        duration = int(request.query_params.get("duration", 15))
        goal = request.query_params.get("goal", "general")

        suggestions = suggest_game_modes(students, duration, goal)
        return Response({"suggestions": suggestions}, status=status.HTTP_200_OK)
