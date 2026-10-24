import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from pydantic import BaseModel

from ai_gateway.adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)
from ai_gateway.base import (
    ModelConfig,
    TokenUsage,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)


class SampleQuizSchema(BaseModel):
    title: str
    questions_count: int


class TestAdapters:
    # =========================================================================
    # OpenAI Adapter Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_openai_generate_text_success(self):
        adapter = OpenAIAdapter(api_key="mock-key")
        mock_response = httpx.Response(
            status_code=200,
            json={
                "choices": [{"message": {"content": "2 + 2 = 4"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 15, "completion_tokens": 8, "total_tokens": 23},
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await adapter.generate_text([{"role": "user", "content": "What is 2+2?"}])

            assert res.content == "2 + 2 = 4"
            assert res.usage.total_tokens == 23
            assert res.provider == "openai"

    @pytest.mark.asyncio
    async def test_openai_structured_output(self):
        adapter = OpenAIAdapter(api_key="mock-key")
        mock_response = httpx.Response(
            status_code=200,
            json={
                "choices": [{
                    "message": {"content": json.dumps({"title": "Fizika Test", "questions_count": 5})},
                    "finish_reason": "stop"
                }],
            },
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await adapter.generate_structured(
                messages=[{"role": "user", "content": "Generate quiz"}],
                schema=SampleQuizSchema,
            )
            assert isinstance(res, SampleQuizSchema)
            assert res.title == "Fizika Test"
            assert res.questions_count == 5

    @pytest.mark.asyncio
    async def test_openai_rate_limit_error_mapping(self):
        adapter = OpenAIAdapter(api_key="mock-key")
        mock_response = httpx.Response(
            status_code=429,
            json={"error": {"message": "Rate limit exceeded for organization"}},
            request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(AIProviderRateLimitError) as exc_info:
                await adapter.generate_text([{"role": "user", "content": "hi"}])
            assert "Rate limit exceeded" in str(exc_info.value)
            assert exc_info.value.provider == "openai"

    def test_openai_cost_estimation(self):
        adapter = OpenAIAdapter()
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        # gpt-4o-mini: input 0.15/1M ($0.00015), output 0.60/1M ($0.00030) -> total $0.000450
        cost = adapter.estimate_cost(usage, "gpt-4o-mini")
        assert cost == Decimal("0.000450")

    # =========================================================================
    # Gemini Adapter Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_gemini_generate_text_success(self):
        adapter = GeminiAdapter(api_key="mock-gemini-key")
        mock_response = httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {"parts": [{"text": "Toshkent O'zbekiston poytaxti"}]},
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 20,
                    "candidatesTokenCount": 10,
                    "totalTokenCount": 30,
                },
            },
            request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await adapter.generate_text([{"role": "user", "content": "Poytaxt qayer?"}])
            assert res.content == "Toshkent O'zbekiston poytaxti"
            assert res.usage.total_tokens == 30
            assert res.provider == "gemini"

    def test_gemini_capabilities(self):
        adapter = GeminiAdapter()
        caps = adapter.get_capabilities()
        assert caps.max_context_window == 1000000
        assert caps.supports_vision is True

    # =========================================================================
    # Claude Adapter Tests
    # =========================================================================

    @pytest.mark.asyncio
    async def test_claude_generate_text_success(self):
        adapter = ClaudeAdapter(api_key="mock-claude-key")
        mock_response = httpx.Response(
            status_code=200,
            json={
                "content": [{"type": "text", "text": "Mantiqiy xulosa: A = B"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 50, "output_tokens": 20},
            },
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            res = await adapter.generate_text([{"role": "user", "content": "Mantiqiy savol"}])
            assert "Mantiqiy xulosa" in res.content
            assert res.usage.total_tokens == 70
            assert res.provider == "claude"

    @pytest.mark.asyncio
    async def test_claude_auth_error_mapping(self):
        adapter = ClaudeAdapter(api_key="invalid-key")
        mock_response = httpx.Response(
            status_code=401,
            json={"error": {"type": "authentication_error", "message": "Invalid API Key"}},
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(AIProviderAuthError):
                await adapter.generate_text([{"role": "user", "content": "hi"}])

    # =========================================================================
    # Groq & DeepSeek Adapters Tests
    # =========================================================================

    def test_groq_and_deepseek_pricing(self):
        groq = GroqAdapter()
        deepseek = DeepSeekAdapter()

        u = TokenUsage(prompt_tokens=1000000, completion_tokens=1000000, total_tokens=2000000)

        # Groq Llama 3.3 70B: $0.59 + $0.79 = $1.38
        assert groq.estimate_cost(u) == Decimal("1.380000")

        # DeepSeek V3: $0.14 + $0.28 = $0.42 (cheapest!)
        assert deepseek.estimate_cost(u) == Decimal("0.420000")
