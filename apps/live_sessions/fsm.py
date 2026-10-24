from typing import Optional
from django.utils import timezone


class FSMError(Exception):
    """Base exception for LiveSession FSM errors."""
    pass


class InvalidFSMTransitionError(FSMError):
    """Raised when an invalid FSM state transition is attempted."""
    pass


class SessionStateMachine:
    """
    Finite State Machine for Live Sessions.
    Guarantees strict, server-authoritative state transitions between
    Lobby, Active gameplay rounds, Pause, and Conclusion.
    """

    ALLOWED_STATUS_TRANSITIONS = {
        "draft": {"lobby", "cancelled"},
        "lobby": {"active", "cancelled"},
        "active": {"paused", "completed", "cancelled"},
        "paused": {"active", "cancelled"},
        "completed": set(),  # Terminal state
        "cancelled": set(),  # Terminal state
    }

    ALLOWED_FSM_STATE_TRANSITIONS = {
        "lobby": {"question_preview", "question_open"},
        "question_preview": {"question_open", "paused"},
        "question_open": {"question_closed", "paused"},
        "question_closed": {"answer_reveal", "round_leaderboard", "question_preview", "summary", "paused"},
        "answer_reveal": {"round_leaderboard", "question_preview", "question_open", "summary", "paused"},
        "round_leaderboard": {"question_preview", "question_open", "summary", "paused"},
        "summary": {"lobby"},  # or transitions to completed
    }

    @classmethod
    def can_transition_status(cls, current_status: str, target_status: str) -> bool:
        allowed = cls.ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
        return target_status in allowed

    @classmethod
    def can_transition_fsm_state(cls, current_fsm: str, target_fsm: str) -> bool:
        allowed = cls.ALLOWED_FSM_STATE_TRANSITIONS.get(current_fsm, set())
        return target_fsm in allowed

    @classmethod
    def transition(
        cls,
        session,
        target_status: Optional[str] = None,
        target_fsm_state: Optional[str] = None,
        save: bool = True,
    ) -> None:
        """
        Transitions the session status and/or fsm_state.
        Validates transition rules; raises InvalidFSMTransitionError on violations.
        """
        # Status transition
        if target_status and target_status != session.status:
            if not cls.can_transition_status(session.status, target_status):
                raise InvalidFSMTransitionError(
                    f"Cannot transition session status from '{session.status}' to '{target_status}'."
                )
            session.status = target_status

            if target_status == "active" and not session.started_at:
                session.started_at = timezone.now()
            elif target_status in ("completed", "cancelled") and not session.ended_at:
                session.ended_at = timezone.now()

        # Inner FSM state transition
        if target_fsm_state and target_fsm_state != session.fsm_state:
            # When pausing, allow keeping the inner fsm_state
            if session.status == "active" or target_status == "active":
                if not cls.can_transition_fsm_state(session.fsm_state, target_fsm_state):
                    raise InvalidFSMTransitionError(
                        f"Cannot transition FSM inner state from '{session.fsm_state}' to '{target_fsm_state}'."
                    )
            session.fsm_state = target_fsm_state

        if save:
            session.save()

    @classmethod
    def start_lobby(cls, session) -> None:
        cls.transition(session, target_status="lobby", target_fsm_state="lobby")

    @classmethod
    def start_game(cls, session) -> None:
        cls.transition(session, target_status="active", target_fsm_state="question_preview")

    @classmethod
    def open_question(cls, session) -> None:
        cls.transition(session, target_status="active", target_fsm_state="question_open")

    @classmethod
    def close_question(cls, session) -> None:
        cls.transition(session, target_status="active", target_fsm_state="question_closed")

    @classmethod
    def reveal_answers(cls, session) -> None:
        cls.transition(session, target_status="active", target_fsm_state="answer_reveal")

    @classmethod
    def show_leaderboard(cls, session) -> None:
        cls.transition(session, target_status="active", target_fsm_state="round_leaderboard")

    @classmethod
    def pause(cls, session) -> None:
        cls.transition(session, target_status="paused")

    @classmethod
    def resume(cls, session) -> None:
        cls.transition(session, target_status="active")

    @classmethod
    def end_game(cls, session) -> None:
        cls.transition(session, target_status="completed", target_fsm_state="summary")

    @classmethod
    def cancel(cls, session) -> None:
        cls.transition(session, target_status="cancelled")
