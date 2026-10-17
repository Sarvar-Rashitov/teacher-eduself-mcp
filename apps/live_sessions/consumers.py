"""
Django Channels WebSocket Consumers for EduSelf Live Sessions.
Implements ClassroomGameConsumer (Students/Projector) and HostGameConsumer (Teacher).
Adheres strictly to REALTIME_PROTOCOL.md, EVENTS.md, and Zero-Knowledge principles.
"""

import time
import json
import uuid
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import LiveSession, Participant, AnswerSubmission
from .fsm import SessionStateMachine, InvalidStateTransitionError, SessionLockedError
from .services import LiveSessionService, ReconnectionManager, AnswerSubmissionError


def make_envelope(event_type: str, session_id: str, payload: dict, seq: int = 1) -> dict:
    """Protokol bo'yicha yagona JSON konverti (Frame Envelope)."""
    return {
        'v': 1,
        'id': f"evt_{uuid.uuid4().hex[:12]}",
        'type': event_type,
        'session_id': str(session_id),
        'seq': seq,
        'ts': int(time.time() * 1000),
        'payload': payload
    }


class ClassroomGameConsumer(AsyncJsonWebsocketConsumer):
    """
    O'quvchilar va Proyektor ekrani uchun WebSocket iste'molchisi.
    """

    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)

    async def connect(self):

        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group = f"room_{self.room_code}"
        self.participant = None
        self.session = None

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Ulanish paytida query-param orqali kelgan ticketni tekshirish
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = dict(q.split('=') for q in query_string.split('&') if '=' in q)
        ticket = params.get('ticket')

        if ticket:
            auth_ok = await self._authenticate_with_ticket(ticket)
            if not auth_ok:
                await self.send_json(make_envelope(
                    'error',
                    self.room_code,
                    {'code': 4001, 'message': 'Ticket yaroqsiz yoki muddati o\'tgan'}
                ))
                await self.close(code=4001)
                return

        # Boshlang'ich welcome xabari
        await self.send_json(make_envelope(
            'session.welcome',
            self.room_code,
            {
                'role': 'student' if self.participant else 'spectator',
                'server_ts': int(time.time() * 1000)
            }
        ))

    async def disconnect(self, close_code):
        if self.participant:
            await self._set_participant_connection(self.participant.id, False)
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        action = content.get('type') or content.get('action')
        payload = content.get('payload', {})

        # 1. Heartbeat: ping -> pong (RTT o'lchash)
        if action == 'ping':
            client_ts = payload.get('client_ts') or content.get('client_ts', int(time.time() * 1000))
            await self.send_json({
                'v': 1,
                'type': 'pong',
                'client_ts': client_ts,
                'server_ts': int(time.time() * 1000)
            })
            return

        # 2. Sessiyaga ulanish / ticket orqali tanishish
        if action == 'session.join':
            ticket = payload.get('ticket') or content.get('ticket')
            if ticket:
                await self._authenticate_with_ticket(ticket)
            snapshot = await self._get_snapshot()
            await self.send_json(make_envelope('session.joined', self.room_code, snapshot))
            return

        # 3. Sinxronizatsiya / snapshot so'rovi
        if action == 'session.sync':
            snapshot = await self._get_snapshot()
            await self.send_json(make_envelope('session.state_snapshot', self.room_code, snapshot))
            return

        # 4. Javob topshirish (answer.submit) - SLA ACK < 300ms!
        if action == 'answer.submit':
            await self._handle_answer_submit(payload or content)
            return

    async def _handle_answer_submit(self, data: dict):
        if not self.participant:
            await self.send_json(make_envelope(
                'error',
                self.room_code,
                {'code': 4003, 'message': 'Autentifikatsiya qilinmagan ishtirokchi.'}
            ))
            return

        q_id = data.get('question_id')
        sub_id = data.get('submission_id') or f"sub_{uuid.uuid4().hex[:12]}"
        resp_data = data.get('response_data', {})
        client_ts = data.get('client_submit_ts') or data.get('client_ts')

        start_time = time.time()
        result = await self._process_answer_submission(
            self.participant.id,
            q_id,
            sub_id,
            resp_data,
            client_ts
        )

        calc_latency = int((time.time() - start_time) * 1000)

        if not result.get('success'):
            await self.send_json(make_envelope(
                'answer.rejected',
                self.room_code,
                {
                    'submission_id': sub_id,
                    'reason': result.get('error', 'Noma\'lum xatolik'),
                    'latency_ms': calc_latency
                }
            ))
            return

        # Muvaffaqiyatli qabul qilindi: Darhol ACK qaytarish (<300ms SLA)
        await self.send_json(make_envelope(
            'answer.ack',
            self.room_code,
            {
                'status': 'accepted',
                'submission_id': sub_id,
                'is_correct': result.get('is_correct'),
                'score_awarded': result.get('score_awarded'),
                'total_score': result.get('total_score'),
                'latency_ms': calc_latency
            }
        ))

        # Hostga o'quvchi javob bergani haqida hisobot bildirishnoma
        host_group = f"host_{self.room_code}"
        await self.channel_layer.group_send(
            host_group,
            {
                'type': 'host_submission_received',
                'participant_id': str(self.participant.id),
                'nickname': self.participant.nickname,
                'question_id': str(q_id),
            }
        )

    # ---------------- Channel Layer Event Handlers ----------------
    async def session_started(self, event):
        await self.send_json(make_envelope('session.started', self.room_code, event.get('payload', {})))

    async def session_locked(self, event):
        await self.send_json(make_envelope('session.locked', self.room_code, event.get('payload', {})))

    async def session_unlocked(self, event):
        await self.send_json(make_envelope('session.unlocked', self.room_code, event.get('payload', {})))

    async def session_paused(self, event):
        await self.send_json(make_envelope('session.paused', self.room_code, event.get('payload', {})))

    async def session_resumed(self, event):
        await self.send_json(make_envelope('session.resumed', self.room_code, event.get('payload', {})))

    async def session_completed(self, event):
        await self.send_json(make_envelope('session.completed', self.room_code, event.get('payload', {})))

    async def question_opened(self, event):
        """Zero-Knowledge savol: To'g'ri javob kaliti yo'qligi kafolatlanadi."""
        payload = event.get('payload', {})
        # To'g'ri javobni olib tashlash
        safe_payload = {k: v for k, v in payload.items() if k not in ('correct_answer', 'explanation')}
        await self.send_json(make_envelope('question.opened', self.room_code, safe_payload))

    async def question_closed(self, event):
        await self.send_json(make_envelope('question.closed', self.room_code, event.get('payload', {})))

    async def answer_revealed(self, event):
        """Savol yopilgach to'g'ri javob va statistika barchaga oshkor qilinadi."""
        await self.send_json(make_envelope('answer.revealed', self.room_code, event.get('payload', {})))

    async def leaderboard_updated(self, event):
        await self.send_json(make_envelope('leaderboard.updated', self.room_code, event.get('payload', {})))

    async def participant_kicked(self, event):
        kicked_id = event.get('payload', {}).get('participant_id')
        if self.participant and str(self.participant.id) == str(kicked_id):
            await self.send_json(make_envelope('participant.kicked', self.room_code, {'reason': 'Host tomonidan chiqarildi'}))
            await self.close(code=4003)

    # ---------------- Database Sync Helpers ----------------
    @database_sync_to_async
    def _authenticate_with_ticket(self, ticket: str) -> bool:
        try:
            payload = ReconnectionManager.validate_ticket(ticket)
            participant_id = payload.get('participant_id')
            if participant_id:
                self.participant = Participant.objects.select_related('session').get(id=participant_id)
                self.participant.is_connected = True
                self.participant.save(update_fields=['is_connected', 'last_seen_at'])
                self.session = self.participant.session
                return True
            return False
        except Exception:
            return False

    @database_sync_to_async
    def _set_participant_connection(self, participant_id, status: bool):
        Participant.objects.filter(id=participant_id).update(is_connected=status, last_seen_at=timezone.now())

    @database_sync_to_async
    def _get_snapshot(self) -> dict:
        session = LiveSession.objects.filter(room_code=self.room_code).first()
        if not session:
            return {}
        return LiveSessionService.get_state_snapshot(session, self.participant, is_host=False)

    @database_sync_to_async
    def _process_answer_submission(self, participant_id, question_id, sub_id, response_data, client_ts) -> dict:
        try:
            participant = Participant.objects.select_related('session').get(id=participant_id)
            session = participant.session
            submission, is_new = LiveSessionService.submit_answer(
                session=session,
                participant=participant,
                question_id=question_id,
                submission_id=sub_id,
                response_data=response_data,
                client_submit_ts=client_ts
            )
            return {
                'success': True,
                'is_correct': submission.is_correct,
                'score_awarded': submission.score_awarded,
                'total_score': participant.score,
            }
        except AnswerSubmissionError as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            return {'success': False, 'error': f"Ichki xatolik: {str(e)}"}


class HostGameConsumer(AsyncJsonWebsocketConsumer):
    """
    O'qituvchi boshqaruv paneli uchun WebSocket iste'molchisi.
    Sessiya ustidan to'liq nazorat (Server-Authoritative Host Controls).
    """

    @classmethod
    async def encode_json(cls, content):
        return json.dumps(content, cls=DjangoJSONEncoder)

    async def connect(self):

        self.room_code = self.scope['url_route']['kwargs']['room_code']
        self.room_group = f"room_{self.room_code}"
        self.host_group = f"host_{self.room_code}"
        self.session = None

        await self.channel_layer.group_add(self.host_group, self.channel_name)
        await self.accept()

        # Host autentifikatsiyasi
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = dict(q.split('=') for q in query_string.split('&') if '=' in q)
        ticket = params.get('ticket')

        if ticket:
            is_valid = await self._validate_host_ticket(ticket)
            if not is_valid:
                await self.send_json(make_envelope('error', self.room_code, {'code': 4003, 'message': 'Ruxsat berilmadi.'}))
                await self.close(code=4003)
                return

        await self.send_json(make_envelope(
            'session.welcome',
            self.room_code,
            {'role': 'host', 'server_ts': int(time.time() * 1000)}
        ))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.host_group, self.channel_name)

    async def receive_json(self, content):
        action = content.get('type') or content.get('action')
        payload = content.get('payload', {})

        # O'qituvchi boshqaruv amallari
        if action == 'session.start':
            await self._action_start_session()
        elif action == 'session.lock':
            await self._action_lock_lobby(True)
        elif action == 'session.unlock':
            await self._action_lock_lobby(False)
        elif action == 'session.pause':
            await self._action_pause_session()
        elif action == 'session.resume':
            await self._action_resume_session()
        elif action == 'question.open':
            q_idx = payload.get('question_index', 0)
            time_limit = payload.get('time_limit', 30)
            await self._action_open_question(q_idx, time_limit)
        elif action == 'question.close':
            await self._action_close_question()
        elif action == 'answer.reveal':
            await self._action_reveal_answer()
        elif action == 'leaderboard.show':
            await self._action_show_leaderboard()
        elif action == 'participant.kick':
            p_id = payload.get('participant_id')
            await self._action_kick_participant(p_id)
        elif action == 'session.end':
            await self._action_end_session()
        elif action == 'ping':
            await self.send_json({'v': 1, 'type': 'pong', 'server_ts': int(time.time() * 1000)})

    # ---------------- Host Commands Implementation ----------------
    async def _action_start_session(self):
        res = await self._fsm_start_session()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_started', 'payload': {'status': 'active'}}
            )
            await self.send_json(make_envelope('session.started_ack', self.room_code, {'status': 'active'}))
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_lock_lobby(self, lock: bool):
        res = await self._fsm_lock_lobby(lock)
        if res.get('success'):
            event_type = 'session_locked' if lock else 'session_unlocked'
            await self.channel_layer.group_send(
                self.room_group,
                {'type': event_type, 'payload': {'is_locked': lock}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_pause_session(self):
        res = await self._fsm_pause()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_paused', 'payload': {'status': 'paused'}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_resume_session(self):
        res = await self._fsm_resume()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_resumed', 'payload': {'status': 'active'}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_open_question(self, question_index: int, time_limit: int):
        res = await self._fsm_open_question(question_index, time_limit)
        if res.get('success'):
            # Xonadagi barchaga Zero-Knowledge tarzida tarqatish
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'question_opened', 'payload': res.get('question_data')}
            )
            # Hostga to'liq ma'lumot (javob kaliti bilan)
            await self.send_json(make_envelope('question.opened_host', self.room_code, res.get('host_question_data')))
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_close_question(self):
        res = await self._fsm_close_question()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'question_closed', 'payload': {}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_reveal_answer(self):
        res = await self._fsm_reveal_answer()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'answer_revealed', 'payload': res.get('reveal_data')}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_show_leaderboard(self):
        res = await self._fsm_show_leaderboard()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'leaderboard_updated', 'payload': {'top_entries': res.get('leaderboard')}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_kick_participant(self, participant_id: str):
        res = await self._fsm_kick_participant(participant_id)
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'participant_kicked', 'payload': {'participant_id': participant_id}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    async def _action_end_session(self):
        res = await self._fsm_end_session()
        if res.get('success'):
            await self.channel_layer.group_send(
                self.room_group,
                {'type': 'session_completed', 'payload': {'leaderboard': res.get('leaderboard')}}
            )
        else:
            await self.send_json(make_envelope('error', self.room_code, {'message': res.get('error')}))

    # ---------------- Host Group Message Receivers ----------------
    async def host_submission_received(self, event):
        """O'quvchi javob berganida o'qituvchi ekranida live yangilanish."""
        await self.send_json(make_envelope('host.submission_received', self.room_code, event))

    # ---------------- Database Sync Helpers for Host ----------------
    @database_sync_to_async
    def _validate_host_ticket(self, ticket: str) -> bool:
        try:
            payload = ReconnectionManager.validate_ticket(ticket)
            return payload.get('role') == 'host'
        except Exception:
            return False

    @database_sync_to_async
    def _fsm_start_session(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.start_session()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_lock_lobby(self, lock: bool) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            if lock:
                fsm.lock_lobby()
            else:
                fsm.unlock_lobby()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_pause(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.pause()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_resume(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.resume()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_open_question(self, question_index: int, time_limit: int) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            questions = list(session.quiz.questions.all().order_by('order_index'))
            if not (0 <= question_index < len(questions)):
                return {'success': False, 'error': 'Noto\'g\'ri savol indeksi.'}

            question = questions[question_index]
            fsm = SessionStateMachine(session)
            deadline_ts = fsm.open_question(question_index, time_limit)

            from apps.quizzes.serializers import QuestionStudentSerializer, QuestionTeacherSerializer
            student_data = QuestionStudentSerializer(question).data
            student_data['deadline_ts'] = deadline_ts
            student_data['time_limit_seconds'] = time_limit
            student_data['question_index'] = question_index
            student_data['total_questions'] = len(questions)

            host_data = QuestionTeacherSerializer(question).data
            host_data['deadline_ts'] = deadline_ts
            host_data['time_limit_seconds'] = time_limit

            return {
                'success': True,
                'question_data': student_data,
                'host_question_data': host_data
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_close_question(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.close_question()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_reveal_answer(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            questions = list(session.quiz.questions.all().order_by('order_index'))
            q = questions[session.current_question_index]
            fsm = SessionStateMachine(session)
            fsm.reveal_answer()

            dist_info = LiveSessionService.get_question_distribution(session, q)
            leaderboard = LiveSessionService.get_leaderboard(session, limit=10)

            return {
                'success': True,
                'reveal_data': {
                    'question_id': str(q.id),
                    'correct_answer': q.correct_answer,
                    'explanation': q.explanation,
                    'distribution': dist_info.get('distribution', {}),
                    'total_answers': dist_info.get('total_answers', 0),
                    'leaderboard': leaderboard
                }
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_show_leaderboard(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.show_leaderboard()
            leaderboard = LiveSessionService.get_leaderboard(session, limit=10)
            return {'success': True, 'leaderboard': leaderboard}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_kick_participant(self, participant_id: str) -> dict:
        try:
            p = Participant.objects.get(id=participant_id, session__room_code=self.room_code)
            p.is_kicked = True
            p.is_connected = False
            p.save(update_fields=['is_kicked', 'is_connected'])
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @database_sync_to_async
    def _fsm_end_session(self) -> dict:
        try:
            session = LiveSession.objects.get(room_code=self.room_code)
            fsm = SessionStateMachine(session)
            fsm.complete()
            leaderboard = LiveSessionService.get_leaderboard(session, limit=10)
            return {'success': True, 'leaderboard': leaderboard}
        except Exception as e:
            return {'success': False, 'error': str(e)}
