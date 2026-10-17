# apps/questions_registry/types/__init__.py
from ..registry import question_registry

from .single_choice import SingleChoiceQuestion
from .multiple_choice import MultipleChoiceQuestion
from .true_false import TrueFalseQuestion
from .ordering import OrderingQuestion
from .categorization import CategorizationQuestion
from .cloze import ClozeQuestion
from .open_short import OpenShortQuestion

# Barcha 7 ta boshlang'ich savol turini markaziy reestrga ro'yxatdan o'tkazamiz
question_registry.register(SingleChoiceQuestion)
question_registry.register(MultipleChoiceQuestion)
question_registry.register(TrueFalseQuestion)
question_registry.register(OrderingQuestion)
question_registry.register(CategorizationQuestion)
question_registry.register(ClozeQuestion)
question_registry.register(OpenShortQuestion)

__all__ = [
    'SingleChoiceQuestion',
    'MultipleChoiceQuestion',
    'TrueFalseQuestion',
    'OrderingQuestion',
    'CategorizationQuestion',
    'ClozeQuestion',
    'OpenShortQuestion',
]
