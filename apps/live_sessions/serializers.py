# apps/live_sessions/serializers.py
from rest_framework import serializers
from .models import LiveSession, Participant, AnswerSubmission


class LiveSessionSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    host_username = serializers.CharField(source='host.username', read_only=True)

    class Meta:
        model = LiveSession
        fields = [
            'id', 'quiz', 'quiz_title', 'host', 'host_username',
            'room_code', 'game_mode', 'status', 'is_lobby_locked',
            'participant_count', 'started_at', 'ended_at', 'created_at'
        ]
        read_only_fields = ['id', 'room_code', 'status', 'created_at']


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ['id', 'nickname', 'team_name', 'score', 'streak', 'is_connected', 'joined_at']
        read_only_fields = ['id', 'score', 'streak', 'joined_at']


class JoinSessionSerializer(serializers.Serializer):
    room_code = serializers.CharField(max_length=6, min_length=6)
    nickname = serializers.CharField(max_length=50)
