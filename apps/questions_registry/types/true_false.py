"""
True / False Question Type Plugin.
Binary verification with standardized true/false options.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class TrueFalseQuestionType(BaseQuestionType):
    type_id = "true_false"
    name = "Rost yoki Yolg‘on (True/False)"
    category = "Assessment"

    DEFAULT_OPTIONS = [
        {"id": "true", "text": "Rost (To‘g‘ri)"},
        {"id": "false", "text": "Yolg‘on (Noto‘g‘ri)"}
    ]

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options should contain 2 items representing true and false.
        - correct_answer must be boolean or 'true'/'false'.
        """
        norm_ans = str(correct_answer).strip().lower()
        if norm_ans not in ('true', 'false', '1', '0'):
            raise QuestionValidationError(
                f"True/False to‘g‘ri javobi faqat True yoki False bo‘lishi shart. Berilgan: '{correct_answer}'"
            )

        if options and len(options) != 2:
            raise QuestionValidationError(
                f"True/False savoli aynan 2 ta variantga ega bo‘lishi shart. Hozirda: {len(options)}"
            )

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """Evaluates boolean match."""
        sub_norm = str(submitted_answer).strip().lower()
        if isinstance(submitted_answer, dict):
            sub_norm = str(submitted_answer.get('selected_option_id', '')).strip().lower()

        cor_norm = str(correct_answer).strip().lower()

        # Normalize 1/0 to true/false
        sub_val = sub_norm in ('true', '1')
        cor_val = cor_norm in ('true', '1')

        if sub_val == cor_val:
            return True, 1.0
        return False, 0.0
