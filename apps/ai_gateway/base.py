import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# =============================================================================
# Exception Hierarchy (DOC-68 Section 3)
# =============================================================================

class AIProviderError(Exception):
    """Base exception for all AI Provider errors."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.details = details or {}


class AIProviderRateLimitError(AIProviderError):
    """HTTP 429 - Rate limit exceeded or quota exhausted."""
    pass


class AIProviderAuthError(AIProviderError):
    """HTTP 401 / 403 - Invalid API key or permission denied."""
    pass


class AIProviderContextLengthError(AIProviderError):
    """Context window exceeded (prompt too long)."""
    pass


class AIProviderContentFilterError(AIProviderError):
    """Content flagged by safety/moderation filters."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Socket timeout or deadline exceeded."""
    pass


class AIProviderServerError(AIProviderError):
    """HTTP 500, 502, 503 - Internal vendor server error."""
    pass


# =============================================================================
# Data Transfer Objects (DTOs)
# =============================================================================

@dataclass
class ModelConfig:
    model_name: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    timeout_seconds: float = 30.0
    api_key_override: Optional[str] = None  # BYOK key


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
    model: str = ""
    provider: str = ""
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class ProviderCapabilities:
    supports_structured_outputs: bool = True
    supports_tools: bool = True
    supports_streaming: bool = True
    supports_vision: bool = False
    max_context_window: int = 128000


# =============================================================================
# Abstract Adapter Contract (DOC-68 Section 2)
# =============================================================================

class BaseAIProviderAdapter(ABC):
    """
    Standard adapter contract for all 7 supported AI providers.
    Implements DOC-68 (AI_ADAPTERS.md).
    """

    provider_name: str = "base"
    default_model: str = ""

    @abstractmethod
    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        """Generates standard conversational text or explanations."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Any,
        config: Optional[ModelConfig] = None,
    ) -> Any:
        """
        Generates strict JSON validated against a Pydantic model or JSON Schema.
        Returns parsed Pydantic instance or dict.
        """
        pass

    @abstractmethod
    async def stream_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        """Streams tokens in real-time for Server-Sent Events (SSE)."""
        pass

    @abstractmethod
    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        """Returns technical capabilities of the given model."""
        pass

    @abstractmethod
    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        """Estimates cost in USD based on input, output, and cached tokens."""
        pass

    @abstractmethod
    async def health_check(self, api_key: Optional[str] = None) -> bool:
        """Minimal dry-run ping to verify API credentials and connectivity."""
        pass
