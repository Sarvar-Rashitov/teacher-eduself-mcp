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
        "numeric",
        "slider",
        "pin_answer",
        "drop_pin",
        "match_pairs",
        "math_equation",
        "code_output",
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


# -----------------------------------------------------------------------------
# New Assessment Question Types (Numeric, Slider, Pin, Pairs, Math, Code)
# -----------------------------------------------------------------------------

def test_numeric_question_evaluation():
    plugin = question_type_registry.get("numeric")
    correct = {"value": 3.14, "tolerance": 0.05}
    assert plugin.validate_payload([], correct) is True

    # Exact
    is_corr, score = plugin.check_answer("3.14", correct)
    assert is_corr is True and score == 1.0

    # Within tolerance
    is_corr, score = plugin.check_answer(3.18, correct)
    assert is_corr is True and score == 1.0

    # Outside tolerance
    is_corr, score = plugin.check_answer(3.30, correct)
    assert is_corr is False and score == 0.0


def test_slider_question_evaluation():
    plugin = question_type_registry.get("slider")
    correct = {"min": 0, "max": 100, "target": 50, "tolerance": 10}
    assert plugin.validate_payload([], correct) is True

    # Exact hit
    is_corr, score = plugin.check_answer(50, correct)
    assert is_corr is True and score == 1.0

    # Within tolerance (gradient partial score)
    is_corr, score = plugin.check_answer(55, correct)
    assert is_corr is True and score >= 0.5

    # Out of tolerance
    is_corr, score = plugin.check_answer(75, correct)
    assert is_corr is False and score == 0.0


def test_pin_answer_question_evaluation():
    plugin = question_type_registry.get("pin_answer")
    correct = {"x": 100, "y": 150, "radius": 20}
    assert plugin.validate_payload([], correct) is True

    # Hit inside radius
    is_corr, score = plugin.check_answer({"x": 105, "y": 148}, correct)
    assert is_corr is True and score == 1.0

    # Miss outside radius
    is_corr, score = plugin.check_answer({"x": 150, "y": 200}, correct)
    assert is_corr is False and score == 0.0


def test_drop_pin_question_evaluation():
    plugin = question_type_registry.get("drop_pin")
    correct = {"lat": 41.31, "lng": 69.24, "tolerance": 0.5}
    assert plugin.validate_payload([], correct) is True

    is_corr, score = plugin.check_answer({"lat": 41.32, "lng": 69.25}, correct)
    assert is_corr is True and score == 1.0


def test_match_pairs_question_evaluation():
    plugin = question_type_registry.get("match_pairs")
    pairs = [
        {"id": "p1", "left": "Toshkent", "right": "O‘zbekiston"},
        {"id": "p2", "left": "Parij", "right": "Fransiya"},
        {"id": "p3", "left": "Tokio", "right": "Yaponiya"},
    ]
    assert plugin.validate_payload(pairs, pairs) is True

    # Full correct match
    submission = {
        "Toshkent": "O‘zbekiston",
        "Parij": "Fransiya",
        "Tokio": "Yaponiya"
    }
    is_corr, score = plugin.check_answer(submission, pairs)
    assert is_corr is True and score == 1.0

    # Partial match
    partial_sub = {
        "Toshkent": "O‘zbekiston",
        "Parij": "Yaponiya",
        "Tokio": "Fransiya"
    }
    is_corr, score = plugin.check_answer(partial_sub, pairs)
    assert score == pytest.approx(0.33, 0.05)


def test_math_equation_question_evaluation():
    plugin = question_type_registry.get("math_equation")
    correct = "E = m * c^2"
    assert plugin.validate_payload([], correct) is True

    is_corr, score = plugin.check_answer("e = m * c^2", correct)
    assert is_corr is True and score == 1.0


def test_code_output_question_evaluation():
    plugin = question_type_registry.get("code_output")
    correct = "Salom, Dunyo!"
    assert plugin.validate_payload([], correct) is True

    is_corr, score = plugin.check_answer("Salom, Dunyo!\n", correct)
    assert is_corr is True and score == 1.0

