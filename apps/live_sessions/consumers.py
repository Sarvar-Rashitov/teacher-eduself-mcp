import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone

from .models import LiveSession, Participant, AnswerSubmission
from .services import LiveSessionService
from .fsm import SessionStateMachine
from apps.quizzes.models import Question
from apps.quizzes.services import ZeroKnowledgeQuestionDelivery


class ClassroomGameConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-time dars va o'yin WebSocket iste'molchisi (Consumer).
    O'qituvchi boshqaruvi va o'quvchilar javoblarini real-vaqtda boshqaradi.
    """

    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"].get("room_code")
        if not self.room_code:
            await self.close(code=4000)
            return

        self.room_group = f"room_{self.room_code}"

        # Redis guruhiga ulanish
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Dastlabki xush kelibsiz xabari
        await self.send_json({
            "type": "session.welcome",
            "room_code": self.room_code,
            "server_ts": int(time.time() * 1000),
        })

    async def disconnect(self, close_code):
        if hasattr(self, "room_group"):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        """
        Mijozdan kelgan xabarlarni qayta ishlash va guruhga tarqatish.
        """
        msg_type = content.get("type", "")
        payload = content.get("payload", {})

        # Heartbeat ping/pong
        if msg_type == "ping":
            await self.send_json({
                "type": "pong",
                "client_ts": content.get("client_ts"),
                "server_ts": int(time.time() * 1000),
            })
            return

        # O'quvchi xonaga qo'shilishi
        elif msg_type == "participant.join":
            nickname = payload.get("nickname", "Anonim")
            participant_id = payload.get("participant_id")
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {
                        "type": "participant.joined",
                        "payload": {
                            "nickname": nickname,
                            "participant_id": participant_id,
                            "joined_at": int(time.time() * 1000),
                        },
                    },
                },
            )

        # O'yinni boshlash (Host)
        elif msg_type in ("session.start", "host.start_game"):
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {
                        "type": "session.started",
                        "payload": {
                            "room_code": self.room_code,
                            "started_at": int(time.time() * 1000),
                        },
                    },
                },
            )

        # Savolni ochish (Host) - Zero-Knowledge kadr!
        elif msg_type in ("question.open", "host.next_question"):
            question_id = payload.get("question_id")
            question_data = await self._get_sanitized_question(question_id)
            if question_data:
                await self.channel_layer.group_send(
                    self.room_group,
                    {
                        "type": "event.broadcast",
                        "content": {
                            "type": "question.opened",
                            "payload": question_data,
                        },
                    },
                )

        # Savolni yopish (Host)
        elif msg_type in ("question.close", "host.close_question"):
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {
                        "type": "question.closed",
                        "payload": {
                            "question_id": payload.get("question_id"),
                            "closed_at": int(time.time() * 1000),
                        },
                    },
                },
            )

        # To'g'ri javobni ko'rsatish (Host)
        elif msg_type in ("answer.reveal", "host.reveal_answer"):
            question_id = payload.get("question_id")
            reveal_data = await self._get_question_reveal_data(question_id)
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {
                        "type": "answer.revealed",
                        "payload": reveal_data,
                    },
                },
            )

        # Talaba javobini yuborishi
        elif msg_type == "answer.submit":
            submission_res = await self._process_answer_submission(payload)
            # Talabaga shaxsiy ACK yuborish
            await self.send_json({
                "type": "answer.acknowledged",
                "payload": submission_res,
            })
            # O'qituvchiga javoblar soni o'sganini bildirish
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {
                        "type": "answer.count_updated",
                        "payload": {
                            "question_id": payload.get("question_id"),
                        },
                    },
                },
            )

        # Pauza va Davom ettirish
        elif msg_type == "session.pause":
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {"type": "session.paused", "payload": {}},
                },
            )

        elif msg_type == "session.resume":
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "event.broadcast",
                    "content": {"type": "session.resumed", "payload": {}},
                },
            )

    async def event_broadcast(self, event):
        """
        Redis guruhidan kelgan hodisani ushbu soketga chiqarish.
        """
        await self.send_json(event["content"])

    @sync_to_async
    def _get_sanitized_question(self, question_id):
        question = Question.objects.filter(pk=question_id).first()
        if not question:
            return None
        return ZeroKnowledgeQuestionDelivery.sanitize(question)

    @sync_to_async
    def _get_question_reveal_data(self, question_id):
        question = Question.objects.filter(pk=question_id).first()
        if not question:
            return {"question_id": question_id}
        return {
            "question_id": str(question.id),
            "correct_answer": question.correct_answer,
            "explanation": question.explanation,
        }

    @sync_to_async
    def _process_answer_submission(self, payload):
        submission_id = payload.get("submission_id", f"sub_{time.time()}")
        participant_id = payload.get("participant_id")
        question_id = payload.get("question_id")
        user_answer = payload.get("user_answer")
        time_taken_ms = payload.get("time_taken_ms", 0)

        session = LiveSession.objects.filter(room_code=self.room_code).first()
        participant = Participant.objects.filter(pk=participant_id).first()
        question = Question.objects.filter(pk=question_id).first()

        if not (session and participant and question):
            return {"status": "error", "message": "Ma'lumotlar to'liq emas"}

        sub, created = LiveSessionService.record_submission(
            session=session,
            participant=participant,
            question=question,
            submission_id=submission_id,
            user_answer=user_answer,
            time_taken_ms=time_taken_ms,
        )

        return {
            "status": "recorded",
            "submission_id": sub.submission_id,
            "is_correct": sub.is_correct,
            "score_awarded": sub.score_awarded,
            "total_score": participant.score,
        }
