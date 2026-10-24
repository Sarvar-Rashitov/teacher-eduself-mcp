"""
Slider Question Type Plugin.
Range-based question evaluated against target value and linear proximity gradient.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class SliderQuestionType(BaseQuestionType):
    type_id = "slider"
    name = "Oraliq / Slayder (Slider)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must specify 'target', optional 'min', 'max', 'tolerance'.
        """
        if not correct_answer:
            raise QuestionValidationError("Slayder savoli uchun maqsadli qiymat ('target') ko‘rsatilishi shart.")

        target = None
        if isinstance(correct_answer, (int, float)):
            target = float(correct_answer)
        elif isinstance(correct_answer, dict):
            if 'target' not in correct_answer and 'value' not in correct_answer:
                raise QuestionValidationError("Slayder obyekti 'target' yoki 'value' maydoniga ega bo‘lishi shart.")
            try:
                target = float(correct_answer.get('target', correct_answer.get('value')))
            except (ValueError, TypeError):
                raise QuestionValidationError("Maqsadli qiymat son bo‘lishi shart.")
        else:
            raise QuestionValidationError("Slayder javobi son yoki parametrlar obyekti bo‘lishi shart.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates submitted slider value.
        Exact target: 100% score.
        Within tolerance: linear fractional score (1.0 down to 0.5).
        """
        if submitted_answer is None or submitted_answer == "":
            return False, 0.0

        try:
            val_raw = submitted_answer
            if isinstance(submitted_answer, dict):
                val_raw = submitted_answer.get('value', submitted_answer.get('target'))
            sub_val = float(val_raw)
        except (ValueError, TypeError):
            return False, 0.0

        target = 0.0
        tolerance = 5.0

        if isinstance(correct_answer, (int, float)):
            target = float(correct_answer)
        elif isinstance(correct_answer, dict):
            try:
                target = float(correct_answer.get('target', correct_answer.get('value', 0)))
                tolerance = float(correct_answer.get('tolerance', 5.0))
            except (ValueError, TypeError):
                return False, 0.0

        diff = abs(sub_val - target)
        if diff == 0:
            return True, 1.0

        if diff <= tolerance:
            # Gradient partial score: from 0.9 down to 0.5
            fraction = max(0.5, 1.0 - (diff / tolerance) * 0.5)
            return True, round(fraction, 2)

        return False, 0.0
