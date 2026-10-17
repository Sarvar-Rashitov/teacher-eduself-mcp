"""
Business and domain services for Quizzes and Questions.
Orchestrates creation, validation via QuestionTypeRegistry, lock protection, and snapshot versioning.
"""

import json
from typing import Dict, Any, Optional
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from apps.questions_registry.registry import question_type_registry
from apps.questions_registry.exceptions import QuestionValidationError
from .models import Quiz, Question, QuizVersion
from .serializers import QuestionStudentSerializer, QuestionTeacherSerializer


class QuizService:
    """
    Application service managing the lifecycle of Quizzes, Questions, and Snapshots.
    """

    @staticmethod
    def create_quiz(
        owner,
        title: str,
        subject: str,
        grade_level: int = 7,
        locale: str = 'uz-Latn',
        description: Optional[str] = None,
        google_sheet_url: Optional[str] = None
    ) -> Quiz:
        """Create a new draft quiz owned by a teacher."""
        return Quiz.objects.create(
            owner=owner,
            title=title,
            subject=subject,
            grade_level=grade_level,
            locale=locale,
            description=description,
            google_sheet_url=google_sheet_url,
            status='draft',
            current_version=1
        )

    @staticmethod
    def add_question(quiz: Quiz, data: dict) -> Question:
        """
        Validates payload against the QuestionTypeRegistry plugin and creates Question.
        """
        q_type = data.get('type')
        if not q_type:
            raise QuestionValidationError("Savol turi ('type') ko‘rsatilishi shart.")

        plugin = question_type_registry.get(q_type)
        options = data.get('options', [])
        correct_answer = data.get('correct_answer')

        # Validate through plugin contract
        plugin.validate_payload(options=options, correct_answer=correct_answer)

        # Calculate automatic order_index if not provided
        order_index = data.get('order_index')
        if order_index is None:
            order_index = quiz.questions.count()

        question = Question.objects.create(
            quiz=quiz,
            type=q_type,
            prompt=data.get('prompt', ''),
            media_url=data.get('media_url'),
            media_type=data.get('media_type'),
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=data.get('accepted_alternatives', []),
            explanation=data.get('explanation'),
            points=data.get('points', 1000),
            time_limit_seconds=data.get('time_limit_seconds', 30),
            difficulty=data.get('difficulty', 'medium'),
            order_index=order_index,
            is_locked=data.get('is_locked', False),
            version=1,
        )
        return question

    @staticmethod
    def update_question(question: Question, data: dict, enforce_lock: bool = True) -> Question:
        """
        Updates an existing question, strictly respecting the is_locked protection flag.
        """
        if question.is_locked and enforce_lock and not data.get('unlock', False):
            raise QuestionValidationError(
                "Ushbu savol qulflangan (is_locked=True). Uni o‘zgartirish uchun avval qulfdan chiqaring."
            )

        q_type = data.get('type', question.type)
        options = data.get('options', question.options)
        correct_answer = data.get('correct_answer', question.correct_answer)

        plugin = question_type_registry.get(q_type)
        plugin.validate_payload(options=options, correct_answer=correct_answer)

        # Update allowed fields
        for field in [
            'prompt', 'media_url', 'media_type', 'explanation',
            'points', 'time_limit_seconds', 'difficulty', 'order_index'
        ]:
            if field in data:
                setattr(question, field, data[field])

        question.type = q_type
        question.options = options
        question.correct_answer = correct_answer
        if 'accepted_alternatives' in data:
            question.accepted_alternatives = data['accepted_alternatives']
        if 'is_locked' in data:
            question.is_locked = data['is_locked']

        question.version += 1
        question.save()
        return question

    @staticmethod
    def delete_question(question: Question, enforce_lock: bool = True) -> bool:
        """Delete question respecting lock and re-indexing remaining questions."""
        if question.is_locked and enforce_lock:
            raise QuestionValidationError("Qulflangan savolni o‘chirib bo‘lmaydi.")

        quiz = question.quiz
        with transaction.atomic():
            question.delete()
            # Re-index remaining questions
            for idx, q in enumerate(quiz.questions.order_by('order_index')):
                if q.order_index != idx:
                    q.order_index = idx
                    q.save(update_fields=['order_index'])
        return True

    @staticmethod
    def publish_quiz_version(quiz: Quiz) -> QuizVersion:
        """
        Takes an immutable snapshot of the current quiz and its questions,
        storing it into QuizVersion and incrementing version counter.
        """
        with transaction.atomic():
            questions_data = QuestionTeacherSerializer(quiz.questions.all(), many=True).data
            raw_snapshot = {
                'quiz_id': str(quiz.id),
                'title': quiz.title,
                'subject': quiz.subject,
                'grade_level': quiz.grade_level,
                'locale': quiz.locale,
                'version_number': quiz.current_version,
                'questions': questions_data,
            }
            # Serialize via DjangoJSONEncoder so UUIDs, datetimes etc. become JSON primitives
            snapshot = json.loads(json.dumps(raw_snapshot, cls=DjangoJSONEncoder))

            version_record = QuizVersion.objects.create(
                quiz=quiz,
                version_number=quiz.current_version,
                snapshot_data=snapshot
            )

            quiz.current_version += 1
            quiz.status = 'published'
            quiz.save(update_fields=['current_version', 'status'])

            return version_record

    @staticmethod
    def get_student_sanitized_quiz(quiz: Quiz) -> dict:
        """
        Prepares a Zero-Knowledge sanitized representation of the quiz for students.
        """
        questions = quiz.questions.all()
        sanitized_questions = QuestionStudentSerializer(questions, many=True).data

        return {
            'id': str(quiz.id),
            'title': quiz.title,
            'subject': quiz.subject,
            'grade_level': quiz.grade_level,
            'locale': quiz.locale,
            'question_count': len(sanitized_questions),
            'questions': sanitized_questions,
        }
