from django.contrib import admin
from .models import UserApiKey, TokenUsageLog


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "masked_key", "is_valid", "created_at", "last_used_at")
    list_filter = ("provider", "is_valid")
    search_fields = ("user__username", "user__email", "masked_key")
    readonly_fields = ("masked_key", "created_at", "last_used_at")


@admin.register(TokenUsageLog)
class TokenUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "user",
        "provider",
        "model_name",
        "total_tokens",
        "estimated_cost_usd",
        "latency_ms",
        "status",
    )
    list_filter = ("provider", "status", "created_at")
    search_fields = ("user__username", "model_name")
    readonly_fields = ("created_at",)
