from django.contrib import admin
from apps.ai_gateway.models import UserApiKey, TokenUsageLog


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "masked_key", "is_valid", "last_used_at", "created_at")
    list_filter = ("provider", "is_valid", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "masked_key")
    readonly_fields = ("encrypted_key", "iv", "auth_tag", "masked_key", "created_at", "last_used_at")


@admin.register(TokenUsageLog)
class TokenUsageLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "model_id", "total_tokens", "estimated_cost_usd", "latency_ms", "task_type", "created_at")
    list_filter = ("provider", "model_id", "task_type", "created_at")
    search_fields = ("user__email", "model_id", "task_type")
    readonly_fields = (
        "id",
        "user",
        "provider",
        "model_id",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_tokens",
        "estimated_cost_usd",
        "latency_ms",
        "task_type",
        "created_at",
    )
