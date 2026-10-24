"""
Platform Internal Tools for AI Workspace:
- Quiz draft creation with snapshotting
- Question locking guardrail toggle
- Content validation
- Classroom game mode suggestions
"""

from typing import Any, Dict, List, Optional
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from pydantic import ValidationError as PydanticValidationError

from quizzes.models import Quiz, Question
from quizzes.services import VersionManager, QuestionValidator
from .schemas import AIGeneratedQuiz, AIGeneratedQuestion


class PlatformTools:
    """
    Internal platform tools callable by AI Workspace workflows and endpoints.
    """

    @classmethod
    @transaction.atomic
    def create_quiz_draft(
        cls,
        title: str,
        questions_data: List[Dict[str, Any]],
        author: Any,
        description: str = "",
        subject: str = "Umumiy",
        grade_level: int = 7,
        locale: str = "uz-Latn",
    ) -> Quiz:
        """
        Creates a new draft Quiz with associated Question models and creates
        an initial Version snapshot.
        """
        quiz = Quiz.objects.create(
            owner=author,
            title=title,
            description=description,
            subject=subject,
            grade_level=grade_level,
            locale=locale,
            status="draft",
        )

        for idx, q_dict in enumerate(questions_data):
            q_type = q_dict.get("type", "single_choice")
            raw_options = q_dict.get("options", [])
            raw_correct = q_dict.get("correct_answer")

            # Normalize options if list of dicts or AIGeneratedOption
            options = []
            for opt in raw_options:
                if hasattr(opt, "model_dump"):
                    options.append(opt.model_dump())
                elif isinstance(opt, dict):
                    options.append({"id": str(opt.get("id")), "text": str(opt.get("text"))})
                else:
                    options.append(opt)

            # Normalize correct_answer format for question registry handlers
            correct_answer = raw_correct
            if q_type == "single_choice" and isinstance(raw_correct, str):
                correct_answer = {"correct_option_id": raw_correct.strip()}
            elif q_type == "multiple_choice" and isinstance(raw_correct, list):
                correct_answer = {"correct_option_ids": [str(x).strip() for x in raw_correct]}
            elif q_type == "true_false":
                if isinstance(raw_correct, bool):
                    correct_answer = {"correct_value": raw_correct}
                elif isinstance(raw_correct, str):
                    correct_answer = {"correct_value": raw_correct.strip().lower() in ("true", "to'g'ri", "ha", "1")}

            question = Question(
                quiz=quiz,
                type=q_type,
                prompt=q_dict.get("prompt", ""),
                options=options,
                correct_answer=correct_answer,
                explanation=q_dict.get("explanation", ""),
                points=q_dict.get("points", 1000),
                time_limit_seconds=q_dict.get("time_limit_seconds", 30),
                difficulty=q_dict.get("difficulty", "medium"),
                order_index=idx + 1,
                is_locked=False,
            )

            # Validate against QuestionValidator
            QuestionValidator.validate_question_instance(question)
            question.save()

        # Create initial version snapshot
        VersionManager.create_snapshot(
            quiz=quiz,
            change_log="AI Workspace tomonidan yaratilgan boshlang'ich qoralama",
            user=author,
        )

        return quiz

    @classmethod
    def lock_question(
        cls,
        question_id: str,
        is_locked: bool,
        user: Any,
    ) -> Question:
        """
        Locks or unlocks a question to prevent or permit automated AI revisions.
        Enforces user ownership permissions.
        """
        question = Question.objects.select_related("quiz").get(id=question_id)

        # Check permissions
        if getattr(user, "is_authenticated", False):
            if question.quiz.owner != user and not getattr(user, "is_staff", False):
                raise PermissionDenied("Faqat ushbu viktorina muallifi savolni qulflashi mumkin.")

        question.is_locked = is_locked
        question.save(update_fields=["is_locked"])
        return question

    @classmethod
    def validate_quiz_content(cls, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates quiz data against AIGeneratedQuiz schema and return detailed errors if any.
        """
        try:
            validated = AIGeneratedQuiz.model_validate(quiz_data)
            return {
                "valid": True,
                "errors": [],
                "data": validated.model_dump(),
            }
        except PydanticValidationError as e:
            return {
                "valid": False,
                "errors": e.errors(),
                "data": None,
            }

    @classmethod
    def suggest_game_modes(
        cls,
        subject: str,
        grade_level: int,
        question_count: int,
    ) -> Dict[str, Any]:
        """
        Pedagogical game mode recommender based on grade, subject, and question load.
        """
        sub_lower = subject.lower()
        if grade_level <= 4:
            primary_mode = "team_battle"
            reason = "Boshlang'ich sinflar uchun jamoaviy va qiziqarli o'yin dinamikasi mos keladi."
        elif sub_lower in ("matematika", "fizika", "kimyo", "math", "physics", "science"):
            primary_mode = "classic"
            reason = "STEM fanlarida hisoblash va mulohaza qilish uchun har bir o'quvchiga o'z ritmida ishlash qulay."
        elif question_count <= 5:
            primary_mode = "speed_run"
            reason = "Qisqa viktorinalar uchun tezkor va yuqori energiyali format tavsiya etiladi."
        else:
            primary_mode = "classic"
            reason = "Standart sinf darsi va yakuniy baholash uchun muvozanatli klassik rejim."

        return {
            "suggested_mode": primary_mode,
            "reason": reason,
            "available_modes": [
                {"id": "classic", "name": "Klassik", "description": "Har bir o'quvchi alohida bellashadi"},
                {"id": "team_battle", "name": "Jamoaviy Jang", "description": "Sinf 2 yoki undan ortiq guruhga bo'linadi"},
                {"id": "speed_run", "name": "Tezkor Bellashuv", "description": "Tezlik va ketma-ket to'g'ri javoblar bonusi"},
            ],
        }
