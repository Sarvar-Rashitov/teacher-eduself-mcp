"""
AI Diff Engine for Question Revision and Question Lock Guardrail Enforcement.
"""

from typing import Any, Dict, List, Optional
from rest_framework.exceptions import PermissionDenied

from quizzes.models import Question
from .schemas import AIQuestionRevisionProposal, AIGeneratedQuestion


class AIDiffEngine:
    """
    Computes visual and structural diffs between original Question models
    and AI-generated revision proposals, enforcing the Question Lock guardrail.
    """

    @staticmethod
    def check_lock_guardrail(question: Question) -> None:
        """
        Enforces DOC-77 / Phase 06 Question Lock Guardrail:
        If question.is_locked is True, AI revisions and deletions are strictly blocked.
        """
        if getattr(question, "is_locked", False):
            raise PermissionDenied(
                f"Savol #{question.order_index} qulflangan (is_locked=True). "
                f"O'qituvchi tomonidan qulflangan savollarni AI tahrirlashi yoki o'chirishi taqiqlanadi."
            )

    def propose_revision(
        self,
        original_question: Question,
        proposal: AIQuestionRevisionProposal,
    ) -> Dict[str, Any]:
        """
        Generates a granular field-by-field diff proposal.
        Raises PermissionDenied if the question is locked.
        """
        self.check_lock_guardrail(original_question)

        new_q: AIGeneratedQuestion = proposal.new_question_data
        diffs: Dict[str, Dict[str, Any]] = {}

        # 1. Prompt diff
        if original_question.prompt != new_q.prompt:
            diffs["prompt"] = {
                "before": original_question.prompt,
                "after": new_q.prompt,
            }

        # 2. Type diff
        if original_question.type != new_q.type.value:
            diffs["type"] = {
                "before": original_question.type,
                "after": new_q.type.value,
            }

        # 3. Options diff
        new_opts = [opt.model_dump() for opt in new_q.options]
        if original_question.options != new_opts:
            diffs["options"] = {
                "before": original_question.options,
                "after": new_opts,
            }

        # 4. Correct answer diff
        if original_question.correct_answer != new_q.correct_answer:
            diffs["correct_answer"] = {
                "before": original_question.correct_answer,
                "after": new_q.correct_answer,
            }

        # 5. Explanation diff
        if (original_question.explanation or "") != (new_q.explanation or ""):
            diffs["explanation"] = {
                "before": original_question.explanation,
                "after": new_q.explanation,
            }

        # 6. Difficulty diff
        if original_question.difficulty != new_q.difficulty.value:
            diffs["difficulty"] = {
                "before": original_question.difficulty,
                "after": new_q.difficulty.value,
            }

        # 7. Time limit diff
        if original_question.time_limit_seconds != new_q.time_limit_seconds:
            diffs["time_limit_seconds"] = {
                "before": original_question.time_limit_seconds,
                "after": new_q.time_limit_seconds,
            }

        # 8. Points diff
        if original_question.points != new_q.points:
            diffs["points"] = {
                "before": original_question.points,
                "after": new_q.points,
            }

        return {
            "question_id": str(original_question.id),
            "order_index": original_question.order_index,
            "is_locked": original_question.is_locked,
            "change_summary": proposal.change_summary,
            "modified_fields": list(diffs.keys()),
            "diffs": diffs,
            "proposed_data": new_q.model_dump(),
        }

    def apply_proposal(
        self,
        original_question: Question,
        proposal: AIQuestionRevisionProposal,
    ) -> Question:
        """
        Applies the revision proposal directly to the Question instance and saves it.
        Increments the question version and enforces lock check.
        """
        self.check_lock_guardrail(original_question)

        new_q: AIGeneratedQuestion = proposal.new_question_data

        original_question.prompt = new_q.prompt
        original_question.type = new_q.type.value
        original_question.options = [opt.model_dump() for opt in new_q.options]
        original_question.correct_answer = new_q.correct_answer
        original_question.accepted_alternatives = new_q.accepted_alternatives or []
        original_question.explanation = new_q.explanation
        original_question.difficulty = new_q.difficulty.value
        original_question.time_limit_seconds = new_q.time_limit_seconds
        original_question.points = new_q.points
        original_question.version = (original_question.version or 1) + 1

        original_question.full_clean()
        original_question.save()

        return original_question
