from django.contrib import admin
from .models import LiveSession, Participant, AnswerSubmission


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    fields = ["nickname", "team_name", "score", "current_streak", "is_connected", "is_kicked"]
    readonly_fields = ["anonymous_token"]


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = [
        "room_code",
        "quiz",
        "host",
        "game_mode",
        "status",
        "fsm_state",
        "is_locked",
        "total_participants",
        "created_at",
    ]
    list_filter = ["status", "fsm_state", "is_locked", "game_mode"]
    search_fields = ["room_code", "quiz__title", "host__username"]
    inlines = [ParticipantInline]
    readonly_fields = ["id", "room_code", "created_at", "updated_at", "snapshot_data"]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = [
        "nickname",
        "session",
        "team_name",
        "score",
        "current_streak",
        "is_connected",
        "is_kicked",
    ]
    list_filter = ["is_connected", "is_kicked", "session__game_mode"]
    search_fields = ["nickname", "session__room_code"]
    readonly_fields = ["id", "anonymous_token", "joined_at", "last_seen_at"]


@admin.register(AnswerSubmission)
class AnswerSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        "participant",
        "session",
        "question_id",
        "is_correct",
        "score_awarded",
        "server_latency_ms",
        "created_at",
    ]
    list_filter = ["is_correct", "created_at"]
    search_fields = ["participant__nickname", "session__room_code", "submission_id"]
    readonly_fields = ["id", "created_at"]
