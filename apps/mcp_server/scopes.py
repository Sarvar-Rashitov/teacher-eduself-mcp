# ============================================================
# EduSelf Teacher — apps/mcp_server/scopes.py
# OAuth Scopes Verification & Enforcement Decorator
# MCP_SCOPES.md DOC-85 asosida
# ============================================================
import inspect
from functools import wraps
from typing import List, Union

from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.exceptions import MCPForbiddenError


# Standart Scope lar ro'yxati
SCOPE_QUIZ_READ = "quiz:read"
SCOPE_QUIZ_WRITE = "quiz:write"
SCOPE_SESSION_CREATE = "session:create"
SCOPE_SESSION_CONTROL = "session:control"
SCOPE_SESSION_READ = "session:read"
SCOPE_REPORT_READ = "report:read"

# Moslashuvchanlik uchun sinonimlar (Aliases)
SCOPE_ALIASES = {
    "quizzes:read": SCOPE_QUIZ_READ,
    "quizzes:write": SCOPE_QUIZ_WRITE,
    "session:host": SCOPE_SESSION_CONTROL,
    "sessions:control": SCOPE_SESSION_CONTROL,
    "reports:read": SCOPE_REPORT_READ,
}


def normalize_scope(scope_name: str) -> str:
    """Scope nomini standart shaklga keltiradi."""
    return SCOPE_ALIASES.get(scope_name.strip(), scope_name.strip())


def has_scope(user_scopes: List[str], required_scope: str) -> bool:
    """Foydalanuvchi doiralari orasida talab qilingan scope bormi tekshiradi."""
    normalized_required = normalize_scope(required_scope)
    normalized_user = {normalize_scope(s) for s in user_scopes}
    return normalized_required in normalized_user


def require_scope(*required_scopes: str):
    """
    MCP tool funksiyasini OAuth 2.1 ruxsat doiralari (Scopes) bilan himoyalovchi dekorator.
    Bir nechta scope ko'rsatilsa, foydalanuvchida ULARNING BARCHASI bo'lishi shart (AND sharti).
    """
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                ctx = get_current_mcp_context()
                user_scopes = ctx.scopes
                for req in required_scopes:
                    if not has_scope(user_scopes, req):
                        raise MCPForbiddenError(
                            f"Ushbu amalni bajarish uchun '{req}' ruxsat doirasi (scope) yetishmaydi!",
                            data={
                                "required_scope": req,
                                "granted_scopes": user_scopes,
                            }
                        )
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                ctx = get_current_mcp_context()
                user_scopes = ctx.scopes
                for req in required_scopes:
                    if not has_scope(user_scopes, req):
                        raise MCPForbiddenError(
                            f"Ushbu amalni bajarish uchun '{req}' ruxsat doirasi (scope) yetishmaydi!",
                            data={
                                "required_scope": req,
                                "granted_scopes": user_scopes,
                            }
                        )
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator
