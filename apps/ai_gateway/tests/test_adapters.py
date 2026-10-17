"""
Unit testlar: AI Adapterlar (OpenAI, Gemini, Claude, Groq, DeepSeek).
Spetsifikatsiya: .docs/ai/AI_ADAPTERS.md
"""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import httpx
from pydantic import BaseModel

from apps.ai_gateway.base import (
    ModelConfig,
    TokenUsage,
    AIProviderRateLimitError,
    AIProviderAuthError,
    AIProviderServerError,
    AIProviderTimeoutError
)
from apps.ai_gateway.adapters.openai_adapter import OpenAIAdapter
from apps.ai_gateway.adapters.gemini_adapter import GeminiAdapter
from apps.ai_gateway.adapters.claude_adapter import ClaudeAdapter
from apps.ai_gateway.adapters.groq_adapter import GroqAdapter
from apps.ai_gateway.adapters.deepseek_adapter import DeepSeekAdapter


class SampleQuizSchema(BaseModel):
    title: str
    num_questions: int


@pytest.mark.asyncio
class TestOpenAIAdapter:
    async def test_generate_text_success(self):
        adapter = OpenAIAdapter()
        config = ModelConfig(model_name="gpt-4o-mini", api_key_override="sk-mock-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Salom, bu test javobi."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            res = await adapter.generate_text([{"role": "user", "content": "Salom"}], config)
            assert res.content == "Salom, bu test javobi."
            assert res.usage.total_tokens == 150
            assert res.model_name == "gpt-4o-mini"

    async def test_generate_structured_success(self):
        adapter = OpenAIAdapter()
        config = ModelConfig(model_name="gpt-4o-mini", api_key_override="sk-mock-key")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {"content": '{"title": "Fizika Testi", "num_questions": 10}'}
            }]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            quiz = await adapter.generate_structured(
                [{"role": "user", "content": "Test yarat"}],
                SampleQuizSchema,
                config
            )
            assert quiz.title == "Fizika Testi"
            assert quiz.num_questions == 10

    async def test_error_mapping_rate_limit(self):
        adapter = OpenAIAdapter()
        config = ModelConfig(api_key_override="sk-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.text = "Rate limit exceeded"
        mock_resp.json.return_value = {"error": {"message": "Rate limit exceeded"}}

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            with pytest.raises(AIProviderRateLimitError):
                await adapter.generate_text([{"role": "user", "content": "Hi"}], config)

    async def test_error_mapping_auth_error(self):
        adapter = OpenAIAdapter()
        config = ModelConfig(api_key_override="sk-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            with pytest.raises(AIProviderAuthError):
                await adapter.generate_text([{"role": "user", "content": "Hi"}], config)

    async def test_cost_estimation(self):
        adapter = OpenAIAdapter()
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
        # 1000/1M * 0.15 + 500/1M * 0.60 = 0.00015 + 0.00030 = 0.000450
        cost = adapter.estimate_cost(usage, "gpt-4o-mini")
        assert cost == Decimal("0.000450")


@pytest.mark.asyncio
class TestGeminiAdapter:
    async def test_gemini_generate_text_success(self):
        adapter = GeminiAdapter()
        config = ModelConfig(model_name="gemini-1.5-flash", api_key_override="AIza-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Gemini javobi."}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20, "totalTokenCount": 70}
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            res = await adapter.generate_text([{"role": "user", "content": "Salom"}], config)
            assert res.content == "Gemini javobi."
            assert res.usage.total_tokens == 70

    async def test_gemini_generate_structured(self):
        adapter = GeminiAdapter()
        config = ModelConfig(model_name="gemini-1.5-flash", api_key_override="AIza-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"title": "Kimyo Testi", "num_questions": 5}'}]}}]
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            quiz = await adapter.generate_structured([{"role": "user", "content": "Kitob"}], SampleQuizSchema, config)
            assert quiz.title == "Kimyo Testi"
            assert quiz.num_questions == 5


@pytest.mark.asyncio
class TestClaudeAdapter:
    async def test_claude_generate_structured_tool_use(self):
        adapter = ClaudeAdapter()
        config = ModelConfig(model_name="claude-3-5-sonnet-20241022", api_key_override="sk-ant-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [{
                "type": "tool_use",
                "name": "samplequizschema",
                "input": {"title": "Olimpiada Masalalari", "num_questions": 3}
            }],
            "usage": {"input_tokens": 120, "output_tokens": 40}
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            quiz = await adapter.generate_structured([{"role": "user", "content": "Olimpiada"}], SampleQuizSchema, config)
            assert quiz.title == "Olimpiada Masalalari"
            assert quiz.num_questions == 3


@pytest.mark.asyncio
class TestGroqAndDeepSeekAdapters:
    async def test_groq_generate_text(self):
        adapter = GroqAdapter()
        config = ModelConfig(model_name="llama-3.3-70b-versatile", api_key_override="gsk_mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Tezkor Groq javobi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            res = await adapter.generate_text([{"role": "user", "content": "Tezkor"}], config)
            assert res.content == "Tezkor Groq javobi"

    async def test_deepseek_generate_text(self):
        adapter = DeepSeekAdapter()
        config = ModelConfig(model_name="deepseek-chat", api_key_override="sk-deepseek-mock")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "DeepSeek javobi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 200, "completion_tokens": 100, "total_tokens": 300}
        }

        with patch("httpx.AsyncClient.post", return_value=mock_resp):
            res = await adapter.generate_text([{"role": "user", "content": "Arzon"}], config)
            assert res.content == "DeepSeek javobi"
