"""
Content and Quiz Management MCP Tools (Tools 1–6).
Conforms to DOC-82 (MCP_TOOLS.md).
"""

import csv
import io
import json
import uuid
from typing import Any, Dict, List, Optional
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.quizzes.models import Quiz, Question
from apps.quizzes.services import QuizService
from apps.questions_registry.registry import question_type_registry
from apps.questions_registry.exceptions import QuestionValidationError

from ..auth import get_current_mcp_context
from ..scopes import require_scope, SCOPE_QUIZ_READ, SCOPE_QUIZ_WRITE
from ..exceptions import (
    MCPNotFoundError,
    MCPForbiddenError,
    MCPContentValidationError,
    MCPInvalidParamsError,
)


def _get_teacher_quiz(quiz_id: str, write: bool = False) -> Quiz:
    """O'qituvchiga tegishli viktorinani multi-tenant izolyatsiyasini tekshirib oladi."""
    context = get_current_mcp_context()
    try:
        quiz_uuid = uuid.UUID(str(quiz_id))
    except (ValueError, TypeError):
        raise MCPInvalidParamsError(f"Yaroqsiz quiz_id: {quiz_id}")

    quiz = Quiz.objects.filter(id=quiz_uuid).first()
    if not quiz:
        raise MCPNotFoundError(f"Viktorina topilmadi: {quiz_id}")

    if quiz.owner_id != context.user.id and not context.user.is_superuser:
        raise MCPForbiddenError("Boshqa o'qituvchining viktorinasiga kirish taqiqlangan!")

    return quiz


@require_scope(SCOPE_QUIZ_WRITE)
def create_quiz_draft(
    title: str,
    subject: str,
    grade_level: int,
    topic: str = "",
    question_count: int = 5,
    language: str = "uz",
    game_mode: str = "classic",
) -> Dict[str, Any]:
    """
    Berilgan parametrlar asosida yangi viktorina draftini yaratadi.
    Scope: quiz:write
    """
    if not title or not title.strip():
        raise MCPInvalidParamsError("Viktorina sarlavhasi (title) bo'sh bo'lishi mumkin emas.")

    context = get_current_mcp_context()
    quiz = Quiz.objects.create(
        title=title.strip(),
        description=f"{subject} {grade_level}-sinf: {topic}" if topic else f"{subject} {grade_level}-sinf",
        owner=context.user,
        subject=subject,
        grade_level=grade_level,
        locale=language,
        status="draft",
    )

    return {
        "quiz_id": str(quiz.id),
        "status": quiz.status,
        "title": quiz.title,
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "created_questions": 0,
    }


@require_scope(SCOPE_QUIZ_READ)
def get_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Saqlangan viktorina va uning barcha savollarini to'liq ko'rish (o'qituvchi formati).
    Scope: quiz:read
    """
    quiz = _get_teacher_quiz(quiz_id, write=False)
    questions_data = []
    for q in quiz.questions.all().order_by("order_index"):
        questions_data.append({
            "id": str(q.id),
            "order_index": q.order_index,
            "type": q.type,
            "prompt": q.prompt,
            "options": q.options,
            "correct_answer": q.correct_answer,
            "explanation": q.explanation,
            "points": q.points,
            "time_limit_seconds": q.time_limit_seconds,
            "is_locked": q.is_locked,
        })

    return {
        "quiz_id": str(quiz.id),
        "title": quiz.title,
        "description": quiz.description,
        "subject": quiz.subject,
        "grade_level": quiz.grade_level,
        "locale": quiz.locale,
        "status": quiz.status,
        "version": quiz.current_version,
        "current_version": quiz.current_version,
        "questions_count": len(questions_data),
        "questions": questions_data,
    }


@require_scope(SCOPE_QUIZ_WRITE)
def update_quiz(
    quiz_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Mavjud viktorina parametrlarini tahrirlash.
    Scope: quiz:write
    """
    quiz = _get_teacher_quiz(quiz_id, write=True)
    update_fields = []

    if title is not None and title.strip():
        quiz.title = title.strip()
        update_fields.append("title")

    if description is not None:
        quiz.description = description.strip()
        update_fields.append("description")

    if settings is not None and isinstance(settings, dict):
        if "subject" in settings:
            quiz.subject = str(settings["subject"])
            update_fields.append("subject")
        if "grade_level" in settings:
            quiz.grade_level = int(settings["grade_level"])
            update_fields.append("grade_level")
        if "language" in settings or "locale" in settings:
            quiz.locale = str(settings.get("language") or settings.get("locale"))
            update_fields.append("locale")

    if update_fields:
        quiz.current_version += 1
        update_fields.append("current_version")
        update_fields.append("updated_at")
        quiz.save(update_fields=update_fields)

    return {
        "quiz_id": str(quiz.id),
        "updated_version": quiz.current_version,
        "version": quiz.current_version,
        "status": "success",
        "title": quiz.title,
    }


@require_scope(SCOPE_QUIZ_READ)
def validate_quiz(quiz_id: str) -> Dict[str, Any]:
    """
    Viktorinadagi barcha savollarning to'liqligi va xatoliklarini tekshirish.
    Scope: quiz:read
    """
    quiz = _get_teacher_quiz(quiz_id, write=False)
    questions = quiz.questions.all().order_by("order_index")

    errors = []
    warnings = []

    if not questions.exists():
        errors.append("Viktorinada birorta ham savol mavjud emas.")

    for idx, q in enumerate(questions, start=1):
        if not question_type_registry.has(q.type):
            errors.append(f"Savol #{idx}: Noma'lum savol turi '{q.type}'.")
            continue

        handler = question_type_registry.get(q.type)
        try:
            handler.validate_payload(q.options, q.correct_answer)
        except QuestionValidationError as ex:
            errors.append(f"Savol #{idx} ('{q.prompt[:30]}...'): {str(ex)}")

        if not q.prompt or len(q.prompt.strip()) < 5:
            warnings.append(f"Savol #{idx}: Savol matni juda qisqa.")

    is_valid = len(errors) == 0
    return {
        "quiz_id": str(quiz.id),
        "is_valid": is_valid,
        "error_count": len(errors),
        "errors": errors,
        "warnings": warnings,
        "question_count": questions.count(),
    }


@require_scope(SCOPE_QUIZ_WRITE)
def import_questions(
    quiz_id: str,
    source_format: str,
    content: str,
) -> Dict[str, Any]:
    """
    JSON, CSV yoki matn formatidagi savollarni tahlil qilib viktorinaga import qiladi.
    Scope: quiz:write
    """
    quiz = _get_teacher_quiz(quiz_id, write=True)
    fmt = (source_format or "").strip().lower()

    parsed_questions: List[Dict[str, Any]] = []

    if fmt == "json":
        try:
            data = json.loads(content)
            if isinstance(data, list):
                parsed_questions = data
            elif isinstance(data, dict) and "questions" in data:
                parsed_questions = data["questions"]
            else:
                raise ValueError("JSON strukturasida savollar massivi topilmadi.")
        except Exception as ex:
            raise MCPContentValidationError(f"Yaroqsiz JSON formati: {str(ex)}")

    elif fmt == "csv":
        try:
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                prompt = row.get("prompt") or row.get("question", "")
                options_str = row.get("options", "")
                options_list = [opt.strip() for opt in options_str.split("|") if opt.strip()]
                correct_str = row.get("correct_answer") or row.get("answer", "")

                formatted_options = []
                for i, text in enumerate(options_list):
                    formatted_options.append({
                        "id": f"opt_{i+1}",
                        "text": text,
                        "is_correct": text == correct_str,
                    })

                parsed_questions.append({
                    "type": row.get("type", "single_choice"),
                    "prompt": prompt,
                    "options": formatted_options,
                    "correct_answer": correct_str,
                    "explanation": row.get("explanation", ""),
                    "points": int(row.get("points", 1000)),
                    "time_limit_seconds": int(row.get("time_limit_seconds", 30)),
                })
        except Exception as ex:
            raise MCPContentValidationError(f"Yaroqsiz CSV formati: {str(ex)}")

    elif fmt == "raw_text":
        # Har bir savol blokini ajratish
        blocks = [b.strip() for b in content.split("\n\n") if b.strip()]
        for block in blocks:
            lines = [l.strip() for l in block.split("\n") if l.strip()]
            if not lines:
                continue
            prompt = lines[0]
            options = []
            correct = ""
            for l in lines[1:]:
                is_correct = l.startswith("*") or "[x]" in l.lower()
                clean_text = l.lstrip("*+- [x] ").strip()
                opt_id = f"opt_{len(options)+1}"
                if is_correct:
                    correct = opt_id
                options.append({"id": opt_id, "text": clean_text, "is_correct": is_correct})
            if not correct and options:
                correct = options[0]["id"]
                options[0]["is_correct"] = True

            parsed_questions.append({
                "type": "single_choice",
                "prompt": prompt,
                "options": options,
                "correct_answer": correct,
                "explanation": "",
                "points": 1000,
                "time_limit_seconds": 30,
            })
    else:
        raise MCPInvalidParamsError(
            f"Qo'llab-quvvatlanmaydigan import formati: '{source_format}'. Mumkin formatlar: 'json', 'csv', 'raw_text'."
        )

    if not parsed_questions:
        raise MCPContentValidationError("Import qilish uchun birorta ham savol aniqlanmadi.")

    imported_count = 0
    start_order = quiz.questions.count()

    with transaction.atomic():
        for i, q_data in enumerate(parsed_questions):
            q_type = q_data.get("type", "single_choice")
            if not question_type_registry.has(q_type):
                q_type = "single_choice"

            handler = question_type_registry.get(q_type)
            opts = q_data.get("options", [])
            correct = q_data.get("correct_answer")

            try:
                handler.validate_payload(opts, correct)
            except QuestionValidationError as ex:
                raise MCPContentValidationError(f"Savol #{i+1} validatsiyadan o'tmadi: {str(ex)}")

            Question.objects.create(
                quiz=quiz,
                type=q_type,
                prompt=q_data.get("prompt", f"Savol #{start_order + i + 1}"),
                options=opts,
                correct_answer=correct,
                explanation=q_data.get("explanation", ""),
                points=q_data.get("points", 1000),
                time_limit_seconds=q_data.get("time_limit_seconds", 30),
                order_index=start_order + i,
            )
            imported_count += 1

        quiz.current_version += 1
        quiz.save(update_fields=["current_version", "updated_at"])

    return {
        "quiz_id": str(quiz.id),
        "imported_count": imported_count,
        "total_questions": quiz.questions.count(),
        "status": "success",
    }


@require_scope(SCOPE_QUIZ_READ)
def list_question_sets(
    query: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """
    O'qituvchining saqlangan viktorinalari ro'yxatini qidirish va sahifalash.
    Scope: quiz:read
    """
    context = get_current_mcp_context()
    qs = Quiz.objects.filter(owner=context.user).order_by("-created_at")

    if query and query.strip():
        q_clean = query.strip()
        qs = qs.filter(title__icontains=q_clean)

    total_count = qs.count()
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    start = (page - 1) * page_size
    end = start + page_size
    items = qs[start:end]

    results = []
    for item in items:
        results.append({
            "quiz_id": str(item.id),
            "title": item.title,
            "description": item.description,
            "status": item.status,
            "version": item.current_version,
            "current_version": item.current_version,
            "questions_count": item.questions.count(),
            "created_at": item.created_at.isoformat(),
        })

    return {
        "quizzes": results,
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "has_more": end < total_count,
    }
