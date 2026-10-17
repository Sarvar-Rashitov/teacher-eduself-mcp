import time
import pytest
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from core.asgi import application
from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.live_sessions.services import LiveSessionService, ReconnectionManager

join_session_async = database_sync_to_async(LiveSessionService.join_session)


@pytest.fixture
def ws_teacher(db):
    return User.objects.create_user(
        username="ws_teacher",
        password="password123",
        role="teacher"
    )



@pytest.fixture
def ws_quiz(db, ws_teacher):
    quiz = Quiz.objects.create(
        title="Real-Time Test Quiz",
        subject="Fizika",
        grade_level=9,
        owner=ws_teacher
    )

    Question.objects.create(
        quiz=quiz,
        type="single_choice",
        prompt="Tezlik birligi nima?",
        options=[
            {"id": "opt_1", "text": "m/s"},
            {"id": "opt_2", "text": "kg"},
            {"id": "opt_3", "text": "Joul"},
        ],
        correct_answer={"correct_option_id": "opt_1"},
        points=1000,
        time_limit_seconds=30,
        order_index=0
    )
    return quiz


@pytest.fixture
def ws_session(db, ws_quiz, ws_teacher):
    return LiveSessionService.create_session(quiz=ws_quiz, host=ws_teacher)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_connect_and_ping_pong(ws_session):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/session/{ws_session.room_code}/"
    )
    connected, _ = await communicator.connect()
    assert connected is True

    # 1. Welcome frame
    welcome = await communicator.receive_json_from()
    assert welcome['type'] == 'session.welcome'

    # 2. Ping-pong
    await communicator.send_json_to({'type': 'ping', 'client_ts': 1700000000})
    pong = await communicator.receive_json_from()
    assert pong['type'] == 'pong'
    assert pong['client_ts'] == 1700000000
    assert 'server_ts' in pong

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_rejects_invalid_ticket(ws_session):
    communicator = WebsocketCommunicator(
        application,
        f"/ws/session/{ws_session.room_code}/?ticket=bad.corrupted.token"
    )
    connected, _ = await communicator.connect()
    assert connected is True

    err_frame = await communicator.receive_json_from()
    assert err_frame['type'] == 'error'
    assert err_frame['payload']['code'] == 4001


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_student_answer_submission_ack(ws_session, ws_quiz):
    participant, _, ticket = await join_session_async(
        room_code=ws_session.room_code,
        nickname="Sanjar"
    )
    # Set deadline
    ws_session.settings_payload['current_deadline_ts'] = time.time() + 30
    await ws_session.asave()

    question = await ws_quiz.questions.afirst()

    communicator = WebsocketCommunicator(
        application,
        f"/ws/session/{ws_session.room_code}/?ticket={ticket}"
    )
    connected, _ = await communicator.connect()
    assert connected is True

    # Welcome frame
    await communicator.receive_json_from()

    # Submit Answer
    submission_id = "ws_sub_id_777"
    await communicator.send_json_to({
        'type': 'answer.submit',
        'payload': {
            'question_id': str(question.id),
            'submission_id': submission_id,
            'response_data': {'selected_option_id': 'opt_1'},
            'client_submit_ts': int(time.time() * 1000)
        }
    })

    ack = await communicator.receive_json_from()
    assert ack['type'] == 'answer.ack'
    assert ack['payload']['status'] == 'accepted'
    assert ack['payload']['is_correct'] is True
    assert ack['payload']['score_awarded'] == 1000

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_host_commands_and_zero_knowledge_broadcast(ws_session, ws_teacher):
    host_ticket = ReconnectionManager.generate_ticket(ws_session.id, role='host')
    _, _, student_ticket = await join_session_async(
        room_code=ws_session.room_code,
        nickname="Guli"
    )

    # 1. Connect Student
    student_comm = WebsocketCommunicator(
        application,
        f"/ws/session/{ws_session.room_code}/?ticket={student_ticket}"
    )
    st_connected, _ = await student_comm.connect()
    assert st_connected is True
    await student_comm.receive_json_from()  # Welcome

    # 2. Connect Host
    host_comm = WebsocketCommunicator(
        application,
        f"/ws/host/{ws_session.room_code}/?ticket={host_ticket}"
    )
    h_connected, _ = await host_comm.connect()
    assert h_connected is True
    await host_comm.receive_json_from()  # Welcome

    # 3. Host starts session
    await host_comm.send_json_to({'type': 'session.start'})
    host_ack = await host_comm.receive_json_from()
    assert host_ack['type'] == 'session.started_ack'

    student_event = await student_comm.receive_json_from()
    assert student_event['type'] == 'session.started'

    # 4. Host opens question -> Student receives Zero-Knowledge frame
    await host_comm.send_json_to({
        'type': 'question.open',
        'payload': {'question_index': 0, 'time_limit': 30}
    })

    # Host receives full question with answers
    host_q_frame = await host_comm.receive_json_from()
    assert host_q_frame['type'] == 'question.opened_host'
    assert 'correct_answer' in host_q_frame['payload']

    # Student receives Zero-Knowledge question (NO correct_answer or explanation)
    student_q_frame = await student_comm.receive_json_from()
    assert student_q_frame['type'] == 'question.opened'
    assert 'correct_answer' not in student_q_frame['payload']
    assert 'explanation' not in student_q_frame['payload']
    assert student_q_frame['payload']['prompt'] == "Tezlik birligi nima?"

    await host_comm.disconnect()
    await student_comm.disconnect()
