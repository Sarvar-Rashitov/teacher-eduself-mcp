"""
Auto-registration of all 7 core question type plugins.
"""

from apps.questions_registry.registry import question_type_registry

from .single_choice import SingleChoiceQuestionType
from .multiple_choice import MultipleChoiceQuestionType
from .true_false import TrueFalseQuestionType
from .ordering import OrderingQuestionType
from .categorization import CategorizationQuestionType
from .cloze import ClozeQuestionType
from .open_short import OpenShortQuestionType

# Primary Plugins
question_type_registry.register(SingleChoiceQuestionType)
question_type_registry.register(MultipleChoiceQuestionType)
question_type_registry.register(TrueFalseQuestionType)
question_type_registry.register(OrderingQuestionType)
question_type_registry.register(CategorizationQuestionType)
question_type_registry.register(ClozeQuestionType)
question_type_registry.register(OpenShortQuestionType)

# Aliases per QUESTION_TYPES.md documentation
class MultipleSelectAlias(MultipleChoiceQuestionType):
    type_id = "multiple_select"

class ShortTextAlias(OpenShortQuestionType):
    type_id = "short_text"

class PuzzleOrderAlias(OrderingQuestionType):
    type_id = "puzzle_order"

class CategorySortAlias(CategorizationQuestionType):
    type_id = "category_sort"

question_type_registry.register(MultipleSelectAlias)
question_type_registry.register(ShortTextAlias)
question_type_registry.register(PuzzleOrderAlias)
question_type_registry.register(CategorySortAlias)

__all__ = [
    'SingleChoiceQuestionType',
    'MultipleChoiceQuestionType',
    'TrueFalseQuestionType',
    'OrderingQuestionType',
    'CategorizationQuestionType',
    'ClozeQuestionType',
    'OpenShortQuestionType',
]
