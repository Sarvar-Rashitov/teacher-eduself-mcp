# ============================================================
# EduSelf Teacher — apps/mcp_server/auth.py
# OAuth 2.1 + PKCE, Bearer Token and API Token Authentication
# MCP_AUTH.md DOC-84 asosida
# ============================================================
import base64
import hashlib
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional, List, Dict, Any

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.mcp_server.exceptions import MCPUnauthorizedError
from apps.mcp_server.models import MCPApiToken

User = get_user_model()


@dataclass
class MCPContext:
    """
    Joriy MCP sessiyasi / so'rovi konteksti.
    O'qituvchi ma'lumotlari va ruxsat doiralarini (scopes) saqlaydi.
    """
    user: Any
    token_type: str = "bearer"  # "bearer" yoki "api_token"
    scopes: List[str] = field(default_factory=list)
    client_id: Optional[str] = None
    raw_token: Optional[str] = None

    @property
    def organization(self):
        return getattr(self.user, 'organization', None)

    @property
    def token_payload(self) -> Dict[str, Any]:
        return {
            "sub": str(self.user.id),
            "user_id": str(self.user.id),
            "scope": " ".join(self.scopes),
            "client_id": self.client_id,
        }


# ContextVar orqali asinxron va oqimlararo izolyatsiya
_current_mcp_context: ContextVar[Optional[MCPContext]] = ContextVar("current_mcp_context", default=None)


def get_current_mcp_context() -> MCPContext:
    """Joriy MCP so'rov kontekstini oladi. Agar mavjud bo'lmasa xatolik beradi."""
    ctx = _current_mcp_context.get()
    if ctx is None:
        raise MCPUnauthorizedError("Autentifikatsiya konteksti topilmadi (so'rov avtorizatsiyadan o'tmagan)")
    return ctx


def set_current_mcp_context(context: Optional[MCPContext]):
    """Joriy kontekstni o'rnatadi."""
    return _current_mcp_context.set(context)


def reset_current_mcp_context(token):
    """Kontekstni tozalaydi."""
    _current_mcp_context.reset(token)


# -------------------------------------------------------------
# PKCE (Proof Key for Code Exchange) Yordamchi Funksiyalari
# -------------------------------------------------------------
def verify_pkce(code_verifier: str, code_challenge: str, method: str = 'S256') -> bool:
    """
    RFC 7636 talablari bo'yicha PKCE S256 kodini tekshiradi.
    code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))
    """
    if method == 'plain':
        return code_verifier == code_challenge

    if method != 'S256':
        return False

    digest = hashlib.sha256(code_verifier.encode('ascii')).digest()
    computed_challenge = base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')
    return computed_challenge == code_challenge.rstrip('=')


# -------------------------------------------------------------
# Token Yaratish va Autentifikatsiya Qilish
# -------------------------------------------------------------
DEFAULT_SCOPES = [
    "quiz:read",
    "quiz:write",
    "session:create",
    "session:control",
    "session:read",
    "report:read"
]


def generate_access_token(user, scopes: Optional[List[str]] = None, client_id: Optional[str] = None, expires_in: int = 3600) -> str:
    """
    O'qituvchi uchun 1 soatlik JWT access_token generatsiya qiladi.
    """
    now = int(time.time())
    if scopes is None:
        scopes = DEFAULT_SCOPES

    payload = {
        "sub": str(user.id),
        "user_id": str(user.id),
        "username": user.username,
        "scope": " ".join(scopes),
        "client_id": client_id,
        "iat": now,
        "exp": now + expires_in,
        "iss": "eduself-mcp-idp"
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def authenticate_token(token: str) -> MCPContext:
    """
    Kelgan Bearer yoki API tokenni tekshiradi va MCPContext qaytaradi.
    Token noto'g'ri yoki muddati o'tgan bo'lsa MCPUnauthorizedError chiqaradi.
    """
    if not token:
        raise MCPUnauthorizedError("Autentifikatsiya tokeni ko'rsatilmadi")

    clean_token = token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()

    # 1. API Token tekshiruvi (usr_token_...)
    if clean_token.startswith("usr_token_") or len(clean_token) == 64:
        try:
            api_token = MCPApiToken.objects.select_related('user').get(token=clean_token)
        except MCPApiToken.DoesNotExist:
            raise MCPUnauthorizedError("Noto'g'ri API kalit taqdim etildi")

        if not api_token.is_valid():
            raise MCPUnauthorizedError("API kalit faol emas yoki muddati o'tgan")

        api_token.last_used_at = timezone.now()
        api_token.save(update_fields=['last_used_at'])

        scopes = [s.strip() for s in api_token.scopes.split() if s.strip()]
        return MCPContext(
            user=api_token.user,
            token_type="api_token",
            scopes=scopes,
            client_id="local-cli",
            raw_token=clean_token
        )

    # 2. JWT Bearer Token tekshiruvi
    try:
        payload = jwt.decode(clean_token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise MCPUnauthorizedError("Token muddati o'tib ketgan")
    except jwt.InvalidTokenError as e:
        raise MCPUnauthorizedError(f"Noto'g'ri token: {str(e)}")

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise MCPUnauthorizedError("Tokenda user identifikatori topilmadi")

    try:
        user = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        raise MCPUnauthorizedError("Foydalanuvchi topilmadi yoki hisob bloklangan")

    raw_scopes = payload.get("scope", "")
    scopes = [s.strip() for s in raw_scopes.split() if s.strip()] if raw_scopes else DEFAULT_SCOPES

    return MCPContext(
        user=user,
        token_type="bearer",
        scopes=scopes,
        client_id=payload.get("client_id"),
        raw_token=clean_token
    )
