import time
import urllib.parse
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .models import LiveSession, Participant
from .fsm import SessionStateMachine
from .services import LiveSessionService, ReconnectionManager


class ClassroomGameConsumer(AsyncJsonWebsocketConsumer):
    """
    Real-Time WebSocket Consumer for both Students and Hosts.
    Enforces RBAC over WebSocket, Zero-Knowledge question delivery,
    Heartbeat (ping/pong), and server-authoritative state transitions.
    """

    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        self.room_group = f"room_{self.room_code}"
        self.role = "spectator"
        self.participant = None
        self.session = None

        # Parse query string for ticket
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        query_params = urllib.parse.parse_qs(query_string)
        ticket = query_params.get("ticket", [None])[0]

        # Fetch session
        self.session = await self.get_session(self.room_code)
        if not self.session:
            await self.close(code=4004)  # Room Not Found
            return

        # Determine role & authentication
        user = self.scope.get("user")
        if user and user.is_authenticated and self.session.host_id == user.id:
            self.role = "host"
        elif ticket:
            ticket_data = ReconnectionManager.validate_ticket(ticket, str(self.session.id))
            if ticket_data:
                self.role = ticket_data.get("role", "student")
                p_id = ticket_data.get("participant_id")
                self.participant = await self.get_participant_by_id(p_id)
            else:
                await self.close(code=4001)  # Unauthorized Ticket
                return
        elif user and user.is_authenticated:
            # Check if user is already a participant
            self.participant = await self.get_participant_by_user(self.session, user)
            if self.participant:
                self.role = "student"

        # Join room group
        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        # Update participant connected state
        if self.participant:
            await self.set_participant_connection(self.participant, True)
            # Broadcast join to group
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "participant_event",
                    "sender_channel_name": self.channel_name,
                    "event_type": "participant.joined",
                    "participant": {
                        "id": str(self.participant.id),
                        "nickname": self.participant.nickname,
                        "team_name": self.participant.team_name,
                        "score": self.participant.score,
                    }
                }
            )

        # Welcome frame (DOC-58 1)
        await self.send_json({
            "type": "session.welcome",
            "role": self.role,
            "session_id": str(self.session.id),
            "room_code": self.room_code,
            "status": self.session.status,
            "fsm_state": self.session.fsm_state,
            "server_ts": int(time.time() * 1000),
        })

    async def disconnect(self, close_code):
        if self.participant:
            await self.set_participant_connection(self.participant, False)
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "participant_event",
                    "event_type": "participant.left",
                    "participant": {
                        "id": str(self.participant.id),
                        "nickname": self.participant.nickname,
                    }
                }
            )

        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive_json(self, content):
        action = content.get("action") or content.get("type")
        payload = content.get("payload", {})

        # 1. Heartbeat
        if action == "ping":
            await self.send_json({
                "type": "pong",
                "client_ts": content.get("client_ts"),
                "server_ts": int(time.time() * 1000)
            })
            return

        # 2. State synchronization (Reconnection catch-up)
        if action in ("sync", "session.sync"):
            if self.participant:
                snapshot = await self.build_sync_snapshot(self.session, self.participant)
                await self.send_json({
                    "type": "session.state_snapshot",
                    "payload": snapshot,
                    "server_ts": int(time.time() * 1000),
                })
            return

        # 3. Student Answer Submission
        if action == "answer.submit":
            if not self.participant:
                await self.send_json({"type": "answer.rejected", "reason": "Faqat ro'yxatdan o'tgan ishtirokchilar javob bera oladi."})
                return

            q_id = payload.get("question_id") or content.get("question_id")
            sub_id = payload.get("submission_id") or content.get("submission_id")
            resp_data = payload.get("response_data") or content.get("response_data") or payload.get("selected_option_id")
            client_ts = payload.get("client_submit_ts") or content.get("client_ts")

            # Process submission atomically
            submission, is_new, msg = await self.process_answer(
                session=self.session,
                participant=self.participant,
                question_id=q_id,
                submission_id=sub_id,
                response_data=resp_data,
                client_ts=client_ts
            )

            if submission is None:
                await self.send_json({
                    "type": "answer.rejected",
                    "reason": msg,
                    "server_ts": int(time.time() * 1000)
                })
            else:
                # Immediate ACK (<300ms SLA)
                await self.send_json({
                    "type": "answer.ack",
                    "status": "accepted" if is_new else "already_recorded",
                    "is_correct": submission.is_correct,
                    "score_awarded": submission.score_awarded,
                    "feedback": msg,
                    "server_ts": int(time.time() * 1000)
                })

            return

        # 4. Host Commands (RBAC: Host Only)
        if self.role != "host":
            await self.send_json({"type": "error", "code": 4003, "message": "Ushbu amalni faqat o'qituvchi bajara oladi."})
            return

        # Host Action Handlers
        if action == "session.start":
            await self.handle_session_start()
        elif action in ("session.lock", "session.unlock"):
            await self.handle_session_lock(lock=(action == "session.lock"))
        elif action == "session.pause":
            await self.handle_session_pause()
        elif action == "session.resume":
            await self.handle_session_resume()
        elif action == "question.open":
            q_idx = payload.get("question_index")
            await self.handle_question_open(q_idx)
        elif action == "question.close":
            await self.handle_question_close()
        elif action == "answer.reveal":
            await self.handle_answer_reveal()
        elif action == "session.end":
            await self.handle_session_end()
        elif action == "participant.kick":
            p_id = payload.get("participant_id")
            await self.handle_participant_kick(p_id)

    # =========================================================================
    # Host Action Execution Methods
    # =========================================================================

    async def handle_session_start(self):
        await self.fsm_start_game(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "session.started",
                "payload": {
                    "session_id": str(self.session.id),
                    "status": "active",
                    "fsm_state": "question_preview",
                }
            }
        )

    async def handle_session_lock(self, lock: bool):
        await self.set_session_lock(self.session, lock)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "session.locked" if lock else "session.unlocked",
                "payload": {"is_locked": lock}
            }
        )

    async def handle_session_pause(self):
        await self.fsm_pause(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "session.paused",
                "payload": {"status": "paused"}
            }
        )

    async def handle_session_resume(self):
        await self.fsm_resume(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "session.resumed",
                "payload": {"status": "active"}
            }
        )

    async def handle_question_open(self, question_index: int | None):
        sanitized_q = await self.service_open_question(self.session, question_index)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "question_opened",
                "payload": sanitized_q
            }
        )

    async def handle_question_close(self):
        await self.service_close_question(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "question.closed",
                "payload": {"fsm_state": "question_closed"}
            }
        )

    async def handle_answer_reveal(self):
        reveal_data = await self.service_reveal_answer(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "answer_revealed",
                "payload": reveal_data
            }
        )

    async def handle_session_end(self):
        await self.fsm_end_game(self.session)
        await self.channel_layer.group_send(
            self.room_group,
            {
                "type": "session_broadcast",
                "event_type": "session.completed",
                "payload": {"status": "completed"}
            }
        )

    async def handle_participant_kick(self, participant_id: str):
        if participant_id:
            await self.kick_participant_in_db(self.session, participant_id)
            await self.channel_layer.group_send(
                self.room_group,
                {
                    "type": "session_broadcast",
                    "event_type": "participant.kicked",
                    "payload": {"participant_id": str(participant_id)}
                }
            )

    # =========================================================================
    # Group Channel Layer Handlers
    # =========================================================================

    async def session_broadcast(self, event):
        await self.send_json({
            "type": event["event_type"],
            "payload": event["payload"],
            "server_ts": int(time.time() * 1000)
        })

    async def question_opened(self, event):
        await self.send_json({
            "type": "question.opened",
            "payload": event["payload"],
            "server_ts": int(time.time() * 1000)
        })

    async def answer_revealed(self, event):
        await self.send_json({
            "type": "answer.revealed",
            "payload": event["payload"],
            "server_ts": int(time.time() * 1000)
        })

    async def participant_event(self, event):
        if event.get("sender_channel_name") == self.channel_name:
            return
        await self.send_json({
            "type": event["event_type"],
            "participant": event["participant"],
            "server_ts": int(time.time() * 1000)
        })

    # =========================================================================
    # Database Helper Methods (sync_to_async)
    # =========================================================================

    @database_sync_to_async
    def get_session(self, room_code):
        return LiveSession.objects.filter(room_code=room_code).first()

    @database_sync_to_async
    def get_participant_by_id(self, p_id):
        return Participant.objects.filter(id=p_id).first()

    @database_sync_to_async
    def get_participant_by_user(self, session, user):
        return Participant.objects.filter(session=session, user=user).first()

    @database_sync_to_async
    def set_participant_connection(self, participant, is_connected):
        participant.is_connected = is_connected
        participant.save(update_fields=["is_connected", "last_seen_at"])

    @database_sync_to_async
    def set_session_lock(self, session, lock):
        session.is_locked = lock
        session.save(update_fields=["is_locked"])

    @database_sync_to_async
    def fsm_start_game(self, session):
        SessionStateMachine.start_game(session)

    @database_sync_to_async
    def fsm_pause(self, session):
        SessionStateMachine.pause(session)

    @database_sync_to_async
    def fsm_resume(self, session):
        SessionStateMachine.resume(session)

    @database_sync_to_async
    def fsm_end_game(self, session):
        SessionStateMachine.end_game(session)

    @database_sync_to_async
    def service_open_question(self, session, question_index):
        return LiveSessionService.open_question(session, question_index)

    @database_sync_to_async
    def service_close_question(self, session):
        LiveSessionService.close_question(session)

    @database_sync_to_async
    def service_reveal_answer(self, session):
        return LiveSessionService.reveal_answer(session)

    @database_sync_to_async
    def kick_participant_in_db(self, session, participant_id):
        p = session.participants.filter(id=participant_id).first()
        if p:
            p.is_kicked = True
            p.is_connected = False
            p.save(update_fields=["is_kicked", "is_connected"])

    @database_sync_to_async
    def process_answer(self, session, participant, question_id, submission_id, response_data, client_ts):
        session.refresh_from_db()
        return LiveSessionService.submit_answer(
            session=session,
            participant=participant,
            question_id=question_id,
            submission_id=submission_id,
            response_data=response_data,
            client_ts=client_ts
        )

    @database_sync_to_async
    def build_sync_snapshot(self, session, participant):
        session.refresh_from_db()
        participant.refresh_from_db()
        return ReconnectionManager.build_state_snapshot(session, participant)


class HostGameConsumer(ClassroomGameConsumer):
    """
    Dedicated Host Consumer (inherits from ClassroomGameConsumer with Host defaults).
    """
    pass
