from decimal import Decimal
import pytest
from unittest.mock import MagicMock
from django.contrib.auth import get_user_model
from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TextResponse,
    TokenUsage,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderServerError,
)
from apps.ai_gateway.models import UserApiKey, TokenUsageLog, AIProviderChoices
from apps.ai_gateway.router import ModelRouter, CircuitBreaker

User = get_user_model()


class DummyAdapter(BaseAIAdapter):
    def __init__(self, name: str, default_model: str, should_fail: bool = False, fail_error: Exception = None):
        super().__init__(default_api_key="dummy-key")
        self.provider_name = name
        self.default_model = default_model
        self.should_fail = should_fail
        self.fail_error = fail_error or AIProviderServerError("Simulated server down", provider=name)
        self.call_count = 0
        self.last_config = None

    def generate_text(self, messages, config=None, model_id=None):
        self.call_count += 1
        self.last_config = config
        if self.should_fail:
            raise self.fail_error
        return TextResponse(
            content=f"Response from {self.provider_name} ({model_id})",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50),
            latency_ms=120,
            model_id=model_id or self.default_model,
            provider=self.provider_name,
        )

    def generate_structured(self, messages, schema, config=None, model_id=None):
        self.call_count += 1
        self.last_config = config
        if self.should_fail:
            raise self.fail_error
        return {"result": f"structured_{self.provider_name}"}

    def get_capabilities(self, model_id=None):
        return MagicMock()

    def estimate_cost(self, usage: TokenUsage, model_id=None) -> Decimal:
        return Decimal("0.000150")

    def health_check(self, api_key=None) -> bool:
        return not self.should_fail


def test_resolve_route_candidates_logic():
    router = ModelRouter()

    # 1. Math STEM task
    stem_candidates = router.resolve_route_candidates(task_type="math_stem")
    assert stem_candidates[0] == ("claude", "claude-3-5-sonnet")
    assert stem_candidates[1] == ("deepseek", "deepseek-reasoner")

    # 2. Large context (>100K tokens)
    large_candidates = router.resolve_route_candidates(task_type="general", estimated_tokens=150_000)
    assert large_candidates[0] == ("gemini", "gemini-1.5-pro")

    # 3. Speed instant task
    speed_candidates = router.resolve_route_candidates(task_type="speed_instant")
    assert speed_candidates[0] == ("groq", "llama-3.3-70b-versatile")

    # 4. User explicit override
    override_candidates = router.resolve_route_candidates(provider_override="claude", model_override="claude-3-5-haiku")
    assert override_candidates == [("claude", "claude-3-5-haiku")]


@pytest.mark.django_db
def test_fallback_cascade_on_rate_limit():
    circuit_breaker = CircuitBreaker()
    router = ModelRouter(circuit_breaker=circuit_breaker)

    # Setup Claude as failing with 429 Rate Limit
    failing_claude = DummyAdapter(
        name="claude",
        default_model="claude-3-5-sonnet",
        should_fail=True,
        fail_error=AIProviderRateLimitError("Rate limit exceeded", provider="claude", status_code=429),
    )
    # DeepSeek is working as secondary fallback
    working_deepseek = DummyAdapter(name="deepseek", default_model="deepseek-reasoner")

    router.register_adapter("claude", failing_claude)
    router.register_adapter("deepseek", working_deepseek)

    # Execute math_stem task (primary is claude, fallback is deepseek)
    response = router.generate_text(
        messages=[{"role": "user", "content": "1 + 1"}],
        task_type="math_stem",
    )

    assert failing_claude.call_count == 1
    assert working_deepseek.call_count == 1
    assert "Response from deepseek" in response.content
    assert response.provider == "deepseek"

    # Verify TokenUsageLog recorded the successful fallback call
    log = TokenUsageLog.objects.latest("created_at")
    assert log.provider == "deepseek"
    assert log.model_id == "deepseek-reasoner"
    assert log.task_type == "math_stem"


def test_circuit_breaker_tripping_and_bypass():
    circuit_breaker = CircuitBreaker(failure_threshold=3, cooldown_seconds=60.0)
    provider = "groq"

    assert circuit_breaker.is_available(provider) is True

    # Record 2 failures
    circuit_breaker.record_failure(provider)
    circuit_breaker.record_failure(provider)
    assert circuit_breaker.is_available(provider) is True

    # 3rd failure trips the circuit
    circuit_breaker.record_failure(provider)
    assert circuit_breaker.is_available(provider) is False

    # Success resets circuit
    circuit_breaker.record_success(provider)
    assert circuit_breaker.is_available(provider) is True


@pytest.mark.django_db
def test_byok_encryption_injection_and_auth_invalidation():
    user = User.objects.create_user(username="teacher_byok_test", password="Password123!")
    key_record = UserApiKey(user=user, provider=AIProviderChoices.OPENAI)
    raw_api_key = "sk-proj-user-custom-byok-key-999"
    key_record.set_key(raw_api_key)
    key_record.save()

    router = ModelRouter()
    mock_openai = DummyAdapter(name="openai", default_model="gpt-4o-mini")
    router.register_adapter("openai", mock_openai)

    # Call with authenticated BYOK user
    response = router.generate_text(
        messages=[{"role": "user", "content": "Test"}],
        task_type="general",
        user=user,
    )

    assert mock_openai.call_count == 1
    # Check that decrypted key was injected into config
    assert mock_openai.last_config.api_key_override == raw_api_key

    # Check TokenUsageLog has is_byok=True
    log = TokenUsageLog.objects.latest("created_at")
    assert log.is_byok is True
    assert log.user == user

    # Now simulate an authentication failure with user's BYOK key
    failing_openai = DummyAdapter(
        name="openai",
        default_model="gpt-4o-mini",
        should_fail=True,
        fail_error=AIProviderAuthError("Bad key", provider="openai", status_code=401),
    )
    router.register_adapter("openai", failing_openai)

    with pytest.raises(AIProviderAuthError):
        router.generate_text(
            messages=[{"role": "user", "content": "Test"}],
            task_type="general",
            user=user,
        )

    # Verify that the invalid BYOK key was automatically marked invalid in DB
    key_record.refresh_from_db()
    assert key_record.is_valid is False
