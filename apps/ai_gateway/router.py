import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type
from asgiref.sync import sync_to_async
from django.utils import timezone

from .base import (
    BaseAIProviderAdapter,
    ModelConfig,
    TextResponse,
    TokenUsage,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from .adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """
    In-memory Circuit Breaker for AI Providers (DOC-69 Section 4).
    Trips to OPEN state after 3 consecutive failures.
    Allows half-open trial after 60-second recovery timeout.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self._failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._states: Dict[str, str] = {}  # "CLOSED", "OPEN", "HALF_OPEN"

    def is_available(self, provider_name: str) -> bool:
        state = self._states.get(provider_name, "CLOSED")
        if state == "CLOSED":
            return True
        if state == "OPEN":
            elapsed = time.time() - self._last_failure_time.get(provider_name, 0.0)
            if elapsed >= self.recovery_timeout:
                self._states[provider_name] = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN allows 1 test call

    def record_success(self, provider_name: str) -> None:
        self._failures[provider_name] = 0
        self._states[provider_name] = "CLOSED"

    def record_failure(self, provider_name: str) -> None:
        count = self._failures.get(provider_name, 0) + 1
        self._failures[provider_name] = count
        self._last_failure_time[provider_name] = time.time()
        if count >= self.failure_threshold:
            self._states[provider_name] = "OPEN"
            logger.warning(f"Circuit Breaker TRIPPED to OPEN for provider '{provider_name}'.")


class ModelRouter:
    """
    Intelligent Model Router with 3-Tier Routing, Fallback Cascading, and Usage Logging.
    Implements DOC-69 (MODEL_ROUTING.md) and DOC-76 (AI_COSTS.md).
    """

    def __init__(
        self,
        adapters: Optional[Dict[str, BaseAIProviderAdapter]] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.adapters = adapters or {
            "openai": OpenAIAdapter(),
            "gemini": GeminiAdapter(),
            "claude": ClaudeAdapter(),
            "groq": GroqAdapter(),
            "deepseek": DeepSeekAdapter(),
        }
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    def get_route(
        self,
        task_category: str = "standard",
        is_large_context: bool = False,
        speed_critical: bool = False,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        Calculates the cascading route: [(provider, model), (fallback_provider, fallback_model), ...]
        Following DOC-69 3-tier hierarchy.
        """
        # Tier 1: User / BYOK Override
        if preferred_provider and preferred_provider in self.adapters:
            default_mod = preferred_model or self.adapters[preferred_provider].default_model
            return [(preferred_provider, default_mod), ("openai", "gpt-4o-mini"), ("deepseek", "deepseek-chat")]

        # Tier 2: Large Context (> 100K tokens, massive textbooks)
        if is_large_context:
            return [
                ("gemini", "gemini-1.5-pro"),
                ("claude", "claude-3-5-sonnet-20241022"),
                ("openai", "gpt-4o"),
            ]

        # Tier 3: Speed-critical (live in-class quick questions)
        if speed_critical:
            return [
                ("groq", "llama-3.3-70b-versatile"),
                ("openai", "gpt-4o-mini"),
                ("deepseek", "deepseek-chat"),
            ]

        # Tier 3: Category-based
        cat = task_category.lower()
        if cat in ("math", "stem", "physics", "coding", "olympiad"):
            return [
                ("claude", "claude-3-5-sonnet-20241022"),
                ("deepseek", "deepseek-chat"),
                ("openai", "gpt-4o"),
            ]
        elif cat in ("language", "literature", "grammar"):
            return [
                ("openai", "gpt-4o"),
                ("claude", "claude-3-5-sonnet-20241022"),
                ("deepseek", "deepseek-chat"),
            ]

        # Default standard quiz
        return [
            ("openai", "gpt-4o-mini"),
            ("deepseek", "deepseek-chat"),
            ("groq", "llama-3.3-70b-versatile"),
        ]

    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        task_category: str = "standard",
        is_large_context: bool = False,
        speed_critical: bool = False,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        user: Optional[Any] = None,
    ) -> TextResponse:
        """
        Executes text generation across the cascading fallback route.
        Automatically logs token usage to TokenUsageLog.
        """
        route = self.get_route(
            task_category=task_category,
            is_large_context=is_large_context,
            speed_critical=speed_critical,
            preferred_provider=preferred_provider,
            preferred_model=preferred_model,
        )

        last_error = None
        for step_idx, (prov_name, model_name) in enumerate(route):
            adapter = self.adapters.get(prov_name)
            if not adapter or not self.circuit_breaker.is_available(prov_name):
                continue

            call_cfg = config or ModelConfig()
            call_cfg.model_name = model_name

            try:
                response = await adapter.generate_text(messages, call_cfg)
                self.circuit_breaker.record_success(prov_name)

                # Log token usage
                cost = adapter.estimate_cost(response.usage, model_name)
                status = "success" if step_idx == 0 else "fallback_used"
                await self._record_usage_log(
                    user=user,
                    provider=prov_name,
                    model_name=model_name,
                    usage=response.usage,
                    cost=cost,
                    latency_ms=response.latency_ms,
                    status=status,
                )
                return response

            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning(f"Provider '{prov_name}' failed with {e.__class__.__name__}: {e}. Trying fallback...")
                self.circuit_breaker.record_failure(prov_name)
                last_error = e
                continue
            except Exception as e:
                self.circuit_breaker.record_failure(prov_name)
                last_error = e
                continue

        if last_error:
            raise last_error
        raise AIProviderError("All providers in fallback cascade were unavailable or failed.")

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Any,
        task_category: str = "standard",
        is_large_context: bool = False,
        speed_critical: bool = False,
        preferred_provider: Optional[str] = None,
        preferred_model: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        user: Optional[Any] = None,
    ) -> Any:
        """
        Executes structured JSON/Pydantic generation with fallback cascading.
        """
        route = self.get_route(
            task_category=task_category,
            is_large_context=is_large_context,
            speed_critical=speed_critical,
            preferred_provider=preferred_provider,
            preferred_model=preferred_model,
        )

        last_error = None
        for step_idx, (prov_name, model_name) in enumerate(route):
            adapter = self.adapters.get(prov_name)
            if not adapter or not self.circuit_breaker.is_available(prov_name):
                continue

            call_cfg = config or ModelConfig()
            call_cfg.model_name = model_name

            try:
                result = await adapter.generate_structured(messages, schema, call_cfg)
                self.circuit_breaker.record_success(prov_name)
                return result
            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning(f"Provider '{prov_name}' structured output failed: {e}. Trying fallback...")
                self.circuit_breaker.record_failure(prov_name)
                last_error = e
                continue
            except Exception as e:
                self.circuit_breaker.record_failure(prov_name)
                last_error = e
                continue

        if last_error:
            raise last_error
        raise AIProviderError("All providers in fallback cascade failed for structured generation.")

    async def _record_usage_log(
        self,
        user: Optional[Any],
        provider: str,
        model_name: str,
        usage: TokenUsage,
        cost: Decimal,
        latency_ms: int,
        status: str,
        error_message: str = "",
    ) -> None:
        try:
            from .models import TokenUsageLog
            await sync_to_async(TokenUsageLog.objects.create)(
                user=user if (user and getattr(user, "is_authenticated", False)) else None,
                provider=provider,
                model_name=model_name,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cached_tokens=usage.cached_tokens,
                estimated_cost_usd=cost,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )
        except Exception as e:
            logger.debug(f"Could not persist TokenUsageLog (e.g. running outside DB or in tests): {e}")
