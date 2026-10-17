from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization, TeacherProfile


class TeacherProfileInline(admin.StackedInline):
    model = TeacherProfile
    can_delete = False
    verbose_name_plural = "O'qituvchi Profili"
    extra = 0


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'subscription_plan', 'ai_monthly_token_budget', 'created_at')
    list_filter = ('subscription_plan', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'organization', 'telegram_id', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active', 'organization')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'telegram_id')
    ordering = ('username',)
    inlines = [TeacherProfileInline]

    fieldsets = BaseUserAdmin.fieldsets + (
        ("EduSelf Qo'shimcha Ma'lumotlari", {
            'fields': ('id', 'role', 'organization', 'telegram_id', 'preferred_locale', 'avatar_url')
        }),
    )
    readonly_fields = ('id',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'phone_number', 'created_at')
    search_fields = ('user__username', 'user__email', 'subject', 'phone_number')
    list_filter = ('subject', 'created_at')
    readonly_fields = ('id', 'created_at', 'updated_at')
