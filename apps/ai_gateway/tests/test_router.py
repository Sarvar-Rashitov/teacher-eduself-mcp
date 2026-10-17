"""
Unit testlar: ModelRouter, Fallback Cascade va Circuit Breaker.
Spetsifikatsiya: .docs/ai/MODEL_ROUTING.md
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from django.contrib.auth import get_user_model

from apps.ai_gateway.base import (
    ModelConfig,
    TokenUsage,
    TextResponse,
    AIProviderRateLimitError,
    AIProviderServerError
)
from apps.ai_gateway.models import UserApiKey, AIProviderChoice
from apps.ai_gateway.router import ModelRouter, CircuitBreaker

User = get_user_model()


class TestCircuitBreaker:
    def test_circuit_trips_after_3_failures(self):
        cb = CircuitBreaker()
        provider = "test_provider"

        assert cb.is_available(provider) is True

        cb.record_failure(provider)
        assert cb.is_available(provider) is True

        cb.record_failure(provider)
        assert cb.is_available(provider) is True

        # 3-xatoda OPEN holatiga o'tadi
        cb.record_failure(provider)
        assert cb.is_available(provider) is False

    def test_circuit_resets_on_success(self):
        cb = CircuitBreaker()
        provider = "test_provider"
        cb.record_failure(provider)
        cb.record_failure(provider)
        cb.record_success(provider)
        assert cb.is_available(provider) is True
        assert cb._failures[provider] == 0


@pytest.mark.django_db
class TestModelRouter:
    @pytest.fixture
    def router(self):
        r = ModelRouter()
        r.circuit_breaker.reset()
        return r

    def test_routing_matrix_selection(self, router):
        """Vazifalar bo'yicha birlamchi va zaxira modellar tanlovi."""
        # Katta darslik -> Gemini
        targets_doc = router.select_targets(task_type='large_document')
        assert targets_doc[0] == ('gemini', 'gemini-1.5-pro')

        # Matematika -> Claude
        targets_math = router.select_targets(task_type='stem_math')
        assert targets_math[0] == ('claude', 'claude-3-5-sonnet-20241022')

        # Tezkor darsdagi test -> Groq
        targets_quick = router.select_targets(task_type='quick_quiz')
        assert targets_quick[0] == ('groq', 'llama-3.3-70b-versatile')

        # Standart -> OpenAI
        targets_std = router.select_targets(task_type='standard')
        assert targets_std[0] == ('openai', 'gpt-4o-mini')

    def test_byok_tier_1_precedence(self, router):
        """Foydalanuvchining shaxsiy BYOK kaliti bo'lsa, 1-pog'ona sifatida birinchi bo'lib tanlanadi."""
        user = User.objects.create_user(username='byok_teacher', password='pass')
        key = UserApiKey.objects.create(user=user, provider=AIProviderChoice.DEEPSEEK)
        key.set_key("sk-deepseek-custom")
        key.save()

        targets = router.select_targets(task_type='standard', user=user)
        # Standartda OpenAI bo'lishiga qaramay, o'qituvchining DeepSeek BYOK kaliti tanlanadi
        assert targets[0][0] == 'deepseek'

    @pytest.mark.asyncio
    async def test_fallback_cascade_on_rate_limit(self, router):
        """
        Birlamchi provayder RateLimit (429) berganda,
        foydalanuvchiga xato bermasdan avtomatik 2-zaxiraga o'tishi kerak.
        """
        messages = [{"role": "user", "content": "Salom"}]

        # 1-provayder (OpenAI) xato beradi
        router.adapters['openai'].generate_text = AsyncMock(
            side_effect=AIProviderRateLimitError("Quota limit", provider="openai")
        )

        # 2-provayder (DeepSeek) muvaffaqiyatli ishlaydi
        router.adapters['deepseek'].generate_text = AsyncMock(
            return_value=TextResponse(
                content="DeepSeek zaxira javobi",
                usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                model_name="deepseek-chat"
            )
        )

        resp = await router.execute_text(messages, task_type='standard')
        assert resp.content == "DeepSeek zaxira javobi"
        assert resp.model_name == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_circuit_breaker_skips_failed_provider(self, router):
        """Circuit Breaker TRIP bo'lganda, so'rov ushbu provayderga yuborilmaydi."""
        provider = 'openai'
        for _ in range(3):
            router.circuit_breaker.record_failure(provider)

        assert router.circuit_breaker.is_available(provider) is False

        # OpenAI ga umuman murojaat qilinmasdan to'g'ridan-to'g'ri DeepSeek chaqiriladi
        router.adapters['openai'].generate_text = AsyncMock()
        router.adapters['deepseek'].generate_text = AsyncMock(
            return_value=TextResponse(content="DeepSeek javobi", model_name="deepseek-chat")
        )

        resp = await router.execute_text([{"role": "user", "content": "Test"}], task_type='standard')
        assert resp.content == "DeepSeek javobi"
        # OpenAI adapteri chaqirilmagan bo'lishi kerak
        router.adapters['openai'].generate_text.assert_not_called()
