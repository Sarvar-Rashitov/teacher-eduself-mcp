# apps/quizzes/serializers.py
from rest_framework import serializers
from .models import Quiz, Question, QuizVersion
from apps.questions_registry.registry import question_registry
from .services import QuestionValidator


class QuestionSerializer(serializers.ModelSerializer):
    """
    O'qituvchi / Host uchun to'liq savol serializeri.
    Barcha maxfiy kalitlar va tushuntirishlarni o'z ichiga oladi.
    """
    class Meta:
        model = Question
        fields = [
            'id', 'quiz', 'type', 'prompt', 'media_url', 'media_type',
            'options', 'correct_answer', 'accepted_alternatives',
            'explanation', 'points', 'time_limit_seconds', 'difficulty',
            'order_index', 'is_locked', 'version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'version', 'created_at', 'updated_at']

    def validate(self, attrs):
        type_id = attrs.get('type') or (self.instance.type if self.instance else None)
        options = attrs.get('options') if 'options' in attrs else (self.instance.options if self.instance else [])
        correct_answer = attrs.get('correct_answer') if 'correct_answer' in attrs else (self.instance.correct_answer if self.instance else None)
        accepted_alternatives = attrs.get('accepted_alternatives', [])
        points = attrs.get('points', 1000)
        time_limit = attrs.get('time_limit_seconds', 30)

        QuestionValidator.validate(
            type_id=type_id,
            options=options,
            correct_answer=correct_answer,
            accepted_alternatives=accepted_alternatives,
            points=points,
            time_limit=time_limit
        )
        return attrs


class StudentQuestionSerializer(serializers.ModelSerializer):
    """
    Zero-Knowledge Student Serializer.
    QUIZ_ENGINE.md §3: correct_answer, accepted_alternatives va explanation
    tarmoq darajasida filtrlanadi!
    """
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'type', 'prompt', 'media_url', 'media_type',
            'options', 'points', 'time_limit_seconds', 'order_index'
        ]

    def get_options(self, obj):
        handler = question_registry.get(obj.type)
        return handler.sanitize_for_student(obj.options)


class QuizSerializer(serializers.ModelSerializer):
    """
    Quiz ro'yxati va umumiy ma'lumotlari serializeri.
    """
    question_count = serializers.IntegerField(read_only=True)
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'subject', 'grade_level',
            'locale', 'status', 'current_version', 'is_public',
            'google_sheet_url', 'question_count', 'owner_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'current_version', 'created_at', 'updated_at']


class QuizDetailSerializer(QuizSerializer):
    """
    O'qituvchi tahrirlashi uchun savollar bilan to'liq quiz serializeri.
    """
    questions = QuestionSerializer(many=True, read_only=True)

    class Meta(QuizSerializer.Meta):
        fields = QuizSerializer.Meta.fields + ['questions']


class QuizVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuizVersion
        fields = ['id', 'quiz', 'version_number', 'snapshot_data', 'created_at']
        read_only_fields = ['id', 'created_at']
