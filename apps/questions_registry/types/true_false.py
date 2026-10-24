from typing import Any, Dict, List
from ..base import BaseQuestionType
from ..exceptions import QuestionValidationError


class TrueFalseQuestion(BaseQuestionType):
    """
    To'g'ri / Noto'g'ri (True / False) savol turi.
    """

    type_id = "true_false"
    name = "To'g'ri / Noto'g'ri"
    category = "assessment"
    auto_graded = True

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        if correct_answer is None:
            raise QuestionValidationError("To'g'ri javob ko'rsatilishi shart.")

        if isinstance(correct_answer, str):
            if correct_answer.lower() not in ("true", "false", "rost", "yolg'on", "ha", "yo'q", "1", "0"):
                raise QuestionValidationError(f"To'g'ri javob bool qiymat bo'lishi kerak: '{correct_answer}'")
        elif not isinstance(correct_answer, bool):
            raise QuestionValidationError(f"To'g'ri javob mantiqiy bool (True/False) bo'lishi shart.")

        return True

    def _normalize(self, val: Any) -> bool:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val)
        if isinstance(val, str):
            return val.strip().lower() in ("true", "rost", "ha", "1")
        if isinstance(val, dict):
            return self._normalize(val.get("value", val.get("id", False)))
        return False

    def check_answer(self, user_answer: Any, correct_answer: Any, **kwargs) -> Dict[str, Any]:
        if user_answer is None:
            return {"is_correct": False, "score_ratio": 0.0, "feedback": "Javob belgilanmadi"}

        user_bool = self._normalize(user_answer)
        target_bool = self._normalize(correct_answer)

        is_match = (user_bool == target_bool)
        return {
            "is_correct": is_match,
            "score_ratio": 1.0 if is_match else 0.0,
            "feedback": "To'g'ri!" if is_match else "Noto'g'ri.",
        }
