import os
import time
import json
from decimal import Decimal
from typing import AsyncIterator, Type, Optional, Any
import httpx

from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TokenUsage,
    TextResponse,
    ProviderCapabilities,
    T,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderContextLengthError,
    AIProviderContentFilterError,
    AIProviderError,
)


class GeminiAdapter(BaseAIAdapter):
    provider_name = "gemini"
    default_model = "gemini-1.5-flash"

    PRICING_PER_1M = {
        "gemini-1.5-flash": {"input": Decimal("0.075"), "output": Decimal("0.30")},
        "gemini-1.5-pro": {"input": Decimal("1.25"), "output": Decimal("5.00")},
    }

    def __init__(self, api_key: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self._default_api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._http_client = http_client

    def _get_api_key(self, config: Optional[ModelConfig]) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        return self._default_api_key

    def _map_http_error(self, exc: Exception) -> AIProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return AIProviderTimeoutError("Gemini request timed out", provider=self.provider_name)
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            text = exc.response.text
            if status in (401, 403):
                return AIProviderAuthError(f"Gemini Auth failed: {text}", provider=self.provider_name, status_code=status)
            elif status == 429:
                return AIProviderRateLimitError(f"Gemini Quota/Rate limit exceeded: {text}", provider=self.provider_name, status_code=status)
            elif status >= 500:
                return AIProviderServerError(f"Gemini Server error: {text}", provider=self.provider_name, status_code=status)
            elif "SAFETY" in text or "BLOCK" in text:
                return AIProviderContentFilterError(f"Gemini Safety filter triggered: {text}", provider=self.provider_name, status_code=status)
            return AIProviderError(f"Gemini Error ({status}): {text}", provider=self.provider_name, status_code=status)
        return AIProviderError(str(exc), provider=self.provider_name)

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, Any]]:
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.get("content", "")}],
            })
        return contents

    async def generate_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        cfg = config or ModelConfig()
        model = cfg.model_override or self.default_model
        api_key = self._get_api_key(cfg)

        payload = {
            "contents": self._convert_messages(messages),
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "topP": cfg.top_p,
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        start_time = time.perf_counter()
        try:
            client = self._http_client or httpx.AsyncClient(timeout=cfg.timeout_seconds)
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            finally:
                if self._http_client is None:
                    await client.aclose()
        except Exception as e:
            raise self._map_http_error(e)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        candidate = data["candidates"][0]
        content = candidate["content"]["parts"][0]["text"]
        finish_reason = candidate.get("finishReason", "STOP")

        meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=meta.get("promptTokenCount", 0),
            completion_tokens=meta.get("candidatesTokenCount", 0),
            total_tokens=meta.get("totalTokenCount", 0),
        )

        return TextResponse(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            model_id=model,
            provider=self.provider_name,
        )

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        cfg = config or ModelConfig()
        model = cfg.model_override or self.default_model
        api_key = self._get_api_key(cfg)

        payload = {
            "contents": self._convert_messages(messages),
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "responseMimeType": "application/json",
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}

        try:
            client = self._http_client or httpx.AsyncClient(timeout=cfg.timeout_seconds)
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            finally:
                if self._http_client is None:
                    await client.aclose()
        except Exception as e:
            raise self._map_http_error(e)

        content = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(content)
        return schema.model_validate(parsed)

    async def stream_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        # For simplicity, fallback to generating text chunks
        res = await self.generate_text(messages, config)
        yield res.content

    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        is_pro = "pro" in model_id
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=2000000 if is_pro else 1000000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        pricing = self.PRICING_PER_1M.get(model_id, self.PRICING_PER_1M["gemini-1.5-flash"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal(1_000_000)) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal(1_000_000)) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self) -> bool:
        if not self._default_api_key:
            return False
        try:
            res = await self.generate_text([{"role": "user", "content": "ping"}], ModelConfig(max_tokens=5, timeout_seconds=5.0))
            return bool(res.content)
        except Exception:
            return False
