from django.utils import timezone
from .models import LiveSession


class InvalidStateTransitionError(Exception):
    """Sessiya holati noto'g'ri o'zgartirilganda chiqariladi."""
    pass


class SessionState:
    DRAFT = "draft"
    LOBBY = "lobby"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class QuestionRoundState:
    PREVIEW = "preview"
    OPEN = "open"
    CLOSED = "closed"
    REVEAL = "reveal"
    LEADERBOARD = "leaderboard"


class SessionStateMachine:
    """
    Jonli sessiya holat mashinasi (Finite State Machine).
    Holatlar o'tishining qat'iy va xavfsiz qoidalarini ta'minlaydi.
    """

    # Ruxsat etilgan o'tishlar xaritasi
    ALLOWED_TRANSITIONS = {
        SessionState.DRAFT: {SessionState.LOBBY, SessionState.CANCELLED},
        SessionState.LOBBY: {SessionState.ACTIVE, SessionState.CANCELLED},
        SessionState.ACTIVE: {SessionState.PAUSED, SessionState.COMPLETED, SessionState.CANCELLED},
        SessionState.PAUSED: {SessionState.ACTIVE, SessionState.COMPLETED, SessionState.CANCELLED},
        SessionState.COMPLETED: set(),  # Yakuniy holat
        SessionState.CANCELLED: set(),  # Yakuniy holat
    }

    @classmethod
    def can_transition(cls, current_state: str, next_state: str) -> bool:
        return next_state in cls.ALLOWED_TRANSITIONS.get(current_state, set())

    @classmethod
    def transition(cls, session: LiveSession, next_state: str) -> LiveSession:
        if not cls.can_transition(session.status, next_state):
            raise InvalidStateTransitionError(
                f"Sessiya '{session.status}' holatidan '{next_state}' holatiga o'ta olmaydi."
            )

        session.status = next_state
        now = timezone.now()

        if next_state == SessionState.ACTIVE and not session.started_at:
            session.started_at = now
        elif next_state in (SessionState.COMPLETED, SessionState.CANCELLED) and not session.ended_at:
            session.ended_at = now

        session.save(update_fields=["status", "started_at", "ended_at"])
        return session

    @classmethod
    def open_lobby(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.LOBBY)

    @classmethod
    def start_game(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.ACTIVE)

    @classmethod
    def pause_game(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.PAUSED)

    @classmethod
    def resume_game(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.ACTIVE)

    @classmethod
    def complete_game(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.COMPLETED)

    @classmethod
    def cancel_game(cls, session: LiveSession) -> LiveSession:
        return cls.transition(session, SessionState.CANCELLED)

    @classmethod
    def set_lock(cls, session: LiveSession, locked: bool) -> LiveSession:
        session.is_locked = locked
        session.save(update_fields=["is_locked"])
        return session
