import uuid
from django.test import TestCase, Client
from django.urls import reverse
from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question, QuizVersion
from apps.quizzes.services import QuizCRUDService, VersionManager, ZeroKnowledgeQuestionDelivery
from apps.questions_registry.exceptions import QuestionValidationError
import apps.questions_registry.types  # ensure registry is loaded


class QuizCRUDTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username="teacher_dilshod",
            email="dilshod@example.com",
            password="StrongPassword123!",
            role="teacher",
        )
        self.quiz = QuizCRUDService.create_quiz(
            owner=self.teacher,
            title="Biologiya 8-sinf",
            subject="Biologiya",
            grade_level=8,
            locale="uz-Latn",
        )

    def test_quiz_creation(self):
        """Viktorina muvaffaqiyatli yaratilishi va dastlabki v1 holati."""
        self.assertIsInstance(self.quiz.id, uuid.UUID)
        self.assertEqual(self.quiz.title, "Biologiya 8-sinf")
        self.assertEqual(self.quiz.current_version, 1)
        self.assertEqual(self.quiz.status, "draft")

    def test_add_valid_question(self):
        """Valid savol qo'shilishi va tartib raqami to'g'ri o'rnatilishi."""
        q_data = {
            "type": "single_choice",
            "prompt": "Hujayra yadrosini kim kashf qilgan?",
            "options": [
                {"id": "a", "text": "Robert Brown"},
                {"id": "b", "text": "Robert Hooke"},
                {"id": "c", "text": "Antoni van Leeuwenhoek"},
            ],
            "correct_answer": "a",
            "points": 1000,
            "time_limit_seconds": 30,
            "explanation": "Robert Brown 1831-yilda o'simlik hujayralarida yadroni aniqlagan.",
        }
        question = QuizCRUDService.add_question(self.quiz, q_data)
        self.assertIsInstance(question.id, uuid.UUID)
        self.assertEqual(question.order_index, 0)
        self.assertEqual(question.points, 1000)
        self.assertEqual(self.quiz.questions.count(), 1)

    def test_add_invalid_question_raises_validation_error(self):
        """Noto'g'ri savol formati yuborilganda QuestionValidationError chiqishi."""
        bad_data = {
            "type": "single_choice",
            "prompt": "Bu xato savol",
            "options": [{"id": "single_opt", "text": "Faqat bitta variant"}],
            "correct_answer": "single_opt",
        }
        with self.assertRaises(QuestionValidationError):
            QuizCRUDService.add_question(self.quiz, bad_data)

    def test_question_lock_protection(self):
        """is_locked=True bo'lgan savolni ruxsatsiz o'zgartirish bloklanishi."""
        q_data = {
            "type": "true_false",
            "prompt": "DNK qo'sh spiraldan iborat.",
            "options": [],
            "correct_answer": True,
            "is_locked": True,
        }
        question = QuizCRUDService.add_question(self.quiz, q_data)
        self.assertTrue(question.is_locked)

        # O'zgartirishga urinish
        with self.assertRaises(QuestionValidationError):
            QuizCRUDService.update_question(question, {"prompt": "Yangi matn"}, force=False)

        # Force=True bilan o'zgartirish
        updated = QuizCRUDService.update_question(question, {"prompt": "Yangi matn"}, force=True)
        self.assertEqual(updated.prompt, "Yangi matn")

    def test_version_snapshot_freezes_state(self):
        """Sessiya boshlanganda snapshot olinishi va versiya oshishi."""
        QuizCRUDService.add_question(
            self.quiz,
            {
                "type": "true_false",
                "prompt": "Mitoxondriya hujayra energiya stansiyasidir.",
                "options": [],
                "correct_answer": True,
            },
        )
        self.assertEqual(self.quiz.current_version, 1)

        version_1 = VersionManager.create_snapshot(self.quiz)
        self.assertEqual(version_1.version_number, 1)
        self.assertEqual(len(version_1.snapshot["questions"]), 1)
        self.assertEqual(version_1.snapshot["questions"][0]["prompt"], "Mitoxondriya hujayra energiya stansiyasidir.")

        # Quiz current_version endi 2 bo'lishi kerak
        self.quiz.refresh_from_db()
        self.assertEqual(self.quiz.current_version, 2)

    def test_zero_knowledge_student_preview(self):
        """Talabaga beriladigan ma'lumotlarda correct_answer va explanation mutlaqo bo'lmasligi."""
        question = QuizCRUDService.add_question(
            self.quiz,
            {
                "type": "single_choice",
                "prompt": "Fotosintez qayerda sodir bo'ladi?",
                "options": [
                    {"id": "opt1", "text": "Xloroplast", "is_correct": True},
                    {"id": "opt2", "text": "Ribosoma", "is_correct": False},
                ],
                "correct_answer": "opt1",
                "explanation": "Xloroplastlarda xlorofill pigmenti bo'ladi.",
            },
        )
        sanitized = ZeroKnowledgeQuestionDelivery.sanitize(question)
        self.assertNotIn("correct_answer", sanitized)
        self.assertNotIn("explanation", sanitized)
        self.assertEqual(sanitized["prompt"], "Fotosintez qayerda sodir bo'ladi?")
        for opt in sanitized["options"]:
            self.assertNotIn("is_correct", opt)

    def test_api_student_preview_endpoint(self):
        """Talaba ko'rinishi REST endpointi javob kalitlarini qaytarmasligi tekshiruvi."""
        client = Client()
        QuizCRUDService.add_question(
            self.quiz,
            {
                "type": "open_short",
                "prompt": "O'zbekiston Respublikasi Konstitutsiyasi qachon qabul qilingan?",
                "options": [],
                "correct_answer": ["1992", "8-dekabr 1992"],
                "explanation": "1992-yil 8-dekabrda qabul qilingan.",
            },
        )
        url = reverse("quizzes:quiz_student_preview", kwargs={"pk": self.quiz.id})
        response = client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(len(data["questions"]), 1)
        q_item = data["questions"][0]
        self.assertNotIn("correct_answer", q_item)
        self.assertNotIn("explanation", q_item)
