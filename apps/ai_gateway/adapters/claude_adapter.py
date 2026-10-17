"""
Anthropic Claude Provider Adapter.
Spetsifikatsiya: .docs/ai/AI_PROVIDERS.md (2.3-bo'lim) & AI_ADAPTERS.md
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


class ClaudeAdapter(BaseAIAdapter):
    provider_name = "claude"
    BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    API_VERSION = "2023-06-01"

    PRICING = {
        "claude-3-5-haiku-20241022": {"input": Decimal("0.80"), "output": Decimal("4.00")},
        "claude-3-5-sonnet-20241022": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    }

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        key = getattr(settings, 'ANTHROPIC_API_KEY', '')
        return key.strip() if key else ""

    def _map_http_error(self, response: httpx.Response):
        code = response.status_code
        try:
            err_data = response.json().get('error', {})
            msg = err_data.get('message', response.text)
        except Exception:
            msg = response.text

        if code == 429:
            raise AIProviderRateLimitError(f"Claude Rate Limit: {msg}", provider=self.provider_name, status_code=code)
        elif code in (401, 403):
            raise AIProviderAuthError(f"Claude Auth Xatosi: {msg}", provider=self.provider_name, status_code=code)
        elif code in (500, 502, 503, 504):
            raise AIProviderServerError(f"Claude Server Xatosi: {msg}", provider=self.provider_name, status_code=code)
        else:
            raise AIProviderError(f"Claude API Xatosi ({code}): {msg}", provider=self.provider_name, status_code=code)

    async def generate_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> TextResponse:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("Claude API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        # Anthropic 'system' xabarini alohida parametr sifatida talab qiladi
        system_prompt = ""
        user_messages = []
        for m in messages:
            if m.get('role') == 'system':
                system_prompt += m.get('content', '') + "\n"
            else:
                user_messages.append({"role": m.get('role', 'user'), "content": m.get('content', '')})

        payload: Dict = {
            "model": model,
            "messages": user_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if system_prompt.strip():
            payload["system"] = system_prompt.strip()

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json"
        }

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(f"{self.BASE_URL}/messages", json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        latency_ms = int((time.time() - start_time) * 1000)
        data = res.json()
        content_text = ""
        for block in data.get('content', []):
            if block.get('type') == 'text':
                content_text += block.get('text', '')

        usage_data = data.get('usage', {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get('input_tokens', 0),
            completion_tokens=usage_data.get('output_tokens', 0),
            total_tokens=usage_data.get('input_tokens', 0) + usage_data.get('output_tokens', 0),
        )

        return TextResponse(
            content=content_text,
            finish_reason=data.get('stop_reason', 'end_turn'),
            usage=usage,
            latency_ms=latency_ms,
            model_name=model
        )

    async def generate_structured(
        self, messages: List[Dict[str, str]], schema: Type[T], config: ModelConfig
    ) -> T:
        api_key = self._get_api_key(config)
        if not api_key:
            raise AIProviderAuthError("Claude API kalit topilmadi.", provider=self.provider_name)

        model = config.model_name or self.DEFAULT_MODEL
        tool_name = schema.__name__.lower()
        schema_dict = schema.model_json_schema()

        # Claude Tool Calling orqali strukturali JSON qaytarish
        tools = [{
            "name": tool_name,
            "description": f"Output structured {schema.__name__}",
            "input_schema": schema_dict
        }]

        user_messages = [
            {"role": m.get('role', 'user'), "content": m.get('content', '')}
            for m in messages if m.get('role') != 'system'
        ]

        payload = {
            "model": model,
            "messages": user_messages,
            "max_tokens": config.max_tokens,
            "tools": tools,
            "tool_choice": {"type": "tool", "name": tool_name}
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
                res = await client.post(f"{self.BASE_URL}/messages", json=payload, headers=headers)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude so'rov vaqti tugadi: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude ulanish xatosi: {e}", provider=self.provider_name) from e

        if res.status_code != 200:
            self._map_http_error(res)

        data = res.json()
        tool_input = {}
        for block in data.get('content', []):
            if block.get('type') == 'tool_use' and block.get('name') == tool_name:
                tool_input = block.get('input', {})
                break

        return schema.model_validate(tool_input)

    async def stream_text(
        self, messages: List[Dict[str, str]], config: ModelConfig
    ) -> AsyncIterator[str]:
        res = await self.generate_text(messages, config)
        yield res.content

    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=200000
        )

    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        pricing = self.PRICING.get(model_id, self.PRICING["claude-3-5-sonnet-20241022"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal(1000000)) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal(1000000)) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._get_api_key()
        if not key:
            return False
        # Minimal 1-token test
        headers = {
            "x-api-key": key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json"
        }
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(f"{self.BASE_URL}/messages", json=payload, headers=headers)
                return res.status_code == 200
        except Exception:
            return False
