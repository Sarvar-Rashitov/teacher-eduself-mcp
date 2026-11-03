"""
Drop Pin Question Type Plugin.
Map location or diagram coordinate placement.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class DropPinQuestionType(BaseQuestionType):
    type_id = "drop_pin"
    name = "Xarita / Joylashuv nuqtasi (Drop Pin)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates target pin coordinates.
        """
        if not correct_answer:
            raise QuestionValidationError("Drop Pin savoli uchun to‘g‘ri joylashuv kiritilishi shart.")

        if not isinstance(correct_answer, dict):
            raise QuestionValidationError("To‘g‘ri joylashuv obyekti kutilmoqda.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates dropped pin proximity.
        """
        if not submitted_answer or not isinstance(submitted_answer, dict):
            return False, 0.0

        sub_lat = submitted_answer.get('lat', submitted_answer.get('x'))
        sub_lng = submitted_answer.get('lng', submitted_answer.get('y'))

        if sub_lat is None or sub_lng is None:
            return False, 0.0

        try:
            sub_lat, sub_lng = float(sub_lat), float(sub_lng)
            target_lat = float(correct_answer.get('lat', correct_answer.get('x', 0)))
            target_lng = float(correct_answer.get('lng', correct_answer.get('y', 0)))
            tolerance = float(correct_answer.get('tolerance', correct_answer.get('radius', 10.0)))
        except (ValueError, TypeError):
            return False, 0.0

        dist = ((sub_lat - target_lat) ** 2 + (sub_lng - target_lng) ** 2) ** 0.5
        if dist <= tolerance:
            return True, 1.0

        return False, 0.0
