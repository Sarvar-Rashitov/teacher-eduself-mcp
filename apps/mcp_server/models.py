# ============================================================
# EduSelf Teacher — apps/mcp_server/models.py
# OAuth 2.1 & API Tokens for External MCP Clients
# MCP_AUTH.md DOC-84 asosida
# ============================================================
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class MCPClient(models.Model):
    """
    Tashqi AI Mijoz dasturi (Claude Desktop, Cursor, Custom Agent).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client_id = models.CharField(max_length=128, unique=True, db_index=True)
    client_name = models.CharField(max_length=255)
    redirect_uris = models.JSONField(default=list, help_text="Ruxsat berilgan redirect URI lar ro'yxati")
    is_trusted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MCP Client"
        verbose_name_plural = "MCP Clients"

    def __str__(self):
        return f"{self.client_name} ({self.client_id})"


class MCPOAuthAuthorizationCode(models.Model):
    """
    OAuth 2.1 + PKCE avtorizatsiya kodi (vaqtinchalik, bir martalik).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=128, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mcp_auth_codes')
    client_id = models.CharField(max_length=128, db_index=True)
    redirect_uri = models.CharField(max_length=512)
    code_challenge = models.CharField(max_length=255)
    code_challenge_method = models.CharField(max_length=32, default='S256')
    scopes = models.CharField(max_length=512, default="quiz:read quiz:write session:create session:control session:read report:read")
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "MCP OAuth Authorization Code"
        verbose_name_plural = "MCP OAuth Authorization Codes"

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at


class MCPApiToken(models.Model):
    """
    Mahalliy Stdio / CLI mijozlar uchun doimiy yoki uzoq muddatli API kalit (usr_token_...).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mcp_api_tokens')
    name = models.CharField(max_length=128, default="CLI Token")
    token = models.CharField(max_length=255, unique=True, db_index=True)
    scopes = models.CharField(max_length=512, default="quiz:read quiz:write session:create session:control session:read report:read")
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "MCP API Token"
        verbose_name_plural = "MCP API Tokens"

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() >= self.expires_at:
            return False
        return True
