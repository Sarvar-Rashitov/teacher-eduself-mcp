"""
Authentication, Token Management, and Context Isolation for EduSelf MCP Server.
Conforms to DOC-84 (MCP_AUTH.md) and DOC-86 (MCP_SECURITY.md).
"""

import time
import jwt
from contextvars import ContextVar
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Set
from django.conf import settings
from django.contrib.auth import get_user_model

from .exceptions import MCPUnauthorizedError
from .scopes import TEACHER_DEFAULT_SCOPES, ALL_SCOPES


User = get_user_model()


@dataclass
class MCPContext:
    """O'qituvchi va mijozning xavfsiz izolyatsiyalangan konteksti."""
    user: Any
    organization: Any = None
    scopes: Set[str] = field(default_factory=set)
    client_name: str = "unknown"
    session_id: Optional[str] = None
    token_payload: dict = field(default_factory=dict)


_current_mcp_context: ContextVar[Optional[MCPContext]] = ContextVar(
    "current_mcp_context", default=None
)


def get_current_mcp_context() -> Optional[MCPContext]:
    """Joriy asinxron/sinxron zanjirdagi MCP kontekstini qaytaradi."""
    return _current_mcp_context.get()


def set_current_mcp_context(context: MCPContext):
    """MCP kontekstini o'rnatadi va qayta tiklash tokenini beradi."""
    return _current_mcp_context.set(context)


def reset_current_mcp_context(token):
    """Avvalgi kontekstni tiklaydi."""
    _current_mcp_context.reset(token)


@contextmanager
def mcp_context_scope(context: MCPContext):
    """Kontekstni vaqtinchalik xavfsiz blok ichida o'rnatish uchun context manager."""
    token = set_current_mcp_context(context)
    try:
        yield context
    finally:
        reset_current_mcp_context(token)


def generate_mcp_token(user, scopes: Optional[Iterable[str]] = None, expires_in: int = 3600, client_name: str = "claude-desktop") -> str:
    """Testlar va OAuth mijozlar uchun haqiqiy JWT Bearer token generatsiya qiladi."""
    now = int(time.time())
    active_scopes = set(scopes) if scopes is not None else TEACHER_DEFAULT_SCOPES
    payload = {
        "user_id": str(user.id),
        "sub": str(user.id),
        "email": getattr(user, "email", ""),
        "role": getattr(user, "role", "TEACHER"),
        "scope": " ".join(active_scopes),
        "client_name": client_name,
        "iat": now,
        "exp": now + expires_in,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def authenticate_bearer_token(auth_header_or_token: str, client_name: str = "unknown") -> MCPContext:
    """
    Bearer token yoki raw tokenni tekshiradi va MCPContext qaytaradi.
    Token noto'g'ri yoki muddati o'tgan bo'lsa, MCPUnauthorizedError ko'taradi.
    """
    if not auth_header_or_token:
        raise MCPUnauthorizedError("Autentifikatsiya tokeni taqdim etilmagan.")

    raw_token = auth_header_or_token.strip()
    if raw_token.lower().startswith("bearer "):
        raw_token = raw_token[7:].strip()

    if not raw_token:
        raise MCPUnauthorizedError("Bo'sh Bearer token taqdim etilgan.")

    try:
        payload = jwt.decode(raw_token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise MCPUnauthorizedError("Token muddati o'tgan (Expired token). Iltimos, qayta kiring.")
    except jwt.InvalidTokenError:
        raise MCPUnauthorizedError("Yaroqsiz token (Invalid signature or malformed payload).")

    user_id = payload.get("user_id") or payload.get("sub")
    if not user_id:
        raise MCPUnauthorizedError("Token ichida foydalanuvchi identifikatori (user_id) topilmadi.")

    try:
        user = User.objects.filter(id=user_id, is_active=True).first()
    except Exception:
        user = None

    if not user:
        raise MCPUnauthorizedError("Foydalanuvchi topilmadi yoki faol emas.")

    # Scopes ajratish
    scope_val = payload.get("scope", "")
    if isinstance(scope_val, str):
        scopes = set(scope_val.split()) if scope_val else set()
    elif isinstance(scope_val, (list, tuple, set)):
        scopes = set(scope_val)
    else:
        scopes = set()

    # Agar token scope ko'rsatmagan bo'lsa va foydalanuvchi o'qituvchi bo'lsa:
    if not scopes:
        scopes = TEACHER_DEFAULT_SCOPES.copy()

    detected_client = payload.get("client_name") or client_name

    organization = getattr(user, "organization", None)
    return MCPContext(
        user=user,
        organization=organization,
        scopes=scopes,
        client_name=detected_client,
        token_payload=payload
    )
