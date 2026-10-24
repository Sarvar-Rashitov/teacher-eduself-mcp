from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class MultipleChoiceQuestionType(BaseQuestionType):
    """
    Multiple Choice / Select question type (Ko‘p tanlovli test).
    Requires at least 3 options and 1 or more correct answers.
    Evaluates using partial credit with penalty formula.
    """

    type_id = "multiple_choice"
    aliases = ("multiple_select", "multi_select")
    display_name = "Multiple Choice"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        if not isinstance(options, list):
            raise QuestionValidationError("'options' must be a list of option objects.")

        if len(options) < 3:
            raise QuestionValidationError(
                f"Multiple choice questions must have at least 3 options. Provided: {len(options)}."
            )

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict):
                raise QuestionValidationError(f"Option at index {idx} must be a dictionary.")
            opt_id = opt.get("id")
            opt_text = opt.get("text")
            if not opt_id or not str(opt_id).strip():
                raise QuestionValidationError(f"Option at index {idx} must have a non-empty 'id'.")
            if opt_text is None or not str(opt_text).strip():
                raise QuestionValidationError(f"Option at index {idx} must have non-empty 'text'.")
            if opt_id in option_ids:
                raise QuestionValidationError(f"Duplicate option id '{opt_id}' found.")
            option_ids.add(opt_id)

        correct_ids = self._extract_correct_ids(correct_answer)
        if not correct_ids:
            raise QuestionValidationError("At least one correct option must be specified in correct_answer.")

        missing_ids = set(correct_ids) - option_ids
        if missing_ids:
            raise QuestionValidationError(
                f"Correct option IDs {list(missing_ids)} do not exist in the options list."
            )

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_ids = set(self._extract_submitted_ids(submission))
        correct_ids = set(self._extract_correct_ids(correct_answer))

        all_option_ids = set()
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict) and "id" in opt:
                    all_option_ids.add(opt["id"])
        else:
            all_option_ids = correct_ids.union(submitted_ids)

        wrong_ids = all_option_ids - correct_ids

        c_total = len(correct_ids)
        w_total = len(wrong_ids)

        c_selected = len(submitted_ids.intersection(correct_ids))
        w_selected = len(submitted_ids.intersection(wrong_ids))

        # DOC-52 3.2: Partial Credit with Penalty Formula
        # Score = max(0, (C_selected / C_total) - (W_selected / W_total))
        if c_total == 0:
            score_fraction = 0.0
        else:
            correct_ratio = c_selected / c_total
            penalty_ratio = (w_selected / w_total) if w_total > 0 else 0.0
            score_fraction = max(0.0, correct_ratio - penalty_ratio)

        is_perfect = (score_fraction == 1.0) and (c_selected == c_total) and (w_selected == 0)

        return EvaluationResult(
            is_correct=is_perfect,
            score_fraction=round(score_fraction, 4),
            feedback="All correct!" if is_perfect else (
                f"Partially correct ({c_selected}/{c_total} correct)." if score_fraction > 0 else "Incorrect."
            ),
            details={
                "selected_ids": list(submitted_ids),
                "correct_ids": list(correct_ids),
                "c_selected": c_selected,
                "c_total": c_total,
                "w_selected": w_selected,
                "w_total": w_total,
            }
        )

    def _extract_correct_ids(self, correct_answer: Any) -> list[str]:
        if isinstance(correct_answer, dict):
            raw = correct_answer.get("correct_option_ids") or correct_answer.get("correct_ids")
            if isinstance(raw, list):
                return [str(x) for x in raw]
        elif isinstance(correct_answer, list):
            return [str(x) for x in correct_answer]
        return []

    def _extract_submitted_ids(self, submission: Any) -> list[str]:
        if isinstance(submission, dict):
            raw = submission.get("selected_option_ids") or submission.get("selected_ids")
            if isinstance(raw, list):
                return [str(x) for x in raw]
        elif isinstance(submission, list):
            return [str(x) for x in submission]
        return []
