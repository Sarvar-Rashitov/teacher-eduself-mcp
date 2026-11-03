"""
OAuth 2.1 Scope Definitions and Access Control Decorators.
Conforms to DOC-85 (MCP_SCOPES.md) specification.
"""

import asyncio
from functools import wraps
from typing import Callable, Iterable, Set
from .exceptions import MCPForbiddenError, MCPUnauthorizedError


# Standart OAuth 2.1 Ruxsat Doiralari (Scopes)
SCOPE_QUIZ_READ = "quiz:read"
SCOPE_QUIZ_WRITE = "quiz:write"
SCOPE_SESSION_CREATE = "session:create"
SCOPE_SESSION_CONTROL = "session:control"
SCOPE_SESSION_READ = "session:read"
SCOPE_REPORT_READ = "report:read"

ALL_SCOPES = {
    SCOPE_QUIZ_READ,
    SCOPE_QUIZ_WRITE,
    SCOPE_SESSION_CREATE,
    SCOPE_SESSION_CONTROL,
    SCOPE_SESSION_READ,
    SCOPE_REPORT_READ,
}

# O'qituvchi uchun to'liq standart ruxsatlar to'plami
TEACHER_DEFAULT_SCOPES = ALL_SCOPES.copy()


def require_scope(*required_scopes: str):
    """
    Funksiyani talab qilingan OAuth scope(lar)i bilan himoyalovchi dekorator.
    Kontekstda ushbu ruxsatlar mavjud bo'lmasa, MCPForbiddenError ko'taradi.
    Ham sinxron, ham asinxron chaqiruvlarni qo'llab-quvvatlaydi.
    """
    def decorator(func: Callable):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            from .auth import get_current_mcp_context
            context = get_current_mcp_context()
            if not context or not context.user:
                raise MCPUnauthorizedError("Autentifikatsiya konteksti topilmadi. Token taqdim etilmagan.")

            user_scopes: Set[str] = context.scopes
            for scope in required_scopes:
                if scope not in user_scopes:
                    raise MCPForbiddenError(
                        f"Ushbu amalni bajarish uchun '{scope}' ruxsati yetishmaydi!"
                    )
            return func(*args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            from .auth import get_current_mcp_context
            context = get_current_mcp_context()
            if not context or not context.user:
                raise MCPUnauthorizedError("Autentifikatsiya konteksti topilmadi. Token taqdim etilmagan.")

            user_scopes: Set[str] = context.scopes
            for scope in required_scopes:
                if scope not in user_scopes:
                    raise MCPForbiddenError(
                        f"Ushbu amalni bajarish uchun '{scope}' ruxsati yetishmaydi!"
                    )
            return await func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
