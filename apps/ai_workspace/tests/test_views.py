import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from quizzes.models import Quiz, Question
from ai_workspace.schemas import (
    AIGeneratedQuiz,
    AIGeneratedQuestion,
    AIGeneratedOption,
    AIQuestionRevisionProposal,
    QuestionTypeEnum,
)

User = get_user_model()


@pytest.mark.django_db
class TestAIWorkspaceAPIViews:
    @pytest.fixture
    def setup_api(self):
        client = APIClient()
        user = User.objects.create_user(
            username="teacher_api",
            email="teacher_api@test.com",
            password="testpassword123",
            role="teacher",
        )
        client.force_authenticate(user=user)

        quiz = Quiz.objects.create(
            owner=user,
            title="Biologiya Viktorinasi",
            subject="Biologiya",
            grade_level=8,
        )
        question = Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="DNK qayerda joylashgan?",
            options=[
                {"id": "A", "text": "Yadroda"},
                {"id": "B", "text": "Sitoplazmada"},
                {"id": "C", "text": "Ribosomada"},
                {"id": "D", "text": "Vakuolada"},
            ],
            correct_answer={"correct_option_id": "A"},
            explanation="Eukariot hujayralarda asosiy DNK yadroda saqlanadi.",
            order_index=1,
            is_locked=False,
            version=1,
        )

        return {"client": client, "user": user, "quiz": quiz, "question": question}

    @patch("ai_workspace.views.AIQuizGenerator")
    def test_generate_quiz_without_save(self, mock_gen_cls, setup_api):
        client = setup_api["client"]

        mock_instance = MagicMock()
        mock_quiz = AIGeneratedQuiz(
            title="Kimyo Asoslari",
            description="Davriy jadval bo'yicha",
            subject="Kimyo",
            grade_level=8,
            language="uz",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Suvning kimyoviy formulasi qanday?",
                    type=QuestionTypeEnum.SINGLE_CHOICE,
                    options=[
                        AIGeneratedOption(id="A", text="$H_2O$"),
                        AIGeneratedOption(id="B", text="$CO_2$"),
                        AIGeneratedOption(id="C", text="$NaCl$"),
                        AIGeneratedOption(id="D", text="$O_2$"),
                    ],
                    correct_answer="A",
                    explanation="Suv 2 vodorod va 1 kislorod atomidan iborat.",
                )
            ],
        )

        async def fake_generate(**kwargs):
            return mock_quiz

        mock_instance.generate_quiz = fake_generate
        mock_gen_cls.return_value = mock_instance

        res = client.post(
            "/api/v1/ai/workspace/generate/",
            {
                "topic": "Suv va uning xossalari",
                "subject": "Kimyo",
                "grade_level": 8,
                "save_draft": False,
            },
            format="json",
        )

        assert res.status_code == 200
        assert "generated_quiz" in res.data
        assert res.data["generated_quiz"]["title"] == "Kimyo Asoslari"
        assert "quiz_id" not in res.data

    @patch("ai_workspace.views.AIQuizGenerator")
    def test_generate_quiz_with_save_draft(self, mock_gen_cls, setup_api):
        client = setup_api["client"]

        mock_instance = MagicMock()
        mock_quiz = AIGeneratedQuiz(
            title="Astronomiya Asoslari",
            description="Quyosh tizimi",
            subject="Fizika",
            grade_level=9,
            language="uz",
            questions=[
                AIGeneratedQuestion(
                    order=1,
                    prompt="Quyosh tizimidagi eng katta sayyora qaysi?",
                    type=QuestionTypeEnum.SINGLE_CHOICE,
                    options=[
                        AIGeneratedOption(id="A", text="Yupiter"),
                        AIGeneratedOption(id="B", text="Saturn"),
                        AIGeneratedOption(id="C", text="Mars"),
                        AIGeneratedOption(id="D", text="Yer"),
                    ],
                    correct_answer="A",
                    explanation="Yupiter Quyosh tizimidagi eng yirik gaz gigantidir.",
                )
            ],
        )

        async def fake_generate(**kwargs):
            return mock_quiz

        mock_instance.generate_quiz = fake_generate
        mock_gen_cls.return_value = mock_instance

        res = client.post(
            "/api/v1/ai/workspace/generate/",
            {
                "topic": "Quyosh tizimi",
                "subject": "Fizika",
                "grade_level": 9,
                "save_draft": True,
            },
            format="json",
        )

        assert res.status_code == 200
        assert res.data.get("status") == "draft_created"
        assert "quiz_id" in res.data

        # Verify quiz created in database
        saved_quiz = Quiz.objects.get(id=res.data["quiz_id"])
        assert saved_quiz.title == "Astronomiya Asoslari"
        assert saved_quiz.status == "draft"
        assert saved_quiz.questions.count() == 1

    @patch("ai_workspace.views.AIQuizGenerator")
    def test_revise_question_success(self, mock_gen_cls, setup_api):
        client = setup_api["client"]
        question = setup_api["question"]

        mock_instance = MagicMock()
        mock_proposal = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Variantlar va tushuntirish aniqlashtirildi",
            modified_fields=["explanation"],
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="DNK molekulasi asosan qayerda joylashgan?",
                type=QuestionTypeEnum.SINGLE_CHOICE,
                options=[
                    AIGeneratedOption(id="A", text="Hujayra yadrosida"),
                    AIGeneratedOption(id="B", text="Sitoplazmada"),
                    AIGeneratedOption(id="C", text="Ribosomada"),
                    AIGeneratedOption(id="D", text="Vakuolada"),
                ],
                correct_answer={"correct_option_id": "A"},
                explanation="DNK molekulalari xromosomalarda, ular esa yadroda saqlanadi.",
            ),
        )

        async def fake_revise(**kwargs):
            return mock_proposal

        mock_instance.revise_single_question = fake_revise
        mock_gen_cls.return_value = mock_instance

        res = client.post(
            "/api/v1/ai/workspace/revise-question/",
            {
                "question_id": str(question.id),
                "revision_instruction": "Tushuntirishni xromosomalar bilan bog'lab kengaytiring",
            },
            format="json",
        )

        assert res.status_code == 200
        assert res.data["question_id"] == str(question.id)
        assert res.data["change_summary"] == "Variantlar va tushuntirish aniqlashtirildi"
        assert "diffs" in res.data

    def test_revise_locked_question_returns_403(self, setup_api):
        client = setup_api["client"]
        question = setup_api["question"]
        question.is_locked = True
        question.save()

        res = client.post(
            "/api/v1/ai/workspace/revise-question/",
            {
                "question_id": str(question.id),
                "revision_instruction": "Matnni o'zgartiring",
            },
            format="json",
        )

        assert res.status_code == 403
        assert "qulflangan" in res.data["error"].lower()

    def test_apply_diff_success(self, setup_api):
        client = setup_api["client"]
        question = setup_api["question"]

        proposal_payload = {
            "question_order": 1,
            "change_summary": "Yangi vaqt limiti va matn",
            "modified_fields": ["prompt", "time_limit_seconds"],
            "new_question_data": {
                "order": 1,
                "prompt": "DNK molekulasi xromosomalarda qayerda joylashgan?",
                "type": "single_choice",
                "options": [
                    {"id": "A", "text": "Yadroda"},
                    {"id": "B", "text": "Sitoplazmada"},
                    {"id": "C", "text": "Golji apparatida"},
                    {"id": "D", "text": "Ribosomada"},
                ],
                "correct_answer": {"correct_option_id": "A"},
                "explanation": "Yadroda.",
                "time_limit_seconds": 25,
                "points": 1000,
                "difficulty": "medium",
            },
        }

        res = client.post(
            "/api/v1/ai/workspace/apply-diff/",
            {
                "question_id": str(question.id),
                "proposal": proposal_payload,
            },
            format="json",
        )

        assert res.status_code == 200
        assert res.data["status"] == "applied"
        assert res.data["version"] == 2

        question.refresh_from_db()
        assert question.version == 2
        assert question.time_limit_seconds == 25

    def test_apply_diff_locked_question_returns_403(self, setup_api):
        client = setup_api["client"]
        question = setup_api["question"]
        question.is_locked = True
        question.save()

        res = client.post(
            "/api/v1/ai/workspace/apply-diff/",
            {
                "question_id": str(question.id),
                "proposal": {
                    "question_order": 1,
                    "change_summary": "Test",
                    "new_question_data": {
                        "order": 1,
                        "prompt": "Savol",
                        "type": "single_choice",
                        "options": [
                            {"id": "A", "text": "1"},
                            {"id": "B", "text": "2"},
                        ],
                        "correct_answer": "A",
                    },
                },
            },
            format="json",
        )

        assert res.status_code == 403
        assert "qulflangan" in res.data["error"].lower()

    def test_lock_question_endpoint(self, setup_api):
        client = setup_api["client"]
        question = setup_api["question"]

        # Lock question
        res = client.post(
            "/api/v1/ai/workspace/lock-question/",
            {"question_id": str(question.id), "is_locked": True},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["is_locked"] is True

        question.refresh_from_db()
        assert question.is_locked is True

        # Unlock question
        res2 = client.post(
            "/api/v1/ai/workspace/lock-question/",
            {"question_id": str(question.id), "is_locked": False},
            format="json",
        )
        assert res2.status_code == 200
        assert res2.data["is_locked"] is False

    def test_validate_quiz_endpoint(self, setup_api):
        client = setup_api["client"]
        valid_quiz = {
            "title": "Adabiyot Testi",
            "subject": "Adabiyot",
            "grade_level": 7,
            "language": "uz",
            "questions": [
                {
                    "order": 1,
                    "prompt": "Alisher Navoiy qaysi asr mutafakkiri?",
                    "type": "single_choice",
                    "options": [
                        {"id": "A", "text": "XV asr"},
                        {"id": "B", "text": "XIV asr"},
                        {"id": "C", "text": "XVI asr"},
                        {"id": "D", "text": "XIII asr"},
                    ],
                    "correct_answer": "A",
                }
            ],
        }

        res = client.post(
            "/api/v1/ai/workspace/validate/",
            {"quiz_data": valid_quiz},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["valid"] is True

    def test_game_modes_endpoint(self, setup_api):
        client = setup_api["client"]
        res = client.get(
            "/api/v1/ai/workspace/game-modes/",
            {"subject": "Matematika", "grade_level": 3, "question_count": 5},
        )
        assert res.status_code == 200
        assert "suggested_mode" in res.data
        assert res.data["suggested_mode"] == "team_battle"
