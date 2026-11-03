"""
Numeric Question Type Plugin.
Evaluates exact or tolerance-based numeric answers.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class NumericQuestionType(BaseQuestionType):
    type_id = "numeric"
    name = "Aniq sonli javob (Numeric Answer)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must specify a numeric value or dict with 'value' and optional 'tolerance'.
        """
        if correct_answer is None or correct_answer == "":
            raise QuestionValidationError("Sonli savol uchun to‘g‘ri qiymat kiritilishi shart.")

        target_val = None
        if isinstance(correct_answer, (int, float)):
            target_val = correct_answer
        elif isinstance(correct_answer, str):
            try:
                target_val = float(correct_answer.strip().replace(",", "."))
            except ValueError:
                raise QuestionValidationError(f"To‘g‘ri javob haqiqiy son bo‘lishi shart. Kiritildi: '{correct_answer}'")
        elif isinstance(correct_answer, dict):
            val = correct_answer.get('value')
            if val is None:
                raise QuestionValidationError("To‘g‘ri javob obyekti 'value' maydoniga ega bo‘lishi shart.")
            try:
                target_val = float(str(val).strip().replace(",", "."))
            except ValueError:
                raise QuestionValidationError(f"'value' haqiqiy son bo‘lishi shart. Kiritildi: '{val}'")
        else:
            raise QuestionValidationError("To‘g‘ri javob formati noto‘g‘ri (son yoki obyekt kutilmoqda).")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Compares submitted numeric value with correct answer within specified tolerance.
        """
        if submitted_answer is None or submitted_answer == "":
            return False, 0.0

        try:
            sub_raw = submitted_answer
            if isinstance(submitted_answer, dict):
                sub_raw = submitted_answer.get('value', submitted_answer.get('answer'))
            sub_val = float(str(sub_raw).strip().replace(",", "."))
        except (ValueError, TypeError):
            return False, 0.0

        target_val = 0.0
        tolerance = 0.001

        if isinstance(correct_answer, (int, float)):
            target_val = float(correct_answer)
        elif isinstance(correct_answer, str):
            try:
                target_val = float(correct_answer.strip().replace(",", "."))
            except ValueError:
                return False, 0.0
        elif isinstance(correct_answer, dict):
            try:
                target_val = float(str(correct_answer.get('value', 0)).strip().replace(",", "."))
                tol_raw = correct_answer.get('tolerance', 0.0)
                if tol_raw is not None:
                    tolerance = abs(float(str(tol_raw).strip().replace(",", ".")))
            except (ValueError, TypeError):
                return False, 0.0

        diff = abs(sub_val - target_val)
        if diff <= tolerance:
            return True, 1.0

        return False, 0.0
