import secrets
from typing import Any, Dict, Optional, Tuple
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.quizzes.models import Quiz, Question
from apps.questions_registry.registry import registry
from .models import LiveSession, Participant, AnswerSubmission
from .fsm import SessionStateMachine, SessionState


class RoomCodeGenerator:
    """
    6 xonali unikal Game PIN generatori.
    Takrorlanishlarning oldini oladi.
    """

    @staticmethod
    def generate_unique_pin() -> str:
        for _ in range(20):
            # 100000 dan 999999 gacha 6 xonali tasodifiy son
            pin = str(secrets.randbelow(900000) + 100000)
            # Faol yoki tugallanmagan xonalar bilan tekshirish
            if not LiveSession.objects.filter(
                room_code=pin,
                status__in=[SessionState.DRAFT, SessionState.LOBBY, SessionState.ACTIVE, SessionState.PAUSED]
            ).exists():
                return pin
        # Zaxira sifatida harfli-raqamli 6 belgi
        return secrets.token_hex(3).upper()


class LiveSessionService:
    """
    Jonli sessiyalarni yaratish, qo'shilish va javoblarni qayd etish xizmati.
    """

    @classmethod
    @transaction.atomic
    def create_session(
        cls,
        host,
        quiz: Quiz,
        game_mode: str = "classic",
        settings_payload: Optional[Dict[str, Any]] = None,
    ) -> LiveSession:
        pin = RoomCodeGenerator.generate_unique_pin()
        session = LiveSession.objects.create(
            quiz=quiz,
            host=host,
            room_code=pin,
            game_mode=game_mode,
            status=SessionState.DRAFT,
            settings_payload=settings_payload or {},
        )
        # Darhol LOBBY holatiga o'tkazish
        SessionStateMachine.open_lobby(session)
        return session

    @classmethod
    @transaction.atomic
    def join_session(cls, room_code: str, nickname: str) -> Tuple[Participant, LiveSession]:
        clean_pin = str(room_code).strip()
        clean_name = str(nickname).strip()

        if not clean_name:
            raise ValidationError("Taxallus (nickname) kiritilishi shart.")

        session = LiveSession.objects.filter(room_code=clean_pin).first()
        if not session:
            raise ValidationError("Bunday PIN kodli xona topilmadi.")

        if session.status in (SessionState.COMPLETED, SessionState.CANCELLED):
            raise ValidationError("Ushbu sessiya allaqachon yakunlangan.")

        if session.is_locked:
            raise ValidationError("O'qituvchi xonani yangi kiruvchilar uchun qulflagan.")

        # Reconnection token yaratish
        token = secrets.token_hex(32)

        # Agar ism takrorlansa, indeks qo'shish
        candidate_name = clean_name
        counter = 1
        while session.participants.filter(nickname=candidate_name).exists():
            candidate_name = f"{clean_name} ({counter})"
            counter += 1

        participant = Participant.objects.create(
            session=session,
            nickname=candidate_name,
            anonymous_token=token,
            score=0,
            streak=0,
            is_connected=True,
        )
        return participant, session

    @classmethod
    def reconnect_participant(cls, token: str) -> Optional[Participant]:
        """
        Internet uzilib qaytgan o'quvchini tokeni orqali topish.
        """
        if not token:
            return None
        participant = Participant.objects.select_related("session").filter(anonymous_token=token).first()
        if participant and participant.session.status not in (SessionState.COMPLETED, SessionState.CANCELLED):
            participant.is_connected = True
            participant.save(update_fields=["is_connected"])
            return participant
        return None

    @classmethod
    @transaction.atomic
    def record_submission(
        cls,
        session: LiveSession,
        participant: Participant,
        question: Question,
        submission_id: str,
        user_answer: Any,
        time_taken_ms: int = 0,
    ) -> Tuple[AnswerSubmission, bool]:
        """
        Idempotent javobni qabul qilish va ball hisoblash.
        Takror yuborilsa, mavjudini qaytaradi.
        """
        existing = AnswerSubmission.objects.filter(submission_id=submission_id).first()
        if existing:
            return existing, False

        # Savol turi registri orqali javobni baholash
        is_correct = False
        score_ratio = 0.0

        if registry.is_registered(question.type):
            handler = registry.get(question.type)
            eval_result = handler.check_answer(
                user_answer=user_answer,
                correct_answer=question.correct_answer,
                accepted_alternatives=question.accepted_alternatives,
            )
            is_correct = eval_result.get("is_correct", False)
            score_ratio = eval_result.get("score_ratio", 0.0)

        # Baza ball bo'yicha hisoblash
        awarded_points = int(question.points * score_ratio)

        submission = AnswerSubmission.objects.create(
            session=session,
            participant=participant,
            question=question,
            submission_id=submission_id,
            user_answer=user_answer,
            is_correct=is_correct,
            score_awarded=awarded_points,
            time_taken_ms=time_taken_ms,
        )

        # Participant ball va streak yangilash
        participant.score += awarded_points
        if is_correct:
            participant.streak += 1
        else:
            participant.streak = 0
        participant.save(update_fields=["score", "streak"])

        return submission, True
