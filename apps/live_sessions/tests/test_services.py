import time
import pytest
from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.live_sessions.services import (
    RoomCodeGenerator,
    ReconnectionManager,
    LiveSessionService,
    SessionJoinError,
    SessionLockedError,
    DeadlineExpiredError
)


@pytest.fixture
def teacher_user(db):
    return User.objects.create_user(
        username="services_teacher",
        password="password123",
        role="teacher"
    )



@pytest.fixture
def sample_quiz(db, teacher_user):
    quiz = Quiz.objects.create(
        title="O'zbekiston Geografiyasi",
        subject="Geografiya",
        grade_level=8,
        owner=teacher_user
    )

    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="O'zbekiston poytaxti qaysi shahar?",
        options=[
            {"id": "opt_A", "text": "Samarqand"},
            {"id": "opt_B", "text": "Toshkent"},
            {"id": "opt_C", "text": "Buxoro"},
            {"id": "opt_D", "text": "Xiva"},
        ],
        correct_answer={"correct_option_id": "opt_B"},
        points=1000,
        time_limit_seconds=30,
        order_index=0
    )
    return quiz


@pytest.mark.django_db
def test_room_code_generator_format_and_uniqueness():
    code = RoomCodeGenerator.generate()
    assert len(code) == 6
    assert code.isdigit()
    assert 100000 <= int(code) <= 999999


@pytest.mark.django_db
def test_reconnection_manager_ticket_cycle():
    ticket = ReconnectionManager.generate_ticket(
        session_id="ses_123",
        participant_id="part_456",
        role="student"
    )
    payload = ReconnectionManager.validate_ticket(ticket)
    assert payload['session_id'] == "ses_123"
    assert payload['participant_id'] == "part_456"
    assert payload['role'] == "student"

    # Reject forged or corrupted ticket
    with pytest.raises(ValueError):
        ReconnectionManager.validate_ticket("forged.invalid.jwt")


@pytest.mark.django_db
def test_live_session_service_create_and_join(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    assert session.status == LiveSession.STATUS_LOBBY
    assert len(session.room_code) == 6

    # Student joins
    participant, joined_session, ticket = LiveSessionService.join_session(
        room_code=session.room_code,
        nickname="Alisher",
        team_name="Lochinlar"
    )
    assert participant.nickname == "Alisher"
    assert participant.team_name == "Lochinlar"
    assert participant.anonymous_token is not None
    assert joined_session.id == session.id

    # Duplicate nickname rejection
    with pytest.raises(SessionJoinError):
        LiveSessionService.join_session(
            room_code=session.room_code,
            nickname="alisher"  # case-insensitive check
        )


@pytest.mark.django_db
def test_join_session_locked_lobby(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    session.is_lobby_locked = True
    session.save()

    with pytest.raises(SessionLockedError):
        LiveSessionService.join_session(
            room_code=session.room_code,
            nickname="Zuhra"
        )


@pytest.mark.django_db
def test_reconnect_with_anonymous_token(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    p1, _, _ = LiveSessionService.join_session(room_code=session.room_code, nickname="Bobur")

    # Reconnect using anonymous_token
    p_reconnected, _, ticket = LiveSessionService.join_session(
        room_code=session.room_code,
        nickname="Bobur",
        anonymous_token=p1.anonymous_token
    )
    assert p_reconnected.id == p1.id
    assert p_reconnected.is_connected is True


@pytest.mark.django_db
def test_submit_answer_evaluation_and_idempotency(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    question = sample_quiz.questions.first()
    participant, _, _ = LiveSessionService.join_session(room_code=session.room_code, nickname="Kamola")

    # Set active deadline
    session.settings_payload['current_deadline_ts'] = time.time() + 30
    session.save()

    submission_id = "client_uuid_sub_123"
    response_data = {"selected_option_id": "opt_B"}  # Correct option!

    # 1. First submission: correct answer
    sub1, is_new1 = LiveSessionService.submit_answer(
        session=session,
        participant=participant,
        question_id=str(question.id),
        submission_id=submission_id,
        response_data=response_data,
        client_submit_ts=int(time.time() * 1000)
    )
    assert is_new1 is True
    assert sub1.is_correct is True
    assert sub1.score_awarded == 1000

    participant.refresh_from_db()
    assert participant.score == 1000
    assert participant.streak == 1

    # 2. Idempotent re-submission (same submission_id)
    sub2, is_new2 = LiveSessionService.submit_answer(
        session=session,
        participant=participant,
        question_id=str(question.id),
        submission_id=submission_id,
        response_data=response_data,
        client_submit_ts=int(time.time() * 1000)
    )
    assert is_new2 is False
    assert sub2.id == sub1.id

    # Score should NOT have doubled!
    participant.refresh_from_db()
    assert participant.score == 1000


@pytest.mark.django_db
def test_submit_answer_deadline_expired(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    question = sample_quiz.questions.first()
    participant, _, _ = LiveSessionService.join_session(room_code=session.room_code, nickname="Diyor")

    # Expired deadline (5 seconds ago)
    session.settings_payload['current_deadline_ts'] = time.time() - 5.0
    session.save()

    with pytest.raises(DeadlineExpiredError):
        LiveSessionService.submit_answer(
            session=session,
            participant=participant,
            question_id=str(question.id),
            submission_id="sub_late_999",
            response_data={"selected_option_id": "opt_B"}
        )


@pytest.mark.django_db
def test_zero_knowledge_state_snapshot(sample_quiz, teacher_user):
    session = LiveSessionService.create_session(quiz=sample_quiz, host=teacher_user)
    participant, _, _ = LiveSessionService.join_session(room_code=session.room_code, nickname="Eldor")

    # Student snapshot: MUST NOT contain correct_answer or explanation
    student_snapshot = LiveSessionService.get_state_snapshot(session, participant=participant, is_host=False)
    q_data = student_snapshot['current_question']
    assert 'correct_answer' not in q_data
    assert 'explanation' not in q_data
    assert student_snapshot['my_state']['nickname'] == "Eldor"

    # Host snapshot: DOES contain correct_answer
    host_snapshot = LiveSessionService.get_state_snapshot(session, participant=None, is_host=True)
    host_q_data = host_snapshot['current_question']
    assert 'correct_answer' in host_q_data
