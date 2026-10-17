# ============================================================
# EduSelf Teacher — apps/mcp_server/exceptions.py
# JSON-RPC 2.0 & EduSelf Domain Exceptions
# MCP_ERRORS.md DOC-89 asosida
# ============================================================
from typing import Any, Optional
from mcp.shared.exceptions import MCPError


# Standard JSON-RPC 2.0 Error Codes
CODE_PARSE_ERROR = -32700
CODE_INVALID_REQUEST = -32600
CODE_METHOD_NOT_FOUND = -32601
CODE_INVALID_PARAMS = -32602
CODE_INTERNAL_ERROR = -32603

# EduSelf Specific Domain Error Codes
CODE_UNAUTHORIZED = -32001
CODE_FORBIDDEN = -32003
CODE_RESOURCE_NOT_FOUND = -32004
CODE_INVALID_SESSION_STATE = -32005
CODE_CONFIRMATION_REQUIRED = -32006
CODE_CONTENT_VALIDATION_FAILED = -32007
CODE_RATE_LIMIT_EXCEEDED = -32008


class EduSelfMCPException(MCPError):
    """Barcha EduSelf MCP xatoliklari uchun tayanch sinf."""
    def __init__(self, code: int, message: str, data: Optional[Any] = None):
        super().__init__(code=code, message=message, data=data)


class MCPUnauthorizedError(EduSelfMCPException):
    """-32001: Autentifikatsiya tokeni yo'q yoki muddati o'tgan."""
    def __init__(self, message: str = "Autentifikatsiya talab qilinadi (token yo'q yoki yaroqsiz)", data: Optional[Any] = None):
        payload = {"error_code": "UNAUTHORIZED"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_UNAUTHORIZED, message=message, data=payload)


class MCPForbiddenError(EduSelfMCPException):
    """-32003: Kerakli scope yetishmaydi yoki boshqa o'qituvchining ma'lumotlariga kirish taqiqlangan."""
    def __init__(self, message: str = "Ushbu amalni bajarish uchun ruxsat yetarli emas", data: Optional[Any] = None):
        payload = {"error_code": "FORBIDDEN"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_FORBIDDEN, message=message, data=payload)


class MCPResourceNotFoundError(EduSelfMCPException):
    """-32004: Quiz, savol yoki sessiya topilmadi."""
    def __init__(self, message: str = "So'ralgan resurs topilmadi", data: Optional[Any] = None):
        payload = {"error_code": "RESOURCE_NOT_FOUND"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_RESOURCE_NOT_FOUND, message=message, data=payload)


class MCPInvalidSessionStateError(EduSelfMCPException):
    """-32005: Sessiya joriy holati ushbu buyruqni qabul qilmaydi."""
    def __init__(self, message: str = "Noto'g'ri sessiya holatida buyruq berildi", data: Optional[Any] = None):
        payload = {"error_code": "INVALID_SESSION_STATE"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_INVALID_SESSION_STATE, message=message, data=payload)


class MCPConfirmationRequiredError(EduSelfMCPException):
    """-32006: Xavfli amal (destructiveHint) uchun o'qituvchi tasdig'i talab qilinadi."""
    def __init__(self, message: str = "Ushbu xavfli amal uchun o'qituvchi tasdig'i talab qilinadi", data: Optional[Any] = None):
        payload = {"error_code": "CONFIRMATION_REQUIRED"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_CONFIRMATION_REQUIRED, message=message, data=payload)


class MCPContentValidationError(EduSelfMCPException):
    """-32007: Savollar pedagogik qoidalarga yoki JSON sxemasiga mos kelmaydi."""
    def __init__(self, message: str = "Savol formati yoki mazmuni pedagogik talablarga mos emas", data: Optional[Any] = None):
        payload = {"error_code": "CONTENT_VALIDATION_FAILED"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_CONTENT_VALIDATION_FAILED, message=message, data=payload)


class MCPRateLimitExceededError(EduSelfMCPException):
    """-32008: So'rovlar me'yordan oshib ketdi."""
    def __init__(self, message: str = "So'rovlar chastotasi me'yordan oshdi", data: Optional[Any] = None):
        payload = {"error_code": "RATE_LIMIT_EXCEEDED"}
        if data and isinstance(data, dict):
            payload.update(data)
        super().__init__(code=CODE_RATE_LIMIT_EXCEEDED, message=message, data=payload)
