"""
Code Output Question Type Plugin.
Code snippets with expected standard output evaluation.
"""

from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


def normalize_code_stdout(text: str) -> str:
    """Normalize terminal/stdout output: trim and normalize line endings."""
    if text is None:
        return ""
    lines = [line.rstrip() for line in str(text).replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


class CodeOutputQuestionType(BaseQuestionType):
    type_id = "code_output"
    name = "Kod va Debugging (Code Output)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must specify the expected output / stdout string.
        """
        if correct_answer is None:
            raise QuestionValidationError("Kod natijasi savoli uchun kutilgan natija (stdout) kiritilishi shart.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Compares normalized student answer to expected output.
        """
        if submitted_answer is None:
            return False, 0.0

        raw_sub = submitted_answer
        if isinstance(submitted_answer, dict):
            raw_sub = submitted_answer.get('output', submitted_answer.get('stdout', submitted_answer.get('answer', '')))

        sub_norm = normalize_code_stdout(str(raw_sub))

        target_norm = ""
        if isinstance(correct_answer, str):
            target_norm = normalize_code_stdout(correct_answer)
        elif isinstance(correct_answer, dict):
            target_norm = normalize_code_stdout(correct_answer.get('output', correct_answer.get('stdout', '')))
        else:
            target_norm = normalize_code_stdout(str(correct_answer))

        if sub_norm == target_norm and sub_norm != "":
            return True, 1.0

        return False, 0.0
