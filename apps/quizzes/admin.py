from django.contrib import admin
from .models import Quiz, Question, QuizVersion


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("order_index", "type", "prompt", "points", "time_limit_seconds", "is_locked")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "subject", "grade_level", "status", "current_version", "created_at")
    list_filter = ("status", "subject", "grade_level", "created_at")
    search_fields = ("title", "subject", "owner__username", "owner__email")
    inlines = [QuestionInline]
    readonly_fields = ("id", "current_version", "created_at", "updated_at")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("order_index", "prompt", "quiz", "type", "points", "time_limit_seconds", "is_locked")
    list_filter = ("type", "difficulty", "is_locked")
    search_fields = ("prompt", "quiz__title")
    readonly_fields = ("id", "version")


@admin.register(QuizVersion)
class QuizVersionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "version_number", "created_at")
    readonly_fields = ("id", "quiz", "version_number", "snapshot", "created_at")
