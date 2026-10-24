"""
MCP Authentication & Context Management according to DOC-84 (MCP_AUTH.md).
Handles JWT Bearer tokens, token generation, validation, and request context.
"""

from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.mcp_server.exceptions import MCPUnauthorizedError, MCPForbiddenError

User = get_user_model()

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "eduself-mcp-server"


class MCPContext:
    """
    Joriy MCP so'rov konteksti.
    Token egasi, ruxsat etilgan scope'lar va mijoz haqidagi ma'lumotlarni saqlaydi.
    """

    def __init__(
        self,
        user: Any,
        scopes: Set[str],
        client_info: Optional[Dict[str, Any]] = None,
        token_payload: Optional[Dict[str, Any]] = None,
    ):
        self.user = user
        self.scopes = set(scopes)
        self.client_info = client_info or {}
        self.token_payload = token_payload or {}

    @property
    def teacher_id(self) -> str:
        return str(self.user.id)

    @property
    def organization_id(self) -> Optional[str]:
        return str(self.user.organization_id) if getattr(self.user, "organization_id", None) else None

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def __repr__(self) -> str:
        return f"<MCPContext user={self.user.username} scopes={sorted(list(self.scopes))}>"


_current_context: ContextVar[Optional[MCPContext]] = ContextVar("mcp_context", default=None)


def get_current_mcp_context() -> MCPContext:
    """Joriy kontekstni qaytaradi. Kontekst bo'lmasa xatolik chiqaradi."""
    ctx = _current_context.get()
    if ctx is None:
        raise MCPUnauthorizedError("Faol MCP sessiyasi yoki konteksti topilmadi.")
    return ctx


def set_current_mcp_context(context: Optional[MCPContext]):
    """Joriy kontekstni o'rnatadi."""
    return _current_context.set(context)


class MCPAuthContextManager:
    """Sinxron va asinxron testlar va kod bloklari uchun context manager."""

    def __init__(self, user: Any, scopes: List[str], client_info: Optional[Dict[str, Any]] = None):
        self.context = MCPContext(user=user, scopes=set(scopes), client_info=client_info)
        self.token = None

    def __enter__(self):
        self.token = set_current_mcp_context(self.context)
        return self.context

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            _current_context.reset(self.token)

    async def __aenter__(self):
        self.token = set_current_mcp_context(self.context)
        return self.context

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.token is not None:
            _current_context.reset(self.token)


def generate_mcp_token(
    user: Any,
    scopes: List[str],
    expires_in_seconds: int = 3600,
    client_id: str = "claude-desktop",
) -> str:
    """
    OAuth 2.1 Access Token (JWT) yaratish.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "iss": JWT_ISSUER,
        "sub": str(user.id),
        "username": user.username,
        "client_id": client_id,
        "scope": " ".join(scopes),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_mcp_token(token_str: str) -> MCPContext:
    """
    JWT tokenni tekshiradi va MCPContext qaytaradi.
    Muddati o'tgan, soxtalashtirilgan yoki topilmagan foydalanuvchilar uchun xato qaytaradi.
    """
    if not token_str or not isinstance(token_str, str):
        raise MCPUnauthorizedError("Token bo'sh yoki noto'g'ri formatda.")

    # "Bearer ..." prefiksini tozalash
    token_clean = token_str.strip()
    if token_clean.lower().startswith("bearer "):
        token_clean = token_clean[7:].strip()

    try:
        payload = jwt.decode(
            token_clean,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "scope"]},
        )
    except jwt.ExpiredSignatureError:
        raise MCPUnauthorizedError("Token muddati tugagan (Expired token).")
    except jwt.InvalidTokenError as e:
        raise MCPUnauthorizedError(f"Yaroqsiz token: {str(e)}")

    user_id = payload.get("sub")
    user = User.objects.filter(id=user_id).first()
    if not user:
        raise MCPUnauthorizedError("Tokendagi foydalanuvchi tizimda topilmadi.")

    if not user.is_active:
        raise MCPForbiddenError("Foydalanuvchi hisobi faol emas (Inactivated account).")

    raw_scopes = payload.get("scope", "")
    scopes_set = set(raw_scopes.split()) if isinstance(raw_scopes, str) else set(raw_scopes)

    return MCPContext(
        user=user,
        scopes=scopes_set,
        client_info={"client_id": payload.get("client_id", "unknown")},
        token_payload=payload,
    )


def authenticate_header(auth_header: Optional[str]) -> MCPContext:
    """
    HTTP Authorization sarlavhasidan tokenni ajratib olib tekshiradi.
    """
    if not auth_header:
        raise MCPUnauthorizedError("Authorization sarlavhasi ko'rsatilmagan.")

    return verify_mcp_token(auth_header)
