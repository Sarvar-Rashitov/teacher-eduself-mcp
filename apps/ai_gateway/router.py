"""
Model Router, Routing Matrix, Fallback Cascade, and Circuit Breaker Engine.

Implements:
- 3-tier routing: User/BYOK override -> Context size constraint -> Task category matrix
- Fallback cascade across primary and backup providers
- Circuit breaker with failure tracking and cooldown
- Automatic TokenUsageLog tracking and financial cost audit
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union
from pydantic import BaseModel
from django.conf import settings
from django.utils import timezone
from .base import (
    BaseAIAdapter,
    ModelConfig,
    TextResponse,
    TokenUsage,
    AIProviderAuthError,
    AIProviderContentFilterError,
    AIProviderContextLengthError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderError,
)
from .models import UserApiKey, TokenUsageLog
from .adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class CircuitBreaker:
    """
    Lightweight circuit breaker for tracking provider failure states.
    States:
        CLOSED: Normal operation, provider is healthy.
        OPEN: Tripped after consecutive server errors; calls bypass this provider.
        HALF_OPEN: Cooldown period elapsed; allows 1 test probe.
    """
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        # provider -> {"failures": int, "last_failure_time": float, "state": str}
        self._states: Dict[str, Dict[str, Any]] = {}

    def is_available(self, provider: str) -> bool:
        state_info = self._states.get(provider)
        if not state_info:
            return True

        if state_info["state"] == "OPEN":
            if time.time() - state_info["last_failure_time"] > self.cooldown_seconds:
                # Transition to HALF_OPEN to attempt recovery
                state_info["state"] = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self, provider: str):
        if provider in self._states:
            self._states[provider] = {"failures": 0, "last_failure_time": 0.0, "state": "CLOSED"}

    def record_failure(self, provider: str):
        now = time.time()
        info = self._states.setdefault(provider, {"failures": 0, "last_failure_time": now, "state": "CLOSED"})
        info["failures"] += 1
        info["last_failure_time"] = now

        if info["failures"] >= self.failure_threshold:
            info["state"] = "OPEN"
            logger.warning("Circuit breaker OPEN for provider '%s' (failures: %d)", provider, info["failures"])

    def reset(self, provider: Optional[str] = None):
        if provider:
            self._states.pop(provider, None)
        else:
            self._states.clear()


class ModelRouter:
    """
    Intelligent Model Router that selects optimal models, handles automatic failover,
    manages BYOK credentials, and records token usage logs.
    """

    # Routing Matrix: task_type -> list of (provider, model_id) tuples in priority order
    ROUTING_MATRIX: Dict[str, List[Tuple[str, str]]] = {
        "math_stem": [
            ("claude", "claude-3-5-sonnet"),
            ("deepseek", "deepseek-reasoner"),
            ("openai", "gpt-4o"),
        ],
        "large_context": [
            ("gemini", "gemini-1.5-pro"),
            ("claude", "claude-3-5-sonnet"),
            ("openai", "gpt-4o"),
        ],
        "speed_instant": [
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

    def __init__(self, circuit_breaker: Optional[CircuitBreaker] = None):
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._adapters: Dict[str, BaseAIAdapter] = {
            "openai": OpenAIAdapter(),
            "gemini": GeminiAdapter(),
            "claude": ClaudeAdapter(),
            "groq": GroqAdapter(),
            "deepseek": DeepSeekAdapter(),
        }

    def register_adapter(self, provider: str, adapter: BaseAIAdapter):
        """Allows injecting custom or mocked adapters for testing and extensions."""
        self._adapters[provider] = adapter

    def get_adapter(self, provider: str) -> BaseAIAdapter:
        if provider not in self._adapters:
            raise ValueError(f"Unknown AI provider '{provider}'. Registered: {list(self._adapters.keys())}")
        return self._adapters[provider]

    def resolve_route_candidates(
        self,
        task_type: str = "general",
        estimated_tokens: int = 0,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        Determines the ordered list of (provider, model_id) candidates using the 3-tier hierarchy:
        1. User Override
        2. Context Size (>100K tokens forces Gemini 1.5 Pro)
        3. Task Category Matrix
        """
        # Tier 1: User explicit override
        if provider_override:
            adapter = self.get_adapter(provider_override)
            model = model_override or adapter.default_model
            return [(provider_override, model)]

        # Tier 2: Large context constraint (> 100,000 tokens)
        if estimated_tokens > 100_000:
            return self.ROUTING_MATRIX["large_context"]

        # Tier 3: Task category matrix
        return self.ROUTING_MATRIX.get(task_type, self.ROUTING_MATRIX["general"])

    def _resolve_byok_key(self, user: Any, provider: str) -> Tuple[Optional[str], bool]:
        """
        Retrieves user's decrypted BYOK key if available and valid.
        Returns: (api_key, is_byok)
        """
        if not user or not getattr(user, "is_authenticated", False):
            return None, False

        try:
            user_key = UserApiKey.objects.filter(user=user, provider=provider, is_valid=True).first()
            if user_key:
                decrypted = user_key.get_key()
                user_key.mark_used()
                return decrypted, True
        except Exception as e:
            logger.error("Failed to decrypt BYOK key for user %s and provider %s: %s", user, provider, e)

        return None, False

    def generate_text(
        self,
        messages: List[Dict[str, str]],
        task_type: str = "general",
        user: Any = None,
        config: Optional[ModelConfig] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        estimated_tokens: int = 0,
    ) -> TextResponse:
        """
        Routes and executes generate_text with fallback cascade and token logging.
        """
        cfg = config or ModelConfig()
        candidates = self.resolve_route_candidates(
            task_type=task_type,
            estimated_tokens=estimated_tokens,
            provider_override=provider_override,
            model_override=model_override,
        )

        last_error = None

        for provider, model_id in candidates:
            # Check Circuit Breaker
            if not self.circuit_breaker.is_available(provider):
                logger.info("Skipping provider '%s' due to OPEN circuit breaker.", provider)
                continue

            adapter = self.get_adapter(provider)
            byok_key, is_byok = self._resolve_byok_key(user, provider)
            call_cfg = ModelConfig(
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                top_p=cfg.top_p,
                timeout_seconds=cfg.timeout_seconds,
                api_key_override=byok_key if is_byok else cfg.api_key_override,
            )

            try:
                response = adapter.generate_text(messages=messages, config=call_cfg, model_id=model_id)
                self.circuit_breaker.record_success(provider)

                # Estimate cost and log
                cost_usd = adapter.estimate_cost(response.usage, model_id=model_id)
                self._record_usage_log(
                    user=user if getattr(user, "is_authenticated", False) else None,
                    provider=provider,
                    model_id=model_id,
                    task_type=task_type,
                    usage=response.usage,
                    cost_usd=cost_usd,
                    latency_ms=response.latency_ms,
                    is_byok=is_byok,
                )
                return response

            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning("Provider '%s' (%s) failed with %s. Falling back...", provider, model_id, type(e).__name__)
                self.circuit_breaker.record_failure(provider)
                last_error = e
                continue
            except (AIProviderAuthError, AIProviderContentFilterError, AIProviderContextLengthError) as e:
                # Non-transient errors (bad credentials or bad content)
                if is_byok and isinstance(e, AIProviderAuthError):
                    # Invalidate bad BYOK key in DB so teacher is prompted to fix it
                    UserApiKey.objects.filter(user=user, provider=provider).update(is_valid=False)
                last_error = e
                break

        if last_error:
            raise last_error
        raise AIProviderServerError("All candidate AI providers failed or were circuit-broken.")

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Union[Type[T], Dict[str, Any]],
        task_type: str = "general",
        user: Any = None,
        config: Optional[ModelConfig] = None,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        estimated_tokens: int = 0,
    ) -> Union[T, Dict[str, Any]]:
        """
        Routes and executes generate_structured with fallback cascade and token logging.
        """
        cfg = config or ModelConfig()
        candidates = self.resolve_route_candidates(
            task_type=task_type,
            estimated_tokens=estimated_tokens,
            provider_override=provider_override,
            model_override=model_override,
        )

        last_error = None

        for provider, model_id in candidates:
            if not self.circuit_breaker.is_available(provider):
                logger.info("Skipping provider '%s' due to OPEN circuit breaker.", provider)
                continue

            adapter = self.get_adapter(provider)
            byok_key, is_byok = self._resolve_byok_key(user, provider)
            call_cfg = ModelConfig(
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                top_p=cfg.top_p,
                timeout_seconds=cfg.timeout_seconds,
                api_key_override=byok_key if is_byok else cfg.api_key_override,
            )

            try:
                start_time = time.perf_counter()
                result = adapter.generate_structured(messages=messages, schema=schema, config=call_cfg, model_id=model_id)
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                self.circuit_breaker.record_success(provider)

                # Approximate usage if adapter doesn't return usage in structured mode
                prompt_approx = sum(len(m.get("content", "")) // 4 for m in messages)
                comp_approx = 500
                usage = TokenUsage(prompt_tokens=prompt_approx, completion_tokens=comp_approx)
                cost_usd = adapter.estimate_cost(usage, model_id=model_id)

                self._record_usage_log(
                    user=user if getattr(user, "is_authenticated", False) else None,
                    provider=provider,
                    model_id=model_id,
                    task_type=task_type,
                    usage=usage,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    is_byok=is_byok,
                )
                return result

            except (AIProviderRateLimitError, AIProviderServerError, AIProviderTimeoutError) as e:
                logger.warning("Provider '%s' (%s) failed structured output with %s. Falling back...", provider, model_id, type(e).__name__)
                self.circuit_breaker.record_failure(provider)
                last_error = e
                continue
            except (AIProviderAuthError, AIProviderContentFilterError, AIProviderContextLengthError) as e:
                if is_byok and isinstance(e, AIProviderAuthError):
                    UserApiKey.objects.filter(user=user, provider=provider).update(is_valid=False)
                last_error = e
                break

        if last_error:
            raise last_error
        raise AIProviderServerError("All candidate AI providers failed or were circuit-broken.")

    def _record_usage_log(
        self,
        user: Any,
        provider: str,
        model_id: str,
        task_type: str,
        usage: TokenUsage,
        cost_usd: Decimal,
        latency_ms: int,
        is_byok: bool,
    ):
        try:
            TokenUsageLog.objects.create(
                user=user,
                provider=provider,
                model_id=model_id,
                task_type=task_type,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                cached_tokens=usage.cached_tokens,
                cost_usd=cost_usd,
                latency_ms=latency_ms,
                is_byok=is_byok,
            )
        except Exception as e:
            logger.error("Failed to write TokenUsageLog: %s", e)
