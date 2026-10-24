"""
MCP Quiz & Question Content Tools according to DOC-82 (MCP_TOOLS.md).
Zero-Bypass architecture: interacts strictly through QuizCRUDService and domain validators.
"""

import json
import csv
import io
from typing import Any, Dict, List, Optional
from apps.quizzes.models import Quiz, Question
from apps.quizzes.services import QuizCRUDService, QuestionValidator
from apps.ai_workspace.tools import validate_quiz_content
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.scopes import Scopes, require_scope
from apps.mcp_server.exceptions import (
    MCPNotFoundError,
    MCPForbiddenError,
    MCPContentValidationError,
)


def _get_quiz_with_ownership_check(quiz_id: str, current_user: Any) -> Quiz:
    """Multi-tenant va ownership tekshiruvi."""
    quiz = Quiz.objects.filter(id=quiz_id).first()
    if not quiz:
        raise MCPNotFoundError(f"Viktorina topilmadi: {quiz_id}")

    if quiz.owner_id != current_user.id:
        raise MCPForbiddenError("Boshqa o'qituvchining viktorinasiga kirish taqiqlangan.")

    return quiz


@require_scope(Scopes.QUIZ_WRITE)
def create_quiz_draft(
    title: str,
    subject: str,
    grade_level: int = 7,
    topic: str = "",
    question_count: int = 10,
    language: str = "uz-Latn",
    questions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Berilgan parametrlar asosida yangi viktorina draftini yaratadi.
    """
    ctx = get_current_mcp_context()

    quiz = QuizCRUDService.create_quiz(
        owner=ctx.user,
        title=title,
        subject=subject,
        grade_level=grade_level,
        locale=language,
        description=topic,
    )

    created_questions = 0
    if questions:
        for q_data in questions:
            QuizCRUDService.add_question(quiz, q_data)
            created_questions += 1

    return {
        "quiz_id": str(quiz.id),
        "status": quiz.status,
        "title": quiz.title,
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "created_questions": created_questions,
    }


@require_scope(Scopes.QUIZ_READ)
def get_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Saqlangan viktorina va uning barcha savollarini olish.
    Boshqa o'qituvchining viktorinasi so'ralsa 403 Forbidden qaytaradi.
    """
    ctx = get_current_mcp_context()
    quiz = _get_quiz_with_ownership_check(quiz_id, ctx.user)

    questions_data = []
    for q in quiz.questions.all().order_by("order_index"):
        questions_data.append({
            "id": str(q.id),
            "type": q.type,
            "prompt": q.prompt,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "accepted_alternatives": q.accepted_alternatives,
            "points": q.points,
            "time_limit_seconds": q.time_limit_seconds,
            "order_index": q.order_index,
            "is_locked": q.is_locked,
        })

    return {
        "quiz_id": str(quiz.id),
        "title": quiz.title,
        "description": quiz.description or "",
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "locale": quiz.locale,
        "status": quiz.status,
        "version": quiz.current_version,
        "questions_count": len(questions_data),
        "questions": questions_data,
    }


@require_scope(Scopes.QUIZ_WRITE)
def update_quiz(quiz_id: str, changes: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mavjud viktorina parametrlarini yoki savollarini tahrirlash.
    """
    ctx = get_current_mcp_context()
    quiz = _get_quiz_with_ownership_check(quiz_id, ctx.user)

    allowed_fields = ["title", "description", "subject", "grade_level", "locale", "status"]
    updated = False
    for field in allowed_fields:
        if field in changes:
            setattr(quiz, field, changes[field])
            updated = True

    if updated:
        quiz.current_version += 1
        quiz.save()

    return {
        "quiz_id": str(quiz.id),
        "updated_version": quiz.current_version,
        "status": "success",
    }


@require_scope(Scopes.QUIZ_READ)
def validate_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Viktorinadagi savollarning to'liqligi va sifatini (Tier 1 Heuristic) tekshirish.
    """
    ctx = get_current_mcp_context()
    quiz = _get_quiz_with_ownership_check(quiz_id, ctx.user)

    quiz_payload = {
        "title": quiz.title,
        "subject": quiz.subject,
        "questions": [
            {
                "prompt": q.prompt,
                "type": q.type,
                "options": q.options,
                "correct_answer": q.correct_answer,
            }
            for q in quiz.questions.all().order_by("order_index")
        ],
    }

    result = validate_quiz_content(quiz_payload)
    return {
        "quiz_id": str(quiz.id),
        "is_valid": result["is_valid"],
        "error_count": len(result["errors"]),
        "errors": result["errors"],
        "warnings": result.get("warnings", []),
    }


@require_scope(Scopes.QUIZ_READ)
def list_question_sets(query: str = "", page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    O'qituvchining saqlangan viktorinalarini qidirish va filtrlash.
    """
    ctx = get_current_mcp_context()
    qs = Quiz.objects.filter(owner=ctx.user).order_by("-created_at")

    if query:
        clean_q = query.strip()
        qs = qs.filter(title__icontains=clean_q) | qs.filter(subject__icontains=clean_q)

    total_count = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    paged_quizzes = qs[start:end]

    items = [
        {
            "quiz_id": str(q.id),
            "title": q.title,
            "subject": q.subject,
            "grade_level": q.grade_level,
            "status": q.status,
            "questions_count": q.questions.count(),
            "created_at": q.created_at.isoformat() if q.created_at else None,
        }
        for q in paged_quizzes
    ]

    return {
        "quizzes": items,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
    }


@require_scope(Scopes.QUIZ_WRITE)
def import_questions(quiz_id: str, source_format: str, content: str) -> Dict[str, Any]:
    """
    CSV yoki JSON formatdan savollarni import qilish.
    """
    ctx = get_current_mcp_context()
    quiz = _get_quiz_with_ownership_check(quiz_id, ctx.user)

    imported_questions = []

    if source_format == "json":
        try:
            data = json.loads(content)
            q_list = data if isinstance(data, list) else data.get("questions", [])
            for q_data in q_list:
                question = QuizCRUDService.add_question(quiz, q_data)
                imported_questions.append(str(question.id))
        except Exception as e:
            raise MCPContentValidationError(f"JSON tahlil xatosi: {str(e)}")

    elif source_format == "csv":
        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                # CSV formatidan QuestionDTO ga o'tkazish
                prompt = row.get("prompt") or row.get("question") or ""
                q_type = row.get("type", "single_choice")
                raw_options = row.get("options", "")
                options = [
                    {"id": f"opt_{i+1}", "text": opt.strip()}
                    for i, opt in enumerate(raw_options.split("|"))
                    if opt.strip()
                ]
                correct = row.get("correct_answer", "opt_1")
                q_data = {
                    "type": q_type,
                    "prompt": prompt,
                    "options": options,
                    "correct_answer": correct,
                    "points": int(row.get("points", 1000)),
                    "time_limit_seconds": int(row.get("time_limit", 30)),
                }
                question = QuizCRUDService.add_question(quiz, q_data)
                imported_questions.append(str(question.id))
        except Exception as e:
            raise MCPContentValidationError(f"CSV tahlil xatosi: {str(e)}")
    else:
        raise MCPContentValidationError(f"Qo'llab-quvvatlanmaydigan format: {source_format}")

    return {
        "quiz_id": str(quiz.id),
        "imported_count": len(imported_questions),
        "status": "success",
    }
