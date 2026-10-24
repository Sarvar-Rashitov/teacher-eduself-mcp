from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "subscription_plan", "ai_monthly_token_budget", "created_at")
    list_filter = ("subscription_plan", "created_at")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "organization",
        "telegram_id",
        "is_staff",
    )
    list_filter = ("role", "is_staff", "is_superuser", "is_active", "organization")
    search_fields = ("username", "email", "first_name", "last_name", "telegram_id")
    ordering = ("username",)

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "EduSelf Qo'shimcha Ma'lumotlari",
            {
                "fields": (
                    "role",
                    "organization",
                    "telegram_id",
                    "preferred_locale",
                    "avatar_url",
                )
            },
        ),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "EduSelf Qo'shimcha Ma'lumotlari",
            {
                "fields": (
                    "role",
                    "organization",
                    "telegram_id",
                    "preferred_locale",
                    "avatar_url",
                )
            },
        ),
    )
