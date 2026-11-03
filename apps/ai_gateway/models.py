"""
Database Models for AI Gateway & BYOK (Bring Your Own Key) Management.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from .crypto import encrypt_api_key, decrypt_api_key, mask_api_key, DecryptionError


class AIProviderChoices(models.TextChoices):
    OPENAI = 'openai', 'OpenAI'
    GEMINI = 'gemini', 'Google Gemini'
    CLAUDE = 'claude', 'Anthropic Claude'
    DEEPSEEK = 'deepseek', 'DeepSeek'
    GROQ = 'groq', 'Groq'
    QWEN = 'qwen', 'Qwen'
    GROK = 'grok', 'xAI Grok'


class UserApiKey(models.Model):
    """
    Stores a user's encrypted personal API key for BYOK functionality.
    Guarantees:
    - Never stores plaintext API keys in the database.
    - Uses AES-256-GCM with distinct IV and Auth Tag per key.
    - Exposes a safe masked key string for UI display.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='api_keys',
        db_index=True
    )
    provider = models.CharField(
        max_length=32,
        choices=AIProviderChoices.choices,
        db_index=True
    )
    encrypted_key = models.BinaryField(help_text="AES-256-GCM encrypted ciphertext")
    iv = models.BinaryField(help_text="12-byte initialization vector")
    auth_tag = models.BinaryField(help_text="16-byte GCM authentication tag")
    masked_key = models.CharField(max_length=64, help_text="e.g. sk-proj-...4a1b")
    is_valid = models.BooleanField(default=True, help_text="False if validation handshake or request failed auth")
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ai_user_api_keys'
        verbose_name = 'User API Key'
        verbose_name_plural = 'User API Keys'
        unique_together = ('user', 'provider')
        indexes = [
            models.Index(fields=['user', 'provider']),
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.get_provider_display()} ({self.masked_key})"

    def set_key(self, plain_key: str) -> None:
        """
        Encrypts the plaintext key and populates encrypted_key, iv, auth_tag, and masked_key.
        """
        if not plain_key:
            raise ValueError("API key cannot be empty.")
        
        enc_key, iv, tag = encrypt_api_key(plain_key)
        self.encrypted_key = enc_key
        self.iv = iv
        self.auth_tag = tag
        self.masked_key = mask_api_key(plain_key)
        self.is_valid = True

    def get_key(self) -> str:
        """
        Decrypts and returns the plaintext API key in memory.
        Raises DecryptionError if the key was tampered with or master key is wrong.
        """
        # Convert memoryview/bytes safely
        enc_bytes = bytes(self.encrypted_key) if self.encrypted_key else b''
        iv_bytes = bytes(self.iv) if self.iv else b''
        tag_bytes = bytes(self.auth_tag) if self.auth_tag else b''
        
        return decrypt_api_key(enc_bytes, iv_bytes, tag_bytes)

    def mark_used(self) -> None:
        """Updates last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at', 'updated_at'])


class TokenUsageLog(models.Model):
    """
    Audit log of token consumption and financial cost per model interaction.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='token_usage_logs',
        db_index=True
    )
    provider = models.CharField(max_length=32, db_index=True)
    model_id = models.CharField(max_length=64, db_index=True)
    task_type = models.CharField(max_length=64, default='general', db_index=True)
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    cached_tokens = models.IntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal('0.000000'))
    latency_ms = models.IntegerField(default=0, help_text="Total round-trip latency in milliseconds")
    is_byok = models.BooleanField(default=False, help_text="True if executed using the user's personal API key")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'ai_token_usage_logs'
        verbose_name = 'Token Usage Log'
        verbose_name_plural = 'Token Usage Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['task_type', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"{self.provider}/{self.model_id} ({self.total_tokens} tokens, ${self.cost_usd}) at {self.created_at}"
