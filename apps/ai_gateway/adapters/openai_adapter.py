"""
OpenAI Provider Adapter Implementation.
Supports GPT-4o, GPT-4o-mini, Structured Outputs, and accurate token cost calculations.
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


class OpenAIAdapter(BaseAIAdapter):
    provider_name: str = "openai"
    default_model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"

    PRICING = {
        "gpt-4o-mini": {"prompt": Decimal("0.15"), "completion": Decimal("0.60")},
        "gpt-4o": {"prompt": Decimal("2.50"), "completion": Decimal("10.00")},
    }

    def __init__(self, default_api_key: Optional[str] = None, http_client: Optional[httpx.Client] = None):
        key = default_api_key or getattr(settings, "OPENAI_API_KEY", "")
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
            err_code = body.get("error", {}).get("code", "")
        except Exception:
            err_msg = response.text
            err_code = ""

        if status == 429:
            raise AIProviderRateLimitError(f"OpenAI rate limit exceeded: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (401, 403):
            raise AIProviderAuthError(f"OpenAI authentication failed: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status == 400:
            if "context_length" in err_msg.lower() or "maximum context" in err_msg.lower():
                raise AIProviderContextLengthError(f"OpenAI context overflow: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            elif "content_filter" in err_msg.lower() or err_code == "content_filter":
                raise AIProviderContentFilterError(f"OpenAI safety filter triggered: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            raise AIProviderError(f"OpenAI bad request (400): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (500, 502, 503, 504):
            raise AIProviderServerError(f"OpenAI server error ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        else:
            raise AIProviderError(f"OpenAI unexpected status ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)

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
            raise AIProviderAuthError("OpenAI API key is missing.", provider=self.provider_name)

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
            raise AIProviderTimeoutError(f"OpenAI request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI connection error: {str(e)}", provider=self.provider_name, raw_error=e)

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
            cached_tokens=usage_data.get("prompt_tokens_details", {}).get("cached_tokens", 0),
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
            raise AIProviderAuthError("OpenAI API key is missing.", provider=self.provider_name)

        is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)
        json_schema = schema.model_json_schema() if is_pydantic else schema

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
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": getattr(schema, "__name__", "StructuredOutput"),
                    "strict": True,
                    "schema": json_schema,
                }
            }
        }

        client = self._get_client(timeout=cfg.timeout_seconds)
        try:
            resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"OpenAI request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI connection error: {str(e)}", provider=self.provider_name, raw_error=e)

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
            supports_vision=True,
            max_context_window=128000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["gpt-4o-mini"])
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
