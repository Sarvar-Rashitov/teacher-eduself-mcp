"""
Django REST Framework serializers for Quiz and Question models.
Enforces Zero-Knowledge Question Delivery for student-facing endpoints.
"""

from rest_framework import serializers
from apps.questions_registry.registry import question_type_registry
from .models import Quiz, Question, QuizVersion


class QuestionTeacherSerializer(serializers.ModelSerializer):
    """
    Teacher/Host serializer.
    Includes full metadata, secret answer keys, alternatives, explanations, and lock status.
    """
    class Meta:
        model = Question
        fields = [
            'id',
            'quiz',
            'type',
            'prompt',
            'media_url',
            'media_type',
            'options',
            'correct_answer',
            'accepted_alternatives',
            'explanation',
            'points',
            'time_limit_seconds',
            'difficulty',
            'order_index',
            'is_locked',
            'version',
        ]
        read_only_fields = ['id', 'version']


class QuestionStudentSerializer(serializers.ModelSerializer):
    """
    Zero-Knowledge student/projector serializer.
    Completely scrubs 'correct_answer', 'accepted_alternatives', 'explanation',
    and removes any 'is_correct' flags from options array.
    """
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id',
            'type',
            'prompt',
            'media_url',
            'media_type',
            'options',
            'points',
            'time_limit_seconds',
            'difficulty',
            'order_index',
        ]

    def get_options(self, obj):
        try:
            plugin = question_type_registry.get(obj.type)
            return plugin.sanitize_for_student(obj.options)
        except Exception:
            # Fallback zero-knowledge sanitizer
            if isinstance(obj.options, list):
                return [
                    {k: v for k, v in opt.items() if k not in ('is_correct', 'correct')}
                    for opt in obj.options if isinstance(opt, dict)
                ]
            return obj.options


class QuizSerializer(serializers.ModelSerializer):
    """
    Quiz details serializer for teacher management dashboard.
    """
    question_count = serializers.IntegerField(read_only=True)
    questions = QuestionTeacherSerializer(many=True, read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id',
            'owner',
            'title',
            'description',
            'subject',
            'grade_level',
            'locale',
            'status',
            'current_version',
            'google_sheet_url',
            'question_count',
            'questions',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'owner', 'current_version', 'created_at', 'updated_at']


class QuizVersionSerializer(serializers.ModelSerializer):
    """
    Snapshot serializer for frozen versions.
    """
    class Meta:
        model = QuizVersion
        fields = ['id', 'quiz', 'version_number', 'snapshot_data', 'created_at']
        read_only_fields = ['id', 'created_at']
