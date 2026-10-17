# apps/live_sessions/consumers.py
# Backend.md §4, REALTIME_PROTOCOL.md, EVENTS.md va LIVE_SESSION.md asosida
import time
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import LiveSession, Participant
from .fsm import SessionFSM
from .services import SessionService, ReconnectionManager
from apps.quizzes.services import QuizService
from apps.questions_registry.registry import question_registry


class ClassroomGameConsumer(AsyncJsonWebsocketConsumer):
    """
    O'quvchilar uchun jonli o'yin WebSocket iste'molchisi.
    ws/session/<room_code>/?token=<anonymous_token>
    """
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group = f"session_{self.room_code}"
        self.anonymous_token = self.scope.get('query_string', b'').decode('utf-8')
        if 'token=' in self.anonymous_token:
            self.anonymous_token = self.anonymous_token.split('token=')[-1].split('&')[0]
        else:
            self.anonymous_token = None

        # 1. Sessiya va ishtirokchini tekshirish
        session_info = await self.get_session_and_participant()
        if not session_info:
            await self.close(code=4004)  # Session not found
            return

        self.session_id, self.participant_id, self.nickname = session_info

        # 2. Guruhga ulanish
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # 3. Welcome xabari (joriy holat snapshot bilan)
        snapshot = await self.get_snapshot()
        await self.send_json({
            'v': 1,
            'type': 'session.welcome',
            'session_id': str(self.session_id),
            'ts': int(time.time() * 1000),
            'payload': snapshot
        })

        # 4. Ishtirokchi qo'shilganini guruhga bildirish
        await self.channel_layer.group_send(
            self.room_group,
            {
                'type': 'participant_joined',
                'nickname': self.nickname,
                'participant_id': str(self.participant_id)
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.set_participant_disconnected()
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        msg_type = content.get('type') or content.get('action')

        # 1. Heartbeat Ping
        if msg_type == 'ping':
            await self.send_json({
                'type': 'pong',
                'client_ts': content.get('client_ts'),
                'server_ts': int(time.time() * 1000)
            })
            return

        # 2. Qayta ulanish sinxronizatsiyasi
        if msg_type == 'sync':
            snapshot = await self.get_snapshot()
            await self.send_json({
                'type': 'session.state_snapshot',
                'ts': int(time.time() * 1000),
                'payload': snapshot
            })
            return

        # 3. Javob yuborish (SLA: ACK < 300ms)
        if msg_type == 'answer.submit':
            await self.handle_answer_submit(content)

    async def handle_answer_submit(self, content):
        q_id = content.get('question_id')
        payload = content.get('payload') or content.get('option_id')
        client_ts = content.get('client_ts')

        result = await self.submit_answer_db(q_id, payload, client_ts)

        if result.get('error'):
            await self.send_json({
                'type': 'answer.rejected',
                'reason': result['error']
            })
        else:
            # Talabaga darhol ACK qaytariladi
            await self.send_json({
                'type': 'answer.ack',
                'status': 'accepted',
                'points_awarded': result['points'],
                'is_correct': result['is_correct'],
                'latency_ms': int((time.time() - (client_ts / 1000 if client_ts else time.time())) * 1000)
            })

    # ============================================================
    # Guruhdan kelgan Broadcast xabarlarni qayta ishlash
    # ============================================================
    async def session_started(self, event):
        await self.send_json({'type': 'session.started', 'payload': event['payload']})

    async def question_opened(self, event):
        # Zero-Knowledge: Talabaga correct_answer yuborilmaydi!
        safe_payload = {k: v for k, v in event['payload'].items() if k != 'correct_answer'}
        await self.send_json({'type': 'question.opened', 'payload': safe_payload})

    async def question_closed(self, event):
        await self.send_json({'type': 'question.closed', 'payload': event.get('payload', {})})

    async def answer_revealed(self, event):
        await self.send_json({'type': 'answer.revealed', 'payload': event['payload']})

    async def session_paused(self, event):
        await self.send_json({'type': 'session.paused', 'payload': event.get('payload', {})})

    async def session_resumed(self, event):
        await self.send_json({'type': 'session.resumed', 'payload': event.get('payload', {})})

    async def session_completed(self, event):
        await self.send_json({'type': 'session.completed', 'payload': event.get('payload', {})})

    async def participant_joined(self, event):
        await self.send_json({'type': 'participant.joined', 'payload': event})

    async def participant_kicked(self, event):
        if str(event.get('participant_id')) == str(self.participant_id):
            await self.send_json({'type': 'participant.kicked', 'reason': 'Host sizni chiqardi.'})
            await self.close(code=4003)

    # ============================================================
    # DB operatsiyalari (Asinxron wrapper)
    # ============================================================
    @database_sync_to_async
    def get_session_and_participant(self):
        session = LiveSession.objects.filter(room_code=self.room_code).first()
        if not session:
            return None
        participant = None
        if self.anonymous_token:
            participant = Participant.objects.filter(session=session, anonymous_token=self.anonymous_token).first()
        if not participant:
            # Anonymous token bo'lmasa yoki topilmasa birinchi topilgan yoki yangi
            participant = Participant.objects.filter(session=session).first()

        p_id = participant.id if participant else None
        p_name = participant.nickname if participant else "Guest"
        return session.id, p_id, p_name

    @database_sync_to_async
    def set_participant_disconnected(self):
        if hasattr(self, 'participant_id') and self.participant_id:
            Participant.objects.filter(id=self.participant_id).update(is_connected=False)

    @database_sync_to_async
    def get_snapshot(self):
        session = LiveSession.objects.filter(room_code=self.room_code).first()
        p = Participant.objects.filter(id=self.participant_id).first() if hasattr(self, 'participant_id') else None
        return ReconnectionManager.get_session_snapshot(session, p) if session else {}

    @database_sync_to_async
    def submit_answer_db(self, question_id, submitted_payload, client_ts):
        session = LiveSession.objects.filter(room_code=self.room_code).first()
        participant = Participant.objects.filter(id=self.participant_id).first()
        if not session or not participant:
            return {'error': 'Sessiya yoki ishtirokchi topilmadi.'}
        try:
            ts_sec = (client_ts / 1000) if client_ts else None
            submission = SessionService.submit_answer(
                session=session,
                participant=participant,
                question_id=question_id,
                submitted_payload=submitted_payload,
                client_ts=ts_sec
            )
            return {
                'points': submission.points_awarded,
                'is_correct': submission.is_correct
            }
        except Exception as e:
            return {'error': str(e)}


class HostGameConsumer(AsyncJsonWebsocketConsumer):
    """
    O'qituvchi (Host / Proyektor) boshqaruv WebSocket iste'molchisi.
    ws/host/<room_code>/
    """
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group = f"session_{self.room_code}"
        self.user = self.scope.get('user')

        session = await self.get_session()
        if not session:
            await self.close(code=4004)
            return

        # Faqat o'qituvchi / host boshqara oladi
        if not await self.is_host_or_admin(session):
            await self.close(code=4003)  # Forbidden
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        await self.send_json({
            'type': 'host.connected',
            'room_code': self.room_code,
            'message': 'Boshqaruv pultiga ulandingiz.'
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group'):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        action = content.get('action') or content.get('type')

        if action == 'session.start':
            payload = await self.start_session()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_started', 'payload': payload}
            )

        elif action == 'question.open':
            payload = await self.open_question(content.get('question_index'))
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'question_opened', 'payload': payload}
            )

        elif action == 'question.close':
            payload = await self.close_question()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'question_closed', 'payload': payload}
            )

        elif action == 'answer.reveal':
            payload = await self.reveal_answer()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'answer_revealed', 'payload': payload}
            )

        elif action == 'session.pause':
            await self.pause_session()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_paused'}
            )

        elif action == 'session.resume':
            await self.resume_session()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_resumed'}
            )

        elif action == 'session.end':
            await self.end_session()
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_completed'}
            )

        elif action == 'participant.kick':
            p_id = content.get('participant_id')
            await self.kick_participant(p_id)
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'participant_kicked', 'participant_id': p_id}
            )

    # ============================================================
    # Guruhdan kelgan Broadcast xabarlarni hostga uzatish
    # ============================================================
    async def session_started(self, event):
        await self.send_json({'type': 'session.started', 'payload': event.get('payload', {})})

    async def question_opened(self, event):
        # Host paneli to'liq ma'lumotni (shu jumladan to'g'ri javobni) qabul qiladi
        await self.send_json({'type': 'question.opened', 'payload': event.get('payload', {})})

    async def question_closed(self, event):
        await self.send_json({'type': 'question.closed', 'payload': event.get('payload', {})})

    async def answer_revealed(self, event):
        await self.send_json({'type': 'answer.revealed', 'payload': event.get('payload', {})})

    async def session_paused(self, event):
        await self.send_json({'type': 'session.paused', 'payload': event.get('payload', {})})

    async def session_resumed(self, event):
        await self.send_json({'type': 'session.resumed', 'payload': event.get('payload', {})})

    async def session_completed(self, event):
        await self.send_json({'type': 'session.completed', 'payload': event.get('payload', {})})

    async def participant_joined(self, event):
        await self.send_json({'type': 'participant.joined', 'payload': event})

    async def participant_kicked(self, event):
        await self.send_json({'type': 'participant.kicked', 'payload': event})

    # ============================================================
    # Host yordamchi DB metodlari
    # ============================================================
    @database_sync_to_async
    def get_session(self):
        return LiveSession.objects.filter(room_code=self.room_code).first()

    @database_sync_to_async
    def is_host_or_admin(self, session):
        if not self.user or not self.user.is_authenticated:
            return False
        return self.user == session.host or self.user.is_superuser or getattr(self.user, 'role', '') == 'system_admin'

    @database_sync_to_async
    def start_session(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        SessionFSM.transition(session, 'in_progress')
        return {
            'total_questions': session.quiz.questions.count(),
            'game_mode': session.game_mode,
        }

    @database_sync_to_async
    def open_question(self, index=None):
        session = LiveSession.objects.get(room_code=self.room_code)
        if index is not None:
            session.current_question_index = int(index)

        questions = list(session.quiz.questions.order_by('order_index'))
        if session.current_question_index < len(questions):
            q = questions[session.current_question_index]
            session.current_question_deadline = time.time() + q.time_limit_seconds
            session.save(update_fields=['current_question_index', 'current_question_deadline', 'updated_at'])

            handler = question_registry.get(q.type)
            return {
                'question_id': str(q.id),
                'question_index': session.current_question_index,
                'type': q.type,
                'prompt': q.prompt,
                'options': handler.sanitize_for_student(q.options),
                'time_limit_seconds': q.time_limit_seconds,
                'deadline_ts': session.current_question_deadline,
                # Host ko'rishi uchun to'g'ri javobni ham saqlaymiz, lekin consumer uni studentlarga filtrlaydi
                'correct_answer': q.correct_answer,
            }
        return {}

    @database_sync_to_async
    def close_question(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        session.current_question_deadline = time.time()
        session.save(update_fields=['current_question_deadline', 'updated_at'])
        return {'question_index': session.current_question_index}

    @database_sync_to_async
    def reveal_answer(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        questions = list(session.quiz.questions.order_by('order_index'))
        if session.current_question_index < len(questions):
            q = questions[session.current_question_index]
            # Peshqadamlar jadvali (Top 5)
            top_participants = list(
                session.participants.order_by('-score')[:5].values('id', 'nickname', 'score', 'streak')
            )
            return {
                'question_id': str(q.id),
                'correct_answer': q.correct_answer,
                'explanation': q.explanation,
                'leaderboard': top_participants
            }
        return {}

    @database_sync_to_async
    def pause_session(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        SessionFSM.transition(session, 'paused')

    @database_sync_to_async
    def resume_session(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        SessionFSM.transition(session, 'in_progress')

    @database_sync_to_async
    def end_session(self):
        session = LiveSession.objects.get(room_code=self.room_code)
        SessionFSM.transition(session, 'completed')

    @database_sync_to_async
    def kick_participant(self, participant_id):
        Participant.objects.filter(id=participant_id, session__room_code=self.room_code).delete()
