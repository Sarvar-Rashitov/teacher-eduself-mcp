import time
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from core.asgi import application
from apps.authentication.models import User
from apps.quizzes.models import Quiz
from apps.quizzes.services import QuizService
from apps.live_sessions.models import LiveSession, Participant
from apps.live_sessions.services import RoomCodeGenerator, SessionService
# Savol turlarini yuklash
import apps.questions_registry.types  # noqa: F401


@pytest.fixture
def active_session_with_question(db):
    teacher = User.objects.create_user(username='ws_teacher', role='teacher')
    quiz = QuizService.create_quiz(
        owner=teacher,
        title='WebSocket Test Quiz',
        subject='Astronomiya'
    )
    q = QuizService.add_question(
        quiz=quiz,
        type_id='single_choice',
        prompt='Quyosh qaysi turdagi yulduz?',
        options=[
            {'id': 'A', 'text': 'Sariq mittivoy'},
            {'id': 'B', 'text': 'Qizil gigant'}
        ],
        correct_answer={'selected_option_id': 'A'},
        points=1000,
        time_limit_seconds=30
    )
    session = SessionService.create_session(quiz=quiz, host=teacher)
    return session, q, teacher


@pytest.mark.django_db
class TestRoomCodeAndServices:
    def test_room_code_generator(self):
        """6 xonali unikal PIN kod yaratilishi."""
        code = RoomCodeGenerator.generate_unique_code()
        assert len(code) == 6
        assert code.isdigit()

    def test_session_join_service(self, active_session_with_question):
        session, _, _ = active_session_with_question
        participant, joined_session, token = SessionService.join_session(
            room_code=session.room_code,
            nickname='Akmal'
        )
        assert participant.nickname == 'Akmal'
        assert participant.session == session
        assert len(token) == 64
        assert joined_session.participants.count() == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestClassroomGameConsumer:
    async def test_websocket_student_connection_and_flow(self, active_session_with_question):
        session, question, _ = active_session_with_question

        # 1. Talaba avval join qiladi (sync_to_async orqali)
        join_fn = database_sync_to_async(SessionService.join_session)
        participant, _, token = await join_fn(
            room_code=session.room_code,
            nickname='Shohruh'
        )

        # 2. WebSocket ulanish
        ws_url = f"/ws/session/{session.room_code}/?token={token}"
        communicator = WebsocketCommunicator(application, ws_url)
        connected, _ = await communicator.connect()
        assert connected, "WebSocket ulanishi muvaffaqiyatli bo'lishi kerak"

        # 3. Welcome xabari qabul qilish
        welcome_msg = await communicator.receive_json_from()
        assert welcome_msg['type'] == 'session.welcome'
        assert welcome_msg['payload']['room_code'] == session.room_code

        # 3.1. Guruhga tarqatilgan participant.joined xabarini qabul qilish
        joined_msg = await communicator.receive_json_from()
        assert joined_msg['type'] == 'participant.joined'

        # 4. Ping-Pong tekshiruvi
        await communicator.send_json_to({
            'type': 'ping',
            'client_ts': 1728900000000
        })
        pong_msg = await communicator.receive_json_from()
        assert pong_msg['type'] == 'pong'
        assert pong_msg['client_ts'] == 1728900000000

        # 5. Savolga javob yuborish (answer.submit)
        await communicator.send_json_to({
            'type': 'answer.submit',
            'question_id': str(question.id),
            'payload': {'selected_option_id': 'A'},
            'client_ts': int(time.time() * 1000)
        })
        ack_msg = await communicator.receive_json_from()
        assert ack_msg['type'] == 'answer.ack'
        assert ack_msg['status'] == 'accepted'
        assert ack_msg['is_correct'] is True
        assert ack_msg['points_awarded'] == 1000

        # 6. Uzilish
        await communicator.disconnect()
