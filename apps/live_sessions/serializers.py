from rest_framework import serializers
from .models import LiveSession, Participant, AnswerSubmission


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = [
            "id",
            "nickname",
            "team_name",
            "score",
            "current_streak",
            "is_connected",
            "joined_at",
        ]


class LiveSessionSerializer(serializers.ModelSerializer):
    host_username = serializers.CharField(source="host.username", read_only=True)
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    participants = ParticipantSerializer(many=True, read_only=True)
    total_participants = serializers.IntegerField(read_only=True)

    class Meta:
        model = LiveSession
        fields = [
            "id",
            "quiz",
            "quiz_title",
            "host",
            "host_username",
            "room_code",
            "game_mode",
            "status",
            "fsm_state",
            "current_question_index",
            "is_locked",
            "settings_payload",
            "total_participants",
            "started_at",
            "ended_at",
            "created_at",
            "participants",
        ]
        read_only_fields = [
            "id",
            "host",
            "room_code",
            "status",
            "fsm_state",
            "current_question_index",
            "started_at",
            "ended_at",
            "created_at",
        ]


class LiveSessionCreateSerializer(serializers.Serializer):
    quiz_id = serializers.UUIDField(required=True)
    game_mode = serializers.CharField(required=False, default="classic")
    settings_payload = serializers.JSONField(required=False, default=dict)


class JoinSessionSerializer(serializers.Serializer):
    room_code = serializers.CharField(required=True, max_length=10)
    nickname = serializers.CharField(required=True, max_length=50)
    anonymous_token = serializers.CharField(required=False, allow_blank=True, max_length=64)


class AnswerSubmissionSerializer(serializers.ModelSerializer):
    participant_nickname = serializers.CharField(source="participant.nickname", read_only=True)

    class Meta:
        model = AnswerSubmission
        fields = [
            "id",
            "session",
            "participant",
            "participant_nickname",
            "question_id",
            "submission_id",
            "response_data",
            "is_correct",
            "score_awarded",
            "client_submit_ts",
            "server_latency_ms",
            "created_at",
        ]
        read_only_fields = ["id", "is_correct", "score_awarded", "created_at"]
