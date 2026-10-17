import pytest
from apps.authentication.models import User
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.live_sessions.fsm import SessionFSM, SessionStateError


@pytest.fixture
def test_session(db):
    teacher = User.objects.create_user(username='fsm_teacher', role='teacher')
    quiz = Quiz.objects.create(owner=teacher, title='Test Quiz', subject='Fizika')
    return LiveSession.objects.create(
        quiz=quiz,
        host=teacher,
        room_code='123456',
        status='draft'
    )


@pytest.mark.django_db
class TestSessionFSM:
    def test_valid_lifecycle_transitions(self, test_session):
        """To'liq muvaffaqiyatli dars hayot sikli o'tishlari."""
        # 1. draft -> lobby
        SessionFSM.transition(test_session, 'lobby')
        assert test_session.status == 'lobby'

        # 2. lobby -> in_progress
        SessionFSM.transition(test_session, 'in_progress')
        assert test_session.status == 'in_progress'
        assert test_session.started_at is not None

        # 3. in_progress -> paused
        SessionFSM.transition(test_session, 'paused')
        assert test_session.status == 'paused'

        # 4. paused -> in_progress
        SessionFSM.transition(test_session, 'in_progress')
        assert test_session.status == 'in_progress'

        # 5. in_progress -> completed
        SessionFSM.transition(test_session, 'completed')
        assert test_session.status == 'completed'
        assert test_session.ended_at is not None

    def test_cancellation_from_lobby(self, test_session):
        """Lobbida bekor qilish."""
        SessionFSM.transition(test_session, 'lobby')
        SessionFSM.transition(test_session, 'cancelled')
        assert test_session.status == 'cancelled'
        assert test_session.ended_at is not None

    def test_illegal_transition_raises_error(self, test_session):
        """Noqonuniy o'tishlar SessionStateError chiqarishi."""
        # draft dan to'g'ridan-to'g'ri completed ga o'tib bo'lmaydi
        with pytest.raises(SessionStateError):
            SessionFSM.transition(test_session, 'completed')

        # completed dan qayta in_progress ga o'tib bo'lmaydi
        test_session.status = 'completed'
        test_session.save()
        with pytest.raises(SessionStateError):
            SessionFSM.transition(test_session, 'in_progress')
