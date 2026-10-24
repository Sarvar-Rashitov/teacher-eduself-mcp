"""
REST API Endpoints for AI Workspace:
- POST /api/v1/ai/workspace/generate/
- POST /api/v1/ai/workspace/revise-question/
- POST /api/v1/ai/workspace/apply-diff/
- POST /api/v1/ai/workspace/lock-question/
- POST /api/v1/ai/workspace/validate/
- GET  /api/v1/ai/workspace/game-modes/
"""

import logging
from asgiref.sync import async_to_sync
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from quizzes.models import Question
from quizzes.serializers import QuestionSerializer
from .generator import AIQuizGenerator
from .diff_engine import AIDiffEngine
from .tools import PlatformTools
from .schemas import AIQuestionRevisionProposal

logger = logging.getLogger(__name__)


class GenerateQuizAPIView(APIView):
    """
    POST /api/v1/ai/workspace/generate/
    Generates a structured classroom quiz adhering to Bloom's taxonomy,
    grade level, and shuffle-safety requirements.
    Optionally saves directly to a Quiz draft.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        topic = request.data.get("topic")
        if not topic or not str(topic).strip():
            return Response(
                {"error": "Viktorina mavzusi ('topic') ko'rsatilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = request.data.get("subject", "Umumiy")
        grade_level = int(request.data.get("grade_level", 7))
        question_count = int(request.data.get("question_count", 5))
        difficulty = request.data.get("difficulty", "medium")
        language = request.data.get("language", "uz")
        additional_instructions = request.data.get("additional_instructions")
        save_draft = bool(request.data.get("save_draft", False))
        preferred_provider = request.data.get("preferred_provider")
        preferred_model = request.data.get("preferred_model")

        generator = AIQuizGenerator()

        try:
            generated_quiz = async_to_sync(generator.generate_quiz)(
                topic=topic,
                grade_level=grade_level,
                language=language,
                question_count=question_count,
                difficulty=difficulty,
                subject=subject,
                additional_instructions=additional_instructions,
                preferred_provider=preferred_provider,
                preferred_model=preferred_model,
                user=request.user,
            )
        except Exception as exc:
            logger.error(f"Quiz generation failed: {exc}", exc_info=True)
            return Response(
                {"error": f"Viktorina generatsiyasi muvaffaqiyatsiz bo'ldi: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        quiz_dict = generated_quiz.model_dump()
        response_data = {"generated_quiz": quiz_dict}

        if save_draft:
            try:
                draft = PlatformTools.create_quiz_draft(
                    title=generated_quiz.title,
                    questions_data=quiz_dict["questions"],
                    author=request.user,
                    description=generated_quiz.description,
                    subject=generated_quiz.subject,
                    grade_level=generated_quiz.grade_level,
                )
                response_data["quiz_id"] = str(draft.id)
                response_data["status"] = "draft_created"
            except Exception as exc:
                logger.error(f"Draft saving failed: {exc}", exc_info=True)
                return Response(
                    {"error": f"Qoralama yaratishda xatolik: {str(exc)}", "generated_quiz": quiz_dict},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(response_data, status=status.HTTP_200_OK)


class ReviseQuestionAPIView(APIView):
    """
    POST /api/v1/ai/workspace/revise-question/
    Generates an AI revision proposal for a single question based on teacher instructions.
    Enforces Question Lock guardrail (is_locked=True raises 403).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question_id = request.data.get("question_id")
        revision_instruction = request.data.get("revision_instruction")

        if not question_id or not revision_instruction:
            return Response(
                {"error": "'question_id' va 'revision_instruction' maydonlari talab qilinadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            question = Question.objects.select_related("quiz").get(id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        # Enforce Question Lock Guardrail
        if question.is_locked:
            return Response(
                {
                    "error": f"Savol #{question.order_index} qulflangan (is_locked=True). "
                    f"O'qituvchi tomonidan qulflangan savollarni AI tahrirlashi taqiqlanadi."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        generator = AIQuizGenerator()
        diff_engine = AIDiffEngine()

        orig_data = {
            "order": question.order_index,
            "prompt": question.prompt,
            "type": question.type,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation or "",
            "difficulty": question.difficulty,
            "time_limit_seconds": question.time_limit_seconds,
            "points": question.points,
        }

        try:
            proposal = async_to_sync(generator.revise_single_question)(
                original_question=orig_data,
                revision_instruction=revision_instruction,
                subject=question.quiz.subject,
                grade_level=question.quiz.grade_level,
                preferred_provider=request.data.get("preferred_provider"),
                preferred_model=request.data.get("preferred_model"),
                user=request.user,
            )
            diff_result = diff_engine.propose_revision(question, proposal)
            return Response(diff_result, status=status.HTTP_200_OK)
        except PermissionDenied as pe:
            return Response({"error": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            logger.error(f"Question revision failed: {exc}", exc_info=True)
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApplyDiffAPIView(APIView):
    """
    POST /api/v1/ai/workspace/apply-diff/
    Applies an approved AI revision proposal to a Question.
    Enforces Question Lock guardrail.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question_id = request.data.get("question_id")
        proposal_data = request.data.get("proposal")

        if not question_id or not proposal_data:
            return Response(
                {"error": "'question_id' va 'proposal' talab qilinadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            question = Question.objects.select_related("quiz").get(id=question_id)
        except Question.DoesNotExist:
            return Response({"error": "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if question.is_locked:
            return Response(
                {"error": "Savol qulflangan (is_locked=True). Tahrir qo'llanilishi mumkin emas."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            proposal_obj = AIQuestionRevisionProposal.model_validate(proposal_data)
            diff_engine = AIDiffEngine()
            updated_question = diff_engine.apply_proposal(question, proposal_obj)
            return Response(
                {
                    "status": "applied",
                    "question_id": str(updated_question.id),
                    "version": updated_question.version,
                    "question": QuestionSerializer(updated_question).data,
                },
                status=status.HTTP_200_OK,
            )
        except PermissionDenied as pe:
            return Response({"error": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            logger.error(f"Applying diff failed: {exc}", exc_info=True)
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LockQuestionAPIView(APIView):
    """
    POST /api/v1/ai/workspace/lock-question/
    Locks or unlocks a question to protect it from automated AI modification.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        question_id = request.data.get("question_id")
        is_locked = request.data.get("is_locked")

        if question_id is None or is_locked is None:
            return Response(
                {"error": "'question_id' va 'is_locked' ko'rsatilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            question = PlatformTools.lock_question(
                question_id=question_id,
                is_locked=bool(is_locked),
                user=request.user,
            )
            return Response(
                {
                    "status": "success",
                    "question_id": str(question.id),
                    "is_locked": question.is_locked,
                },
                status=status.HTTP_200_OK,
            )
        except Question.DoesNotExist:
            return Response({"error": "Savol topilmadi."}, status=status.HTTP_404_NOT_FOUND)
        except PermissionDenied as pe:
            return Response({"error": str(pe)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidateQuizAPIView(APIView):
    """
    POST /api/v1/ai/workspace/validate/
    Validates quiz structure and rules (shuffle safety, option counts, correct answer presence).
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        quiz_data = request.data.get("quiz_data")
        if not quiz_data or not isinstance(quiz_data, dict):
            return Response(
                {"error": "'quiz_data' lug'at shaklida ko'rsatilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = PlatformTools.validate_quiz_content(quiz_data)
        return Response(result, status=status.HTTP_200_OK)


class GameModesAPIView(APIView):
    """
    GET /api/v1/ai/workspace/game-modes/
    Returns classroom game mode recommendations based on subject, grade, and question count.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        subject = request.query_params.get("subject", "Umumiy")
        grade_level = int(request.query_params.get("grade_level", 7))
        question_count = int(request.query_params.get("question_count", 5))

        recommendation = PlatformTools.suggest_game_modes(
            subject=subject,
            grade_level=grade_level,
            question_count=question_count,
        )
        return Response(recommendation, status=status.HTTP_200_OK)
