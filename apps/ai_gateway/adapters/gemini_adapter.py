"""
Google Gemini Provider Adapter.
Spetsifikatsiya: .docs/ai/AI_PROVIDERS.md (2.2-bo'lim) & AI_ADAPTERS.md
"""
import time
import json
from typing import AsyncIterator, Type, TypeVar, Optional, List, Dict
from decimal import Decimal
import httpx
from django.conf import settings
from pydantic import BaseModel

from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TokenUsage,
    TextResponse,
    ProviderCapabilities,
    AIProviderRateLimitError,
    AIProviderAuthError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderError
)

T = TypeVar("T", bound=BaseModel)


class GeminiAdapter(BaseAIAdapter):
    provider_name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-1.5-flash"

    PRICING = {
        "gemini-1.5-flash": {"input": Decimal("0.075"), "output": Decimal("0.30")},
        "gemini-1.5-pro": {"input": Decimal("1.25"), "output": Decimal("5.00")},
    }

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        key = getattr(settings, 'GEMINI_API_KEY', '')
        return key.strip() if key else ""

    def _map_http_error(self, response: httpx.Response):
        code = response.status_code
        try:
            err_data = response.json().get('error', {})
            msg = err_data.get('message', response.text)
        except Exception:
            msg = response.text

        if code == 429:
            raise AIProviderRateLimitError(f"Gemini Quota/Rate Limit: {msg}", provider=self.provider_name, status_code=code)
        elif code in (401, 403):
            raise AIProviderAuthError(f"Gemini Auth Xatosi: {msg}", provider=self.provider_name, status_code=code)
        elif code in (500, 502, 503, 504):
            raise AIProviderServerError(f"Gemini Server Xatosi: {msg}", provider=self.provider_name, status_code=code)
        else:
            raise AIProviderError(f"Gemini API Xatosi ({code}): {msg}", provider=self.provider_name, status_code=code)

    def _format_messages_to_contents(self, messages: List[Dict[str, str]]) -> List[Dict]:
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })
        return contents

    async def generate_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> TextResponse:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("Gemini API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        contents = self._format_messages_to_contents(messages)

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens,
                "topP": config.top_p,
            }
        }

        url = f"{self.BASE_URL}/{model}:generateContent?key={api_key}"
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(url, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        latency_ms = int((time.time() - start_time) * 1000)
        data = res.json()
        candidates = data.get('candidates', [{}])
        first_candidate = candidates[0] if candidates else {}
        parts = first_candidate.get('content', {}).get('parts', [{}])
        content_text = parts[0].get('text', '') if parts else ''

        usage_meta = data.get('usageMetadata', {})
        usage = TokenUsage(
            prompt_tokens=usage_meta.get('promptTokenCount', 0),
            completion_tokens=usage_meta.get('candidatesTokenCount', 0),
            total_tokens=usage_meta.get('totalTokenCount', 0)
        )

        return TextResponse(
            content=content_text,
            finish_reason=first_candidate.get('finishReason', 'STOP'),
            usage=usage,
            latency_ms=latency_ms,
            model_name=model
        )

    async def generate_structured(
        self, messages: List[Dict[str, str]], schema: Type[T], config: ModelConfig
    ) -> T:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("Gemini API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        contents = self._format_messages_to_contents(messages)

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": config.temperature,
                "maxOutputTokens": config.max_tokens,
                "responseMimeType": "application/json",
            }
        }

        url = f"{self.BASE_URL}/{model}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(url, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        data = res.json()
        candidates = data.get('candidates', [{}])
        parts = candidates[0].get('content', {}).get('parts', [{}])
        text_str = parts[0].get('text', '{}')
        parsed = json.loads(text_str)
        return schema.model_validate(parsed)

    async def stream_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> AsyncIterator[str]:
        # Oddiy fallback streaming
        res = await self.generate_text(messages, config)
        yield res.content

    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=1000000  # 1M token context
        )

    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        pricing = self.PRICING.get(model_id, self.PRICING["gemini-1.5-flash"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal(1000000)) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal(1000000)) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._get_api_key()
        if not key:
            return False
        url = f"{self.BASE_URL}?key={key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url)
                return res.status_code == 200
        except Exception:
            return False
