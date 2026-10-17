# apps/quizzes/services.py
# QUIZ_ENGINE.md va Backend.md §2.2 asosida
import logging
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.questions_registry.registry import question_registry
from apps.questions_registry.exceptions import QuestionRegistryError
from .models import Quiz, Question, QuizVersion

logger = logging.getLogger(__name__)


class QuestionValidator:
    """
    Savol ma'lumotlarini QuestionTypeRegistry orqali tekshiruvchi servis.
    """
    @staticmethod
    def validate(type_id: str, options: Any, correct_answer: Any, accepted_alternatives: Optional[List] = None, points: int = 1000, time_limit: int = 30):
        # 1. Vaqt va ball me'yorlari
        if points < 0 or points > 10000:
            raise ValidationError({'points': "Ball 0 dan 10,000 gacha bo'lishi kerak."})
        if time_limit < 5 or time_limit > 300:
            raise ValidationError({'time_limit_seconds': "Taymer 5 dan 300 soniyagacha bo'lishi kerak."})

        # 2. Registr orqali savol turi mavjudligi va payload tekshiruvi
        try:
            handler = question_registry.get(type_id)
            handler.validate_payload(options, correct_answer, accepted_alternatives)
        except QuestionRegistryError as e:
            raise ValidationError({'correct_answer': str(e)})


class QuizService:
    """
    Quiz va Question boshqaruvining asosiy Application Servisi.
    """

    @staticmethod
    def create_quiz(owner, title: str, subject: str, grade_level: int = 7, locale: str = 'uz-Latn', **kwargs) -> Quiz:
        """Yangi qoralama quiz yaratish."""
        return Quiz.objects.create(
            owner=owner,
            title=title,
            subject=subject,
            grade_level=grade_level,
            locale=locale,
            status='draft',
            **kwargs
        )

    @staticmethod
    @transaction.atomic
    def add_question(
        quiz: Quiz,
        type_id: str,
        prompt: str,
        correct_answer: Any,
        options: Any = None,
        points: int = 1000,
        time_limit_seconds: int = 30,
        difficulty: str = 'medium',
        order_index: Optional[int] = None,
        explanation: str = '',
        accepted_alternatives: Optional[List] = None,
        **kwargs
    ) -> Question:
        """
        Quizga yangi savol qo'shish va uning validatsiyasini ta'minlash.
        """
        if options is None:
            options = []
        if accepted_alternatives is None:
            accepted_alternatives = []

        # 1. Validatsiya
        QuestionValidator.validate(
            type_id=type_id,
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=accepted_alternatives,
            points=points,
            time_limit=time_limit_seconds
        )

        # 2. Tartib raqami belgilanmagan bo'lsa oxiriga qo'yish
        if order_index is None:
            last_q = quiz.questions.order_by('-order_index').first()
            order_index = (last_q.order_index + 1) if last_q else 0

        question = Question.objects.create(
            quiz=quiz,
            type=type_id,
            prompt=prompt,
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=accepted_alternatives,
            explanation=explanation,
            points=points,
            time_limit_seconds=time_limit_seconds,
            difficulty=difficulty,
            order_index=order_index,
            **kwargs
        )

        # Quiz versiyasini yangilash
        quiz.current_version += 1
        quiz.save(update_fields=['current_version', 'updated_at'])

        return question

    @staticmethod
    @transaction.atomic
    def update_question(question: Question, is_ai_action: bool = False, **data) -> Question:
        """
        Savolni tahrirlash.
        Agar is_locked=True bo'lsa va AI tahrir qilmoqchi bo'lsa, bloklanadi!
        """
        if question.is_locked and is_ai_action:
            raise ValidationError("Ushbu savol qulflangan, AI orqali o'zgartirish taqiqlangan.")

        type_id = data.get('type', question.type)
        options = data.get('options', question.options)
        correct_answer = data.get('correct_answer', question.correct_answer)
        accepted_alternatives = data.get('accepted_alternatives', question.accepted_alternatives)
        points = data.get('points', question.points)
        time_limit = data.get('time_limit_seconds', question.time_limit_seconds)

        # Validatsiya
        QuestionValidator.validate(
            type_id=type_id,
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=accepted_alternatives,
            points=points,
            time_limit=time_limit
        )

        for key, value in data.items():
            setattr(question, key, value)

        question.version += 1
        question.save()

        # Quiz versiyasini yangilash
        question.quiz.current_version += 1
        question.quiz.save(update_fields=['current_version', 'updated_at'])

        return question

    @staticmethod
    def create_version_snapshot(quiz: Quiz) -> QuizVersion:
        """
        Jonli sessiya boshlanishida quizning butun holatini muzlatish (snapshot).
        QUIZ_ENGINE.md §4: Immutability & Snapshotting.
        """
        questions_data = []
        for q in quiz.questions.order_by('order_index'):
            questions_data.append({
                'id': str(q.id),
                'type': q.type,
                'prompt': q.prompt,
                'media_url': q.media_url,
                'media_type': q.media_type,
                'options': q.options,
                'correct_answer': q.correct_answer,
                'accepted_alternatives': q.accepted_alternatives,
                'explanation': q.explanation,
                'points': q.points,
                'time_limit_seconds': q.time_limit_seconds,
                'difficulty': q.difficulty,
                'order_index': q.order_index,
                'is_locked': q.is_locked,
                'version': q.version,
            })

        snapshot = {
            'quiz_id': str(quiz.id),
            'title': quiz.title,
            'description': quiz.description,
            'subject': quiz.subject,
            'grade_level': quiz.grade_level,
            'locale': quiz.locale,
            'version_number': quiz.current_version,
            'questions': questions_data
        }

        quiz_version, _ = QuizVersion.objects.update_or_create(
            quiz=quiz,
            version_number=quiz.current_version,
            defaults={'snapshot_data': snapshot}
        )
        return quiz_version

    @staticmethod
    def get_sanitized_questions_for_student(quiz: Quiz) -> List[Dict]:
        """
        Zero-Knowledge Question Delivery:
        Talaba uchun savollarni xavfsiz holatga keltirish (correct_answer olib tashlanadi).
        QUIZ_ENGINE.md §3 asosida.
        """
        sanitized_list = []
        for q in quiz.questions.order_by('order_index'):
            handler = question_registry.get(q.type)
            sanitized_options = handler.sanitize_for_student(q.options)

            sanitized_list.append({
                'id': str(q.id),
                'type': q.type,
                'prompt': q.prompt,
                'media_url': q.media_url,
                'media_type': q.media_type,
                'options': sanitized_options,
                'points': q.points,
                'time_limit_seconds': q.time_limit_seconds,
                'order_index': q.order_index,
                # correct_answer, accepted_alternatives va explanation YO'Q!
            })
        return sanitized_list
