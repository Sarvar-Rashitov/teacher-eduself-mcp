import json
import asyncio
from decimal import Decimal
import pytest
import httpx
from pydantic import BaseModel, Field

from apps.ai_gateway.base import (
    ModelConfig,
    TokenUsage,
    TextResponse,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderServerError,
)
from apps.ai_gateway.adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)
from apps.ai_gateway.router import ModelRouter


class SampleQuizOutput(BaseModel):
    title: str = Field(..., description="Quiz title")
    question_count: int = Field(..., description="Number of questions")


class TestAIAdapters:
    def test_openai_adapter_text_and_structured(self):
        async def _run():
            def mock_handler(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content.decode("utf-8"))
                if "response_format" in body:
                    content = json.dumps({"title": "Fizika Test", "question_count": 5})
                else:
                    content = "Salom, bu test javob."

                data = {
                    "id": "chatcmpl-test",
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": content},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 50,
                        "total_tokens": 150,
                    },
                }
                return httpx.Response(200, json=data)

            transport = httpx.MockTransport(mock_handler)
            client = httpx.AsyncClient(transport=transport)
            adapter = OpenAIAdapter(api_key="mock-key", http_client=client)

            # 1. Text generation
            res = await adapter.generate_text([{"role": "user", "content": "test"}])
            assert res.content == "Salom, bu test javob."
            assert res.usage.total_tokens == 150
            assert res.provider == "openai"

            # 2. Structured generation
            struct_res = await adapter.generate_structured(
                [{"role": "user", "content": "generate quiz"}],
                schema=SampleQuizOutput,
            )
            assert struct_res.title == "Fizika Test"
            assert struct_res.question_count == 5

            # 3. Cost calculation
            cost = adapter.estimate_cost(TokenUsage(1_000_000, 1_000_000, 2_000_000), "gpt-4o-mini")
            assert cost == Decimal("0.750000")

        asyncio.run(_run())

    def test_openai_adapter_error_mapping(self):
        async def _run():
            # 429 Rate Limit error
            def rate_limit_handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(429, json={"error": {"message": "Rate limit reached"}})

            transport = httpx.MockTransport(rate_limit_handler)
            client = httpx.AsyncClient(transport=transport)
            adapter = OpenAIAdapter(api_key="mock-key", http_client=client)

            with pytest.raises(AIProviderRateLimitError):
                await adapter.generate_text([{"role": "user", "content": "hi"}])

            # 401 Auth error
            def auth_handler(request: httpx.Request) -> httpx.Response:
                return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

            adapter._http_client = httpx.AsyncClient(transport=httpx.MockTransport(auth_handler))
            with pytest.raises(AIProviderAuthError):
                await adapter.generate_text([{"role": "user", "content": "hi"}])

        asyncio.run(_run())

    def test_gemini_adapter_text(self):
        async def _run():
            def gemini_handler(request: httpx.Request) -> httpx.Response:
                data = {
                    "candidates": [
                        {
                            "content": {"parts": [{"text": "Gemini tahlili"}]},
                            "finishReason": "STOP",
                        }
                    ],
                    "usageMetadata": {
                        "promptTokenCount": 200,
                        "candidatesTokenCount": 100,
                        "totalTokenCount": 300,
                    },
                }
                return httpx.Response(200, json=data)

            transport = httpx.MockTransport(gemini_handler)
            client = httpx.AsyncClient(transport=transport)
            adapter = GeminiAdapter(api_key="mock-key", http_client=client)

            res = await adapter.generate_text([{"role": "user", "content": "matn"}])
            assert res.content == "Gemini tahlili"
            assert res.usage.total_tokens == 300

            cost = adapter.estimate_cost(TokenUsage(1_000_000, 1_000_000, 2_000_000), "gemini-1.5-flash")
            assert cost == Decimal("0.375000")

        asyncio.run(_run())

    def test_claude_adapter_text_and_tool_structured(self):
        async def _run():
            def claude_handler(request: httpx.Request) -> httpx.Response:
                body = json.loads(request.content.decode("utf-8"))
                if "tools" in body:
                    content = [
                        {
                            "type": "tool_use",
                            "id": "call_1",
                            "name": "emit_samplequizoutput",
                            "input": {"title": "Biologiya", "question_count": 10},
                        }
                    ]
                else:
                    content = [{"type": "text", "text": "Claude javobi"}]

                data = {
                    "id": "msg_01",
                    "content": content,
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 50, "output_tokens": 25},
                }
                return httpx.Response(200, json=data)

            transport = httpx.MockTransport(claude_handler)
            client = httpx.AsyncClient(transport=transport)
            adapter = ClaudeAdapter(api_key="mock-key", http_client=client)

            res = await adapter.generate_text([{"role": "user", "content": "hi"}])
            assert res.content == "Claude javobi"

            struct_res = await adapter.generate_structured(
                [{"role": "user", "content": "create"}],
                schema=SampleQuizOutput,
            )
            assert struct_res.title == "Biologiya"
            assert struct_res.question_count == 10

        asyncio.run(_run())


class TestModelRouterAndFallback:
    def test_routing_matrix_resolution(self):
        router = ModelRouter()

        # Big context should route to Gemini primary
        chain_big = router.resolve_route("big_context")
        assert chain_big[0] == ("gemini", "gemini-1.5-pro")

        # STEM should route to Claude primary
        chain_stem = router.resolve_route("stem")
        assert chain_stem[0] == ("claude", "claude-3-5-sonnet")

        # Speed should route to Groq primary
        chain_speed = router.resolve_route("speed")
        assert chain_speed[0] == ("groq", "llama-3.3-70b-versatile")

        # Preferred override
        chain_pref = router.resolve_route("general", preferred_provider="claude")
        assert chain_pref[0][0] == "claude"

    def test_fallback_cascade_on_rate_limit(self):
        """
        DOC-69 Section 4:
        Primary provider (OpenAI) fails with 429 Rate Limit.
        Router must seamlessly cascade to Fallback (DeepSeek) and succeed!
        """
        async def _run():
            primary_mock = OpenAIAdapter(api_key="mock")

            async def mock_fail_text(messages, config=None):
                raise AIProviderRateLimitError("Quota exhausted", provider="openai")

            primary_mock.generate_text = mock_fail_text

            fallback_mock = DeepSeekAdapter(api_key="mock")

            async def mock_success_text(messages, config=None):
                return TextResponse(
                    content="DeepSeek zaxira javobi",
                    finish_reason="stop",
                    usage=TokenUsage(100, 50, 150),
                    latency_ms=120,
                    model_id="deepseek-chat",
                    provider="deepseek",
                )

            fallback_mock.generate_text = mock_success_text

            router = ModelRouter(adapters={
                "openai": primary_mock,
                "deepseek": fallback_mock,
                "groq": GroqAdapter(),
                "claude": ClaudeAdapter(),
                "gemini": GeminiAdapter(),
            })

            res = await router.execute_text([{"role": "user", "content": "Savol"}], task_type="general")
            assert res.content == "DeepSeek zaxira javobi"
            assert res.provider == "deepseek"

        asyncio.run(_run())
