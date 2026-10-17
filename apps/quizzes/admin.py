"""
Django Admin integration for Quiz, Question, and QuizVersion.
"""

from django.contrib import admin
from .models import Quiz, Question, QuizVersion


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ('order_index', 'type', 'prompt', 'points', 'time_limit_seconds', 'is_locked')
    ordering = ('order_index',)


class QuizVersionInline(admin.TabularInline):
    model = QuizVersion
    extra = 0
    readonly_fields = ('version_number', 'created_at')
    can_delete = False


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'subject', 'grade_level', 'status', 'current_version', 'created_at')
    list_filter = ('status', 'subject', 'grade_level', 'locale')
    search_fields = ('title', 'description', 'owner__username', 'owner__email')
    inlines = [QuestionInline, QuizVersionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('prompt', 'quiz', 'type', 'points', 'time_limit_seconds', 'order_index', 'is_locked')
    list_filter = ('type', 'difficulty', 'is_locked', 'quiz__subject')
    search_fields = ('prompt', 'quiz__title')


@admin.register(QuizVersion)
class QuizVersionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'version_number', 'created_at')
    list_filter = ('version_number', 'quiz__subject')
    search_fields = ('quiz__title',)
    readonly_fields = ('created_at',)
