# ============================================================
# EduSelf Teacher — apps/mcp_server/tools/quiz_tools.py
# Category 1: Quiz & Question Management MCP Tools
# MCP_TOOLS.md DOC-82 asosida
# ============================================================
import json
import uuid
from typing import Dict, Any, List, Optional
from asgiref.sync import sync_to_async

from apps.quizzes.models import Quiz, Question, QuizVersion
from apps.questions_registry.registry import question_registry
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import require_scope, SCOPE_QUIZ_READ, SCOPE_QUIZ_WRITE
from apps.mcp_server.exceptions import (
    MCPResourceNotFoundError,
    MCPForbiddenError,
    MCPContentValidationError,
)


def _check_quiz_access(quiz: Quiz, user) -> None:
    """Zero-Bypass: O'qituvchi faqat o'ziga tegishli yoki o'z maktabiga tegishli testga kira oladi."""
    if quiz.owner_id != user.id:
        if user.role == 'school_admin' and user.organization_id and quiz.owner.organization_id == user.organization_id:
            return
        raise MCPForbiddenError(
            f"Sizda ushbu testga ({quiz.id}) kirish huquqi mavjud emas! (Multi-tenant izolyatsiyasi)"
        )


@sync_to_async
def _create_quiz_draft_sync(user, title: str, subject: str, grade_level: int, topic: str, question_count: int, language: str, game_mode: str) -> Dict[str, Any]:
    if not (1 <= grade_level <= 11):
        raise MCPContentValidationError(f"Sinf darajasi (grade_level) 1 dan 11 gacha bo'lishi shart, berildi: {grade_level}")

    locale_map = {
        "uz": "uz-Latn",
        "ru": "ru-RU",
        "en": "en-US",
        "uz-latn": "uz-Latn",
        "uz-cyrl": "uz-Cyrl",
    }
    db_locale = locale_map.get(language.lower(), "uz-Latn")

    quiz = Quiz.objects.create(
        owner=user,
        title=title,
        description=f"AI Draft: {topic}" if topic else "Yangi viktorina drafti",
        subject=subject,
        grade_level=grade_level,
        locale=db_locale,
        status='draft',
        current_version=1,
    )
    return {
        "quiz_id": str(quiz.id),
        "status": quiz.status,
        "title": quiz.title,
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "created_questions": 0,
    }


@require_scope(SCOPE_QUIZ_WRITE)
async def create_quiz_draft(
    title: str,
    subject: str,
    grade_level: int,
    topic: str = "",
    question_count: int = 10,
    language: str = "uz",
    game_mode: str = "classic"
) -> Dict[str, Any]:
    """
    Berilgan parametrlar asosida yangi viktorina draftini yaratadi.
    """
    ctx = get_current_mcp_context()
    return await _create_quiz_draft_sync(
        user=ctx.user,
        title=title,
        subject=subject,
        grade_level=grade_level,
        topic=topic,
        question_count=question_count,
        language=language,
        game_mode=game_mode
    )


@sync_to_async
def _get_quiz_sync(user, quiz_id: str) -> Dict[str, Any]:
    try:
        quiz = Quiz.objects.prefetch_related('questions').get(id=quiz_id)
    except (Quiz.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Quiz ID '{quiz_id}' topilmadi.")

    _check_quiz_access(quiz, user)

    questions_data = []
    for q in quiz.questions.all().order_by('order_index'):
        questions_data.append({
            "id": str(q.id),
            "order": q.order_index,
            "question_type": q.type,
            "prompt": q.prompt,
            "options": q.options,
            "time_limit_seconds": q.time_limit_seconds,
            "points": q.points,
            "is_locked": q.is_locked,
        })

    return {
        "quiz_id": str(quiz.id),
        "title": quiz.title,
        "description": quiz.description,
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "locale": quiz.locale,
        "version": quiz.current_version,
        "status": quiz.status,
        "questions": questions_data,
        "question_count": len(questions_data),
    }


@require_scope(SCOPE_QUIZ_READ)
async def get_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Saqlangan viktorina va uning savollarini to'liq olish.
    """
    ctx = get_current_mcp_context()
    return await _get_quiz_sync(ctx.user, quiz_id)


@sync_to_async
def _update_quiz_sync(user, quiz_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    try:
        quiz = Quiz.objects.get(id=quiz_id)
    except (Quiz.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Quiz ID '{quiz_id}' topilmadi.")

    _check_quiz_access(quiz, user)

    allowed_fields = ['title', 'description', 'subject', 'grade_level', 'locale', 'status']
    for field_name in allowed_fields:
        if field_name in changes:
            setattr(quiz, field_name, changes[field_name])

    quiz.current_version += 1
    quiz.save()

    # Snapshot saqlash
    QuizVersion.objects.create(
        quiz=quiz,
        version_number=quiz.current_version,
        snapshot_data={"changes_applied": changes, "title": quiz.title}
    )

    return {
        "quiz_id": str(quiz.id),
        "updated_version": quiz.current_version,
        "status": "success",
    }


@require_scope(SCOPE_QUIZ_WRITE)
async def update_quiz(quiz_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mavjud viktorina parametrlarini yoki savollarini tahrirlash.
    """
    ctx = get_current_mcp_context()
    return await _update_quiz_sync(ctx.user, quiz_id, changes)


@sync_to_async
def _validate_quiz_sync(user, quiz_id: str) -> Dict[str, Any]:
    try:
        quiz = Quiz.objects.prefetch_related('questions').get(id=quiz_id)
    except (Quiz.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Quiz ID '{quiz_id}' topilmadi.")

    _check_quiz_access(quiz, user)

    questions = list(quiz.questions.all())
    errors = []
    warnings = []

    if not questions:
        errors.append("Viktorinada kamida bitta savol bo'lishi shart.")

    for q in questions:
        try:
            plugin = question_registry.get(q.type)
            plugin.validate_payload(q.options, q.correct_answer, getattr(q, 'accepted_alternatives', []))
        except Exception as e:
            errors.append(f"Savol #{q.order_index} ({q.type}) xatosi: {str(e)}")

        if q.time_limit_seconds < 5:
            warnings.append(f"Savol #{q.order_index}: Vaqt chegarasi juda kam ({q.time_limit_seconds}s)")

    return {
        "quiz_id": str(quiz.id),
        "is_valid": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "warnings": warnings,
    }


@require_scope(SCOPE_QUIZ_READ)
async def validate_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Viktorinadagi savollarning to'liqligi va to'g'ri javoblar mavjudligini tekshirish.
    """
    ctx = get_current_mcp_context()
    return await _validate_quiz_sync(ctx.user, quiz_id)


@sync_to_async
def _import_questions_sync(user, quiz_id: str, source_format: str, content: str) -> Dict[str, Any]:
    try:
        quiz = Quiz.objects.get(id=quiz_id)
    except (Quiz.DoesNotExist, ValueError):
        raise MCPResourceNotFoundError(f"Quiz ID '{quiz_id}' topilmadi.")

    _check_quiz_access(quiz, user)

    imported = 0
    start_order = quiz.questions.count()

    if source_format == "json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise MCPContentValidationError(f"Yaroqsiz JSON formati: {str(e)}")

        if not isinstance(data, list):
            data = [data]

        for idx, item in enumerate(data):
            q_type = item.get("question_type") or item.get("type", "single_choice")
            q_content = item.get("content", {})
            prompt = q_content.get("prompt") or item.get("prompt", "")
            options = q_content.get("options") or item.get("options", [])
            correct_answer = q_content.get("correct_answer") or item.get("correct_answer")

            plugin = question_registry.get(q_type)
            plugin.validate_payload(options, correct_answer)

            Question.objects.create(
                quiz=quiz,
                type=q_type,
                prompt=prompt,
                options=options,
                correct_answer=correct_answer,
                order_index=start_order + idx,
                time_limit_seconds=item.get("time_limit_seconds", 30),
                points=item.get("points", 1000),
            )
            imported += 1

    elif source_format in ["csv", "raw_text"]:
        lines = [line.strip() for line in content.strip().split("\n") if line.strip()]
        for idx, line in enumerate(lines):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                q_text = parts[0]
                correct_ans = parts[1]
                options = [{"id": "opt_correct", "text": correct_ans}]
                for dist_idx, dist in enumerate(parts[2:]):
                    options.append({"id": f"opt_wrong_{dist_idx}", "text": dist})

                Question.objects.create(
                    quiz=quiz,
                    type="single_choice",
                    prompt=q_text,
                    options=options,
                    correct_answer="opt_correct",
                    order_index=start_order + idx,
                    time_limit_seconds=30,
                    points=1000,
                )
                imported += 1
    else:
        raise MCPContentValidationError(f"Noma'lum import formati: '{source_format}'. Qo'llab-quvvatlanadi: json, csv, raw_text")

    return {
        "quiz_id": str(quiz.id),
        "imported_count": imported,
        "total_questions": quiz.questions.count(),
        "status": "success",
    }


@require_scope(SCOPE_QUIZ_WRITE)
async def import_questions(quiz_id: str, source_format: str, content: str) -> Dict[str, Any]:
    """
    CSV, matn yoki JSON formatdan savollarni import qilish.
    """
    ctx = get_current_mcp_context()
    return await _import_questions_sync(ctx.user, quiz_id, source_format, content)


@sync_to_async
def _list_question_sets_sync(user, query: str, page: int, page_size: int) -> Dict[str, Any]:
    qs = Quiz.objects.filter(owner=user)
    if query:
        qs = qs.filter(title__icontains=query) | qs.filter(subject__icontains=query)

    total = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    items = qs.order_by('-created_at')[start:end]

    quizzes_data = []
    for q in items:
        quizzes_data.append({
            "quiz_id": str(q.id),
            "title": q.title,
            "subject": q.subject,
            "grade_level": q.grade_level,
            "locale": q.locale,
            "version": q.current_version,
            "question_count": q.questions.count(),
            "created_at": q.created_at.isoformat(),
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "quizzes": quizzes_data,
    }


@require_scope(SCOPE_QUIZ_READ)
async def list_question_sets(query: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    O'qituvchining saqlangan viktorinalarini qidirish va filtrlash.
    """
    ctx = get_current_mcp_context()
    return await _list_question_sets_sync(ctx.user, query, page, page_size)


# development_plan.md sinonimlari (Aliases)
list_quizzes = list_question_sets
create_quiz = create_quiz_draft
