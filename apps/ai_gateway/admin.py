from django.contrib import admin
from .models import UserApiKey, TokenUsageLog


@admin.register(UserApiKey)
class UserApiKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'provider', 'masked_key', 'is_valid', 'last_used_at', 'created_at')
    list_filter = ('provider', 'is_valid', 'created_at')
    search_fields = ('user__username', 'user__email', 'masked_key')
    readonly_fields = ('masked_key', 'created_at', 'updated_at', 'last_used_at')
    # encrypted_key, iv, auth_tag are sensitive and never displayed as plaintext


@admin.register(TokenUsageLog)
class TokenUsageLogAdmin(admin.ModelAdmin):
    list_display = ('provider', 'model_id', 'user', 'task_type', 'total_tokens', 'cost_usd', 'latency_ms', 'is_byok', 'created_at')
    list_filter = ('provider', 'is_byok', 'task_type', 'created_at')
    search_fields = ('model_id', 'user__username', 'task_type')
    readonly_fields = ('id', 'created_at')
