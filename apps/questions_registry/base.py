"""
Abstract Base Question Type interface.
All 29 question formats implement this contract.
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple, List, Dict


class BaseQuestionType(ABC):
    """
    Contract for any pluggable question format in EduSelf Teacher.
    Handles payload validation, student-facing data sanitization, and answer evaluation.
    """
    type_id: str
    name: str
    category: str = "Assessment"  # Assessment | Formative | Presentation

    @abstractmethod
    def validate_payload(self, options: List[Any], correct_answer: Any, **kwargs) -> bool:
        """
        Validates question options and correct_answer structure.
        Must raise QuestionValidationError if format is invalid.
        """
        pass

    def sanitize_for_student(self, options: List[Any]) -> List[Any]:
        """
        Zero-Knowledge data scrubbing:
        Removes 'is_correct' flags and any secret key hints from options before sending to student devices.
        Can be overridden by custom question types.
        """
        if not isinstance(options, list):
            return []

        sanitized = []
        for opt in options:
            if isinstance(opt, dict):
                clean_opt = {k: v for k, v in opt.items() if k not in ('is_correct', 'correct', 'isCorrect')}
                sanitized.append(clean_opt)
            else:
                sanitized.append(opt)
        return sanitized

    @abstractmethod
    def check_answer(self, submitted_answer: Any, correct_answer: Any, options: List[Any] = None) -> Tuple[bool, float]:
        """
        Evaluates a participant's submitted answer against the secret answer key.
        Returns:
            Tuple[is_correct: bool, score_fraction: float (0.0 to 1.0)]
        """
        pass
