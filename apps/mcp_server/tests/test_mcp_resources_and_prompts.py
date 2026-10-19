import json
import pytest
from django.contrib.auth import get_user_model

from apps.mcp_server.auth import MCPContext, mcp_context_scope
from apps.mcp_server.scopes import TEACHER_DEFAULT_SCOPES
from apps.mcp_server.resources import (
    read_question_types_resource,
    read_game_modes_resource,
    read_teacher_guide_resource,
    read_session_summary_resource,
)
from apps.mcp_server.prompts import (
    get_create_lesson_quiz_prompt,
    get_analyze_session_report_prompt,
    get_plan_team_activity_prompt,
)
from apps.mcp_server.tools.session_tools import create_live_session
from apps.quizzes.models import Quiz, Question


User = get_user_model()


@pytest.fixture
def resource_teacher_context(db):
    user = User.objects.create_user(
        username="mcp_teacher_res",
        email="teacher_res@eduself.uz",
        role="TEACHER",
    )
    return MCPContext(user=user, scopes=TEACHER_DEFAULT_SCOPES.copy())


def test_read_question_types_resource():
    res_str = read_question_types_resource()
    data = json.loads(res_str)
    assert data["resource"] == "eduself://question-types"
    assert data["total_types"] >= 7
    type_ids = [t["type_id"] for t in data["question_types"]]
    assert "single_choice" in type_ids
    assert "multiple_choice" in type_ids


def test_read_game_modes_resource():
    res_str = read_game_modes_resource()
    data = json.loads(res_str)
    assert data["resource"] == "eduself://game-modes"
    assert data["total_modes"] >= 4
    mode_ids = [m["mode_id"] for m in data["game_modes"]]
    assert "classic" in mode_ids
    assert "team_battle" in mode_ids


def test_read_teacher_guide_resource():
    guide = read_teacher_guide_resource()
    assert "# EduSelf O'qituvchi Metodik Qo'llanmasi" in guide
    assert "Classic Mode" in guide
    assert "Team Battle" in guide


@pytest.mark.django_db
def test_read_session_summary_resource(resource_teacher_context):
    with mcp_context_scope(resource_teacher_context):
        quiz = Quiz.objects.create(
            title="Resource Quiz",
            owner=resource_teacher_context.user,
            subject="Matematika",
            grade_level=7,
            status="published",
        )
        Question.objects.create(
            quiz=quiz,
            type="single_choice",
            prompt="Quyosh qayerdan chiqadi?",
            options=[{"id": "o1", "text": "Sharqdan", "is_correct": True}],
            correct_answer="o1",
            order_index=0,
        )
        s_res = create_live_session(quiz_id=str(quiz.id))
        session_id = s_res["session_id"]

        summary_json = read_session_summary_resource(session_id)
        data = json.loads(summary_json)
        assert data["session_id"] == session_id
        assert data["room_code"] == s_res["pin"]
        assert data["status"] == "lobby"


def test_prompt_generation():
    p1 = get_create_lesson_quiz_prompt(subject="Tarix", grade="9", topic="Amir Temur davri")
    assert "Tarix" in p1
    assert "9-sinf" in p1
    assert "Amir Temur" in p1

    p2 = get_analyze_session_report_prompt(session_id="ses_123456")
    assert "ses_123456" in p2
    assert "get_session_report" in p2

    p3 = get_plan_team_activity_prompt(student_count=24, duration_minutes=20)
    assert "24 nafar" in p3
    assert "20 daqiqa" in p3
