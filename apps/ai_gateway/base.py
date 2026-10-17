"""
Base AI Provider Adapter Contract, DTOs & Exception Hierarchy.
Spetsifikatsiya: .docs/ai/AI_ADAPTERS.md
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, Type, TypeVar, Optional, List, Dict, Any
from decimal import Decimal
from dataclasses import dataclass, field
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# ============================================================
# DTO (Data Transfer Objects)
# ============================================================

@dataclass
class ModelConfig:
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    timeout_seconds: float = 30.0
    api_key_override: Optional[str] = None  # BYOK shaxsiy kalit


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class TextResponse:
    content: str
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    model_name: str = ""


@dataclass
class ProviderCapabilities:
    supports_structured_outputs: bool
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    max_context_window: int


# ============================================================
# Istisnolar ierarxiyasi (AI_ADAPTERS.md 3-bo'lim)
# ============================================================

class AIProviderError(Exception):
    """Barcha AI provayder xatoliklari uchun umumiy baza klass."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class AIProviderRateLimitError(AIProviderError):
    """HTTP 429: Provayder so'rovlar limiti tugagan, boshqa zaxiraga o'tish zarur."""
    pass


class AIProviderAuthError(AIProviderError):
    """HTTP 401/403: API kalit yaroqsiz yoki ruxsat yo'q."""
    pass


class AIProviderContextLengthError(AIProviderError):
    """Kiritilgan matn modelning kontekst oynasidan oshib ketdi."""
    pass


class AIProviderContentFilterError(AIProviderError):
    """Provayderning xavfsizlik va axloq filtrlari so'rovni rad etdi."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Provayder belgilangan vaqt ichida javob qaytara olmadi."""
    pass


class AIProviderServerError(AIProviderError):
    """HTTP 500, 502, 503: Provayder serveri vaqtincha ishlamayapti."""
    pass


# ============================================================
# BaseAIAdapter Abstrakt Klassi
# ============================================================

class BaseAIAdapter(ABC):
    """
    Barcha 7 ta AI provayderi (OpenAI, Gemini, Claude, DeepSeek, Groq, va h.k.)
    uchun yagona adapter shartnomasi (Adapter Pattern).
    """
    provider_name: str = ""

    @abstractmethod
    async def generate_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> TextResponse:
        """Oddiy matnli suhbat yoki tushuntirish uchun."""
        pass

    @abstractmethod
    async def generate_structured(
        self, messages: List[Dict[str, str]], schema: Type[T], config: ModelConfig
    ) -> T:
        """Qat'iy Pydantic JSON sxemasi asosida strukturali javob olish."""
        pass

    @abstractmethod
    async def stream_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> AsyncIterator[str]:
        """Real-vaqtda tokenlar oqimi (SSE)."""
        pass

    @abstractmethod
    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        """Modelning texnik imkoniyatlarini qaytarish."""
        pass

    @abstractmethod
    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        """Tokenlar sarfini AQSH dollarida hisoblash."""
        pass

    @abstractmethod
    async def health_check(self, api_key: Optional[str] = None) -> bool:
        """Provayder API faoliyatini tekshirish."""
        pass
