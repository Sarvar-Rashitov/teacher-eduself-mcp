"""
Cloze / Fill in the Blanks Question Type Plugin.
Students complete missing words or select correct dropdown values in a text.
"""

from typing import Any, Tuple, List, Dict
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class ClozeQuestionType(BaseQuestionType):
    type_id = "cloze"
    name = "Bo‘sh joylarni to‘ldirish (Cloze)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must contain answers for each blank.
        """
        if not correct_answer:
            raise QuestionValidationError("Cloze savoli uchun to‘g‘ri javoblar bo‘sh bo‘lishi mumkin emas.")

        if not isinstance(correct_answer, (dict, list)):
            raise QuestionValidationError("Cloze to‘g‘ri javoblari ro‘yxat yoki lug‘at ko‘rinishida bo‘lishi shart.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates filled blanks.
        """
        if isinstance(correct_answer, dict) and isinstance(submitted_answer, dict):
            total = len(correct_answer)
            if total == 0:
                return False, 0.0
            matches = 0
            for k, expected in correct_answer.items():
                student_val = str(submitted_answer.get(k, '')).strip().lower()
                if isinstance(expected, list):
                    if student_val in [str(x).strip().lower() for x in expected]:
                        matches += 1
                else:
                    if student_val == str(expected).strip().lower():
                        matches += 1
            is_correct = (matches == total)
            return is_correct, round(matches / total, 4)

        if isinstance(correct_answer, list) and isinstance(submitted_answer, list):
            total = len(correct_answer)
            if total == 0:
                return False, 0.0
            matches = 0
            for sub, exp in zip(submitted_answer, correct_answer):
                if str(sub).strip().lower() == str(exp).strip().lower():
                    matches += 1
            is_correct = (matches == total and len(submitted_answer) == total)
            return is_correct, round(matches / total, 4)

        return False, 0.0
