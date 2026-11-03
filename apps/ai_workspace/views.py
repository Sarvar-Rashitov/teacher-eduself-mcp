"""
REST API Endpoints for Teacher AI Workspace, Quiz Generation, Diff Proposals, and Tool Calling.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.quizzes.models import Quiz, Question
from .schemas import QuizRequirements, AIQuestionRevisionProposal
from .generator import AIQuizGenerator
from .diff_engine import AIDiffEngine, LockedQuestionError
from .tools import PlatformTools


class GenerateQuizAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            req = QuizRequirements(
                subject=data.get("subject", "Umumiy fan"),
                grade_level=int(data.get("grade_level", 7)),
                topic=data.get("topic", "Mavzu"),
                question_count=int(data.get("question_count", 10)),
                difficulty=data.get("difficulty", "medium"),
                language=data.get("language", "uz"),
                target_game_mode=data.get("target_game_mode", "classic"),
            )
        except Exception as e:
            return Response({"error": f"Invalid requirements: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        generator = AIQuizGenerator()
        try:
            quiz_spec = generator.generate_quiz(
                requirements=req,
                user=request.user,
                additional_context=data.get("additional_context"),
                provider_override=data.get("provider"),
                model_override=data.get("model"),
            )
        except Exception as e:
            return Response({"error": f"Generation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # If teacher requested immediate draft creation
        if data.get("save_as_draft", False):
            draft_info = PlatformTools.create_quiz_draft(quiz_spec, request.user)
            return Response({
                "quiz_spec": quiz_spec.model_dump(),
                "draft": draft_info,
            }, status=status.HTTP_201_CREATED)

        return Response(quiz_spec.model_dump(), status=status.HTTP_200_OK)


class ReviseQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get("quiz_id")
        order = request.data.get("question_order")
        instruction = request.data.get("instruction")

        if not quiz_id or order is None or not instruction:
            return Response(
                {"error": "quiz_id, question_order, and instruction are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        quiz = Quiz.objects.filter(id=quiz_id, owner=request.user).first()
        if not quiz:
            return Response({"error": "Quiz not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        generator = AIQuizGenerator()
        try:
            proposal = generator.revise_question(
                quiz=quiz,
                question_order=int(order),
                instruction=instruction,
                user=request.user,
            )
        except LockedQuestionError as e:
            return Response({"error": str(e)}, status=status.HTTP_423_LOCKED)
        except Exception as e:
            return Response({"error": f"Revision failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Compute diff with existing record
        current_question = quiz.questions.filter(order_index=int(order) - 1).first()
        diff = AIDiffEngine.compute_question_diff(
            current_question=current_question,
            new_data=proposal.new_question_data,
            change_summary=proposal.change_summary,
        )

        return Response({
            "proposal": proposal.model_dump(),
            "diff": {
                "question_order": diff.question_order,
                "is_locked": diff.is_locked,
                "has_changes": diff.has_changes,
                "change_summary": diff.change_summary,
                "changes": [
                    {
                        "field": c.field,
                        "old_value": c.old_value,
                        "new_value": c.new_value,
                        "is_changed": c.is_changed,
                    }
                    for c in diff.changes
                ]
            }
        }, status=status.HTTP_200_OK)


class ApplyProposalAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quiz_id = request.data.get("quiz_id")
        order = request.data.get("question_order")
        proposal_data = request.data.get("proposal")

        if not quiz_id or order is None or not proposal_data:
            return Response({"error": "quiz_id, question_order, and proposal are required."}, status=status.HTTP_400_BAD_REQUEST)

        quiz = Quiz.objects.filter(id=quiz_id, owner=request.user).first()
        if not quiz:
            return Response({"error": "Quiz not found or unauthorized."}, status=status.HTTP_404_NOT_FOUND)

        question = quiz.questions.filter(order_index=int(order) - 1).first()
        if not question:
            return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            proposal = AIQuestionRevisionProposal.model_validate(proposal_data)
            updated_question = AIDiffEngine.apply_proposal(question, proposal)
        except LockedQuestionError as e:
            return Response({"error": str(e)}, status=status.HTTP_423_LOCKED)
        except Exception as e:
            return Response({"error": f"Failed to apply proposal: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Proposal applied successfully.",
            "question_id": str(updated_question.id),
            "order": updated_question.order_index + 1,
            "prompt": updated_question.prompt,
            "options": updated_question.options,
            "correct_answer": updated_question.correct_answer,
            "explanation": updated_question.explanation,
        }, status=status.HTTP_200_OK)


class LockQuestionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question_id = request.data.get("question_id")
        is_locked = request.data.get("is_locked", True)

        if not question_id:
            return Response({"error": "question_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = PlatformTools.lock_question(
                question_id=question_id,
                is_locked=bool(is_locked),
                teacher_user=request.user,
            )
            return Response(result, status=status.HTTP_200_OK)
        except PermissionError as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
