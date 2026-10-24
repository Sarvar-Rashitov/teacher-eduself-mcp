from typing import Any
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class TrueFalseQuestionType(BaseQuestionType):
    """
    True / False question type (To‘g‘ri / Noto‘g‘ri).
    Evaluates binary truth value.
    """

    type_id = "true_false"
    aliases = ("boolean",)
    display_name = "True / False"
    category = "Assessment"
    requires_answer_key = True
    auto_evaluable = True

    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        # Options are optional, but if provided, must be valid
        if options is not None and not isinstance(options, list):
            raise QuestionValidationError("'options' must be a list if provided.")

        correct_val = self._extract_bool(correct_answer)
        if correct_val is None:
            raise QuestionValidationError(
                "correct_answer must specify a valid boolean value (e.g. {'correct_value': true} or 'true'/'false')."
            )

    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        submitted_val = self._extract_bool(submission)
        correct_val = self._extract_bool(correct_answer)

        if submitted_val is None:
            return EvaluationResult(
                is_correct=False,
                score_fraction=0.0,
                feedback="No valid true/false answer submitted.",
                details={"submitted": submission, "expected": correct_val}
            )

        is_match = (submitted_val == correct_val)
        return EvaluationResult(
            is_correct=is_match,
            score_fraction=1.0 if is_match else 0.0,
            feedback="Correct!" if is_match else "Incorrect.",
            details={"submitted": submitted_val, "expected": correct_val}
        )

    def _extract_bool(self, val: Any) -> bool | None:
        if isinstance(val, bool):
            return val
        if isinstance(val, dict):
            if "correct_value" in val:
                return self._extract_bool(val["correct_value"])
            if "selected_value" in val:
                return self._extract_bool(val["selected_value"])
            if "correct_option_id" in val:
                return self._extract_bool(val["correct_option_id"])
            if "selected_option_id" in val:
                return self._extract_bool(val["selected_option_id"])
            if "id" in val:
                return self._extract_bool(val["id"])
        if isinstance(val, str):
            s = val.strip().lower()
            if s in ("true", "t", "1", "to'g'ri", "togri", "yes", "ha"):
                return True
            if s in ("false", "f", "0", "noto'g'ri", "notogri", "no", "yo'q", "yoq"):
                return False
        if isinstance(val, (int, float)):
            if val == 1:
                return True
            if val == 0:
                return False
        return None
