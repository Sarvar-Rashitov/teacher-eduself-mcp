from django.test import TestCase, Client
from django.urls import reverse
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from apps.authentication.models import User
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant
from apps.live_sessions.services import LiveSessionService
from apps.live_sessions.consumers import ClassroomGameConsumer
import apps.questions_registry.types  # ensure registry is loaded


class SessionConsumerAndAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.teacher = User.objects.create_user(
            username="teacher_shaxzod",
            email="shaxzod@example.com",
            password="SecurePass123!",
            role="teacher",
        )
        self.quiz = Quiz.objects.create(
            owner=self.teacher,
            title="Informatika 9-sinf",
            subject="Informatika",
            grade_level=9,
        )
        self.question = Question.objects.create(
            quiz=self.quiz,
            type="single_choice",
            prompt="Python tili muallifi kim?",
            options=[
                {"id": "opt_a", "text": "Guido van Rossum"},
                {"id": "opt_b", "text": "James Gosling"},
            ],
            correct_answer="opt_a",
            points=1000,
            time_limit_seconds=30,
        )
        self.session = LiveSessionService.create_session(
            host=self.teacher,
            quiz=self.quiz,
        )

    def test_session_create_api(self):
        """O'qituvchi API orqali yangi jonli sessiya ochishi."""
        self.client.force_login(self.teacher)
        url = reverse("live_sessions:session_create")
        response = self.client.post(
            url,
            data={"quiz_id": str(self.quiz.id), "game_mode": "classic"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("room_code", data)
        self.assertEqual(data["status"], "lobby")

    def test_session_join_and_reconnect_api(self):
        """O'quvchi PIN kod orqali qo'shilishi va uzilganda token bilan qayta ulanishi."""
        url_join = reverse("live_sessions:session_join")
        response = self.client.post(
            url_join,
            data={"pin": self.session.room_code, "nickname": "Botir"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["nickname"], "Botir")
        self.assertIn("anonymous_token", data)
        token = data["anonymous_token"]

        # Qayta ulanish (Reconnect)
        url_rec = reverse("live_sessions:session_reconnect")
        rec_response = self.client.post(
            url_rec,
            data={"token": token},
            content_type="application/json",
        )
        self.assertEqual(rec_response.status_code, 200)
        rec_data = rec_response.json()
        self.assertEqual(rec_data["status"], "reconnected")
        self.assertEqual(rec_data["nickname"], "Botir")

    async def test_websocket_welcome_and_ping_pong(self):
        """WebSocket ulanishi va ping/pong heartbeat tekshiruvi."""
        communicator = WebsocketCommunicator(
            ClassroomGameConsumer.as_asgi(),
            f"/ws/session/{self.session.room_code}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"room_code": self.session.room_code}}
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # 1. session.welcome xabari kelishi kerak
        welcome = await communicator.receive_json_from()
        self.assertEqual(welcome["type"], "session.welcome")
        self.assertEqual(welcome["room_code"], self.session.room_code)

        # 2. ping yuborib pong olish
        await communicator.send_json_to({"type": "ping", "client_ts": 123456})
        pong = await communicator.receive_json_from()
        self.assertEqual(pong["type"], "pong")
        self.assertEqual(pong["client_ts"], 123456)

        await communicator.disconnect()

    async def test_websocket_answer_submission(self):
        """O'quvchi WebSocket orqali javob yuborganda tekshirilib ACK qaytishi."""
        # Ishtirokchini yaratish
        participant, _ = await database_sync_to_async(LiveSessionService.join_session)(
            room_code=self.session.room_code,
            nickname="Nodira",
        )

        communicator = WebsocketCommunicator(
            ClassroomGameConsumer.as_asgi(),
            f"/ws/session/{self.session.room_code}/",
        )
        communicator.scope["url_route"] = {"kwargs": {"room_code": self.session.room_code}}
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Welcome qabul qilish
        await communicator.receive_json_from()

        # To'g'ri javob yuborish
        await communicator.send_json_to({
            "type": "answer.submit",
            "payload": {
                "submission_id": "sub_test_001",
                "participant_id": str(participant.id),
                "question_id": str(self.question.id),
                "user_answer": "opt_a",
                "time_taken_ms": 2500,
            },
        })

        # Shaxsiy ACK javobi
        ack = await communicator.receive_json_from()
        self.assertEqual(ack["type"], "answer.acknowledged")
        self.assertTrue(ack["payload"]["is_correct"])
        self.assertEqual(ack["payload"]["score_awarded"], 1000)

        await communicator.disconnect()
