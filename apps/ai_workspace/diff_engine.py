"""
Diff Engine for Side-by-Side Proposal Visualization and Safe Application.
Ensures:
- 'No Silent Overwrites': O'qituvchi oldindan o'zgarishlarni aniq ko'radi.
- 'Question Locking': is_locked=True bo'lgan savollarni o'zgartirish taqiqlanadi.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from apps.quizzes.models import Question
from .schemas import AIGeneratedQuestion, AIQuestionRevisionProposal


class LockedQuestionError(Exception):
    """Raised when an operation attempts to modify or overwrite a locked question."""
    pass


@dataclass
class FieldDiff:
    field: str
    old_value: Any
    new_value: Any
    is_changed: bool


@dataclass
class QuestionDiff:
    question_order: int
    question_id: Optional[str]
    is_locked: bool
    has_changes: bool
    changes: List[FieldDiff] = field(default_factory=list)
    change_summary: str = ""


class AIDiffEngine:
    """
    Computes side-by-side differences and applies approved revisions.
    """

    @classmethod
    def compute_question_diff(
        cls,
        current_question: Question,
        new_data: AIGeneratedQuestion,
        change_summary: str = "",
    ) -> QuestionDiff:
        """
        Compares an existing Question model instance with proposed AIGeneratedQuestion.
        """
        diff = QuestionDiff(
            question_order=new_data.order,
            question_id=str(current_question.id) if current_question else None,
            is_locked=current_question.is_locked if current_question else False,
            has_changes=False,
            change_summary=change_summary,
        )

        if not current_question:
            # Brand new question proposal
            diff.has_changes = True
            diff.changes.append(FieldDiff("new_question", None, new_data.model_dump(), True))
            return diff

        # 1. Prompt
        old_prompt = current_question.prompt.strip()
        new_prompt = new_data.prompt.strip()
        diff.changes.append(FieldDiff("prompt", old_prompt, new_prompt, old_prompt != new_prompt))

        # 2. Options
        old_opts = current_question.options
        new_opts = [opt.model_dump() for opt in new_data.options]
        diff.changes.append(FieldDiff("options", old_opts, new_opts, old_opts != new_opts))

        # 3. Correct Answer
        old_ans = current_question.correct_answer
        new_ans = new_data.correct_answer
        diff.changes.append(FieldDiff("correct_answer", old_ans, new_ans, old_ans != new_ans))

        # 4. Explanation
        old_exp = (current_question.explanation or "").strip()
        new_exp = new_data.explanation.strip()
        diff.changes.append(FieldDiff("explanation", old_exp, new_exp, old_exp != new_exp))

        # 5. Points & Time Limit
        old_pts = current_question.points
        new_pts = new_data.points
        diff.changes.append(FieldDiff("points", old_pts, new_pts, old_pts != new_pts))

        old_time = current_question.time_limit_seconds
        new_time = new_data.time_limit_seconds
        diff.changes.append(FieldDiff("time_limit_seconds", old_time, new_time, old_time != new_time))

        diff.has_changes = any(c.is_changed for c in diff.changes)
        return diff

    @classmethod
    def apply_proposal(
        cls,
        question: Question,
        proposal: AIQuestionRevisionProposal,
    ) -> Question:
        """
        Applies approved revision proposal to a Question database record.
        Enforces question locking check.
        """
        if question.is_locked:
            raise LockedQuestionError(
                f"Question {question.id} (order {question.order_index + 1}) is locked and cannot be modified."
            )

        new_data = proposal.new_question_data
        question.prompt = new_data.prompt
        question.options = [opt.model_dump() for opt in new_data.options]
        question.correct_answer = new_data.correct_answer
        question.explanation = new_data.explanation
        question.points = new_data.points
        question.time_limit_seconds = new_data.time_limit_seconds

        question.save(update_fields=[
            "prompt", "options", "correct_answer", "explanation", "points", "time_limit_seconds"
        ])
        return question
