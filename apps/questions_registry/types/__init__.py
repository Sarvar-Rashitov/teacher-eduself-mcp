from ..registry import question_registry
from .single_choice import SingleChoiceQuestionType
from .multiple_choice import MultipleChoiceQuestionType
from .true_false import TrueFalseQuestionType
from .ordering import OrderingQuestionType
from .categorization import CategorizationQuestionType
from .cloze import ClozeQuestionType
from .open_short import OpenShortQuestionType


def register_default_types():
    """Registers all initial built-in question types."""
    question_registry.register(SingleChoiceQuestionType)
    question_registry.register(MultipleChoiceQuestionType)
    question_registry.register(TrueFalseQuestionType)
    question_registry.register(OrderingQuestionType)
    question_registry.register(CategorizationQuestionType)
    question_registry.register(ClozeQuestionType)
    question_registry.register(OpenShortQuestionType)


# Auto-register default types on import
register_default_types()

__all__ = [
    "SingleChoiceQuestionType",
    "MultipleChoiceQuestionType",
    "TrueFalseQuestionType",
    "OrderingQuestionType",
    "CategorizationQuestionType",
    "ClozeQuestionType",
    "OpenShortQuestionType",
    "register_default_types",
]
