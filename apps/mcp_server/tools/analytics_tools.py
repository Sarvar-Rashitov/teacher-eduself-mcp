"""
Games, Analytics and Follow-Up MCP Tools (Tools 14–17).
Conforms to DOC-82 (MCP_TOOLS.md).
"""

import uuid
from typing import Any, Dict, List, Optional
from django.db.models import Avg, Count

from apps.live_sessions.models import LiveSession, Participant, AnswerSubmission
from apps.quizzes.models import Quiz, Question
from apps.game_engine.teams import TeamAllocator, TeamIdentity

from ..auth import get_current_mcp_context
from ..scopes import (
    require_scope,
    SCOPE_SESSION_CREATE,
    SCOPE_REPORT_READ,
    SCOPE_QUIZ_WRITE,
)
from ..exceptions import (
    MCPNotFoundError,
    MCPForbiddenError,
    MCPInvalidParamsError,
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
        raise MCPForbiddenError("Boshqa o'qituvchining jonli sessiyasini tahlil qilish taqiqlangan!")

    return session


@require_scope(SCOPE_SESSION_CREATE)
def create_team_game(
    session_id: str,
    team_count: int = 2,
    allocation_strategy: str = "random",
) -> Dict[str, Any]:
    """
    O'quvchilarni jamoalarga taqsimlab, jamoaviy o'yin rejimini faollashtiradi.
    Scope: session:create
    """
    session = _get_teacher_session(session_id)
    if team_count < 2 or team_count > 8:
        raise MCPInvalidParamsError("Jamoalar soni 2 dan 8 gacha bo'lishi kerak.")

    participants = list(session.participants.filter(is_kicked=False))
    p_ids = [str(p.id) for p in participants]

    allocation = TeamAllocator.random_balanced_allocation(
        participant_ids=p_ids,
        num_teams=team_count,
    )

    # Participantlarga team_name yozish va metadata tayyorlash
    teams_summary = {}
    for team_id, members in allocation.items():
        meta = TeamIdentity.get_team_metadata(team_id)
        team_name = meta.get("name", team_id)
        teams_summary[team_name] = {
            "id": team_id,
            "name": team_name,
            "color": meta.get("color", "#3B82F6"),
            "icon": meta.get("icon", "⭐"),
            "members_count": len(members),
        }
        if members:
            Participant.objects.filter(id__in=members).update(team_name=team_name)

    session.settings_payload["team_mode_enabled"] = True
    session.settings_payload["teams"] = teams_summary
    session.save(update_fields=["settings_payload", "updated_at"])

    return {
        "session_id": str(session.id),
        "team_count": team_count,
        "allocation_strategy": allocation_strategy,
        "total_assigned_students": len(p_ids),
        "teams": list(teams_summary.values()),
    }


@require_scope(SCOPE_SESSION_CREATE)
def create_anonymous_board(
    session_id: str,
    board_title: str,
) -> Dict[str, Any]:
    """
    Jonli sessiya uchun anonim fikrlar yoki savollar doskasini faollashtiradi.
    Scope: session:create
    """
    session = _get_teacher_session(session_id)
    if not board_title or not board_title.strip():
        raise MCPInvalidParamsError("Doska sarlavhasi bo'sh bo'lishi mumkin emas.")

    board_payload = {
        "title": board_title.strip(),
        "is_active": True,
        "posts": [],
    }

    session.settings_payload["anonymous_board"] = board_payload
    session.save(update_fields=["settings_payload", "updated_at"])

    return {
        "session_id": str(session.id),
        "board_title": board_title.strip(),
        "status": "active",
        "message": "Anonim doska muvaffaqiyatli ishga tushirildi.",
    }


@require_scope(SCOPE_REPORT_READ)
def get_session_report(session_id: str) -> Dict[str, Any]:
    """
    Sessiya yakunlangach, sinfning umumiy o'zlashtirishi va eng ko'p xato qilingan savollar tahlilini oladi.
    Scope: report:read
    """
    session = _get_teacher_session(session_id)
    participants = session.participants.all()
    submissions = AnswerSubmission.objects.filter(session=session)

    total_participants = participants.count()
    total_answers = submissions.count()
    correct_answers = submissions.filter(is_correct=True).count()
    class_accuracy = round((correct_answers / total_answers * 100), 1) if total_answers > 0 else 0.0

    # Eng qiyin savollarni hisoblash
    questions = session.quiz.questions.order_by("order_index")
    question_stats = []
    for idx, q in enumerate(questions):
        q_subs = submissions.filter(question=q)
        q_total = q_subs.count()
        q_correct = q_subs.filter(is_correct=True).count()
        acc = round((q_correct / q_total * 100), 1) if q_total > 0 else 0.0
        question_stats.append({
            "order_index": idx + 1,
            "prompt": q.prompt,
            "type": q.type,
            "total_answers": q_total,
            "correct_answers": q_correct,
            "accuracy_percentage": acc,
        })

    # Eng kam to'g'ri topilgan savollar
    hardest_questions = sorted(question_stats, key=lambda x: x["accuracy_percentage"])[:3]

    # Eng yuqori ball to'plagan 5 o'quvchi
    top_performers = []
    for p in participants.order_by("-score")[:5]:
        top_performers.append({
            "nickname": p.nickname,
            "score": p.score,
            "streak": p.streak,
            "team_name": p.team_name,
        })

    return {
        "session_id": str(session.id),
        "quiz_title": session.quiz.title,
        "status": session.status,
        "total_participants": total_participants,
        "total_answers_submitted": total_answers,
        "class_accuracy_percentage": class_accuracy,
        "top_performers": top_performers,
        "hardest_questions": hardest_questions,
    }


@require_scope(SCOPE_QUIZ_WRITE, SCOPE_REPORT_READ)
def generate_followup_activity(
    session_id: str,
    title: str = "",
) -> Dict[str, Any]:
    """
    O'quvchilar ko'p adashgan savollar asosida keyingi dars uchun avtomatik mustahkamlovchi viktorina yaratadi.
    Scope: quiz:write and report:read
    """
    session = _get_teacher_session(session_id)
    context = get_current_mcp_context()

    submissions = AnswerSubmission.objects.filter(session=session)
    questions = list(session.quiz.questions.order_by("order_index"))

    hard_questions = []
    for idx, q in enumerate(questions):
        q_subs = submissions.filter(question=q)
        q_total = q_subs.count()
        q_correct = q_subs.filter(is_correct=True).count()
        acc = (q_correct / q_total * 100) if q_total > 0 else 0.0
        # Agar aniqlik 60% dan past bo'lsa yoki hali javob berilmagan bo'lsa
        if acc < 60.0:
            hard_questions.append(q)

    # Agar qiyin savollar topilmasa, asl viktorinadan dastlabki 3 ta savolni olamiz
    if not hard_questions and questions:
        hard_questions = questions[:min(3, len(questions))]

    quiz_title = title.strip() if title and title.strip() else f"Mustahkamlash: {session.quiz.title}"

    new_quiz = Quiz.objects.create(
        title=quiz_title,
        description=f"Sessiya {session.room_code} xatoliklari bo'yicha mustahkamlovchi amaliyot.",
        owner=context.user,
        subject=session.quiz.subject,
        grade_level=session.quiz.grade_level,
        locale=session.quiz.locale,
        status="draft",
    )

    for i, q in enumerate(hard_questions):
        Question.objects.create(
            quiz=new_quiz,
            type=q.type,
            prompt=q.prompt,
            options=q.options,
            correct_answer=q.correct_answer,
            explanation=q.explanation,
            points=q.points,
            time_limit_seconds=q.time_limit_seconds,
            order_index=i,
            is_locked=False,
        )

    return {
        "followup_quiz_id": str(new_quiz.id),
        "title": new_quiz.title,
        "question_count": new_quiz.questions.count(),
        "status": "DRAFT",
        "message": f"{new_quiz.questions.count()} ta qiyin savol asosida yangi mustahkamlash viktorinasi yaratildi.",
    }
