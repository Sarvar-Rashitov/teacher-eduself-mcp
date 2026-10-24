from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth import get_user_model

from ai_gateway.base import (
    BaseAIProviderAdapter,
    ModelConfig,
    TextResponse,
    TokenUsage,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderServerError,
)
from ai_gateway.models import TokenUsageLog
from ai_gateway.router import CircuitBreaker, ModelRouter

User = get_user_model()


class MockAdapter(BaseAIProviderAdapter):
    def __init__(self, provider_name: str, default_model: str, should_fail: bool = False, fail_error: Exception = None):
        self.provider_name = provider_name
        self.default_model = default_model
        self.should_fail = should_fail
        self.fail_error = fail_error or AIProviderServerError("Internal Vendor Error", provider=provider_name)
        self.call_count = 0

    async def generate_text(self, messages, config=None):
        self.call_count += 1
        if self.should_fail:
            raise self.fail_error
        return TextResponse(
            content=f"Response from {self.provider_name}",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            latency_ms=120,
            model=config.model_name if config else self.default_model,
            provider=self.provider_name,
        )

    async def generate_structured(self, messages, schema, config=None):
        self.call_count += 1
        if self.should_fail:
            raise self.fail_error
        return {"data": f"structured from {self.provider_name}"}

    async def stream_text(self, messages, config=None):
        yield f"stream from {self.provider_name}"

    def get_capabilities(self, model_id=None):
        return None

    def estimate_cost(self, usage, model_id=None):
        return Decimal("0.001000")

    async def health_check(self, api_key=None):
        return True


class TestModelRouter:
    def test_routing_matrix_selection(self):
        router = ModelRouter()

        # Large context -> Gemini is primary
        route_large = router.get_route(is_large_context=True)
        assert route_large[0][0] == "gemini"

        # Math/STEM -> Claude is primary
        route_math = router.get_route(task_category="math")
        assert route_math[0][0] == "claude"

        # Speed critical -> Groq is primary
        route_speed = router.get_route(speed_critical=True)
        assert route_speed[0][0] == "groq"

        # User preferred override
        route_pref = router.get_route(preferred_provider="deepseek", preferred_model="deepseek-reasoner")
        assert route_pref[0] == ("deepseek", "deepseek-reasoner")

    @pytest.mark.asyncio
    @pytest.mark.django_db
    async def test_fallback_cascade_on_server_error(self):
        """
        Self-Audit Checklist Item:
        Asosiy model (masalan, Claude) 500 xato berganda zaxira model (masalan, DeepSeek/Gemini) chaqiriladimi?
        """
        claude_mock = MockAdapter("claude", "claude-3-5-sonnet-20241022", should_fail=True)
        deepseek_mock = MockAdapter("deepseek", "deepseek-chat", should_fail=False)
        openai_mock = MockAdapter("openai", "gpt-4o", should_fail=False)

        custom_adapters = {
            "claude": claude_mock,
            "deepseek": deepseek_mock,
            "openai": openai_mock,
        }
        router = ModelRouter(adapters=custom_adapters)

        # For "math", primary is claude, fallback 1 is deepseek
        res = await router.generate_text([{"role": "user", "content": "Solve x+2=4"}], task_category="math")

        # Claude was called and failed
        assert claude_mock.call_count == 1
        # Fallback DeepSeek was called and succeeded
        assert deepseek_mock.call_count == 1
        assert res.provider == "deepseek"
        assert res.content == "Response from deepseek"

        # Verify usage log recorded fallback_used
        log = await sync_to_async(TokenUsageLog.objects.latest)("created_at")
        assert log.provider == "deepseek"
        assert log.status == "fallback_used"

    def test_circuit_breaker_tripping(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout_seconds=60.0)
        provider = "failing_provider"

        assert cb.is_available(provider) is True

        cb.record_failure(provider)
        cb.record_failure(provider)
        assert cb.is_available(provider) is True

        # 3rd failure trips the breaker to OPEN
        cb.record_failure(provider)
        assert cb.is_available(provider) is False

        # Success resets the breaker
        cb.record_success(provider)
        assert cb.is_available(provider) is True

    @pytest.mark.asyncio
    async def test_all_providers_failing_raises_exception(self):
        failing_adapters = {
            "openai": MockAdapter("openai", "gpt-4o-mini", should_fail=True),
            "deepseek": MockAdapter("deepseek", "deepseek-chat", should_fail=True),
            "groq": MockAdapter("groq", "llama-3.3-70b-versatile", should_fail=True),
        }
        router = ModelRouter(adapters=failing_adapters)

        with pytest.raises(AIProviderServerError):
            await router.generate_text([{"role": "user", "content": "hello"}])
