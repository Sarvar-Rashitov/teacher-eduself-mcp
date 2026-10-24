import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from .crypto import AESGCMCipher, mask_api_key


class UserApiKey(models.Model):
    """
    Stores encrypted BYOK (Bring Your Own Key) credentials.
    Implements DOC-77 (BYOK.md).
    Plaintext API keys are NEVER stored in the database.
    """

    PROVIDER_CHOICES = [
        ("openai", "OpenAI"),
        ("gemini", "Google Gemini"),
        ("claude", "Anthropic Claude"),
        ("deepseek", "DeepSeek"),
        ("groq", "Groq"),
        ("qwen", "Qwen (DashScope)"),
        ("grok", "xAI Grok"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_credentials",
    )
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    encrypted_key = models.BinaryField()
    iv = models.BinaryField()
    auth_tag = models.BinaryField()
    masked_key = models.CharField(max_length=64)
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_ai_credentials"
        unique_together = ("user", "provider")
        verbose_name = "User API Key"
        verbose_name_plural = "User API Keys"

    def __str__(self):
        return f"{self.user} — {self.provider} ({self.masked_key})"

    def set_key(self, plain_key: str, master_key: bytes = None) -> None:
        """Encrypts plaintext key and stores IV, tag, and masked preview."""
        ct, iv, tag = AESGCMCipher.encrypt(plain_key, master_key=master_key)
        self.encrypted_key = ct
        self.iv = iv
        self.auth_tag = tag
        self.masked_key = mask_api_key(plain_key)

    def get_key(self, master_key: bytes = None) -> str:
        """Decrypts and returns the plaintext key in memory."""
        ct = bytes(self.encrypted_key) if not isinstance(self.encrypted_key, bytes) else self.encrypted_key
        iv = bytes(self.iv) if not isinstance(self.iv, bytes) else self.iv
        tag = bytes(self.auth_tag) if not isinstance(self.auth_tag, bytes) else self.auth_tag
        return AESGCMCipher.decrypt(ct, iv, tag, master_key=master_key)

    def mark_used(self) -> None:
        self.last_used_at = timezone.now()
        self.save(update_fields=["last_used_at"])


class TokenUsageLog(models.Model):
    """
    Tracks token consumption, latency, and costs per AI request.
    Implements DOC-76 (AI_COSTS.md).
    """

    STATUS_CHOICES = [
        ("success", "Success"),
        ("fallback_used", "Fallback Used"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_logs",
    )
    provider = models.CharField(max_length=32)
    model_name = models.CharField(max_length=64)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cached_tokens = models.IntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=10, decimal_places=6, default=Decimal("0.000000")
    )
    latency_ms = models.IntegerField(default=0)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="success")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ai_token_usage_logs"
        ordering = ["-created_at"]
        verbose_name = "Token Usage Log"
        verbose_name_plural = "Token Usage Logs"

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.model_name} — {self.total_tokens} tokens (${self.estimated_cost_usd})"
