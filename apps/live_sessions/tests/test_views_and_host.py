import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from core.asgi import application

from apps.authentication.models import User
from apps.quizzes.services import QuizService
from apps.live_sessions.models import LiveSession
from apps.live_sessions.services import SessionService


@pytest.fixture
def auth_teacher_client(db):
    teacher = User.objects.create_user(
        username='host_teacher_1',
        email='host@example.com',
        password='Password123!',
        role='teacher'
    )
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client, teacher


@pytest.fixture
def quiz_with_q(db, auth_teacher_client):
    _, teacher = auth_teacher_client
    quiz = QuizService.create_quiz(owner=teacher, title='Geografiya Quiz', subject='Geografiya')
    QuizService.add_question(
        quiz=quiz,
        type_id='true_false',
        prompt='Orol dengizi qurimoqda.',
        options=[],
        correct_answer={'value': True}
    )
    return quiz


@pytest.mark.django_db
class TestSessionRESTViews:
    def test_create_and_join_session(self, auth_teacher_client, quiz_with_q):
        client, teacher = auth_teacher_client

        # 1. Create Session
        create_url = reverse('live_sessions:create')
        resp = client.post(create_url, {'quiz_id': str(quiz_with_q.id)}, format='json')
        assert resp.status_code == 201
        room_code = resp.data['room_code']

        # 2. Join Session via anonymous student
        anon_client = APIClient()
        join_url = reverse('live_sessions:join')
        join_resp = anon_client.post(join_url, {
            'room_code': room_code,
            'nickname': 'Dilnoza'
        }, format='json')
        assert join_resp.status_code == 200
        assert join_resp.data['status'] == 'ok'
        assert join_resp.data['nickname'] == 'Dilnoza'
        assert 'anonymous_token' in join_resp.data
        assert join_resp.data['role'] == 'student'

        # 3. Session detail
        detail_url = reverse('live_sessions:detail', kwargs={'room_code': room_code})
        detail_resp = client.get(detail_url)
        assert detail_resp.status_code == 200
        assert len(detail_resp.data['participants']) == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestHostGameConsumer:
    async def test_host_websocket_control(self, auth_teacher_client, quiz_with_q):
        _, teacher = auth_teacher_client
        create_fn = database_sync_to_async(SessionService.create_session)
        session = await create_fn(quiz=quiz_with_q, host=teacher)

        # Host ulanishi
        ws_url = f"/ws/host/{session.room_code}/"
        communicator = WebsocketCommunicator(application, ws_url)
        communicator.scope['user'] = teacher

        connected, _ = await communicator.connect()
        assert connected, "Host ulanishi muvaffaqiyatli bo'lishi kerak"

        # Host welcome
        host_welcome = await communicator.receive_json_from()
        assert host_welcome['type'] == 'host.connected'

        # session.start buyrug'i
        await communicator.send_json_to({'action': 'session.start'})
        start_broadcast = await communicator.receive_json_from()
        assert start_broadcast['type'] == 'session.started'

        # question.open buyrug'i
        await communicator.send_json_to({'action': 'question.open', 'question_index': 0})
        q_open_broadcast = await communicator.receive_json_from()
        assert q_open_broadcast['type'] == 'question.opened'
        assert 'prompt' in q_open_broadcast['payload']

        # Disconnect
        await communicator.disconnect()
