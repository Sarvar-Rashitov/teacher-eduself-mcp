"""
Auto-registration of all 14 core assessment question type plugins per QUESTION_TYPES.md.
"""

from apps.questions_registry.registry import question_type_registry

from .single_choice import SingleChoiceQuestionType
from .multiple_choice import MultipleChoiceQuestionType
from .true_false import TrueFalseQuestionType
from .ordering import OrderingQuestionType
from .categorization import CategorizationQuestionType
from .cloze import ClozeQuestionType
from .open_short import OpenShortQuestionType
from .numeric import NumericQuestionType
from .slider import SliderQuestionType
from .pin_answer import PinAnswerQuestionType
from .drop_pin import DropPinQuestionType
from .match_pairs import MatchPairsQuestionType
from .math_equation import MathEquationQuestionType
from .code_output import CodeOutputQuestionType

# Primary Plugins Registration (14 Question Formats)
question_type_registry.register(SingleChoiceQuestionType)
question_type_registry.register(MultipleChoiceQuestionType)
question_type_registry.register(TrueFalseQuestionType)
question_type_registry.register(OpenShortQuestionType)
question_type_registry.register(OrderingQuestionType)
question_type_registry.register(NumericQuestionType)
question_type_registry.register(SliderQuestionType)
question_type_registry.register(PinAnswerQuestionType)
question_type_registry.register(DropPinQuestionType)
question_type_registry.register(MatchPairsQuestionType)
question_type_registry.register(CategorizationQuestionType)
question_type_registry.register(ClozeQuestionType)
question_type_registry.register(MathEquationQuestionType)
question_type_registry.register(CodeOutputQuestionType)

# Standard Aliases per QUESTION_TYPES.md documentation
class MultipleSelectAlias(MultipleChoiceQuestionType):
    type_id = "multiple_select"
    name = "Ko‘p tanlovli test (Multiple Select)"

class ShortTextAlias(OpenShortQuestionType):
    type_id = "short_text"
    name = "Qisqa matnli javob (Short Text)"

class PuzzleOrderAlias(OrderingQuestionType):
    type_id = "puzzle_order"
    name = "Ketma-ketlikni joylashtirish (Puzzle/Order)"

class CategorySortAlias(CategorizationQuestionType):
    type_id = "category_sort"
    name = "Kategoriyalarga ajratish (Category Sort)"

question_type_registry.register(MultipleSelectAlias)
question_type_registry.register(ShortTextAlias)
question_type_registry.register(PuzzleOrderAlias)
question_type_registry.register(CategorySortAlias)

__all__ = [
    'SingleChoiceQuestionType',
    'MultipleChoiceQuestionType',
    'TrueFalseQuestionType',
    'OpenShortQuestionType',
    'OrderingQuestionType',
    'NumericQuestionType',
    'SliderQuestionType',
    'PinAnswerQuestionType',
    'DropPinQuestionType',
    'MatchPairsQuestionType',
    'CategorizationQuestionType',
    'ClozeQuestionType',
    'MathEquationQuestionType',
    'CodeOutputQuestionType',
]
