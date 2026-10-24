"""
MCP Authorization Scopes Specification according to DOC-85 (MCP_SCOPES.md).
Defines standard scopes, validation decorators, and destructive operation markers.
"""

from functools import wraps
import inspect
from typing import Callable, List, Union
from apps.mcp_server.auth import get_current_mcp_context
from apps.mcp_server.exceptions import MCPForbiddenError


class Scopes:
    """Rasmiy OAuth 2.1 ruxsat doiralari (Scopes)."""
    QUIZ_READ = "quiz:read"
    QUIZ_WRITE = "quiz:write"
    SESSION_CREATE = "session:create"
    SESSION_CONTROL = "session:control"
    SESSION_READ = "session:read"
    REPORT_READ = "report:read"

    ALL = {QUIZ_READ, QUIZ_WRITE, SESSION_CREATE, SESSION_CONTROL, SESSION_READ, REPORT_READ}


def require_scope(required_scope: Union[str, List[str]]):
    """
    Funksiya chaqirilishidan oldin joriy kontekstdagi scope'larni tekshiruvchi dekorator.
    Bir nechta scope berilsa, ularning kamida bittasi yoki barchasi talab qilinishi mumkin.
    """
    needed_scopes = [required_scope] if isinstance(required_scope, str) else list(required_scope)

    def decorator(func: Callable) -> Callable:
        setattr(func, "_required_scopes", needed_scopes)

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                ctx = get_current_mcp_context()
                for scope in needed_scopes:
                    if not ctx.has_scope(scope):
                        raise MCPForbiddenError(
                            f"Ushbu amalni bajarish uchun '{scope}' ruxsati yetishmaydi."
                        )
                return await func(*args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                ctx = get_current_mcp_context()
                for scope in needed_scopes:
                    if not ctx.has_scope(scope):
                        raise MCPForbiddenError(
                            f"Ushbu amalni bajarish uchun '{scope}' ruxsati yetishmaydi."
                        )
                return func(*args, **kwargs)
            return sync_wrapper

    return decorator


def destructive_operation(func: Callable) -> Callable:
    """
    O'qituvchi tasdig'ini (destructiveHint: True) talab qiluvchi amallarni belgilovchi dekorator.
    (Masalan: start_session, reveal_answers, end_session).
    """
    setattr(func, "_is_destructive", True)
    return func
