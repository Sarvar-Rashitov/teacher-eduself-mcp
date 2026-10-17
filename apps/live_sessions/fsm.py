# apps/live_sessions/fsm.py
# LIVE_SESSION.md §2: Session Lifecycle FSM
import logging
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import LiveSession

logger = logging.getLogger(__name__)


class SessionStateError(ValidationError):
    """Sessiya holati o'tishidagi noqonuniy harakat."""
    pass


class SessionFSM:
    """
    Sessiya Holat Mashinasi (Finite State Machine).
    Qat'iy server-authoritative o'tishlarni nazorat qiladi.
    """
    ALLOWED_TRANSITIONS = {
        'draft': {'lobby', 'cancelled'},
        'lobby': {'in_progress', 'cancelled'},
        'in_progress': {'paused', 'completed', 'cancelled'},
        'paused': {'in_progress', 'completed', 'cancelled'},
        'completed': set(),
        'cancelled': set(),
    }

    @classmethod
    def can_transition(cls, current_status: str, target_status: str) -> bool:
        """O'tish mumkinligini tekshirish."""
        allowed = cls.ALLOWED_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def transition(cls, session: LiveSession, target_status: str) -> LiveSession:
        """
        Sessiya holatini xavfsiz o'zgartirish.
        """
        current_status = session.status

        if current_status == target_status:
            return session

        if not cls.can_transition(current_status, target_status):
            msg = f"Noqonuniy holat o'tishi: '{current_status}' dan '{target_status}' ga o'tib bo'lmaydi."
            logger.warning(f"Sessiya #{session.room_code}: {msg}")
            raise SessionStateError(msg)

        session.status = target_status

        now = timezone.now()
        if target_status == 'in_progress' and not session.started_at:
            session.started_at = now
        elif target_status in ('completed', 'cancelled') and not session.ended_at:
            session.ended_at = now

        session.save(update_fields=['status', 'started_at', 'ended_at', 'updated_at'])
        logger.info(f"Sessiya #{session.room_code} holati o'zgardi: {current_status} -> {target_status}")

        return session
