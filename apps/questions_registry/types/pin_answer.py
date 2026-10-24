"""
Pin Answer Question Type Plugin.
Locates target coordinates / bounding box on an image diagram or map.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


class PinAnswerQuestionType(BaseQuestionType):
    type_id = "pin_answer"
    name = "Rasmda to‘g‘ri nuqtani tanlash (Pin Answer)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must contain target coordinates (e.g. x, y and radius or bounding box).
        """
        if not correct_answer:
            raise QuestionValidationError("Pin Answer savoli uchun to‘g‘ri koordinatalar ko‘rsatilishi shart.")

        if not isinstance(correct_answer, dict):
            raise QuestionValidationError("To‘g‘ri koordinata obyekti (x, y va radius) bo‘lishi shart.")

        if 'x' not in correct_answer or 'y' not in correct_answer:
            if 'box' not in correct_answer and 'target' not in correct_answer:
                raise QuestionValidationError("Koordinata 'x' va 'y' yoki 'box' maydonlariga ega bo‘lishi shart.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Point-in-circle or point-in-box evaluation.
        """
        if not submitted_answer or not isinstance(submitted_answer, dict):
            return False, 0.0

        sub_x = submitted_answer.get('x')
        sub_y = submitted_answer.get('y')

        if sub_x is None or sub_y is None:
            return False, 0.0

        try:
            sub_x, sub_y = float(sub_x), float(sub_y)
        except (ValueError, TypeError):
            return False, 0.0

        if not isinstance(correct_answer, dict):
            return False, 0.0

        # Circular hit-box
        if 'x' in correct_answer and 'y' in correct_answer:
            try:
                target_x = float(correct_answer['x'])
                target_y = float(correct_answer['y'])
                radius = float(correct_answer.get('radius', 25.0))
            except (ValueError, TypeError):
                return False, 0.0

            dist_sq = (sub_x - target_x) ** 2 + (sub_y - target_y) ** 2
            if dist_sq <= radius ** 2:
                return True, 1.0

        # Rectangular box [x1, y1, x2, y2]
        if 'box' in correct_answer and isinstance(correct_answer['box'], (list, tuple)) and len(correct_answer['box']) >= 4:
            b = correct_answer['box']
            if min(b[0], b[2]) <= sub_x <= max(b[0], b[2]) and min(b[1], b[3]) <= sub_y <= max(b[1], b[3]):
                return True, 1.0

        return False, 0.0
