import pytest
from django.contrib.auth import get_user_model

from apps.mcp_server.auth import MCPContext, mcp_context_scope
from apps.mcp_server.scopes import TEACHER_DEFAULT_SCOPES
from apps.mcp_server.tools.session_tools import (
    create_live_session,
    get_session_status,
    start_session,
    advance_question,
    reveal_answers,
    end_session,
    get_live_results,
)
from apps.mcp_server.exceptions import MCPInvalidSessionStateError
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission


User = get_user_model()


@pytest.fixture
def session_teacher_context(db):
    user = User.objects.create_user(
        username="mcp_teacher_session",
        email="teacher_session@eduself.uz",
        role="TEACHER",
    )
    return MCPContext(user=user, scopes=TEACHER_DEFAULT_SCOPES.copy())


@pytest.fixture
def sample_quiz(session_teacher_context):
    quiz = Quiz.objects.create(
        title="Jonli O'yin Quizi",
        owner=session_teacher_context.user,
        status="PUBLISHED",
    )
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="1-savol: 2 + 2 = ?",
        options=[
            {"id": "opt_1", "text": "4", "is_correct": True},
            {"id": "opt_2", "text": "5", "is_correct": False},
        ],
        correct_answer="opt_1",
        order_index=0,
        time_limit_seconds=20,
    )
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="2-savol: 5 * 5 = ?",
        options=[
            {"id": "opt_1", "text": "25", "is_correct": True},
            {"id": "opt_2", "text": "20", "is_correct": False},
        ],
        correct_answer="opt_1",
        order_index=1,
        time_limit_seconds=20,
    )
    return quiz


@pytest.mark.django_db
def test_create_live_session(session_teacher_context, sample_quiz):
    with mcp_context_scope(session_teacher_context):
        res = create_live_session(quiz_id=str(sample_quiz.id), game_mode="classic")

        assert len(res["pin"]) == 6
        assert res["status"] == LiveSession.STATUS_LOBBY
        assert res["game_mode"] == "classic"
        assert f"https://join.eduself.uz/{res['pin']}" == res["join_url"]


@pytest.mark.django_db
def test_get_session_status(session_teacher_context, sample_quiz):
    with mcp_context_scope(session_teacher_context):
        res = create_live_session(quiz_id=str(sample_quiz.id))
        session_id = res["session_id"]

        status = get_session_status(session_id)
        assert status["status"] == LiveSession.STATUS_LOBBY
        assert status["total_questions"] == 2
        assert status["connected_students"] == 0


@pytest.mark.django_db
def test_start_session_lifecycle(session_teacher_context, sample_quiz):
    with mcp_context_scope(session_teacher_context):
        created = create_live_session(quiz_id=str(sample_quiz.id))
        session_id = created["session_id"]

        # 1. Start session
        start_res = start_session(session_id=session_id)
        assert start_res["status"] == LiveSession.STATUS_ACTIVE
        assert start_res["current_question_index"] == 0

        # 2. Reveal answers
        reveal_res = reveal_answers(session_id=session_id)
        assert reveal_res["status"] == LiveSession.STATUS_ACTIVE

        # 3. Advance to next question
        adv_res = advance_question(session_id=session_id)
        assert adv_res["current_question_index"] == 1

        # 4. End session
        end_res = end_session(session_id=session_id)
        assert end_res["status"] == LiveSession.STATUS_COMPLETED


@pytest.mark.django_db
def test_start_session_when_not_in_lobby_fails(session_teacher_context, sample_quiz):
    with mcp_context_scope(session_teacher_context):
        created = create_live_session(quiz_id=str(sample_quiz.id))
        session_id = created["session_id"]

        start_session(session_id=session_id)

        # Qayta start qilishga urinish xatolik beradi
        with pytest.raises(MCPInvalidSessionStateError):
            start_session(session_id=session_id)


@pytest.mark.django_db
def test_get_live_results(session_teacher_context, sample_quiz):
    with mcp_context_scope(session_teacher_context):
        created = create_live_session(quiz_id=str(sample_quiz.id))
        session_id = created["session_id"]
        session = LiveSession.objects.get(id=session_id)

        # O'quvchi va javob yaratamiz
        p1 = Participant.objects.create(session=session, nickname="Ali", is_connected=True)
        p2 = Participant.objects.create(session=session, nickname="Vali", is_connected=True)

        q1 = sample_quiz.questions.first()
        AnswerSubmission.objects.create(
            session=session,
            participant=p1,
            question=q1,
            submission_id="sub_test_1",
            response_data={"selected": "opt_1"},
            is_correct=True,
            score_awarded=1000,
        )
        AnswerSubmission.objects.create(
            session=session,
            participant=p2,
            question=q1,
            submission_id="sub_test_2",
            response_data={"selected": "opt_2"},
            is_correct=False,
            score_awarded=0,
        )

        results = get_live_results(session_id=session_id)
        assert results["total_submissions"] == 2
        assert results["correct_count"] == 1
        assert results["accuracy_percentage"] == 50.0
        assert results["options_distribution"]["opt_1"] == 1
        assert results["options_distribution"]["opt_2"] == 1
