import pytest
from django.contrib.auth import get_user_model

from apps.mcp_server.auth import MCPContext, mcp_context_scope
from apps.mcp_server.scopes import TEACHER_DEFAULT_SCOPES
from apps.mcp_server.tools.analytics_tools import (
    create_team_game,
    create_anonymous_board,
    get_session_report,
    generate_followup_activity,
)
from apps.mcp_server.tools.session_tools import create_live_session
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission


User = get_user_model()


@pytest.fixture
def analytics_teacher_context(db):
    user = User.objects.create_user(
        username="mcp_teacher_analytics",
        email="teacher_analytics@eduself.uz",
        role="TEACHER",
    )
    return MCPContext(user=user, scopes=TEACHER_DEFAULT_SCOPES.copy())


@pytest.fixture
def analytics_quiz(analytics_teacher_context):
    quiz = Quiz.objects.create(
        title="Fizika Yakuniy Sinov",
        owner=analytics_teacher_context.user,
        status="PUBLISHED",
    )
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="Nyutonning 1-qonuni qanday nomlanadi?",
        options=[
            {"id": "opt_1", "text": "Inersiya qonuni", "is_correct": True},
            {"id": "opt_2", "text": "Gravitatsiya", "is_correct": False},
        ],
        correct_answer="opt_1",
        order_index=0,
    )
    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="Tezlanish birligi nima?",
        options=[
            {"id": "opt_1", "text": "m/s^2", "is_correct": True},
            {"id": "opt_2", "text": "km/h", "is_correct": False},
        ],
        correct_answer="opt_1",
        order_index=1,
    )
    return quiz


@pytest.mark.django_db
def test_create_team_game(analytics_teacher_context, analytics_quiz):
    with mcp_context_scope(analytics_teacher_context):
        s_res = create_live_session(quiz_id=str(analytics_quiz.id))
        session_id = s_res["session_id"]
        session = LiveSession.objects.get(id=session_id)

        # 4 ta ishtirokchi qo'shamiz
        for i in range(4):
            Participant.objects.create(session=session, nickname=f"Student_{i+1}", is_connected=True)

        team_res = create_team_game(session_id=session_id, team_count=2)
        assert team_res["team_count"] == 2
        assert team_res["total_assigned_students"] == 4
        assert len(team_res["teams"]) == 2

        # Har bir ishtirokchida team_name borligini tekshiramiz
        for p in session.participants.all():
            assert p.team_name is not None


@pytest.mark.django_db
def test_create_anonymous_board(analytics_teacher_context, analytics_quiz):
    with mcp_context_scope(analytics_teacher_context):
        s_res = create_live_session(quiz_id=str(analytics_quiz.id))
        session_id = s_res["session_id"]

        board_res = create_anonymous_board(session_id=session_id, board_title="Fikrlar va Takliflar")
        assert board_res["status"] == "active"
        assert board_res["board_title"] == "Fikrlar va Takliflar"

        session = LiveSession.objects.get(id=session_id)
        assert session.settings_payload["anonymous_board"]["title"] == "Fikrlar va Takliflar"


@pytest.mark.django_db
def test_get_session_report_and_followup_activity(analytics_teacher_context, analytics_quiz):
    with mcp_context_scope(analytics_teacher_context):
        s_res = create_live_session(quiz_id=str(analytics_quiz.id))
        session_id = s_res["session_id"]
        session = LiveSession.objects.get(id=session_id)

        p1 = Participant.objects.create(session=session, nickname="Lobar", score=1800, is_connected=True)
        p2 = Participant.objects.create(session=session, nickname="Jasur", score=900, is_connected=True)

        q1 = analytics_quiz.questions.all()[0]
        q2 = analytics_quiz.questions.all()[1]

        # Q1: 100% to'g'ri
        AnswerSubmission.objects.create(session=session, participant=p1, question=q1, submission_id="sub_a_1", response_data={"ans": "opt_1"}, is_correct=True, score_awarded=1000)
        AnswerSubmission.objects.create(session=session, participant=p2, question=q1, submission_id="sub_a_2", response_data={"ans": "opt_1"}, is_correct=True, score_awarded=900)

        # Q2: 0% to'g'ri (eng qiyin savol)
        AnswerSubmission.objects.create(session=session, participant=p1, question=q2, submission_id="sub_a_3", response_data={"ans": "opt_2"}, is_correct=False, score_awarded=0)
        AnswerSubmission.objects.create(session=session, participant=p2, question=q2, submission_id="sub_a_4", response_data={"ans": "opt_2"}, is_correct=False, score_awarded=0)

        report = get_session_report(session_id=session_id)
        assert report["total_participants"] == 2
        assert report["total_answers_submitted"] == 4
        assert report["class_accuracy_percentage"] == 50.0
        assert len(report["top_performers"]) == 2
        assert report["top_performers"][0]["nickname"] == "Lobar"

        # Follow-up avtomatik mustahkamlash viktorinasini yaratish
        followup = generate_followup_activity(session_id=session_id)
        assert followup["status"] == "DRAFT"
        assert followup["question_count"] >= 1

        new_quiz = Quiz.objects.get(id=followup["followup_quiz_id"])
        assert "Mustahkamlash" in new_quiz.title
