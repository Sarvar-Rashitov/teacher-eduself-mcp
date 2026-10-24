from abc import ABC, abstractmethod
from typing import AsyncIterator, Type, TypeVar, Optional, Any
from decimal import Decimal
from dataclasses import dataclass, field
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# --- Exceptions (DOC-68 Section 3) ---
class AIProviderError(Exception):
    """Base exception for all AI Provider errors."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class AIProviderRateLimitError(AIProviderError):
    """Triggered on HTTP 429 Too Many Requests or token quota exhaustion."""
    pass


class AIProviderAuthError(AIProviderError):
    """Triggered on HTTP 401/403 Invalid API Key or Unauthorized."""
    pass


class AIProviderContextLengthError(AIProviderError):
    """Triggered when input exceeds model context window limit."""
    pass


class AIProviderContentFilterError(AIProviderError):
    """Triggered when input or output violates provider safety/content policy."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Triggered on request timeout or socket disconnect."""
    pass


class AIProviderServerError(AIProviderError):
    """Triggered on HTTP 500, 502, 503, 504 server-side errors."""
    pass


# --- DTOs (DOC-68 Section 2) ---
@dataclass
class ModelConfig:
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    timeout_seconds: float = 30.0
    api_key_override: Optional[str] = None  # For BYOK keys
    model_override: Optional[str] = None
    system_prompt: Optional[str] = None


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class TextResponse:
    content: str
    finish_reason: str
    usage: TokenUsage
    latency_ms: int
    model_id: str
    provider: str


@dataclass
class ProviderCapabilities:
    supports_structured_outputs: bool
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    max_context_window: int


# --- Base Adapter Contract ---
class BaseAIAdapter(ABC):
    """
    Abstract AI Provider Adapter (DOC-68).
    Standardizes OpenAI, Gemini, Claude, DeepSeek, and Groq interactions.
    """

    provider_name: str
    default_model: str

    @abstractmethod
    async def generate_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        """Generates plain text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        """Generates response strictly adhering to Pydantic schema."""
        pass

    @abstractmethod
    async def stream_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        """Streams text chunks in real-time."""
        pass

    @abstractmethod
    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        """Returns model capabilities and limits."""
        pass

    @abstractmethod
    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        """Calculates token cost in USD using DOC-76 price matrix."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Pings provider to verify reachability and credential health."""
        pass
