from django.test import TestCase
from apps.questions_registry.registry import registry
from apps.questions_registry.exceptions import (
    QuestionValidationError,
    QuestionTypeNotFoundError,
)
import apps.questions_registry.types  # ensure types are registered


class QuestionRegistryTests(TestCase):
    def test_registry_contains_7_core_types(self):
        """Barcha 7 ta asosiy savol turi ro'yxatdan o'tganligini tekshirish."""
        expected_types = {
            "single_choice",
            "multiple_choice",
            "true_false",
            "ordering",
            "categorization",
            "cloze",
            "open_short",
        }
        all_types = {t["type_id"] for t in registry.list_all()}
        self.assertTrue(expected_types.issubset(all_types))

    def test_unknown_type_raises_error(self):
        """Noma'lum savol turi so'ralganda QuestionTypeNotFoundError chiqishi."""
        with self.assertRaises(QuestionTypeNotFoundError):
            registry.get("non_existent_type_xyz")

    def test_single_choice_validation_and_scoring(self):
        """Yagona tanlovli test validatsiyasi va javob tekshiruvi."""
        handler = registry.get("single_choice")
        valid_options = [
            {"id": "opt_1", "text": "Toshkent"},
            {"id": "opt_2", "text": "Samarqand"},
            {"id": "opt_3", "text": "Buxoro"},
        ]
        # To'g'ri payload
        self.assertTrue(handler.validate_payload(valid_options, "opt_1"))

        # Noto'g'ri: variantlar 2 tadan kam
        with self.assertRaises(QuestionValidationError):
            handler.validate_payload([{"id": "opt_1", "text": "A"}], "opt_1")

        # Noto'g'ri: to'g'ri javob variantlar orasida yo'q
        with self.assertRaises(QuestionValidationError):
            handler.validate_payload(valid_options, "opt_unknown")

        # Javob tekshirish
        res_correct = handler.check_answer("opt_1", "opt_1")
        self.assertTrue(res_correct["is_correct"])
        self.assertEqual(res_correct["score_ratio"], 1.0)

        res_wrong = handler.check_answer("opt_2", "opt_1")
        self.assertFalse(res_wrong["is_correct"])
        self.assertEqual(res_wrong["score_ratio"], 0.0)

    def test_zero_knowledge_sanitization(self):
        """O'quvchiga yuboriladigan variantlardan to'g'ri javob kalitlari tozalanishi."""
        handler = registry.get("single_choice")
        dirty_options = [
            {"id": "a", "text": "A", "is_correct": True, "score": 100},
            {"id": "b", "text": "B", "is_correct": False, "score": 0},
        ]
        clean = handler.sanitize_for_student(dirty_options)
        for opt in clean:
            self.assertNotIn("is_correct", opt)
            self.assertNotIn("score", opt)
            self.assertIn("id", opt)
            self.assertIn("text", opt)

    def test_multiple_choice_partial_credit(self):
        """Ko'p tanlovli testda qisman ball hisoblash."""
        handler = registry.get("multiple_choice")
        options = [
            {"id": "1", "text": "Python"},
            {"id": "2", "text": "JavaScript"},
            {"id": "3", "text": "HTML"},
            {"id": "4", "text": "CSS"},
        ]
        correct_answer = ["1", "2"]  # Dasturlash tillari

        self.assertTrue(handler.validate_payload(options, correct_answer))

        # To'liq to'g'ri tanlov
        res_full = handler.check_answer(["1", "2"], correct_answer, total_options=4)
        self.assertTrue(res_full["is_correct"])
        self.assertEqual(res_full["score_ratio"], 1.0)

        # 1 ta to'g'ri, 1 ta noto'g'ri tanlov
        res_partial = handler.check_answer(["1", "3"], correct_answer, total_options=4)
        self.assertFalse(res_partial["is_correct"])
        self.assertLess(res_partial["score_ratio"], 1.0)

    def test_true_false_evaluation(self):
        """To'g'ri/Noto'g'ri savol tekshiruvi."""
        handler = registry.get("true_false")
        self.assertTrue(handler.validate_payload([], True))

        res1 = handler.check_answer("true", True)
        self.assertTrue(res1["is_correct"])

        res2 = handler.check_answer("false", True)
        self.assertFalse(res2["is_correct"])

    def test_ordering_evaluation(self):
        """Tartiblash savoli tekshiruvi."""
        handler = registry.get("ordering")
        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        correct = ["a", "b", "c"]
        self.assertTrue(handler.validate_payload(items, correct))

        res_correct = handler.check_answer(["a", "b", "c"], correct)
        self.assertTrue(res_correct["is_correct"])
        self.assertEqual(res_correct["score_ratio"], 1.0)

        res_partial = handler.check_answer(["a", "c", "b"], correct)
        self.assertFalse(res_partial["is_correct"])
        self.assertGreater(res_partial["score_ratio"], 0.0)

    def test_open_short_normalization(self):
        """Matnli qisqa javobni normalizatsiya qilib tekshirish."""
        handler = registry.get("open_short")
        self.assertTrue(handler.validate_payload([], ["Toshkent", "Tashkent"]))

        res = handler.check_answer("  toshkent! ", ["Toshkent"])
        self.assertTrue(res["is_correct"])

        res_wrong = handler.check_answer("Samarqand", ["Toshkent"])
        self.assertFalse(res_wrong["is_correct"])
