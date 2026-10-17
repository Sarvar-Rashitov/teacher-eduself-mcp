# apps/live_sessions/services.py
# LIVE_SESSION.md §3, REALTIME_PROTOCOL.md va RECONNECTION.md asosida
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.quizzes.models import Quiz, Question
from apps.quizzes.services import QuizService
from apps.questions_registry.registry import question_registry
from .models import LiveSession, Participant, AnswerSubmission
from .fsm import SessionFSM

logger = logging.getLogger(__name__)


class RoomCodeGenerator:
    """
    6 xonali unikal Game PIN kodlarini to'qnashuvsiz (collision-free) yaratuvchi xizmat.
    LIVE_SESSION.md §3.1 talabi.
    """
    @staticmethod
    def generate_unique_code() -> str:
        active_statuses = ['draft', 'lobby', 'in_progress', 'paused']
        for _ in range(20):
            code = f"{secrets.randbelow(900000) + 100000}"
            if not LiveSession.objects.filter(room_code=code, status__in=active_statuses).exists():
                return code
        raise RuntimeError("Unikal xona PIN kodini generatsiya qilib bo'lmadi (Zaxira to'lgan).")


class SessionService:
    """
    Jonli sessiyalarni boshqarish bo'yicha asosiy domen servisi.
    """

    @staticmethod
    @transaction.atomic
    def create_session(
        quiz: Quiz,
        host,
        game_mode: str = 'classic',
        settings_payload: Optional[Dict] = None
    ) -> LiveSession:
        """
        Yangi jonli sessiya ochish.
        1. Quizning joriy holatidan versiya snapshotini muzlatadi.
        2. 6 xonali unikal PIN yaratadi.
        3. Holatini 'lobby' ga o'tkazadi.
        """
        # Quiz snapshotini muzlatish
        QuizService.create_version_snapshot(quiz)

        room_code = RoomCodeGenerator.generate_unique_code()
        session = LiveSession.objects.create(
            quiz=quiz,
            host=host,
            room_code=room_code,
            game_mode=game_mode,
            status='lobby',
            settings_payload=settings_payload or {
                'speed_bonus': True,
                'show_leaderboard': True,
            }
        )
        logger.info(f"Yangi sessiya yaratildi: #{room_code} (Host: {host.username}, Quiz: {quiz.title})")
        return session

    @staticmethod
    @transaction.atomic
    def join_session(room_code: str, nickname: str) -> Tuple[Participant, LiveSession, str]:
        """
        Talaba xonaga qo'shilishi (PIN va Ism orqali).
        REALTIME_PROTOCOL.md §2 talabi: ticket/token qaytarish.
        """
        clean_code = str(room_code).strip()
        clean_nickname = str(nickname).strip()

        if not clean_code or not clean_nickname:
            raise ValidationError("Xona PIN kodi va ism kiritilishi shart.")

        session = LiveSession.objects.filter(room_code=clean_code).first()
        if not session:
            raise ValidationError(f"#{clean_code} raqamli xona topilmadi.")

        if session.status in ('completed', 'cancelled'):
            raise ValidationError("Ushbu dars sessiyasi allaqachon yakunlangan.")

        if session.status == 'lobby' and session.is_lobby_locked:
            raise ValidationError("Xona o'qituvchi tomonidan qulflangan (ROOM_LOCKED).")

        # Mavjud o'quvchini qidirish (Reconnection holati)
        participant = Participant.objects.filter(session=session, nickname=clean_nickname).first()

        if participant:
            # Qayta ulandi
            participant.is_connected = True
            participant.save(update_fields=['is_connected'])
            logger.info(f"Ishtirokchi qayta ulandi: {clean_nickname} (Xona #{clean_code})")
        else:
            # Yangi ishtirokchi
            token = secrets.token_hex(32)
            participant = Participant.objects.create(
                session=session,
                nickname=clean_nickname,
                anonymous_token=token,
                score=0,
                is_connected=True
            )
            logger.info(f"Yangi ishtirokchi qo'shildi: {clean_nickname} (Xona #{clean_code})")

        return participant, session, participant.anonymous_token

    @staticmethod
    @transaction.atomic
    def submit_answer(
        session: LiveSession,
        participant: Participant,
        question_id: str,
        submitted_payload: Any,
        client_ts: Optional[float] = None
    ) -> AnswerSubmission:
        """
        O'quvchi javobini qabul qilish va server-authoritative baholash.
        """
        now = time.time()

        # 1. Server taymer deadline tekshiruvi
        if session.current_question_deadline and now > session.current_question_deadline:
            raise ValidationError("Vaqt tugadi! Ushbu savolga javob berish muddati o'tgan.")

        # 2. Savolni topish
        question = Question.objects.filter(id=question_id, quiz=session.quiz).first()
        if not question:
            raise ValidationError(f"Savol ID '{question_id}' topilmadi.")

        # 3. Oldin javob berilganmi tekshirish (Idempotency)
        existing = AnswerSubmission.objects.filter(
            session=session,
            participant=participant,
            question_id=question.id
        ).first()
        if existing:
            return existing

        # 4. QuestionTypeRegistry orqali baholash
        handler = question_registry.get(question.type)
        eval_res = handler.evaluate_answer(
            submitted_answer=submitted_payload,
            correct_answer=question.correct_answer,
            max_points=question.points,
            accepted_alternatives=question.accepted_alternatives
        )

        response_time_ms = int((now - client_ts) * 1000) if client_ts else 0

        # 5. Ballarni hisoblash (ScoringEngine & RedisLeaderboard)
        from apps.game_engine.scoring import ScoringEngine
        from apps.game_engine.leaderboard import RedisLeaderboard

        time_elapsed = None
        time_limit = None
        if session.current_question_deadline:
            time_limit = float(question.time_limit_seconds)
            time_remaining = max(0.0, session.current_question_deadline - now)
            time_elapsed = max(0.0, time_limit - time_remaining)

        partial_ratio = (eval_res.score / question.points) if question.points > 0 else 1.0
        calc = ScoringEngine.calculate_score(
            is_correct=eval_res.is_correct,
            base_points=question.points,
            time_elapsed=time_elapsed,
            time_limit=time_limit,
            streak=participant.streak,
            scoring_mode='speed_accuracy',
            partial_ratio=partial_ratio
        )

        awarded_points = calc['points_awarded']
        participant.streak = calc['streak']
        participant.score += awarded_points
        participant.save(update_fields=['score', 'streak'])

        # Redis Shohsupasini (Leaderboard) real-vaqtda yangilash
        try:
            RedisLeaderboard().update_score(str(session.id), str(participant.id), participant.score)
        except Exception as e:
            logger.warning(f"Leaderboard yangilashda ogohlantirish: {e}")

        submission = AnswerSubmission.objects.create(
            session=session,
            participant=participant,
            question_id=question.id,
            submitted_payload=submitted_payload,
            is_correct=eval_res.is_correct,
            points_awarded=awarded_points,
            response_time_ms=max(0, response_time_ms)
        )

        return submission


class ReconnectionManager:
    """
    Qayta ulanish va uzilishdan keyin holatni tiklash menejeri.
    RECONNECTION.md §4 asosida.
    """
    @staticmethod
    def get_session_snapshot(session: LiveSession, participant: Optional[Participant] = None) -> Dict[str, Any]:
        """
        Uzilib qaytgan mijoz uchun butun joriy xona holati snapshotini shakllantirish.
        """
        questions = list(session.quiz.questions.order_by('order_index'))
        total_questions = len(questions)

        current_q_data = None
        if 0 <= session.current_question_index < total_questions:
            current_q = questions[session.current_question_index]
            handler = question_registry.get(current_q.type)
            current_q_data = {
                'question_id': str(current_q.id),
                'question_index': session.current_question_index,
                'type': current_q.type,
                'prompt': current_q.prompt,
                'media_url': current_q.media_url,
                'options': handler.sanitize_for_student(current_q.options),
                'time_limit_seconds': current_q.time_limit_seconds,
                'deadline_ts': session.current_question_deadline,
            }

        return {
            'session_id': str(session.id),
            'room_code': session.room_code,
            'status': session.status,
            'game_mode': session.game_mode,
            'current_question_index': session.current_question_index,
            'total_questions': total_questions,
            'current_question': current_q_data,
            'participant': {
                'nickname': participant.nickname,
                'score': participant.score,
                'streak': participant.streak
            } if participant else None,
            'server_ts': int(time.time() * 1000),
        }
