"""
AI Quiz Generation Engine with Self-Healing Validation Loop and Locked Question Protection.
Integrates with Phase 05 ModelRouter.
"""

import json
import logging
from typing import Any, List, Optional
from apps.ai_gateway.router import ModelRouter
from apps.quizzes.models import Quiz, Question
from .schemas import (
    AIGeneratedQuiz,
    AIGeneratedQuestion,
    QuizRequirements,
    AIQuestionRevisionProposal,
)
from .prompts import (
    build_quiz_generation_messages,
    build_question_revision_messages,
)
from .validator import ContentValidator
from .diff_engine import LockedQuestionError

logger = logging.getLogger(__name__)


class GenerationError(Exception):
    """Raised when quiz generation fails after self-healing attempts."""
    pass


class AIQuizGenerator:
    """
    Orchestrates quiz generation, revision, and self-healing validation via ModelRouter.
    """

    def __init__(self, router: Optional[ModelRouter] = None):
        self.router = router or ModelRouter()

    def generate_quiz(
        self,
        requirements: QuizRequirements,
        user: Any = None,
        additional_context: Optional[str] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        max_self_healing_retries: int = 2,
    ) -> AIGeneratedQuiz:
        """
        Generates a complete quiz conforming to AIGeneratedQuiz with self-healing validation.
        """
        task_type = "math_stem" if requirements.subject.lower() in ("fizika", "matematika", "kimyo", "algebra", "geometriya") else "general"

        messages = build_quiz_generation_messages(
            req=requirements,
            additional_context=additional_context,
        )

        for attempt in range(max_self_healing_retries + 1):
            try:
                quiz_data = self.router.generate_structured(
                    messages=messages,
                    schema=AIGeneratedQuiz,
                    task_type=task_type,
                    user=user,
                    provider_override=provider_override,
                    model_override=model_override,
                )
            except Exception as e:
                logger.error("ModelRouter generation failed on attempt %d: %s", attempt + 1, e)
                if attempt == max_self_healing_retries:
                    raise GenerationError(f"AI generation failed: {str(e)}") from e
                continue

            # Validate generated quiz
            report = ContentValidator.validate_quiz(quiz_data)
            if report.is_valid:
                return quiz_data

            # If validation errors occurred, prepare self-healing re-prompt
            logger.warning("Validation failed on attempt %d: %s", attempt + 1, report.errors)
            if attempt < max_self_healing_retries:
                error_summary = "\n- ".join(report.errors)
                healing_prompt = (
                    f"DIQQAT: Oldingi javobingda quyidagi xatoliklar aniqlandi:\n- {error_summary}\n"
                    "Ushbu xatoliklarni bartaraf etib, qat'iy AIGeneratedQuiz sxemasi bo'yicha qayta generatsiya qil."
                )
                messages.append({"role": "user", "content": healing_prompt})

        # Return best-effort quiz if retries exhausted, but flag warning
        return quiz_data

    def revise_question(
        self,
        quiz: Quiz,
        question_order: int,
        instruction: str,
        user: Any = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> AIQuestionRevisionProposal:
        """
        Revises a single question while strictly enforcing question locking.
        """
        question = quiz.questions.filter(order_index=question_order - 1).first()
        if not question:
            raise ValueError(f"Question with order {question_order} not found in quiz {quiz.id}.")

        if question.is_locked:
            raise LockedQuestionError(
                f"Question {question_order} is locked by teacher and cannot be modified."
            )

        current_data = {
            "order": question.order_index + 1,
            "prompt": question.prompt,
            "type": question.type,
            "options": question.options,
            "correct_answer": question.correct_answer,
            "explanation": question.explanation or "",
            "points": question.points,
            "time_limit_seconds": question.time_limit_seconds,
        }

        messages = build_question_revision_messages(
            current_question_json=json.dumps(current_data, ensure_ascii=False, indent=2),
            instruction=instruction,
        )

        proposal = self.router.generate_structured(
            messages=messages,
            schema=AIQuestionRevisionProposal,
            task_type="general",
            user=user,
            provider_override=provider_override,
            model_override=model_override,
        )
        return proposal

    def regenerate_quiz_preserving_locked(
        self,
        quiz: Quiz,
        requirements: QuizRequirements,
        user: Any = None,
    ) -> AIGeneratedQuiz:
        """
        Regenerates a quiz while preserving locked questions in their exact slots.
        """
        locked_questions = list(quiz.questions.filter(is_locked=True).order_by("order_index"))
        locked_orders = [q.order_index + 1 for q in locked_questions]

        locked_notice = None
        if locked_orders:
            locked_notice = (
                f"Quyidagi tartib raqamli savollar o'qituvchi tomonidan qulflangan: {locked_orders}. "
                "Ularning matni, variantlari va to'g'ri javoblari mutlaqo o'zgarmasdan saqlansin!"
            )

        new_quiz = self.generate_quiz(
            requirements=requirements,
            user=user,
            additional_context=locked_notice,
        )

        # Merge locked questions back into the exact slots
        merged_questions: List[AIGeneratedQuestion] = []
        new_q_iter = iter(new_quiz.questions)

        for order in range(1, requirements.question_count + 1):
            locked_q = next((lq for lq in locked_questions if lq.order_index + 1 == order), None)
            if locked_q:
                # Reconstruct AIGeneratedQuestion from database locked question
                from .schemas import AIGeneratedOption, QuestionTypeEnum
                opts = [AIGeneratedOption(id=opt.get("id", "A"), text=opt.get("text", "")) for opt in locked_q.options]
                q_type = QuestionTypeEnum.SINGLE_CHOICE
                try:
                    q_type = QuestionTypeEnum(locked_q.type)
                except Exception:
                    pass

                merged_questions.append(
                    AIGeneratedQuestion(
                        order=locked_q.order_index + 1,
                        prompt=locked_q.prompt,
                        type=q_type,
                        options=opts,
                        correct_answer=locked_q.correct_answer,
                        explanation=locked_q.explanation or "",
                        points=locked_q.points,
                        time_limit_seconds=locked_q.time_limit_seconds,
                    )
                )
            else:
                try:
                    next_q = next(new_q_iter)
                    next_q.order = order
                    merged_questions.append(next_q)
                except StopIteration:
                    break

        new_quiz.questions = merged_questions
        return new_quiz
