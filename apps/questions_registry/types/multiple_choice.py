"""
Multiple Choice / Multiple Select Question Type Plugin.
3 to 8 options with 2 or more correct options, supporting partial credit.
"""

from typing import Any, Tuple, List, Set
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class MultipleChoiceQuestionType(BaseQuestionType):
    type_id = "multiple_choice"
    name = "Ko‘p tanlovli test (Multiple Choice)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options must be at least 3 items.
        - correct_answer must be a list of at least 2 option IDs.
        - all IDs in correct_answer must exist in options.
        """
        if not isinstance(options, list) or len(options) < 3:
            raise QuestionValidationError(
                f"Multiple Choice savoli kamida 3 ta variantga ega bo‘lishi shart. Hozirda: {len(options) if isinstance(options, list) else 0}"
            )

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or 'id' not in opt or 'text' not in opt:
                raise QuestionValidationError(f"{idx + 1}-variant noto‘g‘ri formatda.")
            option_ids.add(str(opt['id']))

        if not isinstance(correct_answer, list) or len(correct_answer) < 2:
            raise QuestionValidationError(
                "Multiple Choice to‘g‘ri javoblari kamida 2 ta variant ID sidan iborat ro‘yxat bo‘lishi shart."
            )

        for ans in correct_answer:
            if str(ans) not in option_ids:
                raise QuestionValidationError(
                    f"To‘g‘ri javoblardagi '{ans}' varianti variantlar ro‘yxatida mavjud emas."
                )

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates submitted answer with partial credit and penalty formula:
        Score = max(0.0, (C_selected / C_total) - (W_selected / W_total))
        """
        if not isinstance(submitted_answer, list):
            if isinstance(submitted_answer, dict):
                submitted_answer = submitted_answer.get('selected_option_ids', [])
            else:
                submitted_answer = [submitted_answer] if submitted_answer else []

        selected_ids: Set[str] = {str(item).strip() for item in submitted_answer if item}
        correct_ids: Set[str] = {str(item).strip() for item in correct_answer if item}

        if not selected_ids:
            return False, 0.0

        all_ids: Set[str] = {str(opt['id']).strip() for opt in (options or []) if isinstance(opt, dict) and 'id' in opt}
        if not all_ids:
            all_ids = selected_ids.union(correct_ids)

        wrong_ids = all_ids - correct_ids

        c_selected = len(selected_ids.intersection(correct_ids))
        c_total = len(correct_ids)

        w_selected = len(selected_ids.intersection(wrong_ids))
        w_total = len(wrong_ids) if len(wrong_ids) > 0 else 1

        correct_ratio = c_selected / c_total if c_total > 0 else 0.0
        penalty_ratio = w_selected / w_total if w_total > 0 else 0.0

        score = max(0.0, correct_ratio - penalty_ratio)
        is_fully_correct = (selected_ids == correct_ids)

        return is_fully_correct, round(score, 4)
