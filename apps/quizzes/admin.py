# apps/quizzes/admin.py
from django.contrib import admin
from .models import Quiz, Question, QuizVersion


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ('order_index', 'type', 'prompt', 'points', 'time_limit_seconds', 'is_locked')
    ordering = ('order_index',)


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'subject', 'grade_level', 'status', 'current_version', 'is_public', 'created_at')
    list_filter = ('status', 'subject', 'grade_level', 'locale', 'is_public')
    search_fields = ('title', 'description', 'owner__username')
    readonly_fields = ('id', 'current_version', 'created_at', 'updated_at')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('prompt_summary', 'quiz', 'type', 'points', 'time_limit_seconds', 'is_locked', 'order_index')
    list_filter = ('type', 'difficulty', 'is_locked', 'quiz__subject')
    search_fields = ('prompt', 'quiz__title')
    readonly_fields = ('id', 'version', 'created_at', 'updated_at')

    def prompt_summary(self, obj):
        return obj.prompt[:50] + ('...' if len(obj.prompt) > 50 else '')
    prompt_summary.short_description = "Savol matni"


@admin.register(QuizVersion)
class QuizVersionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'version_number', 'created_at')
    list_filter = ('quiz__subject',)
    search_fields = ('quiz__title',)
    readonly_fields = ('id', 'created_at', 'snapshot_data')
