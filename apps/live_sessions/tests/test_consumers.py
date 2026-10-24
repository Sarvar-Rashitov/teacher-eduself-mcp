import time
import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model

from core.asgi import application
from quizzes.models import Quiz
from quizzes.services import QuizCRUD
from live_sessions.models import LiveSession
from live_sessions.services import LiveSessionService, ReconnectionManager

User = get_user_model()


@pytest.fixture
def host_user(db):
    return User.objects.create_user(
        username="teacher_shavkat",
        email="shavkat@eduself.uz",
        password="PassWord123!",
        role="teacher"
    )


@pytest.fixture
def sample_quiz_with_question(db, host_user):
    quiz = Quiz.objects.create(
        owner=host_user,
        title="Matematika 6-sinf",
        subject="Matematika",
        status="published"
    )
    QuizCRUD.add_question(quiz, {
        "type": "single_choice",
        "prompt": "2 + 2 * 2 = ?",
        "options": [
            {"id": "A", "text": "6"},
            {"id": "B", "text": "8"},
            {"id": "C", "text": "4"},
        ],
        "correct_answer": {"correct_option_id": "A"},
        "explanation": "Avval ko'paytirish bajariladi: 2 * 2 = 4, so'ngra 2 + 4 = 6.",
        "points": 1000,
        "time_limit_seconds": 30,
    })
    return quiz


@pytest.fixture
def active_session_and_student(db, host_user, sample_quiz_with_question):
    session = LiveSessionService.create_session(
        host=host_user,
        quiz=sample_quiz_with_question,
        game_mode="classic"
    )
    participant, ticket, _ = LiveSessionService.join_session(
        room_code=session.room_code,
        nickname="Azizbek"
    )
    return session, participant, ticket


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestClassroomGameConsumer:
    async def test_invalid_room_code_closes_connection(self):
        communicator = WebsocketCommunicator(application, "/ws/session/999999/")
        connected, close_code = await communicator.connect()
        assert connected is False
        assert close_code == 4004
        await communicator.disconnect()

    async def test_student_connect_with_valid_ticket(self, active_session_and_student):
        session, participant, ticket = active_session_and_student
        path = f"/ws/session/{session.room_code}/?ticket={ticket}"

        communicator = WebsocketCommunicator(application, path)
        connected, _ = await communicator.connect()
        assert connected is True

        # Should receive session.welcome
        response = await communicator.receive_json_from()
        assert response["type"] == "session.welcome"
        assert response["role"] == "student"
        assert response["room_code"] == session.room_code

        await communicator.disconnect()

    async def test_heartbeat_ping_pong(self, active_session_and_student):
        session, _, ticket = active_session_and_student
        path = f"/ws/session/{session.room_code}/?ticket={ticket}"

        communicator = WebsocketCommunicator(application, path)
        await communicator.connect()
        await communicator.receive_json_from()  # session.welcome

        # Send ping
        await communicator.send_json_to({"action": "ping", "client_ts": 1700000000})
        pong = await communicator.receive_json_from()
        assert pong["type"] == "pong"
        assert pong["client_ts"] == 1700000000
        assert "server_ts" in pong

        await communicator.disconnect()

    async def test_zero_knowledge_question_delivery(self, active_session_and_student):
        session, _, ticket = active_session_and_student
        path = f"/ws/session/{session.room_code}/?ticket={ticket}"

        communicator = WebsocketCommunicator(application, path)
        await communicator.connect()
        await communicator.receive_json_from()  # session.welcome

        # Host opens question
        sanitized_q = await sync_to_async(LiveSessionService.open_question)(session, question_index=0)
        assert sanitized_q is not None

        # Student receives question.opened
        # (Send broadcast to group simulating host action)
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            session.channel_group_name,
            {
                "type": "question_opened",
                "payload": sanitized_q
            }
        )

        msg = await communicator.receive_json_from()
        assert msg["type"] == "question.opened"
        payload = msg["payload"]

        # CRITICAL ZERO-KNOWLEDGE SECURITY ASSERTION
        assert "correct_answer" not in payload
        assert "correct_answer_key" not in payload
        assert "explanation" not in payload
        assert payload["prompt"] == "2 + 2 * 2 = ?"
        assert len(payload["options"]) == 3

        await communicator.disconnect()

    async def test_answer_submission_and_ack(self, active_session_and_student):
        session, participant, ticket = active_session_and_student

        # Open question first so session is in question_open state
        await sync_to_async(LiveSessionService.open_question)(session, question_index=0)
        raw_q_id = session.snapshot_data["questions"][0]["id"]

        path = f"/ws/session/{session.room_code}/?ticket={ticket}"
        communicator = WebsocketCommunicator(application, path)
        await communicator.connect()
        await communicator.receive_json_from()  # session.welcome

        # Student submits correct answer ("A")
        await communicator.send_json_to({
            "action": "answer.submit",
            "question_id": raw_q_id,
            "submission_id": "sub_test_001",
            "response_data": {"selected_option_id": "A"},
            "client_ts": int(time.time() * 1000)
        })

        ack = await communicator.receive_json_from()
        assert ack["type"] == "answer.ack"
        assert ack["status"] == "accepted"
        assert ack["is_correct"] is True
        assert ack["score_awarded"] == 1000

        # Verify idempotency: duplicate submission does not re-award score
        await communicator.send_json_to({
            "action": "answer.submit",
            "question_id": raw_q_id,
            "submission_id": "sub_test_001",
            "response_data": {"selected_option_id": "A"},
            "client_ts": int(time.time() * 1000)
        })

        dup_ack = await communicator.receive_json_from()
        assert dup_ack["type"] == "answer.ack"
        assert dup_ack["status"] == "already_recorded"

        await communicator.disconnect()

    async def test_late_submission_rejection(self, active_session_and_student):
        session, _, ticket = active_session_and_student

        # Open question but set deadline far in the past
        await sync_to_async(LiveSessionService.open_question)(session, question_index=0)
        session.question_deadline_ts = int(time.time() * 1000) - 10000  # 10s ago
        await sync_to_async(session.save)(update_fields=["question_deadline_ts"])

        raw_q_id = session.snapshot_data["questions"][0]["id"]

        path = f"/ws/session/{session.room_code}/?ticket={ticket}"
        communicator = WebsocketCommunicator(application, path)
        await communicator.connect()
        await communicator.receive_json_from()  # session.welcome

        await communicator.send_json_to({
            "action": "answer.submit",
            "question_id": raw_q_id,
            "submission_id": "sub_late_001",
            "response_data": {"selected_option_id": "A"},
            "client_ts": int(time.time() * 1000)
        })

        reject = await communicator.receive_json_from()
        assert reject["type"] == "answer.rejected"
        assert "Vaqt tugadi" in reject["reason"]

        await communicator.disconnect()

    async def test_sync_reconnection(self, active_session_and_student):
        session, participant, ticket = active_session_and_student
        await sync_to_async(LiveSessionService.open_question)(session, question_index=0)

        path = f"/ws/session/{session.room_code}/?ticket={ticket}"
        communicator = WebsocketCommunicator(application, path)
        await communicator.connect()
        await communicator.receive_json_from()  # session.welcome

        # Student sends sync action
        await communicator.send_json_to({"action": "sync"})
        snapshot_msg = await communicator.receive_json_from()

        assert snapshot_msg["type"] == "session.state_snapshot"
        payload = snapshot_msg["payload"]
        assert payload["room_code"] == session.room_code
        assert payload["status"] == "active"
        assert payload["fsm_state"] == "question_open"
        assert payload["my_state"]["nickname"] == "Azizbek"

        await communicator.disconnect()
