"""
Match Pairs Question Type Plugin.
Associates left-side items with right-side matching counterparts.
"""

from typing import Any, Tuple, List, Dict
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class MatchPairsQuestionType(BaseQuestionType):
    type_id = "match_pairs"
    name = "Juftliklarni moslashtirish (Match Pairs)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - options or correct_answer must define at least 2 pairs.
        - pairs should have 'left' and 'right' keys or key-value dictionary.
        """
        pairs = []
        if isinstance(correct_answer, dict):
            pairs = list(correct_answer.items())
        elif isinstance(correct_answer, list):
            pairs = correct_answer
        elif isinstance(options, list) and len(options) >= 2:
            pairs = options

        if len(pairs) < 2:
            raise QuestionValidationError(
                f"Moslashtirish savolida kamida 2 ta juftlik bo‘lishi shart. Hozirda: {len(pairs)}"
            )

        return True

    def sanitize_for_student(self, options: List[Any]) -> List[Any]:
        """
        Separate left items and right items shuffled so student can connect them.
        """
        if not isinstance(options, list):
            return []

        sanitized = []
        for opt in options:
            if isinstance(opt, dict):
                sanitized.append({
                    "id": opt.get("id"),
                    "left": opt.get("left", ""),
                    "right": opt.get("right", "")
                })
        return sanitized

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Calculates fraction of correctly matched pairs.
        """
        if not submitted_answer or not isinstance(submitted_answer, (dict, list)):
            return False, 0.0

        # Build target map
        target_map = {}
        if isinstance(correct_answer, dict):
            target_map = {str(k).strip().lower(): str(v).strip().lower() for k, v in correct_answer.items()}
        elif isinstance(correct_answer, list):
            for item in correct_answer:
                if isinstance(item, dict) and 'left' in item and 'right' in item:
                    target_map[str(item['left']).strip().lower()] = str(item['right']).strip().lower()
        elif isinstance(options, list):
            for item in options:
                if isinstance(item, dict) and 'left' in item and 'right' in item:
                    target_map[str(item['left']).strip().lower()] = str(item['right']).strip().lower()

        if not target_map:
            return False, 0.0

        sub_map = {}
        if isinstance(submitted_answer, dict):
            sub_map = {str(k).strip().lower(): str(v).strip().lower() for k, v in submitted_answer.items()}
        elif isinstance(submitted_answer, list):
            for item in submitted_answer:
                if isinstance(item, dict) and 'left' in item and 'right' in item:
                    sub_map[str(item['left']).strip().lower()] = str(item['right']).strip().lower()

        total = len(target_map)
        correct_count = 0
        for k, v in target_map.items():
            if sub_map.get(k) == v:
                correct_count += 1

        if correct_count == total and total > 0:
            return True, 1.0

        fraction = correct_count / total if total > 0 else 0.0
        return (fraction > 0.5), round(fraction, 2)
