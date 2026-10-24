from rest_framework import serializers
from questions_registry import question_registry, QuestionValidationError
from .models import Quiz, Question, QuizVersion


class QuestionSerializer(serializers.ModelSerializer):
    """Full question serializer for teachers and admins."""

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


class QuestionStudentSerializer(serializers.ModelSerializer):
    """
    Zero-Knowledge student serializer.
    Guarantees that no answer keys, explanations, or option-level 'is_correct'
    flags are ever sent over the network to student devices.
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
            "points",
            "time_limit_seconds",
            "difficulty",
            "order_index",
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        try:
            handler = question_registry.get(instance.type)
            return handler.sanitize_for_student(ret)
        except Exception:
            # Fallback safe sanitization
            ret.pop("correct_answer", None)
            ret.pop("explanation", None)
            return ret


class QuestionCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for validating and creating/updating questions."""

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
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        type_id = attrs.get("type", getattr(self.instance, "type", None))
        prompt = attrs.get("prompt", getattr(self.instance, "prompt", ""))
        options = attrs.get("options", getattr(self.instance, "options", []))
        correct_answer = attrs.get("correct_answer", getattr(self.instance, "correct_answer", {}))
        time_limit = attrs.get("time_limit_seconds", getattr(self.instance, "time_limit_seconds", 30))
        points = attrs.get("points", getattr(self.instance, "points", 1000))

        if not prompt or not str(prompt).strip():
            raise serializers.ValidationError({"prompt": "Savol matni bo'sh bo'lishi mumkin emas."})

        if time_limit < 5 or time_limit > 300:
            raise serializers.ValidationError({
                "time_limit_seconds": "Vaqt 5 dan 300 soniyagacha bo'lishi kerak."
            })

        if points < 0:
            raise serializers.ValidationError({"points": "Ball manfiy bo'lishi mumkin emas."})

        if not question_registry.is_registered(type_id):
            raise serializers.ValidationError({
                "type": f"'{type_id}' nomli savol turi registratsiyadan o'tmagan."
            })

        handler = question_registry.get(type_id)
        try:
            handler.validate_payload(options, correct_answer)
        except QuestionValidationError as exc:
            raise serializers.ValidationError({"payload": exc.message}) from exc

        return attrs


class QuizVersionSerializer(serializers.ModelSerializer):
    """Serializer for QuizVersion snapshot objects."""

    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = QuizVersion
        fields = [
            "id",
            "quiz",
            "version_number",
            "title",
            "change_log",
            "created_at",
            "created_by",
            "created_by_username",
            "snapshot_data",
        ]
        read_only_fields = ["id", "created_at", "version_number"]


class QuizSerializer(serializers.ModelSerializer):
    """Full quiz serializer with all questions for author / teacher."""

    questions = QuestionSerializer(many=True, read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    total_questions = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "owner",
            "owner_username",
            "title",
            "description",
            "subject",
            "grade_level",
            "locale",
            "status",
            "current_version",
            "is_public",
            "google_sheet_url",
            "total_questions",
            "total_points",
            "created_at",
            "updated_at",
            "questions",
        ]
        read_only_fields = ["id", "owner", "current_version", "created_at", "updated_at"]


class QuizStudentSerializer(serializers.ModelSerializer):
    """Zero-Knowledge quiz serializer for student participants."""

    questions = QuestionStudentSerializer(many=True, read_only=True)
    total_questions = serializers.IntegerField(read_only=True)

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
            "total_questions",
            "questions",
        ]


class QuizCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating quiz metadata."""

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
            "is_public",
            "google_sheet_url",
        ]
        read_only_fields = ["id"]
