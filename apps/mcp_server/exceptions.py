"""
JSON-RPC 2.0 Standard and EduSelf Domain Error Exceptions.
Fully conforms to DOC-89 (MCP_ERRORS.md) specification.
"""

from typing import Any, Optional


# JSON-RPC 2.0 Standart Xatolik Kodlari
CODE_PARSE_ERROR = -32700
CODE_INVALID_REQUEST = -32600
CODE_METHOD_NOT_FOUND = -32601
CODE_INVALID_PARAMS = -32602
CODE_INTERNAL_ERROR = -32603

# EduSelf Domen Xatolik Kodlari (-32000 dan -32099 gacha)
CODE_UNAUTHORIZED = -32001
CODE_FORBIDDEN = -32003
CODE_RESOURCE_NOT_FOUND = -32004
CODE_INVALID_SESSION_STATE = -32005
CODE_CONFIRMATION_REQUIRED = -32006
CODE_CONTENT_VALIDATION_FAILED = -32007
CODE_RATE_LIMIT_EXCEEDED = -32008


class MCPBaseError(Exception):
    """MCP tizimi uchun asosiy xatolik sinfi."""
    code: int = CODE_INTERNAL_ERROR
    default_message: str = "Noma'lum server xatoligi yuz berdi."
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: Optional[str] = None, data: Optional[Any] = None, code: Optional[int] = None):
        self.message = message or self.default_message
        self.code = code or self.code
        self.data = data or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """JSON-RPC 2.0 error obyektini hosil qiladi."""
        payload = {
            "code": self.code,
            "message": self.message,
        }
        if self.data or self.error_code:
            data_dict = {"error_code": self.error_code}
            if isinstance(self.data, dict):
                data_dict.update(self.data)
            else:
                data_dict["details"] = self.data
            payload["data"] = data_dict
        return payload


class MCPParseError(MCPBaseError):
    code = CODE_PARSE_ERROR
    default_message = "Serverga yaroqsiz JSON matni kelib tushdi."
    error_code = "PARSE_ERROR"


class MCPInvalidRequestError(MCPBaseError):
    code = CODE_INVALID_REQUEST
    default_message = "Yuborilgan JSON-RPC so'rovi formati noto'g'ri."
    error_code = "INVALID_REQUEST"


class MCPMethodNotFoundError(MCPBaseError):
    code = CODE_METHOD_NOT_FOUND
    default_message = "Chaqirilgan tool, resource yoki metod topilmadi."
    error_code = "METHOD_NOT_FOUND"


class MCPInvalidParamsError(MCPBaseError):
    code = CODE_INVALID_PARAMS
    default_message = "Kiritilgan parametrlar noto'g'ri yoki yetishmaydi."
    error_code = "INVALID_PARAMS"


class MCPInternalError(MCPBaseError):
    code = CODE_INTERNAL_ERROR
    default_message = "Serverning ichki tizimida xatolik yuz berdi."
    error_code = "INTERNAL_ERROR"


# EduSelf Domen Istisnolari
class MCPUnauthorizedError(MCPBaseError):
    code = CODE_UNAUTHORIZED
    default_message = "Autentifikatsiya talab qilinadi: token mavjud emas yoki muddati o'tgan."
    error_code = "UNAUTHORIZED"


class MCPForbiddenError(MCPBaseError):
    code = CODE_FORBIDDEN
    default_message = "Ushbu amalni bajarish uchun ruxsat yetarli emas yoki tenant taqiqlangan."
    error_code = "FORBIDDEN"


class MCPNotFoundError(MCPBaseError):
    code = CODE_RESOURCE_NOT_FOUND
    default_message = "So'ralgan resurs (viktorina yoki sessiya) topilmadi."
    error_code = "RESOURCE_NOT_FOUND"


class MCPInvalidSessionStateError(MCPBaseError):
    code = CODE_INVALID_SESSION_STATE
    default_message = "Sessiyaning joriy holatida ushbu amalni bajarib bo'lmaydi."
    error_code = "INVALID_SESSION_STATE"


class MCPConfirmationRequiredError(MCPBaseError):
    code = CODE_CONFIRMATION_REQUIRED
    default_message = "Ushbu xavfli amalni bajarish uchun o'qituvchining tasdig'i talab qilinadi."
    error_code = "CONFIRMATION_REQUIRED"


class MCPContentValidationError(MCPBaseError):
    code = CODE_CONTENT_VALIDATION_FAILED
    default_message = "Savollar yoki viktorina ta'limiy qoidalarga mos kelmadi."
    error_code = "CONTENT_VALIDATION_FAILED"


class MCPRateLimitExceededError(MCPBaseError):
    code = CODE_RATE_LIMIT_EXCEEDED
    default_message = "So'rovlar soni cheklovidan oshib ketdi."
    error_code = "RATE_LIMIT_EXCEEDED"
