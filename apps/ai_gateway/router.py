import logging
from typing import Optional, Type, Any, AsyncIterator
from decimal import Decimal

from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TextResponse,
    TokenUsage,
    T,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderServerError,
    AIProviderAuthError,
    AIProviderError,
)
from apps.ai_gateway.adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)

logger = logging.getLogger(__name__)


class ModelRouter:
    """
    Intelligent Model Router with Cascade Fallback (DOC-69).
    Routes requests based on task complexity, latency, context size,
    and automatically switches to fallbacks if primary provider fails.
    """

    ROUTING_TABLE: dict[str, list[tuple[str, str]]] = {
        "big_context": [
            ("gemini", "gemini-1.5-pro"),
            ("claude", "claude-3-5-sonnet"),
            ("openai", "gpt-4o"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
        "stem": [
            ("claude", "claude-3-5-sonnet"),
            ("deepseek", "deepseek-reasoner"),
            ("openai", "gpt-4o"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
        "coding": [
            ("claude", "claude-3-5-sonnet"),
            ("deepseek", "deepseek-chat"),
            ("openai", "gpt-4o"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
        "language": [
            ("openai", "gpt-4o"),
            ("claude", "claude-3-5-sonnet"),
            ("deepseek", "deepseek-chat"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
        "speed": [
            ("groq", "llama-3.3-70b-versatile"),
            ("openai", "gpt-4o-mini"),
            ("deepseek", "deepseek-chat"),
        ],
        "general": [
            ("openai", "gpt-4o-mini"),
            ("deepseek", "deepseek-chat"),
            ("groq", "llama-3.3-70b-versatile"),
        ],
    }

    def __init__(
        self,
        adapters: Optional[dict[str, BaseAIAdapter]] = None,
    ):
        if adapters is not None:
            self._adapters = adapters
        else:
            self._adapters = {
                "openai": OpenAIAdapter(),
                "gemini": GeminiAdapter(),
                "claude": ClaudeAdapter(),
                "groq": GroqAdapter(),
                "deepseek": DeepSeekAdapter(),
            }

    def get_adapter(self, provider_name: str) -> BaseAIAdapter:
        if provider_name not in self._adapters:
            raise KeyError(f"No adapter registered for provider: {provider_name}")
        return self._adapters[provider_name]

    def register_adapter(self, provider_name: str, adapter: BaseAIAdapter) -> None:
        self._adapters[provider_name] = adapter

    def resolve_route(
        self,
        task_type: str = "general",
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> list[tuple[str, str]]:
        """
        Resolves primary provider and fallback cascade chain.
        """
        if preferred_provider and preferred_provider in self._adapters:
            adapter = self._adapters[preferred_provider]
            model = preferred_model or adapter.default_model
            # Put preferred first, then remaining fallbacks
            chain = [(preferred_provider, model)]
            for prov, mod in self.ROUTING_TABLE.get(task_type, self.ROUTING_TABLE["general"]):
                if prov != preferred_provider:
                    chain.append((prov, mod))
            return chain

        return list(self.ROUTING_TABLE.get(task_type, self.ROUTING_TABLE["general"]))

    async def _get_user_api_key(self, user: Optional[Any], provider_name: str) -> Optional[str]:
        """Safely retrieves BYOK API key across sync/async boundaries."""
        if not user or not hasattr(user, "ai_api_keys"):
            return None
        from asgiref.sync import sync_to_async
        def _fetch():
            try:
                uk = user.ai_api_keys.filter(provider=provider_name, is_valid=True).first()
                return uk.get_key() if uk else None
            except Exception:
                return None
        return await sync_to_async(_fetch, thread_sensitive=True)()

    async def execute_text(
        self,
        messages: list[dict[str, str]],
        task_type: str = "general",
        config: Optional[ModelConfig] = None,
        preferred_provider: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> TextResponse:
        """
        Executes text generation across fallback cascade if primary fails.
        """
        chain = self.resolve_route(task_type, preferred_provider=preferred_provider)
        last_exception: Optional[Exception] = None

        for provider_name, model_id in chain:
            if provider_name not in self._adapters:
                continue

            adapter = self._adapters[provider_name]
            req_config = config or ModelConfig()
            req_config.model_override = model_id

            # Apply BYOK key if user has one and no override given
            if user and not req_config.api_key_override and hasattr(user, "ai_api_keys"):
                user_key = await self._get_user_api_key(user, provider_name)
                if user_key:
                    req_config.api_key_override = user_key

            # Skip unconfigured providers in live execution without wasting network latency
            api_key = req_config.api_key_override or adapter._get_api_key(req_config)
            if not api_key and getattr(adapter, "_http_client", None) is None:
                continue

            try:
                response = await adapter.generate_text(messages, req_config)
                self._log_usage(user, adapter, response, task_type)
                return response
            except (AIProviderRateLimitError, AIProviderTimeoutError, AIProviderServerError, AIProviderAuthError) as exc:
                logger.warning(
                    f"Provider {provider_name} failed with {exc.__class__.__name__}: {exc}. Cascading to fallback."
                )
                last_exception = exc
                continue
            except Exception as exc:
                # Other non-retryable errors (e.g. content filter, invalid request)
                raise exc

        raise last_exception or AIProviderError("All providers in cascade failed")

    async def execute_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[T],
        task_type: str = "general",
        config: Optional[ModelConfig] = None,
        preferred_provider: Optional[str] = None,
        user: Optional[Any] = None,
    ) -> T:
        """
        Executes structured output generation with fallback cascade.
        """
        chain = self.resolve_route(task_type, preferred_provider=preferred_provider)
        last_exception: Optional[Exception] = None

        for provider_name, model_id in chain:
            if provider_name not in self._adapters:
                continue

            adapter = self._adapters[provider_name]
            req_config = config or ModelConfig()
            req_config.model_override = model_id

            if user and not req_config.api_key_override and hasattr(user, "ai_api_keys"):
                user_key = await self._get_user_api_key(user, provider_name)
                if user_key:
                    req_config.api_key_override = user_key

            # Skip unconfigured providers in live execution without wasting network latency
            api_key = req_config.api_key_override or adapter._get_api_key(req_config)
            if not api_key and getattr(adapter, "_http_client", None) is None:
                continue

            try:
                return await adapter.generate_structured(messages, schema, req_config)
            except (AIProviderRateLimitError, AIProviderTimeoutError, AIProviderServerError, AIProviderAuthError) as exc:
                logger.warning(
                    f"Structured gen provider {provider_name} failed with {exc.__class__.__name__}. Cascading to fallback."
                )
                last_exception = exc
                continue
            except Exception as exc:
                raise exc

        raise last_exception or AIProviderError("All providers in cascade failed for structured generation")

    def _log_usage(
        self,
        user: Optional[Any],
        adapter: BaseAIAdapter,
        response: TextResponse,
        task_type: str,
    ) -> None:
        """Records token usage and estimated cost into TokenUsageLog if DB is accessible."""
        try:
            from apps.ai_gateway.models import TokenUsageLog

            cost = adapter.estimate_cost(response.usage, response.model_id)
            TokenUsageLog.objects.create(
                user=user if (user and getattr(user, "pk", None)) else None,
                provider=response.provider,
                model_id=response.model_id,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.cached_tokens,
                estimated_cost_usd=cost,
                latency_ms=response.latency_ms,
                task_type=task_type,
            )
        except Exception as e:
            logger.debug(f"Could not persist TokenUsageLog: {e}")
