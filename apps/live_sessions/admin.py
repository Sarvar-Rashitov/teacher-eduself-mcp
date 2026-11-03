from django.contrib import admin
from .models import LiveSession, Participant, AnswerSubmission


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    readonly_fields = ['id', 'joined_at', 'last_seen_at']
    fields = ['nickname', 'score', 'streak', 'is_connected', 'is_kicked', 'joined_at']


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ['room_code', 'quiz', 'host', 'status', 'game_mode', 'is_lobby_locked', 'created_at']
    list_filter = ['status', 'game_mode', 'is_lobby_locked']
    search_fields = ['room_code', 'quiz__title', 'host__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    inlines = [ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'session', 'score', 'streak', 'is_connected', 'is_kicked', 'joined_at']
    list_filter = ['is_connected', 'is_kicked', 'session__game_mode']
    search_fields = ['nickname', 'session__room_code', 'anonymous_token']
    readonly_fields = ['id', 'joined_at', 'last_seen_at']


@admin.register(AnswerSubmission)
class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ['submission_id', 'participant', 'session', 'is_correct', 'score_awarded', 'latency_ms', 'created_at']
    list_filter = ['is_correct', 'created_at']
    search_fields = ['submission_id', 'participant__nickname', 'session__room_code']
    readonly_fields = ['id', 'created_at']
