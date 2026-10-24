"""
Question types package.
Registers all 7 core question plugins into QuestionTypeRegistry.
"""

from ..registry import registry
from .single_choice import SingleChoiceQuestion
from .multiple_choice import MultipleChoiceQuestion
from .true_false import TrueFalseQuestion
from .ordering import OrderingQuestion
from .categorization import CategorizationQuestion
from .cloze import ClozeQuestion
from .open_short import OpenShortQuestion

# Avtomatik ro'yxatga olish
registry.register(SingleChoiceQuestion)
registry.register(MultipleChoiceQuestion)
registry.register(TrueFalseQuestion)
registry.register(OrderingQuestion)
registry.register(CategorizationQuestion)
registry.register(ClozeQuestion)
registry.register(OpenShortQuestion)

__all__ = [
    "SingleChoiceQuestion",
    "MultipleChoiceQuestion",
    "TrueFalseQuestion",
    "OrderingQuestion",
    "CategorizationQuestion",
    "ClozeQuestion",
    "OpenShortQuestion",
]
