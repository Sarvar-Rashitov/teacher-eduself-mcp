"""
Live Session Management MCP Tools (Tools 7–13).
Conforms to DOC-82 (MCP_TOOLS.md) and DOC-86 (MCP_SECURITY.md).
"""

import uuid
from typing import Any, Dict, Optional

from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.live_sessions.services import LiveSessionService
from apps.live_sessions.fsm import SessionStateMachine, InvalidStateTransitionError
from apps.quizzes.models import Quiz

from ..auth import get_current_mcp_context
from ..scopes import (
    require_scope,
    SCOPE_SESSION_CREATE,
    SCOPE_SESSION_READ,
    SCOPE_SESSION_CONTROL,
)
from ..exceptions import (
    MCPNotFoundError,
    MCPForbiddenError,
    MCPInvalidParamsError,
    MCPInvalidSessionStateError,
)


def _get_teacher_session(session_id: str) -> LiveSession:
    """Sessiyani multi-tenant izolyatsiyasini tekshirib oladi."""
    context = get_current_mcp_context()
    try:
        session_uuid = uuid.UUID(str(session_id))
    except (ValueError, TypeError):
        raise MCPInvalidParamsError(f"Yaroqsiz session_id: {session_id}")

    session = LiveSession.objects.filter(id=session_uuid).select_related("quiz", "host").first()
    if not session:
        raise MCPNotFoundError(f"Jonli sessiya topilmadi: {session_id}")

    if session.host_id != context.user.id and not context.user.is_superuser:
        raise MCPForbiddenError("Boshqa o'qituvchining jonli sessiyasini boshqarish taqiqlangan!")

    return session


@require_scope(SCOPE_SESSION_CREATE)
def create_live_session(
    quiz_id: str,
    game_mode: str = "classic",
    team_mode_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Tanlangan viktorina va o'yin rejimi bo'yicha yangi jonli sessiya (xona) ochadi.
    Scope: session:create
    """
    context = get_current_mcp_context()
    try:
        quiz_uuid = uuid.UUID(str(quiz_id))
    except (ValueError, TypeError):
        raise MCPInvalidParamsError(f"Yaroqsiz quiz_id: {quiz_id}")

    quiz = Quiz.objects.filter(id=quiz_uuid).first()
    if not quiz:
        raise MCPNotFoundError(f"Viktorina topilmadi: {quiz_id}")

    if quiz.owner_id != context.user.id and not context.user.is_superuser:
        raise MCPForbiddenError("Boshqa o'qituvchining viktorinasidan sessiya ochish taqiqlangan!")

    settings_payload = {
        "game_mode": game_mode,
        "team_mode_enabled": team_mode_enabled,
        "created_via": "mcp",
    }

    session = LiveSessionService.create_session(
        quiz=quiz,
        host=context.user,
        game_mode=game_mode,
        settings_payload=settings_payload,
    )

    return {
        "session_id": str(session.id),
        "pin": session.room_code,
        "join_url": f"https://join.eduself.uz/{session.room_code}",
        "status": session.status,
        "game_mode": session.game_mode,
        "quiz_title": quiz.title,
    }


@require_scope(SCOPE_SESSION_READ)
def get_session_status(session_id: str) -> Dict[str, Any]:
    """
    Jonli sessiyaning joriy holati, fazasi va ulangan o'quvchilar sonini oladi.
    Scope: session:read
    """
    session = _get_teacher_session(session_id)
    fsm = SessionStateMachine(session)

    total_questions = session.quiz.questions.count()
    connected_students = session.participants.filter(is_connected=True, is_kicked=False).count()
    total_participants = session.participants.count()

    return {
        "session_id": str(session.id),
        "pin": session.room_code,
        "status": session.status,
        "current_phase": fsm.current_phase,
        "current_question_index": session.current_question_index,
        "total_questions": total_questions,
        "connected_students": connected_students,
        "total_participants": total_participants,
        "game_mode": session.game_mode,
    }


@require_scope(SCOPE_SESSION_CONTROL)
def start_session(session_id: str, confirmed: bool = False) -> Dict[str, Any]:
    """
    Lobbini yopib, jonli darsni va birinchi savolni boshlaydi.
    Scope: session:control
    DestructiveHint: True
    """
    session = _get_teacher_session(session_id)
    fsm = SessionStateMachine(session)

    if session.status != LiveSession.STATUS_LOBBY:
        raise MCPInvalidSessionStateError(
            f"Sessiyani faqat 'lobby' holatidan boshlash mumkin. Joriy holat: {session.status}",
            data={"current_state": session.status, "allowed_actions": ["get_session_status", "end_session"]}
        )

    try:
        fsm.start_session()
        # Birinchi savolni ochish
        total_questions = session.quiz.questions.count()
        if total_questions > 0:
            first_q = session.quiz.questions.order_by("order_index").first()
            time_limit = first_q.time_limit_seconds if first_q else 30
            fsm.open_question(question_index=0, time_limit_seconds=time_limit)
    except InvalidStateTransitionError as ex:
        raise MCPInvalidSessionStateError(str(ex))

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_phase": fsm.current_phase,
        "current_question_index": session.current_question_index,
        "message": "Sessiya muvaffaqiyatli boshlandi.",
    }


@require_scope(SCOPE_SESSION_CONTROL)
def advance_question(session_id: str) -> Dict[str, Any]:
    """
    Keyingi savolga yoki natijalar fazasiga o'tish.
    Scope: session:control
    """
    session = _get_teacher_session(session_id)
    fsm = SessionStateMachine(session)

    if session.status != LiveSession.STATUS_ACTIVE:
        raise MCPInvalidSessionStateError(
            f"Savolni faqat 'active' sessiyada surish mumkin. Joriy holat: {session.status}"
        )

    questions = session.quiz.questions.order_by("order_index")
    total_questions = questions.count()
    next_index = session.current_question_index + 1

    try:
        if next_index < total_questions:
            next_q = questions[next_index]
            time_limit = next_q.time_limit_seconds or 30
            fsm.open_question(question_index=next_index, time_limit_seconds=time_limit)
            message = f"Savol #{next_index + 1} ochildi."
        else:
            # Barcha savollar tugadi, xulosa fazasiga o'tamiz
            fsm.show_summary()
            message = "Barcha savollar yakunlandi. Xulosa ko'rsatilmoqda."
    except InvalidStateTransitionError as ex:
        raise MCPInvalidSessionStateError(str(ex))

    return {
        "session_id": str(session.id),
        "current_question_index": session.current_question_index,
        "current_phase": fsm.current_phase,
        "status": session.status,
        "message": message,
    }


@require_scope(SCOPE_SESSION_CONTROL)
def reveal_answers(session_id: str, confirmed: bool = False) -> Dict[str, Any]:
    """
    Savol javoblarini qabul qilishni yopib, to'g'ri javobni oshkor qiladi.
    Scope: session:control
    DestructiveHint: True
    """
    session = _get_teacher_session(session_id)
    fsm = SessionStateMachine(session)

    if session.status != LiveSession.STATUS_ACTIVE:
        raise MCPInvalidSessionStateError("Faqat faol sessiyada javoblarni ochish mumkin.")

    try:
        fsm.reveal_answer()
    except InvalidStateTransitionError as ex:
        raise MCPInvalidSessionStateError(str(ex))

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_phase": fsm.current_phase,
        "message": "To'g'ri javoblar oshkor qilindi.",
    }


@require_scope(SCOPE_SESSION_CONTROL)
def end_session(session_id: str, confirmed: bool = False) -> Dict[str, Any]:
    """
    Jonli sessiyani to'liq yakunlaydi va xonani yopadi.
    Scope: session:control
    DestructiveHint: True
    """
    session = _get_teacher_session(session_id)
    fsm = SessionStateMachine(session)

    try:
        fsm.complete()
    except InvalidStateTransitionError as ex:
        raise MCPInvalidSessionStateError(str(ex))

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_phase": fsm.current_phase,
        "message": "Sessiya muvaffaqiyatli yakunlandi.",
    }


@require_scope(SCOPE_SESSION_READ)
def get_live_results(session_id: str) -> Dict[str, Any]:
    """
    Joriy savol bo'yicha ishtirokchilar javoblari va natijalar statistikasini oladi.
    Scope: session:read
    """
    session = _get_teacher_session(session_id)
    current_index = session.current_question_index

    questions = list(session.quiz.questions.order_by("order_index"))
    submissions = AnswerSubmission.objects.filter(session=session)
    if 0 <= current_index < len(questions):
        current_q = questions[current_index]
        submissions = submissions.filter(question=current_q)

    submissions = submissions.select_related("participant")
    total_submissions = submissions.count()
    correct_submissions = submissions.filter(is_correct=True).count()

    options_distribution: Dict[str, int] = {}
    for sub in submissions:
        data = sub.response_data
        if isinstance(data, dict):
            raw_ans = str(data.get("selected") or data.get("answer") or data)
        else:
            raw_ans = str(data)
        options_distribution[raw_ans] = options_distribution.get(raw_ans, 0) + 1

    return {
        "session_id": str(session.id),
        "current_question_index": current_index,
        "total_submissions": total_submissions,
        "correct_count": correct_submissions,
        "accuracy_percentage": round((correct_submissions / total_submissions * 100), 1) if total_submissions > 0 else 0.0,
        "options_distribution": options_distribution,
    }
