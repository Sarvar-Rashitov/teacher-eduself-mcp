import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.quizzes.models import Quiz, Question
from apps.ai_workspace.schemas import (
    AIGeneratedOption,
    AIGeneratedQuestion,
    AIGeneratedQuiz,
)
from apps.ai_workspace.tools import PlatformTools

User = get_user_model()


def test_get_quiz_requirements_heuristics():
    req = PlatformTools.get_quiz_requirements("8-sinf Kimyo fanidan 15 ta test kerak")
    assert req.grade_level == 8
    assert req.subject == "Kimyo"
    assert req.question_count == 15

    req_default = PlatformTools.get_quiz_requirements("Oddiy mavzu")
    assert req_default.grade_level == 7
    assert req_default.question_count == 10


def test_suggest_game_modes():
    suggestions = PlatformTools.suggest_game_modes(student_count=30, duration_minutes=10)
    mode_ids = {s["id"] for s in suggestions}
    assert "team_battle" in mode_ids
    assert "speed_run" in mode_ids
    assert "classic" in mode_ids


@pytest.mark.django_db
def test_create_quiz_draft_and_locking():
    user = User.objects.create_user(username="teacher_tools", password="Password123!")

    quiz_spec = AIGeneratedQuiz(
        title="Botanika Test",
        description="O'simliklar dunyosi",
        subject="Biologiya",
        grade_level=6,
        questions=[
            AIGeneratedQuestion(
                order=1,
                prompt="Ildizning asosiy vazifasi nima?",
                options=[
                    AIGeneratedOption(id="A", text="Oziqlanish va tayanch"),
                    AIGeneratedOption(id="B", text="Nafas olish"),
                ],
                correct_answer="A",
                points=1000,
                time_limit_seconds=30,
            )
        ]
    )

    result = PlatformTools.create_quiz_draft(quiz_spec, user)
    assert result["title"] == "Botanika Test"
    assert result["question_count"] == 1

    created_quiz = Quiz.objects.get(id=result["quiz_id"])
    assert created_quiz.status == "draft"
    assert created_quiz.questions.count() == 1

    q = created_quiz.questions.first()
    assert q.is_locked is False

    # Lock question using tool
    lock_res = PlatformTools.lock_question(str(q.id), is_locked=True, teacher_user=user)
    assert lock_res["is_locked"] is True
    q.refresh_from_db()
    assert q.is_locked is True


@pytest.mark.django_db
def test_api_lock_question_endpoint():
    user = User.objects.create_user(username="teacher_api_lock", password="Password123!")
    quiz = Quiz.objects.create(title="Ona Tili", owner=user)
    q = Question.objects.create(
        quiz=quiz,
        order_index=0,
        prompt="Ot so'z turkumi nima?",
        options=[{"id": "A", "text": "Shaxs va narsa nomi"}],
        correct_answer="A",
        is_locked=False,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    url = "/api/v1/ai-workspace/lock-question/"
    resp = client.post(url, {"question_id": str(q.id), "is_locked": True}, format="json")

    assert resp.status_code == 200
    assert resp.json()["is_locked"] is True

    q.refresh_from_db()
    assert q.is_locked is True


@pytest.mark.django_db
def test_api_apply_proposal_endpoint():
    user = User.objects.create_user(username="teacher_api_apply", password="Password123!")
    quiz = Quiz.objects.create(title="Geometriya", owner=user)
    q = Question.objects.create(
        quiz=quiz,
        order_index=0,
        type="single_choice",
        prompt="Uchburchak ichki burchaklari yig'indisi?",
        options=[{"id": "A", "text": "180"}, {"id": "B", "text": "360"}],
        correct_answer="A",
        points=1000,
        time_limit_seconds=30,
        is_locked=False,
    )

    client = APIClient()
    client.force_authenticate(user=user)

    proposal_payload = {
        "question_order": 1,
        "change_summary": "Yangi variant va ball oshirildi",
        "modified_fields": ["points", "options"],
        "new_question_data": {
            "order": 1,
            "prompt": "Uchburchak ichki burchaklari yig'indisi necha gradus?",
            "type": "single_choice",
            "options": [
                {"id": "A", "text": "180 gradus"},
                {"id": "B", "text": "360 gradus"},
                {"id": "C", "text": "90 gradus"}
            ],
            "correct_answer": "A",
            "explanation": "Evklid geometriyasida barcha uchburchaklarning ichki burchaklari yig'indisi 180 gradus.",
            "points": 1500,
            "time_limit_seconds": 30,
        }
    }

    url = "/api/v1/ai-workspace/apply-proposal/"
    resp = client.post(url, {"quiz_id": str(quiz.id), "question_order": 1, "proposal": proposal_payload}, format="json")

    assert resp.status_code == 200
    assert resp.json()["message"] == "Proposal applied successfully."

    q.refresh_from_db()
    assert q.points == 1500
    assert q.prompt == "Uchburchak ichki burchaklari yig'indisi necha gradus?"
    assert len(q.options) == 3
