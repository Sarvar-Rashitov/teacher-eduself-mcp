# apps/authentication/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, TeacherProfile


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = "O‘qituvchi Profili"
    fk_name = 'user'


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Kengaytirilgan UserAdmin — EduSelf rollari, tashkilot va Telegram ID bilan.
    """
    inlines = (TeacherProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'organization', 'telegram_id', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'preferred_locale', 'organization')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'telegram_id')
    ordering = ('username',)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("EduSelf Sozlamalari (RBAC)", {
            'fields': ('role', 'organization', 'telegram_id', 'preferred_locale', 'avatar_url')
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("EduSelf Sozlamalari (RBAC)", {
            'fields': ('role', 'organization', 'telegram_id', 'preferred_locale')
        }),
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_plan', 'ai_monthly_token_budget', 'created_at')
    list_filter = ('subscription_plan',)
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'phone_number', 'created_at')
    search_fields = ('user__username', 'user__email', 'subject', 'phone_number')
    readonly_fields = ('id', 'created_at', 'updated_at')
