"""
MCP and JSON-RPC 2.0 error specifications according to DOC-89 (MCP_ERRORS.md).
"""

from typing import Any, Dict, Optional


class MCPError(Exception):
    """Asosiy MCP va JSON-RPC 2.0 istisnosi."""

    def __init__(self, message: str, code: int = -32603, data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.data = data or {}

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.data:
            result["data"] = self.data
        return result


class JSONRPCParseError(MCPError):
    def __init__(self, message: str = "Invalid JSON text"):
        super().__init__(message, code=-32700)


class JSONRPCInvalidRequestError(MCPError):
    def __init__(self, message: str = "Invalid JSON-RPC request"):
        super().__init__(message, code=-32600)


class JSONRPCMethodNotFoundError(MCPError):
    def __init__(self, message: str = "Method or tool not found"):
        super().__init__(message, code=-32601)


class JSONRPCInvalidParamsError(MCPError):
    def __init__(self, message: str = "Invalid params or schema validation failed"):
        super().__init__(message, code=-32602)


class JSONRPCInternalError(MCPError):
    def __init__(self, message: str = "Internal server error"):
        super().__init__(message, code=-32603)


# EduSelf maxsus domen xatolari (-32000 ... -32099)

class MCPUnauthorizedError(MCPError):
    """Token yo'q, muddati o'tgan yoki yaroqsiz."""
    def __init__(self, message: str = "Autentifikatsiyadan o'tilmagan yoki token yaroqsiz"):
        super().__init__(message, code=-32001, data={"error_code": "UNAUTHORIZED"})


class MCPForbiddenError(MCPError):
    """Talab qilingan scope mavjud emas yoki tenant/boshqa o'qituvchi resursi."""
    def __init__(self, message: str = "Ushbu amalni bajarish uchun yetarli ruxsat yo'q"):
        super().__init__(message, code=-32003, data={"error_code": "FORBIDDEN"})


class MCPNotFoundError(MCPError):
    """Viktorina yoki sessiya topilmadi."""
    def __init__(self, message: str = "So'ralgan resurs topilmadi"):
        super().__init__(message, code=-32004, data={"error_code": "NOT_FOUND"})


class MCPInvalidSessionStateError(MCPError):
    """Sessiya holati joriy amalga mos kelmaydi."""
    def __init__(self, message: str, current_state: str = "", allowed_actions: Optional[list] = None):
        data = {
            "error_code": "INVALID_SESSION_STATE",
            "current_state": current_state,
            "allowed_actions": allowed_actions or [],
        }
        super().__init__(message, code=-32005, data=data)


class MCPConfirmationRequiredError(MCPError):
    """Xavfli amal uchun inson (o'qituvchi) tasdig'i talab qilinadi."""
    def __init__(self, message: str = "Ushbu amalni bajarish uchun o'qituvchi tasdig'i talab qilinadi"):
        super().__init__(message, code=-32006, data={"error_code": "CONFIRMATION_REQUIRED"})


class MCPContentValidationError(MCPError):
    """Savollar yoki viktorina ta'limiy qoidalarga mos emas."""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(
            message,
            code=-32007,
            data={"error_code": "CONTENT_VALIDATION_FAILED", "errors": validation_errors or []}
        )


class MCPRateLimitExceededError(MCPError):
    """So'rovlar soni me'yordan oshdi."""
    def __init__(self, message: str = "So'rovlar limiti oshib ketdi"):
        super().__init__(message, code=-32008, data={"error_code": "RATE_LIMIT_EXCEEDED"})
