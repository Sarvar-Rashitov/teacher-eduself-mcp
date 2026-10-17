"""
Unit & Integration testlar: AIQuizGenerator, PlatformTools va REST API.
Spetsifikatsiya: .docs/ai/AI_QUIZ_GENERATION.md & AI_TOOL_CALLING.md
"""
import pytest
from unittest.mock import AsyncMock, patch
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
    AIQuestionRevisionProposal,
    QuizRequirements
)
from apps.ai_workspace.generator import AIQuizGenerator
from apps.ai_workspace.tools import PlatformTools

User = get_user_model()


@pytest.fixture
def sample_generated_quiz():
    return AIGeneratedQuiz(
        title="8-sinf Kimyo",
        description="Kimyoviy elementlar",
        subject="Kimyo",
        grade_level=8,
        suggested_game_mode="boss_battle",
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Suvning kimyoviy formulasi qaysi?",
                options=[
                    AIGeneratedOption(id="A", text="$\\text{H}_2\\text{O}$"),
                    AIGeneratedOption(id="B", text="$\\text{CO}_2$"),
                    AIGeneratedOption(id="C", text="$\\text{O}_2$"),
                    AIGeneratedOption(id="D", text="$\\text{NaCl}$")
                ],
                correct_answer="A",
                explanation="Suv vodorod va kisloroddan tashkil topgan: $\\text{H}_2\\text{O}$."
            )
        ]
    )


class TestPlatformTools:
    def test_suggest_game_modes(self):
        """Dars parametrlariga ko'ra rejimlar tavsiyasi."""
        # 25 kishi bo'lsa team_battle tavsiya etiladi
        res = PlatformTools.suggest_game_modes(student_count=25, duration_minutes=15)
        modes = [r['mode'] for r in res]
        assert "team_battle" in modes
        assert "gold_quest" in modes

    @pytest.mark.django_db
    def test_create_quiz_draft(self, sample_generated_quiz):
        """Pydantic AIGeneratedQuiz dan PostgreSQL dagi Quiz va Question modellarini yaratish."""
        user = User.objects.create_user(username='chem_teacher', password='123')
        quiz = PlatformTools.create_quiz_draft(sample_generated_quiz, author=user)

        assert quiz.title == "8-sinf Kimyo"
        assert quiz.status == "draft"
        assert quiz.owner == user
        assert quiz.questions.count() == 1

        q = quiz.questions.first()
        assert q.prompt == "Suvning kimyoviy formulasi qaysi?"
        assert q.correct_answer == {"selected_option_id": "A"}
        assert len(q.options) == 4


@pytest.mark.asyncio
class TestAIQuizGenerator:
    async def test_determine_task_type(self):
        """Fan bo'yicha model tanlash turi."""
        assert AIQuizGenerator._determine_task_type("Fizika") == "stem_math"
        assert AIQuizGenerator._determine_task_type("Matematika") == "stem_math"
        assert AIQuizGenerator._determine_task_type("Informatika") == "coding_it"
        assert AIQuizGenerator._determine_task_type("Tarix") == "standard"

    async def test_generate_quiz_end_to_end(self, sample_generated_quiz):
        """Gateway orqali to'liq viktorina generatsiyasi."""
        req = QuizRequirements(
            subject="Kimyo",
            grade_level=8,
            topic="Moddalar",
            question_count=1
        )

        with patch("apps.ai_gateway.router.model_router.execute_structured", new=AsyncMock(return_value=sample_generated_quiz)):
            result = await AIQuizGenerator.generate_quiz(req)
            assert result.title == "8-sinf Kimyo"
            assert len(result.questions) == 1

    async def test_revise_single_question(self):
        """Aynan bitta savolni tahrirlash taklifi."""
        proposal_mock = AIQuestionRevisionProposal(
            question_order=1,
            change_summary="Savol soddalashtirildi",
            modified_fields=["prompt"],
            new_question_data=AIGeneratedQuestion(
                order=1,
                prompt="Sodda savol?",
                options=[AIGeneratedOption(id="A", text="1"), AIGeneratedOption(id="B", text="2")],
                correct_answer="A",
                explanation="Oddiy tushuntirish."
            )
        )

        with patch("apps.ai_gateway.router.model_router.execute_structured", new=AsyncMock(return_value=proposal_mock)):
            res = await AIQuizGenerator.revise_single_question({"prompt": "Eski"}, "Osonlashtir")
            assert res.change_summary == "Savol soddalashtirildi"
            assert "prompt" in res.modified_fields


@pytest.mark.django_db
class TestAIWorkspaceAPIViews:
    @pytest.fixture
    def client_and_teacher(self):
        user = User.objects.create_user(username='api_teacher', password='123', role='teacher')
        client = APIClient()
        client.force_authenticate(user=user)
        return client, user

    def test_generate_quiz_api(self, client_and_teacher, sample_generated_quiz):
        client, _ = client_and_teacher
        payload = {
            "subject": "Kimyo",
            "grade_level": 8,
            "topic": "Atomlar",
            "question_count": 1
        }

        with patch("apps.ai_gateway.router.model_router.execute_structured", new=AsyncMock(return_value=sample_generated_quiz)):
            res = client.post("/api/ai/generate/", payload, format='json')
            assert res.status_code == 201
            data = res.json()
            assert "quiz_id" in data
            assert data["title"] == "8-sinf Kimyo"

    def test_revise_locked_question_returns_403(self, client_and_teacher):
        client, user = client_and_teacher
        quiz = Quiz.objects.create(title="Test Quiz", owner=user)
        q = Question.objects.create(
            quiz=quiz,
            order_index=1,
            prompt="Qulflangan savol",
            options=[{"id": "A", "text": "Ha"}],
            correct_answer={"selected_option_id": "A"},
            is_locked=True  # Qulflangan!
        )

        res = client.post("/api/ai/revise/", {
            "question_id": str(q.id),
            "instruction": "O'zgartir"
        }, format='json')

        assert res.status_code == 403
        assert "qulflangan" in res.json()["error"]

    def test_suggest_modes_api(self, client_and_teacher):
        client, _ = client_and_teacher
        res = client.get("/api/ai/suggest-modes/?student_count=20&duration_minutes=15")
        assert res.status_code == 200
        assert "recommendations" in res.json()
