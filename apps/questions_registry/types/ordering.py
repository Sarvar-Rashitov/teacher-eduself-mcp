"""
Ordering / Puzzle Sequence Question Type Plugin.
Items must be arranged in the correct chronological or procedural order.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class OrderingQuestionType(BaseQuestionType):
    type_id = "ordering"
    name = "Ketma-ketlikni joylashtirish (Ordering)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options must have at least 2 items.
        - correct_answer must be a list containing all option IDs in the correct order.
        """
        if not isinstance(options, list) or len(options) < 2:
            raise QuestionValidationError("Ordering savoli kamida 2 ta elementga ega bo‘lishi shart.")

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or 'id' not in opt or 'text' not in opt:
                raise QuestionValidationError(f"{idx + 1}-elementda 'id' va 'text' maydoni bo‘lishi shart.")
            option_ids.add(str(opt['id']))

        if not isinstance(correct_answer, list) or len(correct_answer) != len(options):
            raise QuestionValidationError(
                f"To‘g‘ri ketma-ketlik barcha {len(options)} ta element ID larini o‘z ichiga olishi shart."
            )

        if set(str(x) for x in correct_answer) != option_ids:
            raise QuestionValidationError("To‘g‘ri ketma-ketlikdagi ID lar variantlar ro‘yxati bilan to‘liq mos kelishi shart.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates sequence accuracy.
        100% match awards full score; partial score calculated from correct relative positions.
        """
        if not isinstance(submitted_answer, list):
            if isinstance(submitted_answer, dict):
                submitted_answer = submitted_answer.get('ordered_ids', [])
            else:
                return False, 0.0

        sub_list = [str(x).strip() for x in submitted_answer]
        cor_list = [str(x).strip() for x in correct_answer]

        if sub_list == cor_list:
            return True, 1.0

        if len(sub_list) != len(cor_list):
            return False, 0.0

        # Exact positional matches
        correct_positions = sum(1 for s, c in zip(sub_list, cor_list) if s == c)
        score = correct_positions / len(cor_list)

        return False, round(score, 4)
