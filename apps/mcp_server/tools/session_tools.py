# ============================================================
# EduSelf Teacher — apps/mcp_server/tools/session_tools.py
# Category 2: Live Session Control MCP Tools
# MCP_TOOLS.md DOC-82 asosida
# ============================================================
from typing import Dict, Any, Optional
from asgiref.sync import sync_to_async

from apps.quizzes.models import Quiz
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.live_sessions.services import RoomCodeGenerator
from apps.live_sessions.fsm import SessionFSM, SessionStateError
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import (
    require_scope,
    SCOPE_SESSION_CREATE,
    SCOPE_SESSION_CONTROL,
    SCOPE_SESSION_READ,
)
from apps.mcp_server.exceptions import (
    MCPResourceNotFoundError,
    MCPForbiddenError,
    MCPInvalidSessionStateError,
    MCPConfirmationRequiredError,
)


def _check_session_access(session: LiveSession, user) -> None:
    """Zero-Bypass: Faqat sessiya egasi (host) uni boshqara oladi."""
    if session.host_id != user.id:
        if user.role == 'school_admin' and user.organization_id and getattr(session.host, 'organization_id', None) == user.organization_id:
            return
        raise MCPForbiddenError(
            f"Siz ushbu sessiyaning ({session.id}) boshqaruvchisi emassiz! (Multi-tenant izolyatsiyasi)"
        )


@sync_to_async
def _create_live_session_sync(user, quiz_id: str, game_mode: str, team_mode_enabled: bool) -> Dict[str, Any]:
    try:
        quiz = Quiz.objects.get(id=quiz_id)
    except (Quiz.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Quiz ID '{quiz_id}' topilmadi.")

    if quiz.owner_id != user.id and user.role != 'school_admin':
        raise MCPForbiddenError("Boshqa o'qituvchining viktorinasiga asoslangan sessiya ochish taqiqlangan.")

    room_code = RoomCodeGenerator.generate_unique_code()
    session = LiveSession.objects.create(
        host=user,
        quiz=quiz,
        room_code=room_code,
        game_mode=game_mode,
        status='lobby',
        settings_payload={"team_mode_enabled": team_mode_enabled},
    )

    return {
        "session_id": str(session.id),
        "pin": session.room_code,
        "join_url": f"https://join.eduself.uz/{session.room_code}",
        "status": session.status,
        "game_mode": session.game_mode,
    }


@require_scope(SCOPE_SESSION_CREATE)
async def create_live_session(
    quiz_id: str,
    game_mode: str = "classic",
    team_mode_enabled: bool = False
) -> Dict[str, Any]:
    """
    Tanlangan viktorina va o'yin rejimi bo'yicha jonli dars xonasi yaratadi.
    """
    ctx = get_current_mcp_context()
    return await _create_live_session_sync(ctx.user, quiz_id, game_mode, team_mode_enabled)


@sync_to_async
def _get_session_status_sync(user, session_id: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz', 'host').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    connected_count = session.participants.filter(is_connected=True).count()
    total_count = session.participants.count()

    return {
        "session_id": str(session.id),
        "room_code": session.room_code,
        "status": session.status,
        "game_mode": session.game_mode,
        "current_question_index": session.current_question_index,
        "connected_students": connected_count,
        "total_joined_students": total_count,
    }


@require_scope(SCOPE_SESSION_READ)
async def get_session_status(session_id: str) -> Dict[str, Any]:
    """
    Jonli sessiyaning joriy holati va ulangan o'quvchilar sonini olish.
    """
    ctx = get_current_mcp_context()
    return await _get_session_status_sync(ctx.user, session_id)


@sync_to_async
def _start_session_sync(user, session_id: str, confirm: bool) -> Dict[str, Any]:
    if not confirm:
        raise MCPConfirmationRequiredError("O'yinni boshlash uchun o'qituvchi tasdig'i ('confirm=True') talab qilinadi.")

    try:
        session = LiveSession.objects.get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    try:
        SessionFSM.transition(session, 'in_progress')
    except SessionStateError as e:
        raise MCPInvalidSessionStateError(
            f"Sessiyani boshlab bo'lmaydi: {str(e)}",
            data={"current_state": session.status, "session_id": str(session.id)}
        )

    session.current_question_index = 0
    session.save(update_fields=['current_question_index'])

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "message": "Jonli o'yin muvaffaqiyatli boshlandi!",
    }


@require_scope(SCOPE_SESSION_CONTROL)
async def start_session(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    """
    Lobbini yopib, 1-savolni ishga tushirish (destructiveHint: True).
    """
    ctx = get_current_mcp_context()
    return await _start_session_sync(ctx.user, session_id, confirm)


@sync_to_async
def _advance_question_sync(user, session_id: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    if session.status != 'in_progress':
        raise MCPInvalidSessionStateError(f"Sessiya faol emas ({session.status}). Savollarni surib bo'lmaydi.")

    total_questions = session.quiz.questions.count()
    next_index = session.current_question_index + 1

    if next_index >= total_questions:
        try:
            SessionFSM.transition(session, 'completed')
        except SessionStateError:
            pass
        return {
            "session_id": str(session.id),
            "status": session.status,
            "current_question_index": session.current_question_index,
            "is_last_question": True,
            "message": "Barcha savollar tugadi, o'yin yakunlandi.",
        }

    session.current_question_index = next_index
    session.save(update_fields=['current_question_index'])

    return {
        "session_id": str(session.id),
        "status": session.status,
        "current_question_index": session.current_question_index,
        "total_questions": total_questions,
    }


@require_scope(SCOPE_SESSION_CONTROL)
async def advance_question(session_id: str) -> Dict[str, Any]:
    """
    Keyingi savolga o'tish.
    """
    ctx = get_current_mcp_context()
    return await _advance_question_sync(ctx.user, session_id)


@sync_to_async
def _reveal_answers_sync(user, session_id: str, confirm: bool) -> Dict[str, Any]:
    if not confirm:
        raise MCPConfirmationRequiredError("Javoblarni oshkor qilish uchun tasdiq zarur.")

    try:
        session = LiveSession.objects.get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    if session.status != 'in_progress':
        raise MCPInvalidSessionStateError(f"Sessiya faol holatda emas ({session.status}).")

    session.settings_payload["answers_revealed"] = True
    session.save(update_fields=['settings_payload'])

    return {
        "session_id": str(session.id),
        "status": session.status,
        "revealed": True,
    }


@require_scope(SCOPE_SESSION_CONTROL)
async def reveal_answers(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    """
    Savolni yopib, proyektor va o'quvchilar ekranida to'g'ri javobni oshkor qilish (destructiveHint: True).
    """
    ctx = get_current_mcp_context()
    return await _reveal_answers_sync(ctx.user, session_id, confirm)


@sync_to_async
def _end_session_sync(user, session_id: str, confirm: bool) -> Dict[str, Any]:
    if not confirm:
        raise MCPConfirmationRequiredError("Sessiyani yakunlash uchun o'qituvchi tasdig'i talab qilinadi.")

    try:
        session = LiveSession.objects.get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    try:
        SessionFSM.transition(session, 'completed')
    except SessionStateError as e:
        raise MCPInvalidSessionStateError(f"Sessiyani tugatib bo'lmaydi: {str(e)}")

    return {
        "session_id": str(session.id),
        "status": session.status,
        "is_finished": True,
        "message": "Jonli dars yakunlandi.",
    }


@require_scope(SCOPE_SESSION_CONTROL)
async def end_session(session_id: str, confirm: bool = True) -> Dict[str, Any]:
    """
    Sessiyani yakunlash, yakuniy reytingni ko'rsatish va xonani yopish (destructiveHint: True).
    """
    ctx = get_current_mcp_context()
    return await _end_session_sync(ctx.user, session_id, confirm)


@sync_to_async
def _get_live_results_sync(user, session_id: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    participants = session.participants.all().order_by('-score')[:10]
    leaderboard = [
        {"nickname": p.nickname, "score": p.score, "team": p.team_name}
        for p in participants
    ]

    total_submissions = AnswerSubmission.objects.filter(session=session).count()
    correct_submissions = AnswerSubmission.objects.filter(session=session, is_correct=True).count()
    accuracy = (correct_submissions / total_submissions * 100) if total_submissions > 0 else 0.0

    return {
        "session_id": str(session.id),
        "status": session.status,
        "total_submissions": total_submissions,
        "accuracy_percentage": round(accuracy, 1),
        "top_leaderboard": leaderboard,
    }


@require_scope(SCOPE_SESSION_READ)
async def get_live_results(session_id: str) -> Dict[str, Any]:
    """
    Joriy savol va sessiya bo'yicha oraliq natijalar statistikasini olish.
    """
    ctx = get_current_mcp_context()
    return await _get_live_results_sync(ctx.user, session_id)


# Aliases
start_live_session = start_session
