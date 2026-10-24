import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.ai_gateway.crypto import encrypt_api_key, decrypt_api_key


class AIProviderChoices(models.TextChoices):
    OPENAI = "openai", "OpenAI"
    GEMINI = "gemini", "Google Gemini"
    CLAUDE = "claude", "Anthropic Claude"
    DEEPSEEK = "deepseek", "DeepSeek"
    GROQ = "groq", "Groq"
    QWEN = "qwen", "Qwen (Alibaba)"
    GROK = "grok", "xAI Grok"


class UserApiKey(models.Model):
    """
    DOC-77: Secure encrypted store for user-provided BYOK API keys.
    Never stores plain-text API keys; protected with AES-256-GCM.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_api_keys",
    )
    provider = models.CharField(
        max_length=32,
        choices=AIProviderChoices.choices,
    )
    encrypted_key = models.BinaryField()
    iv = models.BinaryField()
    auth_tag = models.BinaryField()
    masked_key = models.CharField(max_length=64)
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_ai_credentials"
        verbose_name = "User AI API Key"
        verbose_name_plural = "User AI API Keys"
        unique_together = [("user", "provider")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.get_provider_display()} ({self.masked_key})"

    def set_key(self, plain_key: str) -> None:
        """Encrypts and sets the API key."""
        ciphertext, iv, auth_tag, masked = encrypt_api_key(plain_key)
        self.encrypted_key = ciphertext
        self.iv = iv
        self.auth_tag = auth_tag
        self.masked_key = masked
        self.is_valid = True

    def get_key(self) -> str:
        """Decrypts and returns the plain-text API key in memory."""
        return decrypt_api_key(self.encrypted_key, self.iv, self.auth_tag)


class TokenUsageLog(models.Model):
    """
    DOC-76: Tracks token consumption, latency, and estimated cost per AI request.
    Enforces per-teacher quotas and platform financial guardrails.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="token_usage_logs",
    )
    provider = models.CharField(max_length=32)
    model_id = models.CharField(max_length=64)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cached_tokens = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0.000000"))
    latency_ms = models.IntegerField(default=0)
    task_type = models.CharField(max_length=64, default="general")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "token_usage_logs"
        verbose_name = "Token Usage Log"
        verbose_name_plural = "Token Usage Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.provider}:{self.model_id} - {self.total_tokens} toks (${self.estimated_cost_usd})"
