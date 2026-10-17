"""
AI Gateway & BYOK Models.
Spetsifikatsiya: .docs/ai/BYOK.md & AI_COSTS.md
"""
import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from apps.ai_gateway.crypto import encrypt_api_key, decrypt_api_key


class AIProviderChoice(models.TextChoices):
    OPENAI = 'openai', 'OpenAI'
    GEMINI = 'gemini', 'Google Gemini'
    CLAUDE = 'claude', 'Anthropic Claude'
    DEEPSEEK = 'deepseek', 'DeepSeek'
    GROQ = 'groq', 'Groq'
    QWEN = 'qwen', 'Qwen (DashScope)'
    GROK = 'grok', 'xAI Grok'


class UserApiKey(models.Model):
    """
    O'qituvchi yoki muassasaning shaxsiy API kalitlari (BYOK).
    Kalitlar AES-256-GCM orqali shifrlangan holatda saqlanadi.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ai_api_keys'
    )
    provider = models.CharField(
        max_length=32,
        choices=AIProviderChoice.choices,
        db_index=True
    )
    encrypted_key = models.BinaryField(help_text="AES-256-GCM shifrlangan ma'lumot")
    iv = models.BinaryField(help_text="12-baytlik unikal Initialization Vector")
    auth_tag = models.BinaryField(help_text="16-baytlik GCM autentifikatsiya tegi")
    masked_key = models.CharField(
        max_length=64,
        help_text="Xavfsiz niqoblangan kalit (masalan, sk-proj-...8f9a)"
    )
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'user_ai_credentials'
        verbose_name = 'Foydalanuvchi API kaliti (BYOK)'
        verbose_name_plural = 'Foydalanuvchi API kalitlari (BYOK)'
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'provider'],
                name='unique_user_provider_api_key'
            )
        ]

    def set_key(self, plain_key: str):
        """API kalitni shifrlab saqlash."""
        enc_data, iv, tag, masked = encrypt_api_key(plain_key)
        self.encrypted_key = enc_data
        self.iv = iv
        self.auth_tag = tag
        self.masked_key = masked

    def get_key(self) -> str:
        """Shifrlangan kalitni ochib qaytarish."""
        # Convert memoryview/bytes
        enc = bytes(self.encrypted_key) if isinstance(self.encrypted_key, memoryview) else self.encrypted_key
        iv = bytes(self.iv) if isinstance(self.iv, memoryview) else self.iv
        tag = bytes(self.auth_tag) if isinstance(self.auth_tag, memoryview) else self.auth_tag
        return decrypt_api_key(enc, iv, tag)

    def __str__(self):
        return f"{self.user} - {self.provider} ({self.masked_key})"


class TokenUsageLog(models.Model):
    """
    Har bir AI so'rovi uchun tokenlar sarfi va moliyaviy xarajat auditi.
    Spetsifikatsiya: .docs/ai/AI_COSTS.md
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_token_logs'
    )
    provider = models.CharField(max_length=32, db_index=True)
    model_name = models.CharField(max_length=64, db_index=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    cached_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=Decimal('0.000000'),
        help_text="Hisoblangan AQSH dollaridagi xarajat"
    )
    latency_ms = models.PositiveIntegerField(default=0)
    task_type = models.CharField(max_length=64, default='quiz_generation', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ai_token_usage_logs'
        verbose_name = 'AI Token Sarfi Logi'
        verbose_name_plural = 'AI Token Sarflari Loglari'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.provider}/{self.model_name}: {self.total_tokens} tokens (${self.estimated_cost_usd})"
