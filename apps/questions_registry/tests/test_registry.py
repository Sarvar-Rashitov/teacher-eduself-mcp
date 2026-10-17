import pytest
from apps.questions_registry.registry import question_registry
from apps.questions_registry.exceptions import (
    InvalidQuestionTypeError,
    QuestionValidationError
)
# Plaginlar yuklanishi uchun types import qilinadi
import apps.questions_registry.types  # noqa: F401


class TestQuestionRegistry:
    def test_registry_has_7_core_types(self):
        """Dastlabki 7 ta yadroviy savol turi mavjudligini tekshirish."""
        types = question_registry.list_types()
        type_ids = [t['type_id'] for t in types]

        assert 'single_choice' in type_ids
        assert 'multiple_choice' in type_ids
        assert 'true_false' in type_ids
        assert 'ordering' in type_ids
        assert 'categorization' in type_ids
        assert 'cloze' in type_ids
        assert 'open_short' in type_ids

    def test_get_invalid_type_raises_error(self):
        with pytest.raises(InvalidQuestionTypeError):
            question_registry.get('non_existent_type_123')


class TestSingleChoicePlugin:
    def test_single_choice_validation_success(self):
        handler = question_registry.get('single_choice')
        options = [
            {'id': 'A', 'text': 'Toshkent'},
            {'id': 'B', 'text': 'Samarqand'}
        ]
        assert handler.validate_payload(options, correct_answer={'selected_option_id': 'A'}) is True

    def test_single_choice_validation_failure(self):
        handler = question_registry.get('single_choice')
        options = [{'id': 'A', 'text': 'Faqat 1 ta variant'}]
        with pytest.raises(QuestionValidationError):
            handler.validate_payload(options, correct_answer={'selected_option_id': 'A'})

    def test_single_choice_evaluation(self):
        handler = question_registry.get('single_choice')
        # To'g'ri javob
        res1 = handler.evaluate_answer({'selected_option_id': 'A'}, {'selected_option_id': 'A'}, max_points=1000)
        assert res1.is_correct is True
        assert res1.score == 1000

        # Noto'g'ri javob
        res2 = handler.evaluate_answer({'selected_option_id': 'B'}, {'selected_option_id': 'A'}, max_points=1000)
        assert res2.is_correct is False
        assert res2.score == 0


class TestMultipleChoicePlugin:
    def test_multiple_choice_partial_credit(self):
        handler = question_registry.get('multiple_choice')
        options = [
            {'id': 'A', 'text': '1'},
            {'id': 'B', 'text': '2'},
            {'id': 'C', 'text': '3'}
        ]
        correct = {'selected_option_ids': ['A', 'B']}
        assert handler.validate_payload(options, correct) is True

        # To'liq to'g'ri
        res_full = handler.evaluate_answer({'selected_option_ids': ['A', 'B']}, correct, max_points=1000)
        assert res_full.is_correct is True
        assert res_full.score == 1000

        # Qisman to'g'ri (1 ta to'g'ri tanlandi)
        res_part = handler.evaluate_answer({'selected_option_ids': ['A']}, correct, max_points=1000)
        assert res_part.is_correct is False
        assert res_part.score == 500


class TestTrueFalsePlugin:
    def test_true_false_evaluation(self):
        handler = question_registry.get('true_false')
        res = handler.evaluate_answer({'value': True}, {'value': True}, max_points=500)
        assert res.is_correct is True
        assert res.score == 500


class TestOrderingPlugin:
    def test_ordering_evaluation(self):
        handler = question_registry.get('ordering')
        options = [
            {'id': '1', 'text': 'Boshlanishi'},
            {'id': '2', 'text': 'O\'rtasi'},
            {'id': '3', 'text': 'Oxiri'}
        ]
        correct = {'ordered_ids': ['1', '2', '3']}
        assert handler.validate_payload(options, correct) is True

        # To'liq tartib
        res = handler.evaluate_answer({'ordered_ids': ['1', '2', '3']}, correct, max_points=1000)
        assert res.is_correct is True
        assert res.score == 1000


class TestClozePlugin:
    def test_cloze_evaluation(self):
        handler = question_registry.get('cloze')
        correct = {'blanks': {'b1': 'O\'zbekiston', 'b2': 'Toshkent'}}
        assert handler.validate_payload(None, correct) is True

        res = handler.evaluate_answer(
            {'blanks': {'b1': '  o\'zbekiston  ', 'b2': 'toshkent'}},
            correct,
            max_points=1000
        )
        assert res.is_correct is True
        assert res.score == 1000


class TestOpenShortPlugin:
    def test_open_short_evaluation(self):
        handler = question_registry.get('open_short')
        correct = {'text': 'Toshkent'}
        alternatives = ['Tashkent', 'Тошкент']

        # Asosiy to'g'ri
        res1 = handler.evaluate_answer({'text': '  toshkent  '}, correct, max_points=1000, accepted_alternatives=alternatives)
        assert res1.is_correct is True
        assert res1.score == 1000

        # Alternativ to'g'ri
        res2 = handler.evaluate_answer({'text': 'tashkent'}, correct, max_points=1000, accepted_alternatives=alternatives)
        assert res2.is_correct is True
        assert res2.score == 1000
