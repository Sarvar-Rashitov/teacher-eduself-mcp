import pytest
from questions_registry import (
    question_registry,
    QuestionValidationError,
    QuestionTypeNotFoundError,
    BaseQuestionType,
)


class TestQuestionRegistry:
    def test_default_types_registered(self):
        expected_types = [
            "single_choice",
            "multiple_choice",
            "true_false",
            "ordering",
            "categorization",
            "cloze",
            "open_short",
        ]
        for t in expected_types:
            assert question_registry.is_registered(t)
            handler = question_registry.get(t)
            assert isinstance(handler, BaseQuestionType)
            assert handler.type_id == t

    def test_aliases_resolution(self):
        assert question_registry.get("multiple_select").type_id == "multiple_choice"
        assert question_registry.get("multi_select").type_id == "multiple_choice"
        assert question_registry.get("puzzle_order").type_id == "ordering"
        assert question_registry.get("sequence").type_id == "ordering"
        assert question_registry.get("category_sort").type_id == "categorization"
        assert question_registry.get("fill_in_blanks").type_id == "cloze"
        assert question_registry.get("short_text").type_id == "open_short"
        assert question_registry.get("type_answer").type_id == "open_short"

    def test_unregistered_type_raises_error(self):
        with pytest.raises(QuestionTypeNotFoundError):
            question_registry.get("non_existent_type_xyz")


class TestSingleChoiceQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("single_choice")
        self.valid_options = [
            {"id": "opt_1", "text": "Alisher Navoiy"},
            {"id": "opt_2", "text": "Zahiriddin Muhammad Bobur"},
            {"id": "opt_3", "text": "Amir Temur"},
            {"id": "opt_4", "text": "Mirzo Ulug'bek"},
        ]
        self.valid_answer = {"correct_option_id": "opt_1"}

    def test_valid_payload(self):
        # Should not raise
        self.handler.validate_payload(self.valid_options, self.valid_answer)

    def test_invalid_option_count(self):
        # < 2 options
        with pytest.raises(QuestionValidationError, match="between 2 and 6"):
            self.handler.validate_payload([{"id": "1", "text": "One"}], {"correct_option_id": "1"})

        # > 6 options
        seven_options = [{"id": f"opt_{i}", "text": f"Choice {i}"} for i in range(7)]
        with pytest.raises(QuestionValidationError, match="between 2 and 6"):
            self.handler.validate_payload(seven_options, {"correct_option_id": "opt_0"})

    def test_missing_or_duplicate_ids(self):
        dup_options = [
            {"id": "dup", "text": "Choice A"},
            {"id": "dup", "text": "Choice B"},
        ]
        with pytest.raises(QuestionValidationError, match="Duplicate option id"):
            self.handler.validate_payload(dup_options, {"correct_option_id": "dup"})

    def test_correct_answer_not_in_options(self):
        with pytest.raises(QuestionValidationError, match="not present in options list"):
            self.handler.validate_payload(self.valid_options, {"correct_option_id": "non_existent"})

    def test_check_answer(self):
        # Correct answer
        res = self.handler.check_answer({"selected_option_id": "opt_1"}, self.valid_answer)
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # Incorrect answer
        res = self.handler.check_answer({"selected_option_id": "opt_2"}, self.valid_answer)
        assert res.is_correct is False
        assert res.score_fraction == 0.0

    def test_zero_knowledge_sanitization(self):
        question_data = {
            "type": "single_choice",
            "prompt": "Kim 'Xamsa' dostonini yozgan?",
            "options": [
                {"id": "opt_1", "text": "Navoiy", "is_correct": True},
                {"id": "opt_2", "text": "Bobur", "is_correct": False},
            ],
            "correct_answer": {"correct_option_id": "opt_1"},
            "explanation": "Alisher Navoiy 1483-1485 yillarda Xamsa yozgan.",
            "points": 1000,
        }
        sanitized = self.handler.sanitize_for_student(question_data)
        assert "correct_answer" not in sanitized
        assert "explanation" not in sanitized
        assert "is_correct" not in sanitized["options"][0]
        assert "is_correct" not in sanitized["options"][1]
        assert sanitized["prompt"] == question_data["prompt"]
        assert sanitized["points"] == 1000


class TestMultipleChoiceQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("multiple_choice")
        self.valid_options = [
            {"id": "A", "text": "Toshkent"},
            {"id": "B", "text": "Samarqand"},
            {"id": "C", "text": "Buxoro"},
            {"id": "D", "text": "Madrid"},
        ]
        self.valid_answer = {"correct_option_ids": ["A", "B", "C"]}

    def test_valid_payload(self):
        self.handler.validate_payload(self.valid_options, self.valid_answer)

    def test_insufficient_options(self):
        with pytest.raises(QuestionValidationError, match="at least 3 options"):
            self.handler.validate_payload(
                [{"id": "1", "text": "A"}, {"id": "2", "text": "B"}],
                {"correct_option_ids": ["1"]}
            )

    def test_invalid_correct_id(self):
        with pytest.raises(QuestionValidationError, match="do not exist in the options list"):
            self.handler.validate_payload(self.valid_options, {"correct_option_ids": ["A", "Z"]})

    def test_check_answer_partial_and_penalty(self):
        # 3 correct (A, B, C), 1 wrong (D)
        # All correct: Score = 1.0
        res = self.handler.check_answer(
            {"selected_option_ids": ["A", "B", "C"]},
            self.valid_answer,
            options=self.valid_options
        )
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # Partial correct: 2 of 3 chosen, 0 wrong -> 2/3 = 0.6667
        res = self.handler.check_answer(
            {"selected_option_ids": ["A", "B"]},
            self.valid_answer,
            options=self.valid_options
        )
        assert res.is_correct is False
        assert pytest.approx(res.score_fraction, 0.01) == 0.67

        # With wrong choice penalty: 2 correct (2/3), 1 wrong chosen (1/1) -> max(0, 2/3 - 1/1) = 0.0
        res = self.handler.check_answer(
            {"selected_option_ids": ["A", "B", "D"]},
            self.valid_answer,
            options=self.valid_options
        )
        assert res.is_correct is False
        assert res.score_fraction == 0.0


class TestTrueFalseQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("true_false")

    def test_validate_and_check(self):
        self.handler.validate_payload(None, {"correct_value": True})

        res = self.handler.check_answer({"selected_value": True}, {"correct_value": True})
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        res_false = self.handler.check_answer({"selected_value": False}, {"correct_value": True})
        assert res_false.is_correct is False
        assert res_false.score_fraction == 0.0

        # String representation
        res_str = self.handler.check_answer("true", {"correct_value": True})
        assert res_str.is_correct is True


class TestOrderingQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("ordering")
        self.options = [
            {"id": "step1", "text": "Tuxum qo'yish"},
            {"id": "step2", "text": "Qurt (lichinka)"},
            {"id": "step3", "text": "G'umbak"},
            {"id": "step4", "text": "Kapalak"},
        ]
        self.correct_answer = {"ordered_item_ids": ["step1", "step2", "step3", "step4"]}

    def test_validate(self):
        self.handler.validate_payload(self.options, self.correct_answer)

        # Incomplete order
        with pytest.raises(QuestionValidationError, match="contain exactly all option IDs"):
            self.handler.validate_payload(self.options, {"ordered_item_ids": ["step1", "step2"]})

    def test_check_answer_perfect_and_partial(self):
        # Perfect
        res = self.handler.check_answer(
            {"submitted_order": ["step1", "step2", "step3", "step4"]},
            self.correct_answer
        )
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # Reversed order: completely reversed pairs
        res_rev = self.handler.check_answer(
            {"submitted_order": ["step4", "step3", "step2", "step1"]},
            self.correct_answer
        )
        assert res_rev.is_correct is False
        assert res_rev.score_fraction == 0.0

        # Slight swap: 1 swap in 6 pairs -> 5/6 = 0.8333
        res_swap = self.handler.check_answer(
            {"submitted_order": ["step1", "step2", "step4", "step3"]},
            self.correct_answer
        )
        assert res_swap.is_correct is False
        assert pytest.approx(res_swap.score_fraction, 0.01) == 0.83


class TestCategorizationQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("categorization")
        self.options = {
            "categories": [
                {"id": "cat_fruits", "title": "Mevalar"},
                {"id": "cat_veggies", "title": "Sabzavotlar"},
            ],
            "items": [
                {"id": "item_apple", "text": "Olma"},
                {"id": "item_carrot", "text": "Sabzi"},
                {"id": "item_pear", "text": "Nok"},
                {"id": "item_potato", "text": "Kartoshka"},
            ],
        }
        self.correct_answer = {
            "item_category_map": {
                "item_apple": "cat_fruits",
                "item_carrot": "cat_veggies",
                "item_pear": "cat_fruits",
                "item_potato": "cat_veggies",
            }
        }

    def test_validate_and_check(self):
        self.handler.validate_payload(self.options, self.correct_answer)

        # Perfect submission
        res = self.handler.check_answer(
            {"answers": self.correct_answer["item_category_map"]},
            self.correct_answer
        )
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # 3 out of 4 correct -> 0.75
        partial_submission = {
            "answers": {
                "item_apple": "cat_fruits",
                "item_carrot": "cat_veggies",
                "item_pear": "cat_veggies",  # wrong
                "item_potato": "cat_veggies",
            }
        }
        res_partial = self.handler.check_answer(partial_submission, self.correct_answer)
        assert res_partial.is_correct is False
        assert res_partial.score_fraction == 0.75


class TestClozeQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("cloze")
        self.correct_answer = {
            "blanks": {
                "blank_1": ["Toshkent", "Tashkent"],
                "blank_2": ["O'zbekiston", "Ozbekiston"],
            }
        }

    def test_validate_and_check(self):
        self.handler.validate_payload(None, self.correct_answer)

        # All correct
        res = self.handler.check_answer(
            {"answers": {"blank_1": "toshkent", "blank_2": "ozbekiston"}},
            self.correct_answer
        )
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # 1 correct of 2 -> 0.5
        res_partial = self.handler.check_answer(
            {"answers": {"blank_1": "Samarqand", "blank_2": "Ozbekiston"}},
            self.correct_answer
        )
        assert res_partial.is_correct is False
        assert res_partial.score_fraction == 0.5


class TestOpenShortQuestionType:
    def setup_method(self):
        self.handler = question_registry.get("open_short")
        self.correct_answer = {"accepted_answers": ["Toshkent", "Tashkent", "Тошкент"]}

    def test_validate_and_check(self):
        self.handler.validate_payload(None, self.correct_answer)

        # Exact match (case insensitive, trimmed)
        res = self.handler.check_answer("  toshkent  ", self.correct_answer)
        assert res.is_correct is True
        assert res.score_fraction == 1.0

        # Typo with Levenshtein tolerance <= 1 ("Toshknt" missing 1 char)
        res_typo = self.handler.check_answer(
            "Toshknt",
            self.correct_answer,
            options={"allow_typos_levenshtein": 1}
        )
        assert res_typo.is_correct is True
        assert res_typo.score_fraction == 1.0

        # Complete mismatch
        res_wrong = self.handler.check_answer("Samarqand", self.correct_answer)
        assert res_wrong.is_correct is False
        assert res_wrong.score_fraction == 0.0
