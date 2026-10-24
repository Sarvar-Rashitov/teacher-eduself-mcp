from rest_framework import serializers
from apps.questions_registry.registry import registry
from .models import Quiz, Question, QuizVersion


class TeacherQuestionSerializer(serializers.ModelSerializer):
    """
    O'qituvchi boshqaruv paneli uchun to'liq savol serializeri.
    Barcha to'g'ri javob kalitlari va tushuntirishlarni o'z ichiga oladi.
    """
    class Meta:
        model = Question
        fields = [
            "id",
            "quiz",
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
            "version",
        ]
        read_only_fields = ["id", "version"]


class StudentQuestionSerializer(serializers.ModelSerializer):
    """
    Talaba va jonli sessiya uchun xavfsiz (Zero-Knowledge) savol serializeri.
    To'g'ri javob kaliti va izohlar butunlay olib tashlangan.
    """
    options = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "type",
            "prompt",
            "media_url",
            "media_type",
            "options",
            "points",
            "time_limit_seconds",
            "order_index",
        ]

    def get_options(self, obj):
        if registry.is_registered(obj.type):
            handler = registry.get(obj.type)
            return handler.sanitize_for_student(obj.options)
        return obj.options


class QuizSerializer(serializers.ModelSerializer):
    """
    Viktorinalar ro'yxati va umumiy ma'lumotlar serializeri.
    """
    question_count = serializers.IntegerField(source="questions.count", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "title",
            "description",
            "subject",
            "grade_level",
            "locale",
            "status",
            "current_version",
            "google_sheet_url",
            "question_count",
            "owner_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "current_version", "created_at", "updated_at"]


class QuizDetailSerializer(QuizSerializer):
    """
    Viktorina va uning barcha savollari tafsilotlari serializeri.
    """
    questions = TeacherQuestionSerializer(many=True, read_only=True)

    class Meta(QuizSerializer.Meta):
        fields = QuizSerializer.Meta.fields + ["questions"]


class QuizVersionSerializer(serializers.ModelSerializer):
    """
    Muzlatilgan versiyalar serializeri.
    """
    class Meta:
        model = QuizVersion
        fields = ["id", "quiz", "version_number", "snapshot", "created_at"]
        read_only_fields = ["id", "created_at"]
