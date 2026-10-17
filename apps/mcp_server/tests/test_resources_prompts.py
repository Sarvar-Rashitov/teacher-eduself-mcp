# ============================================================
# EduSelf Teacher — apps/mcp_server/tests/test_resources_prompts.py
# Tests for MCP Resources & Prompt Templates
# ============================================================
import json
import pytest
from django.contrib.auth import get_user_model

from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.mcp_server.auth import MCPContext, set_current_mcp_context, reset_current_mcp_context
from apps.mcp_server.server import mcp_server
import apps.mcp_server.resources as resources
import apps.mcp_server.prompts as prompts

User = get_user_model()


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        username="mcp_resources_teacher",
        password="password123",
        role="teacher"
    )


@pytest.fixture
def teacher_ctx(teacher):
    ctx = MCPContext(
        user=teacher,
        scopes=["quiz:read", "quiz:write", "session:create", "session:control", "session:read", "report:read"]
    )
    token = set_current_mcp_context(ctx)
    yield ctx
    reset_current_mcp_context(token)


@pytest.fixture
def sample_session(db, teacher):
    quiz = Quiz.objects.create(
        owner=teacher,
        title="Resurs Sinovi Testi",
        subject="Biologiya",
        grade_level=8
    )
    return LiveSession.objects.create(
        host=teacher,
        quiz=quiz,
        room_code="778899",
        status="lobby"
    )


@pytest.mark.django_db(transaction=True)
class TestMCPResources:
    def test_question_types_resource(self):
        content = resources.get_question_types_resource()
        data = json.loads(content)
        assert data["total_types"] >= 7
        assert "question_types" in data

    def test_game_modes_resource(self):
        content = resources.get_game_modes_resource()
        data = json.loads(content)
        assert "game_modes" in data
        assert data["total_modes"] >= 4

    def test_teacher_guide_resource(self):
        content = resources.get_teacher_guide_resource()
        assert "EduSelf O'qituvchi Metodik Qo'llanmasi" in content
        assert "Mavzuni kiritish" in content

    @pytest.mark.asyncio
    async def test_session_summary_resource(self, teacher_ctx, sample_session):
        content = await resources.get_session_summary_resource(str(sample_session.id))
        data = json.loads(content)
        assert data["room_code"] == "778899"
        assert data["status"] == "lobby"


@pytest.mark.django_db
class TestMCPPrompts:
    def test_prompt_create_lesson_quiz(self):
        msg = prompts.prompt_create_lesson_quiz("Fizika", 9, "Nyuton qonunlari")
        assert "Fizika" in msg
        assert "9-sinf" in msg
        assert "Nyuton qonunlari" in msg
        assert "create_quiz_draft" in msg

    def test_prompt_analyze_session_report(self):
        msg = prompts.prompt_analyze_session_report("ses_12345")
        assert "ses_12345" in msg
        assert "get_session_report" in msg

    def test_prompt_plan_team_activity(self):
        msg = prompts.prompt_plan_team_activity(student_count=28, duration_minutes=35)
        assert "28" in msg
        assert "35" in msg
        assert "create_team_game" in msg
