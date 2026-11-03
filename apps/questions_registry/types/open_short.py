"""
Open Short / Short Text Question Type Plugin.
Text answers with case normalization, whitespace trimming, and synonym acceptance.
"""

import re
import string
from typing import Any, Tuple, List
from apps.questions_registry.base import BaseQuestionType
from apps.questions_registry.exceptions import QuestionValidationError


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove punctuation, collapse whitespace."""
    if not text:
        return ""
    text = text.lower()
    # Replace punctuation with space
    for ch in string.punctuation:
        text = text.replace(ch, " ")
    # Collapse whitespace
    return " ".join(text.split())


class OpenShortQuestionType(BaseQuestionType):
    type_id = "open_short"
    name = "Qisqa matnli javob (Short Text)"
    category = "Assessment"

    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates:
        - correct_answer must be a non-empty string or list of valid string answers.
        """
        if not correct_answer:
            raise QuestionValidationError("Qisqa matnli savol uchun kamida bitta to‘g‘ri javob kiritilishi shart.")

        if isinstance(correct_answer, list) and len(correct_answer) == 0:
            raise QuestionValidationError("To‘g‘ri javoblar ro‘yxati bo‘sh bo‘lishi mumkin emas.")

        return True

    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Compares normalized submitted text with primary and accepted alternative answers.
        """
        raw_submission = ""
        if isinstance(submitted_answer, str):
            raw_submission = submitted_answer
        elif isinstance(submitted_answer, dict):
            raw_submission = submitted_answer.get('text', '') or submitted_answer.get('answer', '')

        norm_sub = normalize_text(str(raw_submission))
        if not norm_sub:
            return False, 0.0

        # Collect accepted answers
        acceptable = []
        if isinstance(correct_answer, str):
            acceptable.append(correct_answer)
        elif isinstance(correct_answer, list):
            acceptable.extend([str(x) for x in correct_answer])
        elif isinstance(correct_answer, dict):
            primary = correct_answer.get('text') or correct_answer.get('answer')
            if primary:
                acceptable.append(str(primary))
            alternatives = correct_answer.get('alternatives') or correct_answer.get('accepted_answers', [])
            acceptable.extend([str(x) for x in alternatives])

        normalized_candidates = {normalize_text(cand) for cand in acceptable if cand}

        if norm_sub in normalized_candidates:
            return True, 1.0

        return False, 0.0
