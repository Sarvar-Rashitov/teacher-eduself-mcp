"""
Base AI Adapter Contract, Domain Data Transfer Objects (DTOs), and Normalized Exceptions.

All AI provider implementations (OpenAI, Gemini, Claude, Groq, DeepSeek, etc.)
must adhere to this contract.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class AIProviderError(Exception):
    """Base exception for all AI provider interactions."""
    def __init__(self, message: str, provider: str = "", status_code: Optional[int] = None, raw_error: Any = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.raw_error = raw_error


class AIProviderRateLimitError(AIProviderError):
    """Raised when the provider responds with HTTP 429 Too Many Requests."""
    pass


class AIProviderAuthError(AIProviderError):
    """Raised when authentication fails (HTTP 401, 403 or invalid API key)."""
    pass


class AIProviderContextLengthError(AIProviderError):
    """Raised when the prompt/context exceeds the model's maximum window."""
    pass


class AIProviderContentFilterError(AIProviderError):
    """Raised when content is blocked by safety / responsible AI filters."""
    pass


class AIProviderTimeoutError(AIProviderError):
    """Raised when request timed out or socket hung up."""
    pass


class AIProviderServerError(AIProviderError):
    """Raised when provider returns HTTP 500, 502, 503, or 504 server errors."""
    pass


# ==============================================================================
# Data Transfer Objects (DTOs)
# ==============================================================================

@dataclass
class ModelConfig:
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.95
    timeout_seconds: float = 30.0
    api_key_override: Optional[str] = None  # For BYOK keys


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0

    def __post_init__(self):
        if self.total_tokens == 0 and (self.prompt_tokens > 0 or self.completion_tokens > 0):
            self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class TextResponse:
    content: str
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: int = 0
    model_id: str = ""
    provider: str = ""


@dataclass
class ProviderCapabilities:
    supports_structured_outputs: bool
    supports_tools: bool
    supports_streaming: bool
    supports_vision: bool
    max_context_window: int


# ==============================================================================
# Base Adapter Interface
# ==============================================================================

class BaseAIAdapter(ABC):
    """
    Abstract contract defining unified operations across all LLM providers.
    """
    provider_name: str = "base"
    default_model: str = "default"

    def __init__(self, default_api_key: Optional[str] = None):
        self.default_api_key = default_api_key

    def _resolve_api_key(self, config: Optional[ModelConfig] = None) -> Optional[str]:
        """Resolves whether to use user's BYOK override or platform default key."""
        if config and config.api_key_override:
            return config.api_key_override
        return self.default_api_key

    @abstractmethod
    def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        model_id: Optional[str] = None
    ) -> TextResponse:
        """
        Executes a standard chat completion request.
        """
        pass

    @abstractmethod
    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Union[Type[T], Dict[str, Any]],
        config: Optional[ModelConfig] = None,
        model_id: Optional[str] = None
    ) -> Union[T, Dict[str, Any]]:
        """
        Enforces strict JSON/Pydantic schema output from the model.
        """
        pass

    @abstractmethod
    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        """
        Returns model technical capabilities (context length, structured outputs, vision, etc.).
        """
        pass

    @abstractmethod
    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        """
        Calculates dollar cost in USD for the given token usage.
        """
        pass

    @abstractmethod
    def health_check(self, api_key: Optional[str] = None) -> bool:
        """
        Executes minimal validation handshake with provider to confirm key validity.
        """
        pass
