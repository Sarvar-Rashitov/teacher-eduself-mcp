from django.test import TestCase
from apps.authentication.models import User
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession
from apps.live_sessions.fsm import SessionStateMachine, SessionState, InvalidStateTransitionError
from apps.live_sessions.services import RoomCodeGenerator, LiveSessionService


class SessionFSMTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            username="host_teacher",
            email="host@example.com",
            password="HostPassword123!",
            role="teacher",
        )
        self.quiz = Quiz.objects.create(
            owner=self.host,
            title="Matematika Testi",
            subject="Matematika",
            grade_level=6,
        )
        self.session = LiveSession.objects.create(
            quiz=self.quiz,
            host=self.host,
            room_code=RoomCodeGenerator.generate_unique_pin(),
            status=SessionState.DRAFT,
        )

    def test_room_code_format(self):
        """PIN kod 6 ta raqamdan iborat bo'lishi kerak."""
        pin = RoomCodeGenerator.generate_unique_pin()
        self.assertEqual(len(pin), 6)
        self.assertTrue(pin.isalnum())

    def test_valid_fsm_lifecycle(self):
        """To'liq muvaffaqiyatli sikl: draft -> lobby -> active -> paused -> active -> completed."""
        self.assertEqual(self.session.status, SessionState.DRAFT)

        # 1. Lobby ga o'tish
        SessionStateMachine.open_lobby(self.session)
        self.assertEqual(self.session.status, SessionState.LOBBY)

        # 2. O'yinni boshlash (Active)
        SessionStateMachine.start_game(self.session)
        self.assertEqual(self.session.status, SessionState.ACTIVE)
        self.assertIsNotNone(self.session.started_at)

        # 3. Pauza qilish
        SessionStateMachine.pause_game(self.session)
        self.assertEqual(self.session.status, SessionState.PAUSED)

        # 4. Davom ettirish
        SessionStateMachine.resume_game(self.session)
        self.assertEqual(self.session.status, SessionState.ACTIVE)

        # 5. Tugallash
        SessionStateMachine.complete_game(self.session)
        self.assertEqual(self.session.status, SessionState.COMPLETED)
        self.assertIsNotNone(self.session.ended_at)

    def test_invalid_fsm_transition_raises_error(self):
        """Ruxsat etilmagan holat o'tishlari (masalan, draft -> active) xatolik berishi shart."""
        self.assertEqual(self.session.status, SessionState.DRAFT)

        with self.assertRaises(InvalidStateTransitionError):
            SessionStateMachine.start_game(self.session)

        # Lobby ga o'tgach, to'g'ridan-to'g'ri completed ga o'tish taqiqlangan
        SessionStateMachine.open_lobby(self.session)
        with self.assertRaises(InvalidStateTransitionError):
            SessionStateMachine.complete_game(self.session)

    def test_lobby_locking(self):
        """Xonani qulflash va qulfdan chiqarish."""
        self.assertFalse(self.session.is_locked)
        SessionStateMachine.set_lock(self.session, True)
        self.assertTrue(self.session.is_locked)
        SessionStateMachine.set_lock(self.session, False)
        self.assertFalse(self.session.is_locked)
