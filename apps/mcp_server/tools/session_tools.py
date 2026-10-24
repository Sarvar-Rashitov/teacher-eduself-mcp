"""
MCP Live Session Management Tools according to DOC-82 (MCP_TOOLS.md).
Zero-Bypass architecture: interacts strictly through LiveSessionService and SessionStateMachine.
"""

from typing import Any, Dict, Optional
from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.live_sessions.services import LiveSessionService
from apps.live_sessions.fsm import SessionStateMachine, SessionState, InvalidStateTransitionError
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import Scopes, require_scope, destructive_operation
from apps.mcp_server.exceptions import (
    MCPNotFoundError,
    MCPForbiddenError,
    MCPInvalidSessionStateError,
)


def _get_session_with_ownership_check(session_id: str, current_user: Any) -> LiveSession:
    """Sessiya topilishi va faqat o'z o'qituvchisiga tegishli ekanligini tekshirish."""
    session = LiveSession.objects.select_related("quiz", "host").filter(id=session_id).first()
    if not session:
        raise MCPNotFoundError(f"Jonli sessiya topilmadi: {session_id}")

    if session.host_id != current_user.id:
        raise MCPForbiddenError("Boshqa o'qituvchining jonli darsini boshqarish taqiqlangan.")

    return session


@require_scope(Scopes.SESSION_CREATE)
def create_live_session(
    quiz_id: str,
    game_mode: str = "classic",
    team_mode_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Tanlangan viktorina va o'yin rejimi bo'yicha yangi jonli xona (Live Session) yaratadi.
    """
    ctx = get_current_mcp_context()

    quiz = Quiz.objects.filter(id=quiz_id).first()
    if not quiz:
        raise MCPNotFoundError(f"Viktorina topilmadi: {quiz_id}")

    if quiz.owner_id != ctx.user.id:
        raise MCPForbiddenError("Boshqa o'qituvchining viktorinasi bilan sessiya ochish taqiqlangan.")

    settings_payload = {
        "team_mode_enabled": team_mode_enabled,
        "mcp_created": True,
    }

    session = LiveSessionService.create_session(
        host=ctx.user,
        quiz=quiz,
        game_mode=game_mode,
        settings_payload=settings_payload,
    )

    return {
        "session_id": str(session.id),
        "pin": session.room_code,
        "join_url": f"https://join.eduself.uz/{session.room_code}",
        "status": session.status,
        "game_mode": session.game_mode,
    }


@require_scope(Scopes.SESSION_READ)
def get_session_status(session_id: str) -> Dict[str, Any]:
    """
    Jonli sessiyaning joriy holati va ulangan o'quvchilar sonini olish.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    connected_count = session.participants.filter(is_connected=True).count()
    total_count = session.participants.count()

    return {
        "session_id": str(session.id),
        "pin": session.room_code,
        "status": session.status,
        "game_mode": session.game_mode,
        "current_question_index": session.current_question_index,
        "total_questions": session.quiz.questions.count(),
        "connected_students": connected_count,
        "total_students": total_count,
        "is_locked": session.is_locked,
    }


@destructive_operation
@require_scope(Scopes.SESSION_CONTROL)
def start_session(session_id: str) -> Dict[str, Any]:
    """
    Lobbini yopib, jonli darsni va 1-savolni ishga tushirish (Destructive hint: True).
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    if session.status != SessionState.LOBBY:
        raise MCPInvalidSessionStateError(
            f"Faqat lobbida turgan sessiyani boshlash mumkin. Joriy holat: {session.status}",
            current_state=session.status,
            allowed_actions=["get_session_status"],
        )

    SessionStateMachine.start_game(session)
    session.current_question_index = 0
    session.save(update_fields=["current_question_index"])

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "message": "Jonli o'yin muvaffaqiyatli boshlandi!",
    }


@require_scope(Scopes.SESSION_CONTROL)
def advance_question(session_id: str) -> Dict[str, Any]:
    """
    Keyingi savolga o'tish.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    if session.status != SessionState.ACTIVE:
        raise MCPInvalidSessionStateError(
            f"Faqat faol sessiyada savolni almashtirish mumkin. Joriy holat: {session.status}",
            current_state=session.status,
        )

    total_questions = session.quiz.questions.count()
    next_index = session.current_question_index + 1

    if next_index >= total_questions:
        # Barcha savollar tugadi
        return {
            "session_id": str(session.id),
            "status": session.status,
            "current_question_index": session.current_question_index,
            "has_more_questions": False,
            "message": "Barcha savollar tugadi. Darsni yakunlash (end_session) mumkin.",
        }

    session.current_question_index = next_index
    session.save(update_fields=["current_question_index"])

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "total_questions": total_questions,
        "has_more_questions": True,
    }


@destructive_operation
@require_scope(Scopes.SESSION_CONTROL)
def reveal_answers(session_id: str) -> Dict[str, Any]:
    """
    Savolni yopib, proyektor va o'quvchilar ekranida to'g'ri javobni oshkor qilish (Destructive hint: True).
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    questions = list(session.quiz.questions.all().order_by("order_index"))
    idx = session.current_question_index
    current_q = questions[idx] if idx < len(questions) else None

    if not current_q:
        raise MCPNotFoundError("Joriy savol topilmadi.")

    submissions = AnswerSubmission.objects.filter(session=session, question=current_q)
    correct_count = submissions.filter(is_correct=True).count()
    total_submissions = submissions.count()

    return {
        "session_id": str(session.id),
        "question_index": idx,
        "question_prompt": current_q.prompt,
        "correct_answer": current_q.correct_answer,
        "total_submissions": total_submissions,
        "correct_count": correct_count,
        "accuracy_percentage": round((correct_count / total_submissions * 100), 1) if total_submissions > 0 else 0.0,
    }


@destructive_operation
@require_scope(Scopes.SESSION_CONTROL)
def end_session(session_id: str) -> Dict[str, Any]:
    """
    Sessiyani yakunlash, yakuniy reytingni ko'rsatish va xonani yopish (Destructive hint: True).
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    if session.status in (SessionState.COMPLETED, SessionState.CANCELLED):
        raise MCPInvalidSessionStateError(
            f"Sessiya allaqachon yakunlangan: {session.status}",
            current_state=session.status,
        )

    try:
        SessionStateMachine.complete_game(session)
    except InvalidStateTransitionError as e:
        raise MCPInvalidSessionStateError(str(e), current_state=session.status)

    top_participants = [
        {"nickname": p.nickname, "score": p.score, "streak": p.streak}
        for p in session.participants.all().order_by("-score")[:5]
    ]

    return {
        "session_id": str(session.id),
        "status": session.status,
        "total_participants": session.participants.count(),
        "top_podium": top_participants,
        "message": "Jonli dars muvaffaqiyatli yakunlandi!",
    }


@require_scope(Scopes.SESSION_READ)
def get_live_results(session_id: str) -> Dict[str, Any]:
    """
    Joriy savol bo'yicha kimlar qanday javob bergani statistikasini olish.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    questions = list(session.quiz.questions.all().order_by("order_index"))
    idx = session.current_question_index
    current_q = questions[idx] if idx < len(questions) else None

    submissions_list = []
    if current_q:
        submissions = AnswerSubmission.objects.filter(
            session=session, question=current_q
        ).select_related("participant")

        for s in submissions:
            submissions_list.append({
                "nickname": s.participant.nickname,
                "is_correct": s.is_correct,
                "score_awarded": s.score_awarded,
                "time_taken_ms": s.time_taken_ms,
            })

    top_scorers = [
        {"nickname": p.nickname, "score": p.score}
        for p in session.participants.all().order_by("-score")[:5]
    ]

    return {
        "session_id": str(session.id),
        "question_index": idx,
        "submissions_count": len(submissions_list),
        "submissions": submissions_list,
        "top_scorers": top_scorers,
    }
