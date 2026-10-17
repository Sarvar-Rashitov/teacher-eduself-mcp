# apps/live_sessions/admin.py
from django.contrib import admin
from .models import LiveSession, Participant, AnswerSubmission


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ('nickname', 'score', 'streak', 'is_connected', 'joined_at')
    readonly_fields = ('joined_at',)


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('room_code', 'quiz', 'host', 'game_mode', 'status', 'participant_count', 'started_at', 'created_at')
    list_filter = ('status', 'game_mode', 'is_lobby_locked')
    search_fields = ('room_code', 'quiz__title', 'host__username')
    readonly_fields = ('id', 'room_code', 'created_at', 'updated_at')
    inlines = [ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('nickname', 'session', 'score', 'streak', 'is_connected', 'joined_at')
    list_filter = ('is_connected', 'session__game_mode')
    search_fields = ('nickname', 'session__room_code', 'anonymous_token')
    readonly_fields = ('id', 'anonymous_token', 'joined_at')


@admin.register(AnswerSubmission)
class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ('session', 'participant', 'question_id', 'is_correct', 'points_awarded', 'response_time_ms', 'created_at')
    list_filter = ('is_correct', 'session__game_mode')
    search_fields = ('participant__nickname', 'session__room_code')
    readonly_fields = ('id', 'created_at')
