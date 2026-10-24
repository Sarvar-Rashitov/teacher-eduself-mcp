from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import copy


@dataclass
class EvaluationResult:
    """Represents the outcome of evaluating a student's answer submission."""
    is_correct: bool
    score_fraction: float  # Normalized between 0.0 and 1.0
    feedback: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Clamp score_fraction to [0.0, 1.0]
        if self.score_fraction < 0.0:
            self.score_fraction = 0.0
        elif self.score_fraction > 1.0:
            self.score_fraction = 1.0


class BaseQuestionType(ABC):
    """
    Abstract Base Class for all 29 question types in the EduSelf platform.
    Follows the Registry / Plugin Pattern: new question types can be registered
    dynamically without touching the database schema or core engine.
    """

    type_id: str
    category: str = "Assessment"  # Assessment, Formative, Presentation, Hybrid
    display_name: str = ""
    aliases: tuple[str, ...] = ()
    requires_answer_key: bool = True
    auto_evaluable: bool = True

    @abstractmethod
    def validate_payload(self, options: Any, correct_answer: Any, **kwargs) -> None:
        """
        Validate question options and correct_answer payload structure.
        Must raise QuestionValidationError if invalid.
        """
        pass

    @abstractmethod
    def check_answer(
        self,
        submission: Any,
        correct_answer: Any,
        options: Any = None,
        **kwargs
    ) -> EvaluationResult:
        """
        Evaluates student's answer submission against the secret answer key.
        Returns an EvaluationResult with score_fraction (0.0 to 1.0) and status.
        """
        pass

    def sanitize_for_student(self, question_data: dict[str, Any]) -> dict[str, Any]:
        """
        Zero-Knowledge Question Delivery:
        Strips secret answer keys, teacher explanations, accepted alternative answers,
        and option-level 'is_correct' flags so student clients never receive answers
        before questions are closed and revealed.
        """
        sanitized = copy.deepcopy(question_data)

        # Remove secret keys and teacher notes
        sanitized.pop("correct_answer", None)
        sanitized.pop("correct_answer_key", None)
        sanitized.pop("accepted_alternatives", None)
        sanitized.pop("accepted_answers", None)
        sanitized.pop("explanation", None)

        # Sanitize options if they are structured as dicts with 'is_correct'
        options = sanitized.get("options")
        if isinstance(options, list):
            for opt in options:
                if isinstance(opt, dict):
                    opt.pop("is_correct", None)
        elif isinstance(options, dict):
            # For complex options structures (e.g. categorization or pairing)
            options.pop("correct_mapping", None)
            options.pop("is_correct", None)

        return sanitized
