from typing import Any
from django.core.exceptions import ValidationError
from django.db import models, transaction
from questions_registry import question_registry, QuestionValidationError
from .models import Quiz, Question, QuizVersion


class QuestionValidator:
    """
    Central validation service for Question structures.
    Validates generic bounds (time limits, prompt non-emptiness, points)
    and delegates domain-specific logic to the registered QuestionType handler.
    """

    @classmethod
    def validate(
        cls,
        type_id: str,
        prompt: str,
        options: Any,
        correct_answer: Any,
        time_limit_seconds: int = 30,
        points: int = 1000,
    ) -> None:
        errors = {}

        if not prompt or not str(prompt).strip():
            errors["prompt"] = "Savol matni bo'sh bo'lishi mumkin emas."

        if time_limit_seconds < 5 or time_limit_seconds > 300:
            errors["time_limit_seconds"] = "Vaqt chegarasi 5 dan 300 soniyagacha bo'lishi shart."

        if points < 0:
            errors["points"] = "Ball manfiy bo'lishi mumkin emas."

        if not question_registry.is_registered(type_id):
            errors["type"] = f"'{type_id}' nomli savol turi registratsiyadan o'tmagan."
        else:
            handler = question_registry.get(type_id)
            try:
                handler.validate_payload(options, correct_answer)
            except QuestionValidationError as exc:
                errors["payload"] = exc.message

        if errors:
            raise ValidationError(errors)

    @classmethod
    def validate_question_instance(cls, question: Question) -> None:
        cls.validate(
            type_id=question.type,
            prompt=question.prompt,
            options=question.options,
            correct_answer=question.correct_answer,
            time_limit_seconds=question.time_limit_seconds,
            points=question.points,
        )


class VersionManager:
    """
    Manages immutable snapshotting and version history for quizzes.
    Protects running live sessions and historical performance records from being
    corrupted when teachers subsequently edit quiz questions.
    """

    @classmethod
    @transaction.atomic
    def create_snapshot(
        cls,
        quiz: Quiz,
        change_log: str | None = None,
        user: Any = None
    ) -> QuizVersion:
        # Determine next version number
        latest = quiz.versions.order_by("-version_number").first()
        next_version = (latest.version_number + 1) if latest else 1

        # Serialize full quiz state
        questions_data = []
        for q in quiz.questions.all().order_by("order_index"):
            questions_data.append({
                "id": str(q.id),
                "type": q.type,
                "prompt": q.prompt,
                "media_url": q.media_url,
                "media_type": q.media_type,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "accepted_alternatives": q.accepted_alternatives,
                "explanation": q.explanation,
                "points": q.points,
                "time_limit_seconds": q.time_limit_seconds,
                "difficulty": q.difficulty,
                "order_index": q.order_index,
                "is_locked": q.is_locked,
                "version": q.version,
            })

        snapshot_payload = {
            "quiz_id": str(quiz.id),
            "title": quiz.title,
            "description": quiz.description,
            "subject": quiz.subject,
            "grade_level": quiz.grade_level,
            "locale": quiz.locale,
            "status": quiz.status,
            "version_number": next_version,
            "total_questions": len(questions_data),
            "questions": questions_data,
        }

        version_obj = QuizVersion.objects.create(
            quiz=quiz,
            version_number=next_version,
            title=f"{quiz.title} (Snapshot v{next_version})",
            snapshot_data=snapshot_payload,
            change_log=change_log or f"Versiya {next_version} avtomatik yaratildi.",
            created_by=user or quiz.owner,
        )

        quiz.current_version = next_version
        quiz.save(update_fields=["current_version", "updated_at"])

        return version_obj

    @classmethod
    def get_snapshot(cls, quiz: Quiz, version_number: int) -> dict | None:
        version_obj = quiz.versions.filter(version_number=version_number).first()
        return version_obj.snapshot_data if version_obj else None


class QuizCRUD:
    """
    High-level business service for Quiz and Question lifecycle management.
    """

    @classmethod
    def create_quiz(cls, owner: Any, data: dict[str, Any]) -> Quiz:
        return Quiz.objects.create(
            owner=owner,
            title=data.get("title", ""),
            description=data.get("description", ""),
            subject=data.get("subject", "Umumiy"),
            grade_level=data.get("grade_level", 7),
            locale=data.get("locale", "uz-Latn"),
            status=data.get("status", "draft"),
            is_public=data.get("is_public", False),
            google_sheet_url=data.get("google_sheet_url"),
        )

    @classmethod
    def update_quiz(cls, quiz: Quiz, data: dict[str, Any]) -> Quiz:
        updatable_fields = [
            "title",
            "description",
            "subject",
            "grade_level",
            "locale",
            "status",
            "is_public",
            "google_sheet_url",
        ]
        for field in updatable_fields:
            if field in data:
                setattr(quiz, field, data[field])
        quiz.save()
        return quiz

    @classmethod
    def delete_quiz(cls, quiz: Quiz) -> None:
        quiz.delete()

    @classmethod
    def add_question(cls, quiz: Quiz, data: dict[str, Any]) -> Question:
        """
        Validates and adds a question to a quiz.
        """
        type_id = data.get("type", "single_choice")
        prompt = data.get("prompt", "")
        options = data.get("options", [])
        correct_answer = data.get("correct_answer", {})
        time_limit = data.get("time_limit_seconds", 30)
        points = data.get("points", 1000)

        # Validate with QuestionValidator
        QuestionValidator.validate(
            type_id=type_id,
            prompt=prompt,
            options=options,
            correct_answer=correct_answer,
            time_limit_seconds=time_limit,
            points=points,
        )

        order_index = data.get("order_index")
        if order_index is None:
            max_order = quiz.questions.all().aggregate(models.Max("order_index"))["order_index__max"]
            order_index = (max_order + 1) if max_order is not None else 0

        question = Question.objects.create(
            quiz=quiz,
            type=type_id,
            prompt=prompt,
            media_url=data.get("media_url"),
            media_type=data.get("media_type"),
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=data.get("accepted_alternatives", []),
            explanation=data.get("explanation"),
            points=points,
            time_limit_seconds=time_limit,
            difficulty=data.get("difficulty", "medium"),
            order_index=order_index,
            is_locked=data.get("is_locked", False),
        )
        return question

    @classmethod
    def update_question(
        cls,
        question: Question,
        data: dict[str, Any],
        override_locked: bool = False
    ) -> Question:
        """
        Updates a question. Respects is_locked safety lock unless override_locked is True.
        """
        if question.is_locked and not override_locked:
            raise ValidationError(
                {"is_locked": "Bu savol qulflangan (is_locked=True). Tahrirlash taqiqlanadi."}
            )

        fields = [
            "type",
            "prompt",
            "media_url",
            "media_type",
            "options",
            "correct_answer",
            "accepted_alternatives",
            "explanation",
            "points",
            "time_limit_seconds",
            "difficulty",
            "order_index",
            "is_locked",
        ]
        for field in fields:
            if field in data:
                setattr(question, field, data[field])

        question.clean()
        question.save()
        return question

    @classmethod
    def delete_question(cls, question: Question, override_locked: bool = False) -> None:
        """
        Deletes a question. Respects is_locked safety lock unless override_locked is True.
        """
        if question.is_locked and not override_locked:
            raise ValidationError(
                {"is_locked": "Bu savol qulflangan (is_locked=True). O'chirish taqiqlanadi."}
            )
        question.delete()

    @classmethod
    @transaction.atomic
    def reorder_questions(cls, quiz: Quiz, ordered_ids: list[str]) -> list[Question]:
        """
        Reorders questions in the quiz according to the given ID sequence.
        """
        questions = list(quiz.questions.filter(id__in=ordered_ids))
        q_map = {str(q.id): q for q in questions}

        updated = []
        for index, q_id in enumerate(ordered_ids):
            q = q_map.get(str(q_id))
            if q:
                q.order_index = index
                q.save(update_fields=["order_index"])
                updated.append(q)
        return updated

    @classmethod
    @transaction.atomic
    def publish_quiz(cls, quiz: Quiz, user: Any = None) -> Quiz:
        """
        Transitions quiz to 'published' status and takes an immutable snapshot.
        """
        if quiz.questions.count() == 0:
            raise ValidationError(
                "Nashr qilish uchun viktorinada kamida bitta savol bo'lishi shart."
            )

        quiz.status = "published"
        quiz.save(update_fields=["status", "updated_at"])
        VersionManager.create_snapshot(
            quiz=quiz,
            change_log="Viktorina nashr qilindi va snapshot olindi.",
            user=user
        )
        return quiz

    @classmethod
    def get_sanitized_quiz(cls, quiz: Quiz) -> dict[str, Any]:
        """
        Zero-Knowledge Delivery: returns quiz schema with all questions sanitized
        for student and projector clients (answer keys and explanations completely stripped).
        """
        sanitized_questions = []
        for q in quiz.questions.all().order_by("order_index"):
            handler = question_registry.get(q.type)
            raw_data = {
                "id": str(q.id),
                "type": q.type,
                "prompt": q.prompt,
                "media_url": q.media_url,
                "media_type": q.media_type,
                "options": q.options,
                "correct_answer": q.correct_answer,
                "accepted_alternatives": q.accepted_alternatives,
                "explanation": q.explanation,
                "points": q.points,
                "time_limit_seconds": q.time_limit_seconds,
                "difficulty": q.difficulty,
                "order_index": q.order_index,
            }
            sanitized_questions.append(handler.sanitize_for_student(raw_data))

        return {
            "id": str(quiz.id),
            "title": quiz.title,
            "description": quiz.description,
            "subject": quiz.subject,
            "grade_level": quiz.grade_level,
            "locale": quiz.locale,
            "status": quiz.status,
            "current_version": quiz.current_version,
            "total_questions": len(sanitized_questions),
            "questions": sanitized_questions,
        }
