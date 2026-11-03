from rest_framework import serializers
from .models import LiveSession, Participant, AnswerSubmission
from apps.quizzes.models import Quiz


class CreateSessionSerializer(serializers.Serializer):
    quiz_id = serializers.UUIDField()
    game_mode = serializers.CharField(max_length=50, default='classic')
    settings_payload = serializers.DictField(required=False, default=dict)

    def validate_quiz_id(self, value):
        if not Quiz.objects.filter(id=value).exists():
            raise serializers.ValidationError("Ko'rsatilgan Quiz topilmadi.")
        return value


class JoinSessionSerializer(serializers.Serializer):
    room_code = serializers.CharField(max_length=10)
    nickname = serializers.CharField(max_length=50)
    team_name = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    anonymous_token = serializers.CharField(max_length=64, required=False, allow_blank=True, allow_null=True)


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = [
            'id',
            'nickname',
            'team_name',
            'score',
            'streak',
            'is_connected',
            'joined_at',
        ]


class LiveSessionSerializer(serializers.ModelSerializer):
    participants_count = serializers.SerializerMethodField()
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)

    class Meta:
        model = LiveSession
        fields = [
            'id',
            'room_code',
            'quiz',
            'quiz_title',
            'game_mode',
            'status',
            'is_lobby_locked',
            'current_question_index',
            'participants_count',
            'started_at',
            'ended_at',
            'created_at',
        ]

    def get_participants_count(self, obj):
        return obj.participants.filter(is_kicked=False).count()


class AnswerSubmitSerializer(serializers.Serializer):
    question_id = serializers.UUIDField()
    submission_id = serializers.CharField(max_length=64)
    response_data = serializers.DictField()
    client_submit_ts = serializers.IntegerField(required=False, default=None)
