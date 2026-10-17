"""
Unit tests for QuestionTypeRegistry and the 7 core question type plugins.
"""

import pytest
from apps.questions_registry.registry import question_type_registry
from apps.questions_registry.exceptions import QuestionValidationError, QuestionTypeNotFoundError
from apps.questions_registry.types import (
    SingleChoiceQuestionType,
    MultipleChoiceQuestionType,
    TrueFalseQuestionType,
    OrderingQuestionType,
    CategorizationQuestionType,
    ClozeQuestionType,
    OpenShortQuestionType,
)


def test_registry_contains_all_core_types():
    """Verify that all core question types and aliases are registered."""
    expected_types = [
        "single_choice",
        "multiple_choice",
        "multiple_select",
        "true_false",
        "ordering",
        "puzzle_order",
        "categorization",
        "category_sort",
        "cloze",
        "open_short",
        "short_text",
    ]
    for type_id in expected_types:
        assert question_type_registry.has(type_id) is True
        plugin = question_type_registry.get(type_id)
        assert plugin is not None


def test_unknown_type_raises_error():
    """Unknown question type should raise QuestionTypeNotFoundError."""
    with pytest.raises(QuestionTypeNotFoundError):
        question_type_registry.get("non_existent_type_xyz")


# -----------------------------------------------------------------------------
# Single Choice Plugin Tests
# -----------------------------------------------------------------------------

def test_single_choice_validation_success():
    plugin = question_type_registry.get("single_choice")
    options = [
        {"id": "opt_1", "text": "Toshkent"},
        {"id": "opt_2", "text": "Samarqand"},
        {"id": "opt_3", "text": "Buxoro"},
    ]
    assert plugin.validate_payload(options, correct_answer="opt_1") is True


def test_single_choice_validation_failure_on_invalid_count():
    plugin = question_type_registry.get("single_choice")
    options = [{"id": "opt_1", "text": "Faqat bitta variant"}]
    with pytest.raises(QuestionValidationError):
        plugin.validate_payload(options, correct_answer="opt_1")


def test_single_choice_validation_failure_on_missing_key():
    plugin = question_type_registry.get("single_choice")
    options = [
        {"id": "opt_1", "text": "A"},
        {"id": "opt_2", "text": "B"},
    ]
    with pytest.raises(QuestionValidationError):
        plugin.validate_payload(options, correct_answer="opt_missing")


def test_single_choice_evaluation():
    plugin = question_type_registry.get("single_choice")
    is_correct, score = plugin.check_answer("opt_1", "opt_1")
    assert is_correct is True
    assert score == 1.0

    is_correct, score = plugin.check_answer("opt_2", "opt_1")
    assert is_correct is False
    assert score == 0.0


# -----------------------------------------------------------------------------
# Multiple Choice Plugin Tests (Partial Credit & Penalties)
# -----------------------------------------------------------------------------

def test_multiple_choice_evaluation_partial_credit():
    plugin = question_type_registry.get("multiple_choice")
    options = [
        {"id": "opt_A", "text": "To'g'ri 1"},
        {"id": "opt_B", "text": "To'g'ri 2"},
        {"id": "opt_C", "text": "Noto'g'ri 1"},
        {"id": "opt_D", "text": "Noto'g'ri 2"},
    ]
    correct_answer = ["opt_A", "opt_B"]

    # 1. Full correct
    is_corr, score = plugin.check_answer(["opt_A", "opt_B"], correct_answer, options)
    assert is_corr is True
    assert score == 1.0

    # 2. Partial correct (only 1 out of 2)
    is_corr, score = plugin.check_answer(["opt_A"], correct_answer, options)
    assert is_corr is False
    assert score == 0.5

    # 3. 1 correct + 1 wrong (partial credit minus penalty)
    is_corr, score = plugin.check_answer(["opt_A", "opt_C"], correct_answer, options)
    assert is_corr is False
    assert score == 0.0  # 0.5 - 0.5 = 0.0


# -----------------------------------------------------------------------------
# True / False Plugin Tests
# -----------------------------------------------------------------------------

def test_true_false_evaluation():
    plugin = question_type_registry.get("true_false")
    assert plugin.validate_payload([], True) is True

    is_corr, score = plugin.check_answer("true", True)
    assert is_corr is True and score == 1.0

    is_corr, score = plugin.check_answer("false", True)
    assert is_corr is False and score == 0.0


# -----------------------------------------------------------------------------
# Ordering Plugin Tests
# -----------------------------------------------------------------------------

def test_ordering_evaluation():
    plugin = question_type_registry.get("ordering")
    options = [
        {"id": "step_1", "text": "Kirish"},
        {"id": "step_2", "text": "Asosiy qism"},
        {"id": "step_3", "text": "Xulosa"},
    ]
    correct_order = ["step_1", "step_2", "step_3"]

    assert plugin.validate_payload(options, correct_order) is True

    # Exact match
    is_corr, score = plugin.check_answer(["step_1", "step_2", "step_3"], correct_order, options)
    assert is_corr is True and score == 1.0

    # 1 item misplaced
    is_corr, score = plugin.check_answer(["step_1", "step_3", "step_2"], correct_order, options)
    assert is_corr is False
    assert 0.0 < score < 1.0


# -----------------------------------------------------------------------------
# Categorization Plugin Tests
# -----------------------------------------------------------------------------

def test_categorization_evaluation():
    plugin = question_type_registry.get("categorization")
    correct_mapping = {
        "item_apple": "cat_fruits",
        "item_carrot": "cat_vegetables",
        "item_banana": "cat_fruits",
    }
    submission = {
        "item_apple": "cat_fruits",
        "item_carrot": "cat_vegetables",
        "item_banana": "cat_fruits",
    }
    is_corr, score = plugin.check_answer(submission, correct_mapping)
    assert is_corr is True and score == 1.0

    partial_sub = {
        "item_apple": "cat_fruits",
        "item_carrot": "cat_fruits",  # wrong
        "item_banana": "cat_fruits",
    }
    is_corr, score = plugin.check_answer(partial_sub, correct_mapping)
    assert is_corr is False
    assert score == pytest.approx(0.6667, 0.01)


# -----------------------------------------------------------------------------
# Open Short Plugin Tests (Normalization)
# -----------------------------------------------------------------------------

def test_open_short_evaluation_normalization():
    plugin = question_type_registry.get("open_short")
    correct = {"text": "Nyuton", "alternatives": ["Isaak Nyuton", "Newton"]}

    assert plugin.validate_payload([], correct) is True

    # Case insensitive, punctuation ignored, trimmed
    is_corr, score = plugin.check_answer("  nyuton!  ", correct)
    assert is_corr is True and score == 1.0

    is_corr, score = plugin.check_answer("isaak  nyuton", correct)
    assert is_corr is True and score == 1.0

    is_corr, score = plugin.check_answer("Eynshteyn", correct)
    assert is_corr is False and score == 0.0


# -----------------------------------------------------------------------------
# Zero-Knowledge Sanitization Test
# -----------------------------------------------------------------------------

def test_sanitize_for_student_scrubs_is_correct():
    plugin = question_type_registry.get("single_choice")
    dirty_options = [
        {"id": "opt_1", "text": "Variant A", "is_correct": True},
        {"id": "opt_2", "text": "Variant B", "is_correct": False},
    ]
    cleaned = plugin.sanitize_for_student(dirty_options)
    for opt in cleaned:
        assert "is_correct" not in opt
        assert "correct" not in opt
        assert "id" in opt
        assert "text" in opt
