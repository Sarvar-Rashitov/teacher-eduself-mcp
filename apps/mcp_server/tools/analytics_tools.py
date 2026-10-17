# ============================================================
# EduSelf Teacher — apps/mcp_server/tools/analytics_tools.py
# Category 3: Games, Reports & Followup Activity MCP Tools
# MCP_TOOLS.md DOC-82 asosida
# ============================================================
from typing import Dict, Any, List
from asgiref.sync import sync_to_async

from django.db.models import Avg, Count, Q
from apps.quizzes.models import Quiz, Question
from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.game_engine.teams import TeamAllocator
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import (
    require_scope,
    SCOPE_SESSION_CREATE,
    SCOPE_REPORT_READ,
    SCOPE_QUIZ_WRITE,
)
from apps.mcp_server.exceptions import (
    MCPResourceNotFoundError,
    MCPForbiddenError,
    MCPContentValidationError,
)


def _check_session_access(session: LiveSession, user) -> None:
    if session.host_id != user.id:
        if user.role == 'school_admin' and user.organization_id and getattr(session.host, 'organization_id', None) == user.organization_id:
            return
        raise MCPForbiddenError(
            f"Sizda ushbu sessiya ({session.id}) hisobotlariga kirish huquqi yo'q!"
        )


@sync_to_async
def _create_team_game_sync(user, session_id: str, team_count: int, allocation_strategy: str) -> Dict[str, Any]:
    if not (2 <= team_count <= 8):
        raise MCPContentValidationError(f"Jamoalar soni 2 dan 8 gacha bo'lishi kerak, berildi: {team_count}")

    try:
        session = LiveSession.objects.prefetch_related('participants').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    participants = list(session.participants.all())
    participant_ids = [str(p.id) for p in participants]

    if not participant_ids:
        session.settings_payload["team_mode_enabled"] = True
        session.settings_payload["team_count"] = team_count
        session.settings_payload["allocation_strategy"] = allocation_strategy
        session.save(update_fields=['settings_payload'])
        return {
            "session_id": str(session.id),
            "team_count": team_count,
            "allocation_strategy": allocation_strategy,
            "assigned_students": 0,
            "message": "Jamoaviy o'yin rejimi sozlandi. O'quvchilar ulangach taqsimlanadi.",
        }

    team_names = [f"Jamoa {chr(65 + i)}" for i in range(team_count)]
    allocated_map = TeamAllocator.allocate_random_balanced(participant_ids, team_names)

    for p in participants:
        assigned = allocated_map.get(str(p.id))
        if assigned:
            p.team_name = assigned
            p.save(update_fields=['team_name'])

    session.settings_payload["team_mode_enabled"] = True
    session.settings_payload["team_count"] = team_count
    session.save(update_fields=['settings_payload'])

    return {
        "session_id": str(session.id),
        "team_count": team_count,
        "allocation_strategy": allocation_strategy,
        "assigned_students": len(participant_ids),
        "teams": team_names,
    }


@require_scope(SCOPE_SESSION_CREATE)
async def create_team_game(
    session_id: str,
    team_count: int = 2,
    allocation_strategy: str = "random"
) -> Dict[str, Any]:
    """
    O'quvchilarni jamoalarga bo'lib o'yin sozlamasini kiritish.
    """
    ctx = get_current_mcp_context()
    return await _create_team_game_sync(ctx.user, session_id, team_count, allocation_strategy)


@sync_to_async
def _create_anonymous_board_sync(user, session_id: str, board_title: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    session.settings_payload["anonymous_board"] = {
        "title": board_title,
        "is_active": True,
        "entries": [],
    }
    session.save(update_fields=['settings_payload'])

    return {
        "session_id": str(session.id),
        "board_title": board_title,
        "status": "active",
        "message": f"'{board_title}' anonim fikrlar doskasi ishga tushirildi.",
    }


@require_scope(SCOPE_SESSION_CREATE)
async def create_anonymous_board(
    session_id: str,
    board_title: str = "Fikrlar Doskasi"
) -> Dict[str, Any]:
    """
    Anonim fikrlar yoki Word Cloud doskasini ishga tushirish.
    """
    ctx = get_current_mcp_context()
    return await _create_anonymous_board_sync(ctx.user, session_id, board_title)


@sync_to_async
def _get_session_report_sync(user, session_id: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz', 'host').prefetch_related('participants').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    participants = list(session.participants.all().order_by('-score'))
    total_participants = len(participants)
    avg_score = (sum(p.score for p in participants) / total_participants) if total_participants > 0 else 0

    submissions = AnswerSubmission.objects.filter(session=session)
    total_submissions = submissions.count()
    correct_count = submissions.filter(is_correct=True).count()
    overall_accuracy = (correct_count / total_submissions * 100) if total_submissions > 0 else 0.0

    hard_questions = []
    if session.quiz:
        for q in session.quiz.questions.all():
            q_subs = submissions.filter(question_id=q.id)
            q_total = q_subs.count()
            if q_total > 0:
                q_correct = q_subs.filter(is_correct=True).count()
                error_rate = ((q_total - q_correct) / q_total) * 100
                if error_rate > 40:
                    hard_questions.append({
                        "question_id": str(q.id),
                        "order": q.order_index,
                        "prompt": q.prompt,
                        "error_rate": round(error_rate, 1),
                    })

    return {
        "session_id": str(session.id),
        "room_code": session.room_code,
        "status": session.status,
        "quiz_title": session.quiz.title if session.quiz else "Noma'lum",
        "total_participants": total_participants,
        "average_score": round(avg_score, 1),
        "overall_accuracy": round(overall_accuracy, 1),
        "most_difficult_questions": hard_questions,
        "top_students": [
            {"nickname": p.nickname, "score": p.score, "team": p.team_name}
            for p in participants[:5]
        ],
    }


@require_scope(SCOPE_REPORT_READ)
async def get_session_report(session_id: str) -> Dict[str, Any]:
    """
    Sessiya yakunlangach, sinfning umumiy o'zlashtirishi va xatolar tahlilini olish.
    """
    ctx = get_current_mcp_context()
    return await _get_session_report_sync(ctx.user, session_id)


@sync_to_async
def _generate_followup_activity_sync(user, session_id: str, question_count: int) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    if not session.quiz:
        raise MCPResourceNotFoundError("Sessiyaga biriktirilgan viktorina topilmadi.")

    new_quiz = Quiz.objects.create(
        owner=user,
        title=f"Mustahkamlash: {session.quiz.title}",
        description=f"{session.room_code} sessiyasidagi xatolar asosida avtomatik shakllantirilgan qayta takrorlash testi",
        subject=session.quiz.subject,
        grade_level=session.quiz.grade_level,
        locale=session.quiz.locale,
        status='draft',
        current_version=1,
    )

    questions = list(session.quiz.questions.all().order_by('order_index')[:question_count])
    for idx, q in enumerate(questions):
        Question.objects.create(
            quiz=new_quiz,
            type=q.type,
            prompt=q.prompt,
            options=q.options,
            correct_answer=q.correct_answer,
            order_index=idx,
            time_limit_seconds=q.time_limit_seconds,
            points=q.points,
        )

    return {
        "followup_quiz_id": str(new_quiz.id),
        "quiz_title": new_quiz.title,
        "questions_count": len(questions),
        "based_on_session": str(session.id),
        "status": "draft",
    }


@require_scope(SCOPE_QUIZ_WRITE, SCOPE_REPORT_READ)
async def generate_followup_activity(session_id: str, question_count: int = 5) -> Dict[str, Any]:
    """
    O'quvchilar ko'p adashgan mavzular bo'yicha mustahkamlovchi mini-viktorina yaratish.
    """
    ctx = get_current_mcp_context()
    return await _generate_followup_activity_sync(ctx.user, session_id, question_count)


@sync_to_async
def _export_results_sync(user, session_id: str, export_format: str) -> Dict[str, Any]:
    try:
        session = LiveSession.objects.select_related('quiz').prefetch_related('participants').get(id=session_id)
    except (LiveSession.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Sessiya ID '{session_id}' topilmadi.")

    _check_session_access(session, user)

    participants = session.participants.all().order_by('-score')
    records = []
    for rank, p in enumerate(participants, start=1):
        records.append({
            "rank": rank,
            "nickname": p.nickname,
            "score": p.score,
            "team": p.team_name or "",
            "is_connected": p.is_connected,
        })

    return {
        "session_id": str(session.id),
        "room_code": session.room_code,
        "format": export_format,
        "total_records": len(records),
        "data": records,
    }


@require_scope(SCOPE_REPORT_READ)
async def export_results(session_id: str, export_format: str = "json") -> Dict[str, Any]:
    """
    Sessiya natijalarini to'liq eksport qilish.
    """
    ctx = get_current_mcp_context()
    return await _export_results_sync(ctx.user, session_id, export_format)


# Aliases
get_quiz_analytics = get_session_report
