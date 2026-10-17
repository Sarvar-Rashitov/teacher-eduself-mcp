"""
Django Admin registration and customization for Organization, User and TeacherProfile.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, TeacherProfile


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = 'O‘qituvchi Profili'
    fk_name = 'user'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_plan', 'ai_monthly_token_budget', 'created_at')
    list_filter = ('subscription_plan',)
    search_fields = ('name',)
    ordering = ('-created_at',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (TeacherProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'organization', 'telegram_id', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'organization')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'telegram_id')
    ordering = ('username',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ('EduSelf Qo‘shimcha Ma’lumotlari', {
            'fields': ('role', 'organization', 'telegram_id', 'preferred_locale', 'avatar_url')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('EduSelf Qo‘shimcha Ma’lumotlari', {
            'fields': ('role', 'organization', 'telegram_id', 'preferred_locale', 'avatar_url')
        }),
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject_specialization', 'default_grade', 'school_name', 'created_at')
    list_filter = ('default_grade', 'subject_specialization')
    search_fields = ('user__username', 'user__email', 'school_name', 'subject_specialization')
