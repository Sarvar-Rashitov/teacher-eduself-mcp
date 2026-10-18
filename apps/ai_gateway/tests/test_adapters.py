import json
from decimal import Decimal
import httpx
import pytest
from pydantic import BaseModel
from apps.ai_gateway.base import (
    ModelConfig,
    TokenUsage,
    AIProviderAuthError,
    AIProviderContextLengthError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)
from apps.ai_gateway.adapters import (
    OpenAIAdapter,
    GeminiAdapter,
    ClaudeAdapter,
    GroqAdapter,
    DeepSeekAdapter,
)


class QuizQuestionSchema(BaseModel):
    question: str
    options: list[str]
    correct_index: int


# ==============================================================================
# OpenAI Adapter Tests
# ==============================================================================

def test_openai_generate_text_success():
    def mock_handler(request: httpx.Request):
        payload = {
            "choices": [{"message": {"content": "Salom! Bu OpenAI javobi."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = OpenAIAdapter(default_api_key="sk-openai-test-key", http_client=client)

    response = adapter.generate_text([{"role": "user", "content": "Salom"}])
    assert response.content == "Salom! Bu OpenAI javobi."
    assert response.usage.total_tokens == 25
    assert response.provider == "openai"


def test_openai_generate_structured_pydantic():
    def mock_handler(request: httpx.Request):
        structured_data = {
            "question": "O'zbekiston poytaxti qaysi shahar?",
            "options": ["Toshkent", "Samarqand", "Buxoro", "Xiva"],
            "correct_index": 0,
        }
        payload = {
            "choices": [{"message": {"content": json.dumps(structured_data)}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = OpenAIAdapter(default_api_key="sk-openai-test-key", http_client=client)

    result = adapter.generate_structured(
        messages=[{"role": "user", "content": "Savol tuz"}],
        schema=QuizQuestionSchema,
    )
    assert isinstance(result, QuizQuestionSchema)
    assert result.question == "O'zbekiston poytaxti qaysi shahar?"
    assert result.options[0] == "Toshkent"
    assert result.correct_index == 0


def test_openai_rate_limit_error_mapping():
    def mock_handler(request: httpx.Request):
        return httpx.Response(429, json={"error": {"message": "Rate limit exceeded", "type": "tokens"}})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = OpenAIAdapter(default_api_key="sk-openai-test-key", http_client=client)

    with pytest.raises(AIProviderRateLimitError) as exc_info:
        adapter.generate_text([{"role": "user", "content": "Test"}])
    assert exc_info.value.status_code == 429


def test_openai_cost_estimation():
    adapter = OpenAIAdapter()
    usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000)
    # gpt-4o-mini: 1000/1M * 0.15 + 1000/1M * 0.60 = 0.00015 + 0.00060 = 0.000750
    cost = adapter.estimate_cost(usage, model_id="gpt-4o-mini")
    assert cost == Decimal("0.000750")


# ==============================================================================
# Gemini Adapter Tests
# ==============================================================================

def test_gemini_generate_text_success():
    def mock_handler(request: httpx.Request):
        payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "Gemini 1.5 tahlili tayyor."}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 50,
                "candidatesTokenCount": 20,
                "totalTokenCount": 70,
            },
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = GeminiAdapter(default_api_key="AIzaSy-gemini-test-key", http_client=client)

    response = adapter.generate_text([{"role": "user", "content": "Darslikni tahlil qil"}])
    assert response.content == "Gemini 1.5 tahlili tayyor."
    assert response.usage.total_tokens == 70
    assert response.provider == "gemini"


def test_gemini_auth_error_mapping():
    def mock_handler(request: httpx.Request):
        return httpx.Response(400, json={"error": {"message": "API_KEY_INVALID", "status": "INVALID_ARGUMENT"}})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = GeminiAdapter(default_api_key="invalid-key", http_client=client)

    with pytest.raises(AIProviderAuthError):
        adapter.generate_text([{"role": "user", "content": "Test"}])


def test_gemini_context_window_capabilities():
    adapter = GeminiAdapter()
    caps = adapter.get_capabilities()
    assert caps.max_context_window == 1000000
    assert caps.supports_vision is True


# ==============================================================================
# Claude Adapter Tests
# ==============================================================================

def test_claude_generate_text_success():
    def mock_handler(request: httpx.Request):
        payload = {
            "content": [{"type": "text", "text": "Claude 3.5 matematik yechimi."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 40, "output_tokens": 25},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = ClaudeAdapter(default_api_key="sk-ant-test-key", http_client=client)

    response = adapter.generate_text([{"role": "user", "content": "Tenglamani yech"}])
    assert response.content == "Claude 3.5 matematik yechimi."
    assert response.usage.total_tokens == 65
    assert response.provider == "claude"


def test_claude_generate_structured_tool_use():
    def mock_handler(request: httpx.Request):
        structured_data = {
            "question": "Nyutonning ikkinchi qonuni formulasi qaysi?",
            "options": ["F = ma", "E = mc^2", "P = UI", "v = s / t"],
            "correct_index": 0,
        }
        payload = {
            "content": [{"type": "tool_use", "name": "emit_structured_output", "input": structured_data}],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 50, "output_tokens": 30},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = ClaudeAdapter(default_api_key="sk-ant-test-key", http_client=client)

    result = adapter.generate_structured(
        messages=[{"role": "user", "content": "Fizika savoli"}],
        schema=QuizQuestionSchema,
    )
    assert isinstance(result, QuizQuestionSchema)
    assert result.question == "Nyutonning ikkinchi qonuni formulasi qaysi?"
    assert result.options[0] == "F = ma"


# ==============================================================================
# Groq & DeepSeek Adapter Tests
# ==============================================================================

def test_groq_sub_second_generate():
    def mock_handler(request: httpx.Request):
        payload = {
            "choices": [{"message": {"content": "Tezkor Groq javobi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    adapter = GroqAdapter(default_api_key="gsk-test-key", http_client=client)

    response = adapter.generate_text([{"role": "user", "content": "Tezkor savol"}])
    assert response.content == "Tezkor Groq javobi"
    assert response.provider == "groq"


def test_deepseek_cost_effective_estimation():
    adapter = DeepSeekAdapter()
    usage = TokenUsage(prompt_tokens=10000, completion_tokens=5000)
    # deepseek-chat: 10K/1M * 0.14 = 0.001400; 5K/1M * 0.28 = 0.001400; total = 0.002800
    cost = adapter.estimate_cost(usage, model_id="deepseek-chat")
    assert cost == Decimal("0.002800")
