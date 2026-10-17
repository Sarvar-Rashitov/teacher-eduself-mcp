"""
OpenAI Provider Adapter.
Spetsifikatsiya: .docs/ai/AI_PROVIDERS.md (2.1-bo'lim) & AI_ADAPTERS.md
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


class OpenAIAdapter(BaseAIAdapter):
    provider_name = "openai"
    BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    # Narxlar (1M token uchun AQSH dollarida)
    PRICING = {
        "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
        "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    }

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        key = getattr(settings, 'OPENAI_API_KEY', '')
        return key.strip() if key else ""

    def _map_http_error(self, response: httpx.Response):
        code = response.status_code
        try:
            err_data = response.json().get('error', {})
            msg = err_data.get('message', response.text)
        except Exception:
            msg = response.text

        if code == 429:
            raise AIProviderRateLimitError(f"OpenAI Rate Limit: {msg}", provider=self.provider_name, status_code=code)
        elif code in (401, 403):
            raise AIProviderAuthError(f"OpenAI Auth Xatosi: {msg}", provider=self.provider_name, status_code=code)
        elif code in (500, 502, 503, 504):
            raise AIProviderServerError(f"OpenAI Server Xatosi: {msg}", provider=self.provider_name, status_code=code)
        else:
            raise AIProviderError(f"OpenAI API Xatosi ({code}): {msg}", provider=self.provider_name, status_code=code)

    async def generate_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> TextResponse:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("OpenAI API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(f"{self.BASE_URL}/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"OpenAI so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        latency_ms = int((time.time() - start_time) * 1000)
        data = res.json()
        choice = data['choices'][0]
        usage_data = data.get('usage', {})

        usage = TokenUsage(
            prompt_tokens=usage_data.get('prompt_tokens', 0),
            completion_tokens=usage_data.get('completion_tokens', 0),
            total_tokens=usage_data.get('total_tokens', 0),
        )

        return TextResponse(
            content=choice['message']['content'],
            finish_reason=choice.get('finish_reason', 'stop'),
            usage=usage,
            latency_ms=latency_ms,
            model_name=model
        )

    async def generate_structured(
        self, messages: List[Dict[str, str]], schema: Type[T], config: ModelConfig
    ) -> T:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("OpenAI API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        schema_dict = schema.model_json_schema()

        payload = {
            "model": model,
            "messages": messages,
            "temperature": config.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema_dict
                }
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(f"{self.BASE_URL}/chat/completions", json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"OpenAI so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        data = res.json()
        content = data['choices'][0]['message']['content']
        parsed_dict = json.loads(content)
        return schema.model_validate(parsed_dict)

    async def stream_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> AsyncIterator[str]:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("OpenAI API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": config.temperature,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
            async with client.stream("POST", f"{self.BASE_URL}/chat/completions", json=payload, headers=headers) as response:
                if response.status_code != 200:
                    await response.aread()
                    self._map_http_error(response)

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if chunk_str == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(chunk_str)
                            delta = chunk_data['choices'][0]['delta'].get('content', '')
                            if delta:
                                yield delta
                        except Exception:
                            continue

    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=128000
        )

    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        pricing = self.PRICING.get(model_id, self.PRICING["gpt-4o-mini"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal(1000000)) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal(1000000)) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._get_api_key()
        if not key:
            return False
        headers = {"Authorization": f"Bearer {key}"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self.BASE_URL}/models", headers=headers)
                return res.status_code == 200
        except Exception:
            return False
