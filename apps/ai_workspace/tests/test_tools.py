import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from quizzes.models import Quiz, Question
from ai_workspace.tools import PlatformTools

User = get_user_model()


@pytest.mark.django_db
class TestPlatformTools:
    @pytest.fixture
    def setup_user(self):
        user = User.objects.create_user(
            username="teacher_tools",
            email="teacher_tools@test.com",
            password="testpassword123",
            role="teacher",
        )
        other_user = User.objects.create_user(
            username="other_teacher",
            email="other@test.com",
            password="testpassword123",
            role="teacher",
        )
        return {"user": user, "other_user": other_user}

    def test_create_quiz_draft_creates_models_and_snapshot(self, setup_user):
        user = setup_user["user"]
        questions_payload = [
            {
                "order": 1,
                "prompt": "O'zbekiston Respublikasi Konstitutsiyasi qachon qabul qilingan?",
                "type": "single_choice",
                "options": [
                    {"id": "A", "text": "1992-yil 8-dekabr"},
                    {"id": "B", "text": "1991-yil 1-sentyabr"},
                    {"id": "C", "text": "1993-yil 2-iyul"},
                    {"id": "D", "text": "1990-yil 20-iyun"},
                ],
                "correct_answer": "A",
                "explanation": "1992-yil 8-dekabrda 12-chaqiriq Oliy Kengash sessiyasida qabul qilingan.",
                "points": 1000,
                "time_limit_seconds": 30,
                "difficulty": "medium",
            }
        ]

        quiz = PlatformTools.create_quiz_draft(
            title="Konstitutsiya darsi",
            questions_data=questions_payload,
            author=user,
            description="Konstitutsiya bo'yicha viktorina",
            subject="Huquq",
            grade_level=8,
        )

        assert quiz.status == "draft"
        assert quiz.owner == user
        assert quiz.questions.count() == 1

        question = quiz.questions.first()
        assert question.prompt == "O'zbekiston Respublikasi Konstitutsiyasi qachon qabul qilingan?"
        assert question.correct_answer == {"correct_option_id": "A"}
        assert question.is_locked is False

        # Verify initial snapshot creation
        assert quiz.versions.count() == 1
        snapshot = quiz.versions.first()
        assert snapshot.version_number == 1
        assert len(snapshot.snapshot_data["questions"]) == 1

    def test_lock_question_toggle_and_permissions(self, setup_user):
        user = setup_user["user"]
        other_user = setup_user["other_user"]

        quiz = Quiz.objects.create(
            owner=user,
            title="Qulflash testi",
            subject="Fizika",
            grade_level=9,
        )
        question = Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="Yorug'lik tezligi qancha?",
            options=[
                {"id": "A", "text": "300 000 km/s"},
                {"id": "B", "text": "150 000 km/s"},
            ],
            correct_answer={"correct_option_id": "A"},
            order_index=1,
            is_locked=False,
        )

        # Owner locks the question
        locked_q = PlatformTools.lock_question(
            question_id=str(question.id),
            is_locked=True,
            user=user,
        )
        assert locked_q.is_locked is True

        # Other teacher tries to modify lock -> PermissionDenied
        with pytest.raises(PermissionDenied):
            PlatformTools.lock_question(
                question_id=str(question.id),
                is_locked=False,
                user=other_user,
            )

        # Verify question remains locked
        question.refresh_from_db()
        assert question.is_locked is True

    def test_validate_quiz_content(self):
        valid_payload = {
            "title": "Informatika asoslari",
            "description": "Algoritmlar bo'limi",
            "subject": "Informatika",
            "grade_level": 7,
            "language": "uz",
            "suggested_game_mode": "classic",
            "questions": [
                {
                    "order": 1,
                    "prompt": "Axborotning eng kichik o'lchov birligi nima?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "Bayt"},
                        {"id": "B", "text": "Bit"},
                        {"id": "C", "text": "Kilobayt"},
                        {"id": "D", "text": "Megabayt"},
                    ],
                    "correct_answer": "B",
                    "explanation": "1 bayt = 8 bit, bit eng kichik o'lchov birligidir.",
                    "difficulty": "easy",
                }
            ],
        }

        res = PlatformTools.validate_quiz_content(valid_payload)
        assert res["valid"] is True
        assert len(res["errors"]) == 0

        # Invalid payload (duplicate option)
        invalid_payload = dict(valid_payload)
        invalid_payload["questions"] = [
            {
                "order": 1,
                "prompt": "Test savoli",
                "type": "single_choice",
                "options": [
                    {"id": "A", "text": "Takror"},
                    {"id": "B", "text": "Takror"},
                ],
                "correct_answer": "A",
            }
        ]

        res_invalid = PlatformTools.validate_quiz_content(invalid_payload)
        assert res_invalid["valid"] is False
        assert len(res_invalid["errors"]) > 0

    def test_suggest_game_modes(self):
        # Primary grade
        res_primary = PlatformTools.suggest_game_modes("Matematika", grade_level=3, question_count=10)
        assert res_primary["suggested_mode"] == "team_battle"

        # High school STEM
        res_stem = PlatformTools.suggest_game_modes("Fizika", grade_level=9, question_count=8)
        assert res_stem["suggested_mode"] == "classic"

        # Short quiz
        res_short = PlatformTools.suggest_game_modes("Adabiyot", grade_level=8, question_count=4)
        assert res_short["suggested_mode"] == "speed_run"
