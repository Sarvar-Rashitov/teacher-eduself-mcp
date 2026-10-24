import pytest
from django.contrib.auth import get_user_model
from quizzes.models import Quiz
from live_sessions.models import LiveSession
from live_sessions.fsm import SessionStateMachine, InvalidFSMTransitionError

User = get_user_model()


@pytest.fixture
def host_user(db):
    return User.objects.create_user(
        username="teacher_bob",
        email="bob@eduself.uz",
        password="SecurePass2026!",
        role="teacher"
    )


@pytest.fixture
def sample_quiz(db, host_user):
    return Quiz.objects.create(
        owner=host_user,
        title="Biologiya 7-sinf",
        subject="Biologiya",
        status="published"
    )


@pytest.fixture
def live_session(db, host_user, sample_quiz):
    return LiveSession.objects.create(
        quiz=sample_quiz,
        host=host_user,
        room_code="123456",
        status="draft",
        fsm_state="lobby",
    )


@pytest.mark.django_db
class TestSessionStateMachine:
    def test_valid_lifecycle_transitions(self, live_session):
        # 1. draft -> lobby
        SessionStateMachine.start_lobby(live_session)
        assert live_session.status == "lobby"
        assert live_session.fsm_state == "lobby"

        # 2. lobby -> active (question_preview)
        SessionStateMachine.start_game(live_session)
        assert live_session.status == "active"
        assert live_session.fsm_state == "question_preview"
        assert live_session.started_at is not None

        # 3. question_preview -> question_open
        SessionStateMachine.open_question(live_session)
        assert live_session.status == "active"
        assert live_session.fsm_state == "question_open"

        # 4. question_open -> question_closed
        SessionStateMachine.close_question(live_session)
        assert live_session.status == "active"
        assert live_session.fsm_state == "question_closed"

        # 5. question_closed -> answer_reveal
        SessionStateMachine.reveal_answers(live_session)
        assert live_session.status == "active"
        assert live_session.fsm_state == "answer_reveal"

        # 6. answer_reveal -> round_leaderboard
        SessionStateMachine.show_leaderboard(live_session)
        assert live_session.status == "active"
        assert live_session.fsm_state == "round_leaderboard"

        # 7. pause and resume
        SessionStateMachine.pause(live_session)
        assert live_session.status == "paused"

        SessionStateMachine.resume(live_session)
        assert live_session.status == "active"

        # 8. active -> completed
        SessionStateMachine.end_game(live_session)
        assert live_session.status == "completed"
        assert live_session.ended_at is not None

    def test_invalid_status_transitions_raise_error(self, live_session):
        # Cannot jump from draft to completed
        with pytest.raises(InvalidFSMTransitionError, match="Cannot transition session status"):
            SessionStateMachine.transition(live_session, target_status="completed")

        # Cannot transition from completed to lobby
        live_session.status = "completed"
        live_session.save()
        with pytest.raises(InvalidFSMTransitionError, match="Cannot transition session status"):
            SessionStateMachine.start_lobby(live_session)

    def test_invalid_fsm_inner_transitions_raise_error(self, live_session):
        SessionStateMachine.start_lobby(live_session)
        SessionStateMachine.start_game(live_session)
        assert live_session.fsm_state == "question_preview"

        # Cannot jump from question_preview directly to answer_reveal
        with pytest.raises(InvalidFSMTransitionError, match="Cannot transition FSM inner state"):
            SessionStateMachine.transition(live_session, target_fsm_state="answer_reveal")

    def test_cancellation(self, live_session):
        SessionStateMachine.start_lobby(live_session)
        SessionStateMachine.cancel(live_session)
        assert live_session.status == "cancelled"
        assert live_session.ended_at is not None

        # Cannot reopen cancelled session
        with pytest.raises(InvalidFSMTransitionError):
            SessionStateMachine.start_game(live_session)
