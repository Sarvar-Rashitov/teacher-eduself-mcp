"""
Math Equation Question Type Plugin.
Mathematical expressions, algebraic equations, and formulas.
"""

import re
from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


def normalize_math(expr: str) -> str:
    """Normalize mathematical formula string: remove spaces, lowercase variables, standard operators."""
    if not expr:
        return ""
    # Strip spaces
    s = str(expr).replace(" ", "").lower()
    # Normalize symbols
    s = s.replace("*", "·").replace("x", "·") if "·" in s else s.replace("·", "*")
    return s


class MathEquationQuestionType(BaseQuestionType):
    type_id = "math_equation"
    name = "Matematik formula (Math Equation)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must contain a non-empty equation string or list of equivalent forms.
        """
        if not correct_answer:
            raise QuestionValidationError("Matematik formula savoli uchun to‘g‘ri formula kiritilishi shart.")

        if isinstance(correct_answer, str) and not correct_answer.strip():
            raise QuestionValidationError("Formula matni bo‘sh bo‘lishi mumkin emas.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Compares normalized submitted equation against accepted representations.
        """
        if not submitted_answer:
            return False, 0.0

        raw_sub = submitted_answer
        if isinstance(submitted_answer, dict):
            raw_sub = submitted_answer.get('equation', submitted_answer.get('formula', submitted_answer.get('answer', '')))

        sub_norm = normalize_math(str(raw_sub))
        if not sub_norm:
            return False, 0.0

        # Accepted forms
        targets = []
        if isinstance(correct_answer, str):
            targets.append(correct_answer)
        elif isinstance(correct_answer, list):
            targets.extend(correct_answer)
        elif isinstance(correct_answer, dict):
            if 'equation' in correct_answer:
                targets.append(correct_answer['equation'])
            if 'alternatives' in correct_answer and isinstance(correct_answer['alternatives'], list):
                targets.extend(correct_answer['alternatives'])

        for t in targets:
            if normalize_math(str(t)) == sub_norm:
                return True, 1.0

        return False, 0.0
