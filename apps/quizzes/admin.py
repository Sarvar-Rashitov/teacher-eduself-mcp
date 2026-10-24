from django.contrib import admin
from .models import Quiz, Question, QuizVersion


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 1
    fields = [
        "type",
        "prompt",
        "options",
        "correct_answer",
        "points",
        "time_limit_seconds",
        "difficulty",
        "order_index",
        "is_locked",
    ]


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "owner",
        "subject",
        "grade_level",
        "status",
        "current_version",
        "is_public",
        "created_at",
    ]
    list_filter = ["status", "subject", "grade_level", "is_public"]
    search_fields = ["title", "description", "owner__username"]
    inlines = [QuestionInline]
    readonly_fields = ["id", "current_version", "created_at", "updated_at"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = [
        "prompt_snippet",
        "quiz",
        "type",
        "points",
        "time_limit_seconds",
        "difficulty",
        "order_index",
        "is_locked",
    ]
    list_filter = ["type", "difficulty", "is_locked"]
    search_fields = ["prompt", "quiz__title"]
    readonly_fields = ["id", "version"]

    def prompt_snippet(self, obj):
        return obj.prompt[:60] + ("..." if len(obj.prompt) > 60 else "")
    prompt_snippet.short_description = "Savol"


@admin.register(QuizVersion)
class QuizVersionAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "quiz",
        "version_number",
        "created_at",
        "created_by",
    ]
    list_filter = ["version_number", "created_at"]
    search_fields = ["title", "quiz__title", "change_log"]
    readonly_fields = ["id", "created_at", "snapshot_data"]
