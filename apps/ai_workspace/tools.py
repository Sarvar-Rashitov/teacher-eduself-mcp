"""
Platform Internal Tools for AI Agent Execution (Tool Calling).
Implements safe function calling with server-side authorization and input validation.
"""

import logging
from typing import Any, Dict, List, Optional
from django.db import transaction
from apps.quizzes.models import Quiz, Question
from apps.game_engine.registry import game_mode_registry
from .schemas import AIGeneratedQuiz, QuizRequirements, AIQuestionRevisionProposal
from .validator import ContentValidator

logger = logging.getLogger(__name__)


class PlatformTools:
    """
    Catalog of secure platform tools exposed to the AI Teacher Agent.
    """

    @classmethod
    def get_quiz_requirements(cls, prompt: str) -> QuizRequirements:
        """
        Extracts structured pedagogical parameters from a teacher's free-text request.
        """
        clean_text = prompt.lower()

        # Extract subject heuristic
        subjects = ["fizika", "matematika", "kimyo", "biologiya", "tarix", "ona tili", "adabiyot", "ingliz tili", "geografiya", "informatika"]
        found_subject = "Umumiy fan"
        for sub in subjects:
            if sub in clean_text:
                found_subject = sub.capitalize()
                break

        # Extract grade level heuristic (e.g. "8-sinf", "7 sinf")
        import re
        grade_match = re.search(r"(\d{1,2})\s*-\s*sinf", clean_text) or re.search(r"(\d{1,2})\s*sinf", clean_text)
        grade = int(grade_match.group(1)) if grade_match else 7
        grade = max(1, min(11, grade))

        # Extract question count (e.g. "10 ta savol", "15 test")
        count_match = re.search(r"(\d{1,2})\s*ta\s*savol", clean_text) or re.search(r"(\d{1,2})\s*ta\s*test", clean_text)
        count = int(count_match.group(1)) if count_match else 10
        count = max(1, min(50, count))

        return QuizRequirements(
            subject=found_subject,
            grade_level=grade,
            topic=prompt[:100],
            question_count=count,
            language="uz",
        )

    @classmethod
    def suggest_game_modes(
        cls,
        student_count: int = 25,
        duration_minutes: int = 20,
        learning_goal: str = "general",
    ) -> List[Dict[str, Any]]:
        """
        Recommends appropriate game modes based on class size, time, and goal.
        """
        suggestions = []

        if student_count >= 10 and game_mode_registry.has("team_battle"):
            team_mode = game_mode_registry.get("team_battle")
            suggestions.append({
                "id": team_mode.mode_id,
                "name": team_mode.display_name,
                "reason": "10 dan ortiq o'quvchilar uchun jamoaviy birdamlik va sog'lom raqobatni shakllantiradi."
            })

        if duration_minutes <= 15 and game_mode_registry.has("speed_run"):
            speed_mode = game_mode_registry.get("speed_run")
            suggestions.append({
                "id": speed_mode.mode_id,
                "name": speed_mode.display_name,
                "reason": "Qisqa vaqt ichida tezkor refleks va dars mavzusini mustahkamlash uchun ideal."
            })

        if game_mode_registry.has("classic"):
            classic_mode = game_mode_registry.get("classic")
            suggestions.append({
                "id": classic_mode.mode_id,
                "name": classic_mode.display_name,
                "reason": "Standart individual format, barcha maktab sinflari uchun mos."
            })

        return suggestions

    @classmethod
    @transaction.atomic
    def create_quiz_draft(
        cls,
        spec: AIGeneratedQuiz,
        teacher_user: Any,
    ) -> Dict[str, Any]:
        """
        Saves an AI-generated quiz draft to the canonical Quiz and Question tables.
        """
        if not teacher_user or not getattr(teacher_user, "is_authenticated", False):
            raise PermissionError("Authentication required to create quiz draft.")

        quiz = Quiz.objects.create(
            title=spec.title,
            description=spec.description,
            owner=teacher_user,
            status="draft",
        )

        created_questions = []
        for q in spec.questions:
            # Map question type
            q_type = q.type.value if hasattr(q.type, "value") else str(q.type)
            if q_type == "multiple_select":
                q_type = "multiple_choice"

            question_obj = Question.objects.create(
                quiz=quiz,
                order_index=q.order - 1,
                type=q_type,
                prompt=q.prompt,
                options=[opt.model_dump() for opt in q.options],
                correct_answer=q.correct_answer,
                explanation=q.explanation,
                points=q.points,
                time_limit_seconds=q.time_limit_seconds,
                is_locked=False,
            )
            created_questions.append(str(question_obj.id))

        return {
            "quiz_id": str(quiz.id),
            "status": quiz.status,
            "title": quiz.title,
            "question_count": len(created_questions),
            "created_question_ids": created_questions,
        }

    @classmethod
    def validate_quiz_content(cls, quiz: AIGeneratedQuiz) -> Dict[str, Any]:
        """
        Runs the ContentValidator pipeline on the provided quiz.
        """
        report = ContentValidator.validate_quiz(quiz)
        return {
            "is_valid": report.is_valid,
            "errors": report.errors,
            "warnings": report.warnings,
            "flagged_orders": report.flagged_question_orders,
        }

    @classmethod
    def lock_question(
        cls,
        question_id: str,
        is_locked: bool,
        teacher_user: Any,
    ) -> Dict[str, Any]:
        """
        Locks or unlocks a question to protect it from AI overwrite.
        """
        question = Question.objects.select_related("quiz").filter(id=question_id).first()
        if not question:
            raise ValueError(f"Question {question_id} not found.")

        if question.quiz.owner != teacher_user:
            raise PermissionError("You do not have permission to modify this quiz question.")

        question.is_locked = is_locked
        question.save(update_fields=["is_locked"])

        return {
            "question_id": str(question.id),
            "order": question.order_index + 1,
            "is_locked": question.is_locked,
        }
