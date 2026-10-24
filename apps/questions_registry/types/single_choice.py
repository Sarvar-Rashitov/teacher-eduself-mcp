from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class SingleChoiceQuestionType(BaseQuestionType):
    """
    Standard Single Choice question type (Yagona tanlovli test).
    Requires 2 to 6 options, with exactly 1 correct option.
    """

    type_id = "single_choice"
    aliases = ("single_select",)
    display_name = "Single Choice"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        if not isinstance(options, list):
            raise QuestionValidationError("'options' must be a list of option objects.")

        if len(options) < 2 or len(options) > 6:
            raise QuestionValidationError(
                f"Single choice questions must have between 2 and 6 options. Provided: {len(options)}."
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

        # Validate correct_answer
        correct_id = self._extract_correct_id(correct_answer)
        if not correct_id:
            raise QuestionValidationError("A valid 'correct_option_id' must be specified in correct_answer.")

        if correct_id not in option_ids:
            raise QuestionValidationError(
                f"Correct option id '{correct_id}' is not present in options list."
            )

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_id = self._extract_submitted_id(submission)
        target_id = self._extract_correct_id(correct_answer)

        is_match = (submitted_id is not None) and (str(submitted_id).strip() == str(target_id).strip())
        score_fraction = 1.0 if is_match else 0.0

        return EvaluationResult(
            is_correct=is_match,
            score_fraction=score_fraction,
            feedback="Correct answer!" if is_match else "Incorrect answer.",
            details={"selected_option_id": submitted_id, "correct_option_id": target_id}
        )

    def _extract_correct_id(self, correct_answer: Any) -> str | None:
        if isinstance(correct_answer, dict):
            return correct_answer.get("correct_option_id") or correct_answer.get("id")
        if isinstance(correct_answer, str):
            return correct_answer.strip()
        return None

    def _extract_submitted_id(self, submission: Any) -> str | None:
        if isinstance(submission, dict):
            return submission.get("selected_option_id") or submission.get("id")
        if isinstance(submission, str):
            return submission.strip()
        return None
