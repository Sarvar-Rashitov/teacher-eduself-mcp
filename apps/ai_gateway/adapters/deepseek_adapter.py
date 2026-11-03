"""
DeepSeek Provider Adapter Implementation.
Supports DeepSeek-V3 (deepseek-chat) and DeepSeek-R1 reasoning (deepseek-reasoner)
with ultra-cost-effective pricing and reasoning extraction.
"""

import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type, TypeVar, Union
import httpx
from pydantic import BaseModel
from django.conf import settings
from ..base import (
    BaseAIAdapter,
    ModelConfig,
    ProviderCapabilities,
    TextResponse,
    TokenUsage,
    AIProviderAuthError,
    AIProviderContextLengthError,
    AIProviderContentFilterError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderError,
)

T = TypeVar("T", bound=BaseModel)


class DeepSeekAdapter(BaseAIAdapter):
    provider_name: str = "deepseek"
    default_model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"

    PRICING = {
        "deepseek-chat": {"prompt": Decimal("0.14"), "completion": Decimal("0.28")},
        "deepseek-reasoner": {"prompt": Decimal("0.55"), "completion": Decimal("2.19")},
    }

    def __init__(self, default_api_key: Optional[str] = None, http_client: Optional[httpx.Client] = None):
        key = default_api_key or getattr(settings, "DEEPSEEK_API_KEY", "")
        super().__init__(default_api_key=key)
        self._client = http_client

    def _get_client(self, timeout: float = 30.0) -> httpx.Client:
        if self._client:
            return self._client
        return httpx.Client(timeout=timeout)

    def _handle_http_error(self, response: httpx.Response, raw_error: Any = None):
        status = response.status_code
        try:
            body = response.json()
            err_msg = body.get("error", {}).get("message", response.text)
        except Exception:
            err_msg = response.text

        if status == 429:
            raise AIProviderRateLimitError(f"DeepSeek rate limit exceeded: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (401, 403):
            raise AIProviderAuthError(f"DeepSeek authentication failed: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status == 400:
            if "context" in err_msg.lower() or "too long" in err_msg.lower():
                raise AIProviderContextLengthError(f"DeepSeek context overflow: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            raise AIProviderError(f"DeepSeek bad request (400): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (500, 502, 503, 504):
            raise AIProviderServerError(f"DeepSeek server error ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        else:
            raise AIProviderError(f"DeepSeek unexpected status ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)

    def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
        model_id: Optional[str] = None
    ) -> TextResponse:
        cfg = config or ModelConfig()
        model = model_id or self.default_model
        api_key = self._resolve_api_key(cfg)

        if not api_key:
            raise AIProviderAuthError("DeepSeek API key is missing.", provider=self.provider_name)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "top_p": cfg.top_p,
        }

        start_time = time.perf_counter()
        client = self._get_client(timeout=cfg.timeout_seconds)

        try:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"DeepSeek request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"DeepSeek connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if resp.is_error:
            self._handle_http_error(resp)

        data = resp.json()
        choice = data["choices"][0]
        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
            cached_tokens=usage_data.get("prompt_cache_hit_tokens", 0),
        )

        return TextResponse(
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
            latency_ms=latency_ms,
            model_id=model,
            provider=self.provider_name,
        )

    def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Union[Type[T], Dict[str, Any]],
        config: Optional[ModelConfig] = None,
        model_id: Optional[str] = None
    ) -> Union[T, Dict[str, Any]]:
        cfg = config or ModelConfig()
        model = model_id or self.default_model
        api_key = self._resolve_api_key(cfg)

        if not api_key:
            raise AIProviderAuthError("DeepSeek API key is missing.", provider=self.provider_name)

        is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)
        json_schema = schema.model_json_schema() if is_pydantic else schema

        enriched_messages = list(messages)
        schema_instruction = f"\nYou MUST reply strictly with valid JSON conforming to this schema:\n{json.dumps(json_schema)}"
        if enriched_messages and enriched_messages[-1].get("role") == "user":
            enriched_messages[-1] = {
                "role": "user",
                "content": enriched_messages[-1]["content"] + schema_instruction
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": enriched_messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "top_p": cfg.top_p,
            "response_format": {"type": "json_object"},
        }

        client = self._get_client(timeout=cfg.timeout_seconds)

        try:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"DeepSeek request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"DeepSeek connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        if resp.is_error:
            self._handle_http_error(resp)

        raw_content = resp.json()["choices"][0]["message"]["content"]
        parsed_dict = json.loads(raw_content)

        if is_pydantic:
            return schema.model_validate(parsed_dict)
        return parsed_dict

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            max_context_window=64000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["deepseek-chat"])
        prompt_cost = (Decimal(usage.prompt_tokens) / Decimal(1_000_000)) * pricing["prompt"]
        completion_cost = (Decimal(usage.completion_tokens) / Decimal(1_000_000)) * pricing["completion"]
        return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))

    def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self.default_api_key
        if not key:
            return False
        headers = {"Authorization": f"Bearer {key}"}
        try:
            client = self._get_client(timeout=5.0)
            resp = client.get(f"{self.base_url}/models", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False
