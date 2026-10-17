# apps/questions_registry/types/true_false.py
from typing import Any, List, Optional
from ..base import BaseQuestionType, EvaluationResult
from ..exceptions import QuestionValidationError


class TrueFalseQuestion(BaseQuestionType):
    type_id = "true_false"
    name = "To'g'ri / Noto'g'ri (True/False)"
    category = "assessment"
    description = "2 ta variant: To'g'ri yoki Noto'g'ri."

    def validate_payload(self, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None) -> bool:
        # Variantlar ixtiyoriy (default: True/False), lekin berilsa 2 ta bo'lishi kerak
        if options and (not isinstance(options, list) or len(options) != 2):
            raise QuestionValidationError("To'g'ri/Noto'g'ri savolida aynan 2 ta variant bo'lishi kerak.")

        correct_val = correct_answer.get('value') if isinstance(correct_answer, dict) else correct_answer
        if correct_val not in (True, False, 'true', 'false', 'True', 'False', '1', '0'):
            raise QuestionValidationError("To'g'ri javob True yoki False bo'lishi shart.")

        return True

    def sanitize_for_student(self, options: Any) -> Any:
        if not options:
            return [
                {'id': 'true', 'text': "To'g'ri"},
                {'id': 'false', 'text': "Noto'g'ri"}
            ]
        return [{'id': opt.get('id'), 'text': opt.get('text', '')} for opt in options]

    def _normalize_bool(self, val: Any) -> Optional[bool]:
        if isinstance(val, dict):
            val = val.get('value') or val.get('selected_option_id')
        if val in (True, 'true', 'True', '1', 1):
            return True
        if val in (False, 'false', 'False', '0', 0):
            return False
        return None

    def evaluate_answer(
        self,
        submitted_answer: Any,
        correct_answer: Any,
        max_points: int = 1000,
        accepted_alternatives: Optional[List] = None
    ) -> EvaluationResult:
        sub_bool = self._normalize_bool(submitted_answer)
        cor_bool = self._normalize_bool(correct_answer)

        is_correct = (sub_bool is not None) and (sub_bool == cor_bool)
        score = max_points if is_correct else 0
        ratio = 1.0 if is_correct else 0.0

        return EvaluationResult(
            is_correct=is_correct,
            score=score,
            score_ratio=ratio,
            details={'submitted': sub_bool, 'expected': cor_bool}
        )
