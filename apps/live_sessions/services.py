import time
import secrets
from typing import Any, Tuple, Optional
from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.utils import timezone

from questions_registry import question_registry
from quizzes.models import Quiz
from quizzes.services import VersionManager
from .models import LiveSession, Participant, AnswerSubmission
from .fsm import SessionStateMachine, InvalidFSMTransitionError


class RoomCodeGenerator:
    """
    Generates cryptographically random, collision-free 6-digit game PINs.
    """

    @classmethod
    def generate_unique_code(cls, max_attempts: int = 20) -> str:
        for _ in range(max_attempts):
            code = f"{secrets.randbelow(900000) + 100000}"
            # Check if active room with this code exists
            exists = LiveSession.objects.filter(
                room_code=code,
                status__in=["draft", "lobby", "active", "paused"]
            ).exists()
            if not exists:
                return code
        raise RuntimeError("Barcha mavjud 6 xonali xona kodlari band!")


class ReconnectionManager:
    """
    Manages one-time tickets, reconnection tokens, and state snapshots
    for zero-data-loss disconnect recovery as specified in DOC-58 and DOC-60.
    """

    SIGNER_SALT = "eduself-session-ticket-salt"

    @classmethod
    def generate_anonymous_token(cls) -> str:
        return secrets.token_hex(32)

    @classmethod
    def generate_ticket(
        cls,
        session_id: str,
        participant_id: str,
        role: str = "student",
        ttl_seconds: int = 60
    ) -> str:
        data = {
            "session_id": str(session_id),
            "participant_id": str(participant_id),
            "role": role,
            "exp": int(time.time()) + ttl_seconds,
        }
        return signing.dumps(data, salt=cls.SIGNER_SALT)

    @classmethod
    def validate_ticket(cls, ticket: str, session_id: str) -> Optional[dict]:
        try:
            data = signing.loads(ticket, salt=cls.SIGNER_SALT, max_age=60)
            if str(data.get("session_id")) != str(session_id):
                return None
            return data
        except (signing.BadSignature, signing.SignatureExpired):
            return None

    @classmethod
    def build_state_snapshot(cls, session: LiveSession, participant: Participant) -> dict:
        """
        Builds complete State Snapshot for seamless recovery (DOC-60 Section 4).
        """
        questions = session.snapshot_data.get("questions", [])
        total_questions = len(questions)

        current_q_data = None
        has_answered = False

        if 0 <= session.current_question_index < total_questions:
            raw_q = questions[session.current_question_index]
            handler = question_registry.get(raw_q.get("type", "single_choice"))
            # Sanitize for student
            current_q_data = handler.sanitize_for_student(raw_q)

            # Check if student already answered
            q_id = str(raw_q.get("id"))
            has_answered = session.submissions.filter(
                participant=participant,
                question_id=q_id
            ).exists()

        now_ms = int(time.time() * 1000)
        remaining_time_ms = 0
        if session.question_deadline_ts:
            remaining_time_ms = max(0, session.question_deadline_ts - now_ms)

        return {
            "session_id": str(session.id),
            "room_code": session.room_code,
            "status": session.status,
            "fsm_state": session.fsm_state,
            "current_question_index": session.current_question_index,
            "total_questions": total_questions,
            "remaining_time_ms": remaining_time_ms,
            "current_question": current_q_data,
            "my_state": {
                "participant_id": str(participant.id),
                "nickname": participant.nickname,
                "score": participant.score,
                "current_streak": participant.current_streak,
                "has_answered_current": has_answered,
                "team_name": participant.team_name,
            }
        }


class LiveSessionService:
    """
    Central orchestration service for LiveSessions, participants, and answers.
    """

    @classmethod
    def create_session(
        cls,
        host: Any,
        quiz: Quiz,
        game_mode: str = "classic",
        settings_payload: Optional[dict] = None
    ) -> LiveSession:
        """
        Creates a new live room, freezes the quiz into an immutable snapshot,
        and assigns a 6-digit PIN.
        """
        room_code = RoomCodeGenerator.generate_unique_code()

        # Create or retrieve frozen quiz snapshot
        snapshot_obj = VersionManager.create_snapshot(
            quiz=quiz,
            change_log=f"Jonli sessiya ochildi (Xona kodi: {room_code})",
            user=host
        )

        session = LiveSession.objects.create(
            quiz=quiz,
            host=host,
            room_code=room_code,
            game_mode=game_mode,
            status="lobby",
            fsm_state="lobby",
            settings_payload=settings_payload or {},
            snapshot_data=snapshot_obj.snapshot_data,
        )
        return session

    @classmethod
    def join_session(
        cls,
        room_code: str,
        nickname: str,
        anonymous_token: Optional[str] = None,
        user: Any = None
    ) -> Tuple[Participant, str, bool]:
        """
        Joins an active session by room PIN.
        Returns: (participant, ticket, is_reconnection)
        """
        clean_code = str(room_code).strip()
        session = LiveSession.objects.filter(room_code=clean_code).first()

        if not session:
            raise ValidationError("Ko'rsatilgan PIN kodli xona topilmadi.")

        if session.status in ["completed", "cancelled"]:
            raise ValidationError("Ushbu sessiya allaqachon yakunlangan yoki bekor qilingan.")

        # Reconnection check
        if anonymous_token:
            existing = session.participants.filter(anonymous_token=anonymous_token).first()
            if existing:
                if existing.is_kicked:
                    raise ValidationError("Siz ushbu xonadan chetlatilgansiz (Kicked).")
                existing.is_connected = True
                existing.save(update_fields=["is_connected", "last_seen_at"])
                ticket = ReconnectionManager.generate_ticket(str(session.id), str(existing.id), role="student")
                return existing, ticket, True

        # Check if lobby is locked for new entrants
        if session.is_locked:
            raise ValidationError("Xona o'qituvchi tomonidan yangi ishtirokchilar uchun qulflangan.")

        clean_nick = str(nickname).strip()
        if not clean_nick:
            raise ValidationError("Ism yoki taxallus kiritilishi shart.")

        token = anonymous_token or ReconnectionManager.generate_anonymous_token()

        participant = Participant.objects.create(
            session=session,
            user=user if (user and user.is_authenticated) else None,
            nickname=clean_nick,
            anonymous_token=token,
            is_connected=True,
        )

        ticket = ReconnectionManager.generate_ticket(str(session.id), str(participant.id), role="student")
        return participant, ticket, False

    @classmethod
    def open_question(cls, session: LiveSession, question_index: Optional[int] = None) -> dict:
        """
        Opens a question for answering. Sets deadline timestamp and transitions FSM.
        Returns Zero-Knowledge question payload.
        """
        questions = session.snapshot_data.get("questions", [])
        if not questions:
            raise ValidationError("Viktorina snapshot'ida savollar topilmadi.")

        if question_index is not None:
            session.current_question_index = question_index

        idx = session.current_question_index
        if idx < 0 or idx >= len(questions):
            raise ValidationError(f"Savol indeksi ({idx}) chegaradan tashqarida.")

        raw_question = questions[idx]
        time_limit = raw_question.get("time_limit_seconds", 30)

        now_ms = int(time.time() * 1000)
        deadline_ms = now_ms + (time_limit * 1000)

        session.question_deadline_ts = deadline_ms
        SessionStateMachine.open_question(session)

        # Zero-Knowledge delivery
        handler = question_registry.get(raw_question.get("type", "single_choice"))
        sanitized = handler.sanitize_for_student(raw_question)
        sanitized["question_index"] = idx
        sanitized["total_questions"] = len(questions)
        sanitized["deadline_ts"] = deadline_ms
        sanitized["time_limit_seconds"] = time_limit

        return sanitized

    @classmethod
    def close_question(cls, session: LiveSession) -> None:
        session.question_deadline_ts = None
        SessionStateMachine.close_question(session)

    @classmethod
    def reveal_answer(cls, session: LiveSession) -> dict:
        """
        Reveals correct answer and statistics for current question.
        """
        SessionStateMachine.reveal_answers(session)

        questions = session.snapshot_data.get("questions", [])
        idx = session.current_question_index
        raw_question = questions[idx] if (0 <= idx < len(questions)) else {}

        q_id = str(raw_question.get("id"))
        submissions = session.submissions.filter(question_id=q_id)
        total_submissions = submissions.count()
        correct_submissions = submissions.filter(is_correct=True).count()

        return {
            "question_id": q_id,
            "correct_answer": raw_question.get("correct_answer"),
            "explanation": raw_question.get("explanation"),
            "total_answers": total_submissions,
            "correct_answers": correct_submissions,
        }

    @classmethod
    def submit_answer(
        cls,
        session: LiveSession,
        participant: Participant,
        question_id: str,
        submission_id: str,
        response_data: Any,
        client_ts: Optional[int] = None
    ) -> Tuple[Optional[AnswerSubmission], bool, str]:
        """
        Processes answer submission.
        Guarantees server-authoritative deadline check, idempotency, and immediate ACK.
        Returns: (submission, is_new, feedback_message)
        """
        # 1. State check
        if session.status != "active" or session.fsm_state != "question_open":
            return None, False, "Savolga javob berish vaqti yopiq yoki to'xtatilgan."

        # 2. Server Deadline check (with 1.5s network grace tolerance)
        now_ms = int(time.time() * 1000)
        if session.question_deadline_ts and now_ms > (session.question_deadline_ts + 1500):
            return None, False, "Vaqt tugadi! Javob qabul qilinmadi."

        # 3. Idempotency check by submission_id or question_id
        existing = AnswerSubmission.objects.filter(
            session=session,
            participant=participant,
            question_id=str(question_id)
        ).first()

        if existing:
            return existing, False, "Javobingiz allaqachon qabul qilingan."

        # 4. Find question in snapshot
        questions = session.snapshot_data.get("questions", [])
        target_q = next((q for q in questions if str(q.get("id")) == str(question_id)), None)

        if not target_q:
            return None, False, "Savol topilmadi."

        # 5. Evaluate answer via QuestionType handler
        handler = question_registry.get(target_q.get("type", "single_choice"))
        eval_res = handler.check_answer(
            submission=response_data,
            correct_answer=target_q.get("correct_answer"),
            options=target_q.get("options")
        )

        base_points = target_q.get("points", 1000)
        score_awarded = int(base_points * eval_res.score_fraction)

        server_latency = max(0, int(now_ms - client_ts)) if client_ts else 0

        submission = AnswerSubmission.objects.create(
            session=session,
            participant=participant,
            question_id=str(question_id),
            submission_id=str(submission_id or secrets.token_hex(16)),
            response_data=response_data,
            is_correct=eval_res.is_correct,
            score_awarded=score_awarded,
            client_submit_ts=client_ts,
            server_latency_ms=server_latency,
        )

        # Update participant score and streak
        participant.score += score_awarded
        if eval_res.is_correct:
            participant.current_streak += 1
        else:
            participant.current_streak = 0
        participant.save(update_fields=["score", "current_streak"])

        return submission, True, "Javob muvaffaqiyatli qabul qilindi."
