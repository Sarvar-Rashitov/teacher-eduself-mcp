# ============================================================
# EduSelf Teacher — apps/mcp_server/tests/test_mcp_tools.py
# Unit & Integration Tests for 17 Core MCP Tools & Zero-Bypass
# ============================================================
import json
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.mcp_server.auth import MCPContext, set_current_mcp_context, reset_current_mcp_context
from apps.mcp_server.exceptions import (
    MCPForbiddenError,
    MCPResourceNotFoundError,
    MCPConfirmationRequiredError,
    MCPInvalidSessionStateError,
)
import apps.mcp_server.tools as mcp_tools

User = get_user_model()


@pytest.fixture
def teacher1(db):
    return User.objects.create_user(
        username="mcp_teacher_1",
        password="password123",
        role="teacher"
    )


@pytest.fixture
def teacher2(db):
    return User.objects.create_user(
        username="mcp_teacher_2",
        password="password123",
        role="teacher"
    )


@pytest.fixture
def teacher_ctx(teacher1):
    ctx = MCPContext(
        user=teacher1,
        scopes=["quiz:read", "quiz:write", "session:create", "session:control", "session:read", "report:read"]
    )
    token = set_current_mcp_context(ctx)
    yield ctx
    reset_current_mcp_context(token)


@pytest.fixture
def other_quiz(db, teacher2):
    return Quiz.objects.create(
        owner=teacher2,
        title="Begona O'qituvchi Testi",
        subject="Fizika",
        grade_level=9
    )


@pytest.fixture
def other_session(db, teacher2, other_quiz):
    return LiveSession.objects.create(
        host=teacher2,
        quiz=other_quiz,
        room_code="112233",
        status="lobby"
    )


# ============================================================
# 1. Tests for Category 1: Quiz & Content Management
# ============================================================
@pytest.mark.django_db(transaction=True)
class TestQuizMCPTools:
    @pytest.mark.asyncio
    async def test_create_quiz_draft(self, teacher_ctx):
        res = await mcp_tools.create_quiz_draft(
            title="Biologiya 8-sinf Genetika",
            subject="Biologiya",
            grade_level=8,
            topic="Genetika qonunlari",
            question_count=5,
            language="uz"
        )
        assert res["status"] == "draft"
        assert res["title"] == "Biologiya 8-sinf Genetika"
        assert "quiz_id" in res

    @pytest.mark.asyncio
    async def test_get_quiz_success(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Matematika Algebra",
            subject="Matematika",
            grade_level=7
        )
        quiz_id = quiz["quiz_id"]

        detail = await mcp_tools.get_quiz(quiz_id=quiz_id)
        assert detail["quiz_id"] == quiz_id
        assert detail["title"] == "Matematika Algebra"
        assert detail["grade_level"] == 7

    @pytest.mark.asyncio
    async def test_zero_bypass_quiz_ownership_isolation(self, teacher_ctx, other_quiz):
        with pytest.raises(MCPForbiddenError) as exc_info:
            await mcp_tools.get_quiz(quiz_id=str(other_quiz.id))
        assert exc_info.value.code == -32003

    @pytest.mark.asyncio
    async def test_get_nonexistent_quiz_raises_not_found(self, teacher_ctx):
        with pytest.raises(MCPResourceNotFoundError) as exc_info:
            await mcp_tools.get_quiz(quiz_id="00000000-0000-0000-0000-000000000000")
        assert exc_info.value.code == -32004

    @pytest.mark.asyncio
    async def test_update_quiz(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Dastlabki Sarlavha",
            subject="Informatika",
            grade_level=10
        )
        res = await mcp_tools.update_quiz(
            quiz_id=quiz["quiz_id"],
            changes={"title": "Yangi Tahrirlangan Sarlavha", "grade_level": 11}
        )
        assert res["status"] == "success"
        assert res["updated_version"] == 2

        detail = await mcp_tools.get_quiz(quiz["quiz_id"])
        assert detail["title"] == "Yangi Tahrirlangan Sarlavha"
        assert detail["grade_level"] == 11

    @pytest.mark.asyncio
    async def test_import_questions_json(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Import Sinovi",
            subject="Kimyo",
            grade_level=9
        )
        questions_payload = json.dumps([
            {
                "question_type": "single_choice",
                "time_limit_seconds": 25,
                "points": 1000,
                "content": {
                    "prompt": "Suvning formulasi nima?",
                    "options": [
                        {"id": "a", "text": "H2O"},
                        {"id": "b", "text": "CO2"},
                        {"id": "c", "text": "NaCl"},
                        {"id": "d", "text": "O2"}
                    ],
                    "correct_answer": "a"
                }
            }
        ])
        res = await mcp_tools.import_questions(
            quiz_id=quiz["quiz_id"],
            source_format="json",
            content=questions_payload
        )
        assert res["status"] == "success"
        assert res["imported_count"] == 1

        val = await mcp_tools.validate_quiz(quiz_id=quiz["quiz_id"])
        assert val["is_valid"] is True
        assert val["error_count"] == 0

    @pytest.mark.asyncio
    async def test_list_question_sets(self, teacher_ctx):
        res = await mcp_tools.list_question_sets(query="", page=1, page_size=10)
        assert "quizzes" in res
        assert "total" in res


# ============================================================
# 2. Tests for Category 2: Live Session Control
# ============================================================
@pytest.mark.django_db(transaction=True)
class TestLiveSessionMCPTools:
    @pytest.mark.asyncio
    async def test_create_and_manage_live_session(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Jonli O'yin Testi",
            subject="Tarix",
            grade_level=6
        )

        await sync_to_async(Question.objects.create)(
            quiz_id=quiz["quiz_id"],
            type="single_choice",
            prompt="1-savol matni",
            options=[{"id": "a", "text": "Variant A"}],
            correct_answer="a",
            order_index=0
        )
        await sync_to_async(Question.objects.create)(
            quiz_id=quiz["quiz_id"],
            type="single_choice",
            prompt="2-savol matni",
            options=[{"id": "b", "text": "Variant B"}],
            correct_answer="b",
            order_index=1
        )

        # 1. create_live_session
        sess = await mcp_tools.create_live_session(
            quiz_id=quiz["quiz_id"],
            game_mode="classic",
            team_mode_enabled=False
        )
        session_id = sess["session_id"]
        assert sess["status"] == "lobby"
        assert len(sess["pin"]) == 6

        # 2. get_session_status
        status_info = await mcp_tools.get_session_status(session_id=session_id)
        assert status_info["status"] == "lobby"
        assert status_info["connected_students"] == 0

        # 3. start_session tasdiqsiz (confirm=False) xatolik berishi kerak
        with pytest.raises(MCPConfirmationRequiredError):
            await mcp_tools.start_session(session_id=session_id, confirm=False)

        # 4. start_session muvaffaqiyatli
        start_res = await mcp_tools.start_session(session_id=session_id, confirm=True)
        assert start_res["status"] == "in_progress"

        # 5. advance_question
        adv_res = await mcp_tools.advance_question(session_id=session_id)
        assert "status" in adv_res

        # 6. reveal_answers
        rev_res = await mcp_tools.reveal_answers(session_id=session_id, confirm=True)
        assert rev_res["revealed"] is True

        # 7. end_session
        end_res = await mcp_tools.end_session(session_id=session_id, confirm=True)
        assert end_res["status"] == "completed"
        assert end_res["is_finished"] is True

    @pytest.mark.asyncio
    async def test_zero_bypass_session_host_isolation(self, teacher_ctx, other_session):
        with pytest.raises(MCPForbiddenError):
            await mcp_tools.start_session(session_id=str(other_session.id), confirm=True)


# ============================================================
# 3. Tests for Category 3: Analytics, Games & Followup
# ============================================================
@pytest.mark.django_db(transaction=True)
class TestAnalyticsAndGameTools:
    @pytest.mark.asyncio
    async def test_create_team_game(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Jamoaviy O'yin Testi",
            subject="Geografiya",
            grade_level=7
        )
        sess = await mcp_tools.create_live_session(quiz_id=quiz["quiz_id"])
        session_id = sess["session_id"]

        team_res = await mcp_tools.create_team_game(
            session_id=session_id,
            team_count=3,
            allocation_strategy="random"
        )
        assert team_res["team_count"] == 3
        assert team_res["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_create_anonymous_board(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Doska Testi",
            subject="Adabiyot",
            grade_level=8
        )
        sess = await mcp_tools.create_live_session(quiz_id=quiz["quiz_id"])
        session_id = sess["session_id"]

        board_res = await mcp_tools.create_anonymous_board(
            session_id=session_id,
            board_title="She'riyat bo'yicha fikrlar"
        )
        assert board_res["status"] == "active"
        assert board_res["board_title"] == "She'riyat bo'yicha fikrlar"

    @pytest.mark.asyncio
    async def test_get_session_report_and_followup(self, teacher_ctx):
        quiz = await mcp_tools.create_quiz_draft(
            title="Hisobot Testi",
            subject="Ingliz tili",
            grade_level=9
        )
        sess = await mcp_tools.create_live_session(quiz_id=quiz["quiz_id"])
        session_id = sess["session_id"]

        report = await mcp_tools.get_session_report(session_id=session_id)
        assert "overall_accuracy" in report
        assert "most_difficult_questions" in report

        followup = await mcp_tools.generate_followup_activity(session_id=session_id)
        assert "followup_quiz_id" in followup
        assert followup["based_on_session"] == session_id

        export = await mcp_tools.export_results(session_id=session_id, export_format="json")
        assert export["format"] == "json"
        assert "data" in export
