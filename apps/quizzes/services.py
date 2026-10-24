from typing import Any, Dict, List, Optional
from django.db import transaction
from apps.questions_registry.registry import registry
from apps.questions_registry.exceptions import QuestionValidationError
from apps.authentication.security import sanitize_html, sanitize_plain_text
from .models import Quiz, Question, QuizVersion


class QuestionValidator:
    """
    Savollarni saqlashdan oldin qat'iy tekshiruvchi xizmat.
    Savol turiga tegishli registry plagini orqali options va correct_answer ni tekshiradi.
    """

    @staticmethod
    def validate(question_data: Dict[str, Any]) -> None:
        q_type = question_data.get("type")
        if not q_type:
            raise QuestionValidationError("Savol turi ('type') ko'rsatilishi shart.")

        if not registry.is_registered(q_type):
            raise QuestionValidationError(f"Savol turi '{q_type}' ro'yxatdan o'tmagan.")

        prompt = question_data.get("prompt", "")
        if not prompt or str(prompt).strip() == "":
            raise QuestionValidationError("Savol matni ('prompt') bo'sh bo'lishi mumkin emas.")

        # XSS sanitizatsiyasi
        cleaned_prompt = sanitize_html(str(prompt)).strip()
        if not cleaned_prompt:
            raise QuestionValidationError("Savol matni faqat taqiqlangan skriptlardan iborat bo'lishi mumkin emas.")
        question_data["prompt"] = cleaned_prompt

        points = question_data.get("points", 1000)
        if not isinstance(points, int) or points < 0:
            raise QuestionValidationError("Ball musbat butun son bo'lishi shart.")

        time_limit = question_data.get("time_limit_seconds", 30)
        if not isinstance(time_limit, int) or time_limit < 5 or time_limit > 300:
            raise QuestionValidationError("Vaqt chegarasi 5 dan 300 soniyagacha bo'lishi kerak.")

        handler = registry.get(q_type)
        options = question_data.get("options", [])
        correct_answer = question_data.get("correct_answer")
        accepted_alt = question_data.get("accepted_alternatives", [])

        # Plagin orqali mantiqiy tekshiruv
        handler.validate_payload(
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=accepted_alt,
        )


class QuizCRUDService:
    """
    Viktorina va savollarni yaratish, tahrirlash va tartiblash xizmati.
    """

    @staticmethod
    def create_quiz(owner, title: str, subject: str, grade_level: int = 7, locale: str = "uz-Latn", description: str = "") -> Quiz:
        cleaned_title = sanitize_plain_text(title)
        if not cleaned_title:
            raise QuestionValidationError("Viktorina nomi bo'sh bo'lishi mumkin emas.")

        return Quiz.objects.create(
            owner=owner,
            title=cleaned_title,
            subject=sanitize_plain_text(subject),
            grade_level=grade_level,
            locale=locale,
            description=sanitize_html(description) if description else "",
            status="draft",
        )

    @classmethod
    @transaction.atomic
    def add_question(cls, quiz: Quiz, data: Dict[str, Any]) -> Question:
        QuestionValidator.validate(data)

        # Tartib raqamini hisoblash
        last_index = quiz.questions.count()
        order_index = data.get("order_index", last_index)

        question = Question.objects.create(
            quiz=quiz,
            type=data["type"],
            prompt=data["prompt"],
            media_url=data.get("media_url"),
            media_type=data.get("media_type"),
            options=data.get("options", []),
            correct_answer=data["correct_answer"],
            accepted_alternatives=data.get("accepted_alternatives", []),
            explanation=data.get("explanation"),
            points=data.get("points", 1000),
            time_limit_seconds=data.get("time_limit_seconds", 30),
            difficulty=data.get("difficulty", "medium"),
            order_index=order_index,
            is_locked=data.get("is_locked", False),
        )
        return question

    @classmethod
    @transaction.atomic
    def update_question(cls, question: Question, data: Dict[str, Any], force: bool = False) -> Question:
        if question.is_locked and not force:
            raise QuestionValidationError("Ushbu savol qulflangan (is_locked=True) va uni o'zgartirish taqiqlangan.")

        merged_data = {
            "type": data.get("type", question.type),
            "prompt": data.get("prompt", question.prompt),
            "options": data.get("options", question.options),
            "correct_answer": data.get("correct_answer", question.correct_answer),
            "accepted_alternatives": data.get("accepted_alternatives", question.accepted_alternatives),
            "points": data.get("points", question.points),
            "time_limit_seconds": data.get("time_limit_seconds", question.time_limit_seconds),
        }
        QuestionValidator.validate(merged_data)

        for key, value in data.items():
            if hasattr(question, key) and key not in ("id", "quiz"):
                setattr(question, key, value)

        question.version += 1
        question.save()
        return question

    @staticmethod
    @transaction.atomic
    def reorder_questions(quiz: Quiz, ordered_ids: List[str]) -> None:
        for index, q_id in enumerate(ordered_ids):
            Question.objects.filter(quiz=quiz, id=q_id).update(order_index=index)


class VersionManager:
    """
    Viktorinalarni muzlatish (Snapshot) va versiyalash boshqaruvi.
    """

    @staticmethod
    @transaction.atomic
    def create_snapshot(quiz: Quiz) -> QuizVersion:
        questions = quiz.questions.all().order_by("order_index")
        snapshot_payload = {
            "quiz_id": str(quiz.id),
            "title": quiz.title,
            "subject": quiz.subject,
            "grade_level": quiz.grade_level,
            "locale": quiz.locale,
            "questions": [
                {
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
                    "version": q.version,
                }
                for q in questions
            ],
        }

        version_num = quiz.current_version
        version_obj = QuizVersion.objects.create(
            quiz=quiz,
            version_number=version_num,
            snapshot=snapshot_payload,
        )

        quiz.current_version += 1
        quiz.save(update_fields=["current_version", "updated_at"])
        return version_obj


class ZeroKnowledgeQuestionDelivery:
    """
    Talaba va proyektor qurilmalariga xavfsiz uzatish.
    Tarmoq darajasida correct_answer va maxfiy izohlarni butunlay tozalaydi.
    """

    @staticmethod
    def sanitize(question: Question) -> Dict[str, Any]:
        handler = registry.get(question.type) if registry.is_registered(question.type) else None
        clean_options = handler.sanitize_for_student(question.options) if handler else question.options

        return {
            "id": str(question.id),
            "type": question.type,
            "prompt": question.prompt,
            "media_url": question.media_url,
            "media_type": question.media_type,
            "options": clean_options,
            "points": question.points,
            "time_limit_seconds": question.time_limit_seconds,
            "order_index": question.order_index,
            # E'TIBOR: correct_answer va explanation MUTLAQO MAVJUD EMAS!
        }
