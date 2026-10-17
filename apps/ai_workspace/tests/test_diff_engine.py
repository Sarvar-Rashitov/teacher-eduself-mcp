"""
Unit testlar: AIDiffEngine va Savollarni Qulflash (Locking).
Spetsifikatsiya: .docs/ai/AI_AGENT.md (4 va 5-bo'lim)
"""
import pytest
from django.contrib.auth import get_user_model
from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.diff_engine import AIDiffEngine, QuestionLockedError

User = get_user_model()


@pytest.mark.django_db
class TestAIDiffEngine:
    @pytest.fixture
    def quiz_with_question(self):
        user = User.objects.create_user(username='math_teacher', password='123')
        quiz = Quiz.objects.create(title="Algebra", owner=user)
        q = Question.objects.create(
            quiz=quiz,
            order_index=1,
            type='single_choice',
            prompt="2 + 2 = ?",
            options=[{"id": "A", "text": "4"}, {"id": "B", "text": "5"}],
            correct_answer={"selected_option_id": "A"},
            points=1000,
            is_locked=False
        )
        return quiz, q, user

    def test_compute_diff_detects_changes(self):
        """O'zgargan maydonlarni (prompt, options) to'g'ri aniqlash."""
        orig = {
            "prompt": "Eski savol",
            "options": [{"id": "A", "text": "1"}],
            "points": 1000
        }
        prop = {
            "prompt": "Yangi qiyinlashtirilgan savol",
            "options": [{"id": "A", "text": "2"}],
            "points": 1500
        }
        diff = AIDiffEngine.compute_question_diff(orig, prop)
        assert diff["has_changes"] is True
        assert "prompt" in diff["modified_fields"]
        assert "options" in diff["modified_fields"]
        assert "points" in diff["modified_fields"]

    def test_compute_diff_no_changes(self):
        """O'zgarish bo'lmaganda has_changes=False."""
        orig = {"prompt": "Bir xil savol", "points": 1000}
        prop = {"prompt": "Bir xil savol", "points": 1000}
        diff = AIDiffEngine.compute_question_diff(orig, prop)
        assert diff["has_changes"] is False
        assert len(diff["modified_fields"]) == 0

    def test_locked_question_cannot_be_modified(self, quiz_with_question):
        """
        AI_AGENT.md 5-bo'lim:
        is_locked=True qilingan savol AI tomonidan o'zgartirilganda QuestionLockedError qo'zg'atilishi shart!
        """
        _, question, _ = quiz_with_question
        question.is_locked = True
        question.save()

        with pytest.raises(QuestionLockedError, match="o'qituvchi tomonidan qulflangan"):
            AIDiffEngine.apply_revision(question, {"prompt": "AI o'zgartirmoqchi bo'lgan matn"})

    def test_unlocked_question_revision_applied(self, quiz_with_question):
        """Qulflanmagan savolga o'zgartirish muvaffaqiyatli saqlanadi."""
        _, question, _ = quiz_with_question
        assert question.is_locked is False

        updated = AIDiffEngine.apply_revision(question, {
            "prompt": "Yangilangan savol matni: $x^2 = 16$",
            "points": 2000
        })
        assert updated.prompt == "Yangilangan savol matni: $x^2 = 16$"
        assert updated.points == 2000
