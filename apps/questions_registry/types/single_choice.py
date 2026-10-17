"""
Single Choice Question Type Plugin.
2 to 6 options with exactly one correct option.
"""

from typing import Any, Tuple, List, Dict
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class SingleChoiceQuestionType(BaseQuestionType):
    type_id = "single_choice"
    name = "Yagona tanlovli test (Single Choice)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options must be a list of 2 to 6 items.
        - each option must have 'id' and 'text'.
        - correct_answer must specify the valid id of one option.
        """
        if not isinstance(options, list) or len(options) < 2 or len(options) > 6:
            raise QuestionValidationError(
                f"Single Choice savoli 2 tadan 6 tagacha variantga ega bo‘lishi shart. Hozirda: {len(options) if isinstance(options, list) else 0}"
            )

        option_ids = set()
        for idx, opt in enumerate(options):
            if not isinstance(opt, dict) or 'id' not in opt or 'text' not in opt:
                raise QuestionValidationError(
                    f"{idx + 1}-variant noto‘g‘ri formatda. 'id' va 'text' maydonlari majburiy."
                )
            if not str(opt['text']).strip():
                raise QuestionValidationError(f"{idx + 1}-variant matni bo‘sh bo‘lishi mumkin emas.")
            option_ids.add(str(opt['id']))

        # Extract target correct option id
        correct_id = None
        if isinstance(correct_answer, str):
            correct_id = correct_answer
        elif isinstance(correct_answer, dict):
            correct_id = correct_answer.get('option_id') or correct_answer.get('id')

        if not correct_id or str(correct_id) not in option_ids:
            raise QuestionValidationError(
                f"To‘g‘ri javob kaliti ('{correct_id}') berilgan variantlar orasida mavjud emas: {list(option_ids)}"
            )

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates submitted answer.
        """
        submitted_id = None
        if isinstance(submitted_answer, str):
            submitted_id = submitted_answer.strip()
        elif isinstance(submitted_answer, dict):
            submitted_id = submitted_answer.get('selected_option_id') or submitted_answer.get('id')

        expected_id = str(correct_answer).strip() if isinstance(correct_answer, str) else str(correct_answer.get('option_id', '')).strip()

        if submitted_id and str(submitted_id).strip() == expected_id:
            return True, 1.0
        return False, 0.0
