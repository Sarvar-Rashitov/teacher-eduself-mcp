"""
Services layer for Live Sessions, Room Codes, Tickets, Reconnection and Answer Submissions.
"""

import time
import secrets
import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.questions_registry.registry import question_type_registry
from apps.quizzes.models import Question
from apps.quizzes.serializers import QuestionStudentSerializer
from .models import LiveSession, Participant, AnswerSubmission
from .fsm import SessionStateMachine, InvalidStateTransitionError, SessionLockedError


class RoomCodeGenerationError(Exception):
    pass


class SessionJoinError(Exception):
    pass


class AnswerSubmissionError(Exception):
    pass


class DeadlineExpiredError(AnswerSubmissionError):
    pass


class DuplicateAnswerError(AnswerSubmissionError):
    pass


class RoomCodeGenerator:
    """
    6 xonali unikal Game PIN generatori.
    Faol xonalar bilan to'qnashuvni (collision) oldini oladi.
    """
    @staticmethod
    def generate() -> str:
        for _ in range(20):
            # 100000 dan 999999 gacha 6 xonali raqam
            code = f"{secrets.randbelow(900000) + 100000}"
            # Faol xonalar bilan tekshirish
            exists = LiveSession.objects.filter(
                room_code=code,
                status__in=[
                    LiveSession.STATUS_DRAFT,
                    LiveSession.STATUS_LOBBY,
                    LiveSession.STATUS_ACTIVE,
                    LiveSession.STATUS_PAUSED
                ]
            ).exists()
            if not exists:
                return code
        raise RoomCodeGenerationError("Faol xonalar uchun unikal PIN kod topilmadi.")


class ReconnectionManager:
    """
    WebSocket ulanishlari uchun qisqa muddatli ticketlar (60s) va
    qayta ulanish tokenlarini (reconnection / anonymous token) boshqarish.
    """
    TICKET_TTL = 60  # soniya

    @classmethod
    def generate_ticket(cls, session_id: str, participant_id: str = None, role: str = 'student') -> str:
        payload = {
            'session_id': str(session_id),
            'participant_id': str(participant_id) if participant_id else None,
            'role': role,
            'exp': int(time.time()) + cls.TICKET_TTL,
            'iat': int(time.time()),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    @classmethod
    def validate_ticket(cls, ticket: str) -> dict:
        try:
            return jwt.decode(ticket, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise ValueError("Ticket muddati o'tgan (Expired ticket).")
        except jwt.InvalidTokenError:
            raise ValueError("Yaroqsiz ticket (Invalid ticket).")

    @classmethod
    def generate_anonymous_token(cls) -> str:
        return secrets.token_urlsafe(32)


class LiveSessionService:
    """
    Jonli sessiya boshqaruvi: yaratish, qo'shilish, holat snapshot'i va javoblarni baholash.
    """

    @classmethod
    def create_session(cls, quiz, host, game_mode: str = 'classic', settings_payload: dict = None) -> LiveSession:
        room_code = RoomCodeGenerator.generate()
        session = LiveSession.objects.create(
            quiz=quiz,
            host=host,
            room_code=room_code,
            game_mode=game_mode,
            status=LiveSession.STATUS_LOBBY,  # To'g'ridan-to'g'ri lobbyga ochiladi
            settings_payload=settings_payload or {'round_phase': SessionStateMachine.PHASE_IDLE}
        )
        return session

    @classmethod
    def join_session(cls, room_code: str, nickname: str, team_name: str = None, anonymous_token: str = None):
        """
        O'quvchini sessiyaga qo'shish yoki qayta tiklash.
        Qaytaradi: (Participant, LiveSession, ticket: str)
        """
        try:
            session = LiveSession.objects.get(room_code=room_code)
        except LiveSession.DoesNotExist:
            raise SessionJoinError("Bunday PIN kodli xona mavjud emas.")

        # Agar ishtirokchida avvalgi anonymous_token bo'lsa (reconnection)
        if anonymous_token:
            participant = Participant.objects.filter(session=session, anonymous_token=anonymous_token).first()
            if participant:
                if participant.is_kicked:
                    raise SessionJoinError("Siz bu sessiyadan chiqarilgansiz.")
                participant.is_connected = True
                participant.save(update_fields=['is_connected', 'last_seen_at'])
                ticket = ReconnectionManager.generate_ticket(session.id, participant.id, role='student')
                return participant, session, ticket

        # Yangi ulanish: FSM orqali tekshirish
        fsm = SessionStateMachine(session)
        if not fsm.can_participant_join():
            if session.is_lobby_locked:
                raise SessionLockedError("Xona o'qituvchi tomonidan qulflangan.")
            raise SessionJoinError(f"Bu sessiyaga hozir qo'shilib bo'lmaydi (holat: {session.status}).")

        # Taxallus bandligini tekshirish
        existing_nick = Participant.objects.filter(session=session, nickname__iexact=nickname).first()
        if existing_nick:
            raise SessionJoinError(f"'{nickname}' taxallusi allaqachon band. Iltimos boshqa taxallus tanlang.")

        new_token = ReconnectionManager.generate_anonymous_token()
        participant = Participant.objects.create(
            session=session,
            nickname=nickname,
            team_name=team_name,
            anonymous_token=new_token,
            is_connected=True
        )

        ticket = ReconnectionManager.generate_ticket(session.id, participant.id, role='student')
        return participant, session, ticket

    @classmethod
    def get_state_snapshot(cls, session: LiveSession, participant: Participant = None, is_host: bool = False) -> dict:
        """
        Qayta ulanish yoki sinxronizatsiya uchun to'liq holat snapshot'i.
        Zero-Knowledge tamoyili bo'yicha talabaga to'g'ri javob kalitlari berilmaydi.
        """
        questions = session.quiz.questions.all().order_by('order_index')
        total_questions = questions.count()

        current_question_data = None
        current_question = None
        if 0 <= session.current_question_index < total_questions:
            current_question = questions[session.current_question_index]
            if is_host:
                from apps.quizzes.serializers import QuestionTeacherSerializer
                current_question_data = QuestionTeacherSerializer(current_question).data
            else:
                current_question_data = QuestionStudentSerializer(current_question).data

        participant_state = None
        if participant:
            has_answered = False
            if current_question:
                has_answered = AnswerSubmission.objects.filter(
                    session=session,
                    participant=participant,
                    question=current_question
                ).exists()

            participant_state = {
                'participant_id': str(participant.id),
                'nickname': participant.nickname,
                'team_name': participant.team_name,
                'score': participant.score,
                'streak': participant.streak,
                'has_answered_current': has_answered,
            }

        snapshot = {
            'session_id': str(session.id),
            'room_code': session.room_code,
            'status': session.status,
            'round_phase': session.settings_payload.get('round_phase', SessionStateMachine.PHASE_IDLE),
            'current_question_index': session.current_question_index,
            'total_questions': total_questions,
            'deadline_ts': session.settings_payload.get('current_deadline_ts'),
            'current_question': current_question_data,
            'participant_count': session.participants.filter(is_kicked=False).count(),
            'my_state': participant_state,
        }
        return snapshot

    @classmethod
    @transaction.atomic
    def submit_answer(
        cls,
        session: LiveSession,
        participant: Participant,
        question_id: str,
        submission_id: str,
        response_data: dict,
        client_submit_ts: int = None
    ) -> tuple[AnswerSubmission, bool]:
        """
        O'quvchi javobini qabul qilish va idempotent baholash.
        Qaytaradi: (submission, is_new: bool)
        """
        # 1. Idempotentlik tekshiruvi (submission_id orqali)
        existing = AnswerSubmission.objects.filter(submission_id=submission_id).first()
        if existing:
            return existing, False

        # 2. Savol mavjudligini tekshirish
        try:
            question = Question.objects.get(id=question_id, quiz=session.quiz)
        except Question.DoesNotExist:
            raise AnswerSubmissionError("Bunday savol topilmadi.")

        # 3. O'quvchi bu savolga avval javob topshirganligini tekshirish
        already_submitted = AnswerSubmission.objects.filter(
            session=session,
            participant=participant,
            question=question
        ).first()
        if already_submitted:
            return already_submitted, False

        # 4. Vaqt chegarasini (Deadline) tekshirish
        deadline_ts = session.settings_payload.get('current_deadline_ts')
        now_ts = timezone.now().timestamp()
        # 1.0 soniya tarmoq kechikishiga bag'rikenglik (network grace)
        if deadline_ts and now_ts > (deadline_ts + 1.0):
            raise DeadlineExpiredError("Savolga javob berish vaqti tugadi.")

        # 5. QuestionTypeRegistry orqali baholash
        plugin = question_type_registry.get(question.type)
        is_correct, score_fraction = plugin.check_answer(
            submitted_answer=response_data,
            correct_answer=question.correct_answer,
            options=question.options
        )
        score_awarded = int(question.points * score_fraction)


        # 6. Latency hisoblash
        latency_ms = 0
        if client_submit_ts:
            client_sec = client_submit_ts / 1000.0
            latency_ms = max(0, int((now_ts - client_sec) * 1000))

        # 7. Ball va streakni yangilash
        participant.score += score_awarded
        if is_correct:
            participant.streak += 1
        else:
            participant.streak = 0
        participant.save(update_fields=['score', 'streak', 'last_seen_at'])

        # 8. Yozuvni saqlash
        submission = AnswerSubmission.objects.create(
            session=session,
            participant=participant,
            question=question,
            submission_id=submission_id,
            response_data=response_data,
            is_correct=is_correct,
            score_awarded=score_awarded,
            latency_ms=latency_ms,
            client_submit_ts=client_submit_ts
        )

        return submission, True

    @classmethod
    def get_question_distribution(cls, session: LiveSession, question: Question) -> dict:
        """Savol bo'yicha berilgan javoblar statistikasini hisoblaydi."""
        submissions = AnswerSubmission.objects.filter(session=session, question=question)
        distribution = {}
        total = submissions.count()

        for sub in submissions:
            data = sub.response_data
            # single choice yoki matnli javoblar uchun
            choice = data.get('selected_option_id') or data.get('answer') or 'other'
            distribution[str(choice)] = distribution.get(str(choice), 0) + 1

        return {
            'distribution': distribution,
            'total_answers': total
        }

    @classmethod
    def get_leaderboard(cls, session: LiveSession, limit: int = 10) -> list:
        """Top o'quvchilar reytingini qaytaradi."""
        participants = session.participants.filter(is_kicked=False).order_by('-score', 'joined_at')[:limit]
        leaderboard = []
        for rank, p in enumerate(participants, start=1):
            leaderboard.append({
                'rank': rank,
                'participant_id': str(p.id),
                'nickname': p.nickname,
                'score': p.score,
                'streak': p.streak,
                'team_name': p.team_name,
            })
        return leaderboard
