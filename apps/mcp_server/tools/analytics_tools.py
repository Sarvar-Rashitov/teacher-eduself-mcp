"""
MCP Analytics & Game Tools according to DOC-82 (MCP_TOOLS.md).
Zero-Bypass architecture: interacts with TeamAllocator, LiveSession, and QuizCRUDService.
"""

from typing import Any, Dict, List, Optional
from apps.live_sessions.models import LiveSession, AnswerSubmission, Participant
from apps.quizzes.services import QuizCRUDService
from apps.game_engine.teams import TeamAllocator, DEFAULT_TEAMS
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import Scopes, require_scope
from apps.mcp_server.exceptions import MCPNotFoundError, MCPForbiddenError


def _get_session_with_ownership_check(session_id: str, current_user: Any) -> LiveSession:
    session = LiveSession.objects.select_related("quiz", "host").filter(id=session_id).first()
    if not session:
        raise MCPNotFoundError(f"Jonli sessiya topilmadi: {session_id}")

    if session.host_id != current_user.id:
        raise MCPForbiddenError("Boshqa o'qituvchining jonli dars hisobotiga kirish taqiqlangan.")

    return session


@require_scope(Scopes.SESSION_CREATE)
def create_team_game(
    session_id: str,
    team_count: int = 2,
    allocation_strategy: str = "random",
) -> Dict[str, Any]:
    """
    O'quvchilarni jamoalarga bo'lib o'yin sozlamasini saqlash.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    participants = list(session.participants.values_list("nickname", flat=True))
    if not participants:
        # Hech kim ulanmagan bo'lsa ham jamoalar shablonini qaytarish
        team_defs = [
            {"id": t.team_id, "name": t.name_uz, "color": t.color, "icon": t.icon, "members": []}
            for t in DEFAULT_TEAMS[:team_count]
        ]
        return {
            "session_id": str(session.id),
            "team_count": team_count,
            "strategy": allocation_strategy,
            "teams": team_defs,
        }

    allocated = TeamAllocator.allocate_random_balanced(participants, k=team_count)
    team_defs = []
    for idx, t in enumerate(DEFAULT_TEAMS[:team_count]):
        team_key = f"team_{idx+1}"
        members = allocated.get(team_key, [])
        team_defs.append({
            "id": t.team_id,
            "name": t.name_uz,
            "color": t.color,
            "icon": t.icon,
            "members": members,
            "member_count": len(members),
        })

    # Sessiyaning settings_payload iga jamoalarni yozish
    session.settings_payload["teams"] = team_defs
    session.settings_payload["team_mode_enabled"] = True
    session.save(update_fields=["settings_payload"])

    return {
        "session_id": str(session.id),
        "team_count": team_count,
        "strategy": allocation_strategy,
        "teams": team_defs,
    }


@require_scope(Scopes.REPORT_READ)
def get_session_report(session_id: str) -> Dict[str, Any]:
    """
    Sessiya yakunlangach, sinfning umumiy o'zlashtirishi va eng ko'p xato qilingan savollar tahlilini olish.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    questions = list(session.quiz.questions.all().order_by("order_index"))
    participants = list(session.participants.all().order_by("-score"))
    submissions = AnswerSubmission.objects.filter(session=session)

    total_submissions = submissions.count()
    correct_submissions = submissions.filter(is_correct=True).count()
    overall_accuracy = (
        round((correct_submissions / total_submissions) * 100, 1)
        if total_submissions > 0
        else 0.0
    )

    # Har bir savol bo'yicha tahlil
    questions_analysis = []
    difficult_questions = []

    for idx, q in enumerate(questions, start=1):
        q_subs = submissions.filter(question=q)
        q_total = q_subs.count()
        q_correct = q_subs.filter(is_correct=True).count()
        acc = round((q_correct / q_total) * 100, 1) if q_total > 0 else 0.0

        item = {
            "order": idx,
            "prompt": q.prompt,
            "total_answers": q_total,
            "correct_answers": q_correct,
            "accuracy_percentage": acc,
        }
        questions_analysis.append(item)

        if q_total > 0 and acc < 50.0:
            difficult_questions.append({
                "question_id": str(q.id),
                "prompt": q.prompt,
                "accuracy_percentage": acc,
            })

    # Reyting (Podium)
    podium = [
        {"rank": i + 1, "nickname": p.nickname, "score": p.score, "streak": p.streak}
        for i, p in enumerate(participants[:5])
    ]

    return {
        "session_id": str(session.id),
        "quiz_title": session.quiz.title,
        "total_participants": len(participants),
        "overall_accuracy_percentage": overall_accuracy,
        "difficult_questions_count": len(difficult_questions),
        "difficult_questions": difficult_questions,
        "questions_analysis": questions_analysis,
        "podium": podium,
    }


@require_scope(Scopes.QUIZ_WRITE)
def generate_followup_activity(session_id: str) -> Dict[str, Any]:
    """
    O'quvchilar ko'p adashgan mavzular bo'yicha keyingi dars uchun avtomatik mustahkamlovchi mini-viktorina yaratish.
    """
    ctx = get_current_mcp_context()
    session = _get_session_with_ownership_check(session_id, ctx.user)

    submissions = AnswerSubmission.objects.filter(session=session)
    questions = list(session.quiz.questions.all().order_by("order_index"))

    focus_questions = []
    for q in questions:
        q_subs = submissions.filter(question=q)
        q_total = q_subs.count()
        q_correct = q_subs.filter(is_correct=True).count()
        acc = (q_correct / q_total) * 100 if q_total > 0 else 0.0

        # Agar savolda xatolik darajasi 50% dan yuqori bo'lsa yoki savolga javob berilmagan bo'lsa
        if q_total == 0 or acc < 60.0:
            focus_questions.append(q)

    # Yangi mini-viktorina yaratish
    new_title = f"Mustahkamlovchi dars: {session.quiz.title}"
    new_quiz = QuizCRUDService.create_quiz(
        owner=ctx.user,
        title=new_title,
        subject=session.quiz.subject,
        grade_level=session.quiz.grade_level,
        locale=session.quiz.locale,
        description=f"'{session.quiz.title}' sessiyasi tahlili asosida yaratilgan mini-test.",
    )

    created_count = 0
    # Agar adashilgan savollar bo'lsa ularni yangi quizga ko'chirish, aks holda barcha savollardan 3 tasini olish
    source_questions = focus_questions if focus_questions else questions[:3]

    for q in source_questions:
        q_data = {
            "type": q.type,
            "prompt": q.prompt,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "accepted_alternatives": q.accepted_alternatives,
            "points": q.points,
            "time_limit_seconds": q.time_limit_seconds,
            "order_index": created_count,
        }
        QuizCRUDService.add_question(new_quiz, q_data)
        created_count += 1

    return {
        "new_quiz_id": str(new_quiz.id),
        "title": new_quiz.title,
        "focus_questions_count": created_count,
        "status": new_quiz.status,
    }
