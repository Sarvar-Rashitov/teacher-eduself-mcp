import pytest
from django.utils import timezone
from apps.authentication.models import User
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.live_sessions.fsm import SessionStateMachine, InvalidStateTransitionError, SessionLockedError


@pytest.fixture
def test_teacher(db):
    return User.objects.create_user(
        username="fsm_teacher",
        password="password123",
        role="teacher"
    )



@pytest.fixture
def test_quiz(db, test_teacher):
    return Quiz.objects.create(
        title="FSM Test Quiz",
        subject="Matematika",
        grade_level=7,
        owner=test_teacher
    )



@pytest.fixture
def live_session(db, test_quiz, test_teacher):
    return LiveSession.objects.create(
        quiz=test_quiz,
        host=test_teacher,
        room_code="123456",
        status=LiveSession.STATUS_DRAFT
    )


@pytest.mark.django_db
def test_fsm_initial_state_to_lobby(live_session):
    fsm = SessionStateMachine(live_session)
    assert fsm.current_state == LiveSession.STATUS_DRAFT
    assert not fsm.can_participant_join()

    fsm.to_lobby()
    assert live_session.status == LiveSession.STATUS_LOBBY
    assert fsm.can_participant_join()


@pytest.mark.django_db
def test_fsm_lock_and_unlock_lobby(live_session):
    fsm = SessionStateMachine(live_session)
    fsm.to_lobby()
    assert fsm.can_participant_join()

    fsm.lock_lobby()
    assert live_session.is_lobby_locked is True
    assert not fsm.can_participant_join()

    fsm.unlock_lobby()
    assert live_session.is_lobby_locked is False
    assert fsm.can_participant_join()


@pytest.mark.django_db
def test_fsm_start_session_lifecycle(live_session):
    fsm = SessionStateMachine(live_session)
    fsm.to_lobby()
    fsm.start_session()

    assert live_session.status == LiveSession.STATUS_ACTIVE
    assert live_session.started_at is not None
    assert fsm.current_phase == SessionStateMachine.PHASE_IDLE


@pytest.mark.django_db
def test_fsm_question_phases(live_session):
    fsm = SessionStateMachine(live_session)
    fsm.to_lobby()
    fsm.start_session()

    # Open question
    deadline = fsm.open_question(question_index=0, time_limit_seconds=30)
    assert fsm.current_phase == SessionStateMachine.PHASE_QUESTION_OPEN
    assert deadline > timezone.now().timestamp()
    assert live_session.current_question_index == 0

    # Close question
    fsm.close_question()
    assert fsm.current_phase == SessionStateMachine.PHASE_QUESTION_CLOSED

    # Reveal answer
    fsm.reveal_answer()
    assert fsm.current_phase == SessionStateMachine.PHASE_ANSWER_REVEAL

    # Show leaderboard
    fsm.show_leaderboard()
    assert fsm.current_phase == SessionStateMachine.PHASE_LEADERBOARD


@pytest.mark.django_db
def test_fsm_invalid_transition_raises_error(live_session):
    fsm = SessionStateMachine(live_session)
    # Cannot open question directly from draft state
    with pytest.raises(InvalidStateTransitionError):
        fsm.open_question(question_index=0)

    fsm.to_lobby()
    # Cannot reveal answer before opening question
    with pytest.raises(InvalidStateTransitionError):
        fsm.reveal_answer()


@pytest.mark.django_db
def test_fsm_pause_and_resume(live_session):
    fsm = SessionStateMachine(live_session)
    fsm.to_lobby()
    fsm.start_session()
    fsm.open_question(question_index=0, time_limit_seconds=20)

    # Pause
    fsm.pause()
    assert live_session.status == LiveSession.STATUS_PAUSED
    assert live_session.settings_payload['paused_from_phase'] == SessionStateMachine.PHASE_QUESTION_OPEN

    # Resume
    fsm.resume()
    assert live_session.status == LiveSession.STATUS_ACTIVE
    assert fsm.current_phase == SessionStateMachine.PHASE_QUESTION_OPEN


@pytest.mark.django_db
def test_fsm_complete_and_cancel(live_session):
    fsm = SessionStateMachine(live_session)
    fsm.to_lobby()
    fsm.start_session()
    fsm.complete()

    assert live_session.status == LiveSession.STATUS_COMPLETED
    assert live_session.ended_at is not None

    # Cannot transition once completed
    with pytest.raises(InvalidStateTransitionError):
        fsm.start_session()
