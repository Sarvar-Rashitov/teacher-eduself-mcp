"""
Categorization / Category Sort Question Type Plugin.
Items must be sorted into predefined category buckets.
"""

from typing import Any, Tuple, List, Dict
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class CategorizationQuestionType(BaseQuestionType):
    type_id = "categorization"
    name = "Kategoriyalarga ajratish (Categorization)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options must define categories and items to be sorted.
        - correct_answer must map each item to its correct category id.
        """
        if not isinstance(options, dict) and not isinstance(options, list):
            raise QuestionValidationError("Kategorizatsiya varianti ro‘yxat yoki lug‘at bo‘lishi shart.")

        if not isinstance(correct_answer, dict) or not correct_answer:
            raise QuestionValidationError(
                "Categorization to‘g‘ri javobi {item_id: category_id} shaklidagi lug‘at bo‘lishi shart."
            )

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates accuracy of categorized items.
        Score equals correct_matches / total_items.
        """
        if not isinstance(submitted_answer, dict) or not isinstance(correct_answer, dict):
            return False, 0.0

        total = len(correct_answer)
        if total == 0:
            return False, 0.0

        matches = 0
        for item_id, cat_id in correct_answer.items():
            if str(submitted_answer.get(item_id, '')).strip() == str(cat_id).strip():
                matches += 1

        is_correct = (matches == total)
        score = matches / total
        return is_correct, round(score, 4)
