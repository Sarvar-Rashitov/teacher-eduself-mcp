from django.contrib import admin
from .models import LiveSession, Participant, AnswerSubmission


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    readonly_fields = ("id", "nickname", "score", "streak", "is_connected", "joined_at")


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ("room_code", "quiz", "host", "status", "game_mode", "is_locked", "created_at")
    list_filter = ("status", "game_mode", "is_locked", "created_at")
    search_fields = ("room_code", "quiz__title", "host__username")
    inlines = [ParticipantInline]
    readonly_fields = ("id", "room_code", "created_at")


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("nickname", "session", "score", "streak", "is_connected", "joined_at")
    list_filter = ("is_connected", "joined_at")
    search_fields = ("nickname", "session__room_code")
    readonly_fields = ("id", "anonymous_token", "joined_at")


@admin.register(AnswerSubmission)
class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = ("participant", "session", "question", "is_correct", "score_awarded", "time_taken_ms", "created_at")
    list_filter = ("is_correct", "created_at")
    search_fields = ("participant__nickname", "session__room_code", "submission_id")
    readonly_fields = ("id", "submission_id", "created_at")
