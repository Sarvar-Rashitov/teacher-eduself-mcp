import json
import os
import time
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, List, Optional, Type
import httpx
from pydantic import BaseModel

from ..base import (
    BaseAIProviderAdapter,
    ModelConfig,
    ProviderCapabilities,
    TextResponse,
    TokenUsage,
    AIProviderAuthError,
    AIProviderContextLengthError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
)


class OpenAIAdapter(BaseAIProviderAdapter):
    """
    OpenAI Provider Adapter (GPT-4o, GPT-4o-mini).
    Implements DOC-67 (AI_PROVIDERS.md) and DOC-68 (AI_ADAPTERS.md).
    """

    provider_name = "openai"
    default_model = "gpt-4o-mini"
    base_url = "https://api.openai.com/v1"

    # Pricing per 1M tokens in USD (DOC-76)
    PRICING = {
        "gpt-4o-mini": {"input": Decimal("0.15"), "output": Decimal("0.60")},
        "gpt-4o": {"input": Decimal("2.50"), "output": Decimal("10.00")},
    }

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        return self._api_key

    def _map_http_error(self, status_code: int, error_data: Dict[str, Any]) -> AIProviderError:
        msg = error_data.get("error", {}).get("message", "OpenAI API Error")
        if status_code in (401, 403):
            return AIProviderAuthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code == 429:
            return AIProviderRateLimitError(msg, provider=self.provider_name, status_code=status_code)
        if "context_length_exceeded" in msg or "maximum context length" in msg:
            return AIProviderContextLengthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code >= 500:
            return AIProviderServerError(msg, provider=self.provider_name, status_code=status_code)
        return AIProviderError(msg, provider=self.provider_name, status_code=status_code)

    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        cfg = config or ModelConfig(model_name=self.default_model)
        model = cfg.model_name or self.default_model
        api_key = self._get_api_key(cfg)

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

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"OpenAI request timed out after {cfg.timeout_seconds}s", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI connection error: {e}", provider=self.provider_name) from e

        latency_ms = int((time.time() - start_time) * 1000)

        if resp.status_code != 200:
            try:
                err_data = resp.json()
            except Exception:
                err_data = {"error": {"message": resp.text}}
            raise self._map_http_error(resp.status_code, err_data)

        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"]["content"]
        raw_usage = data.get("usage", {})

        usage = TokenUsage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
            cached_tokens=raw_usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
        )

        return TextResponse(
            content=content,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
            latency_ms=latency_ms,
            model=model,
            provider=self.provider_name,
            raw_response=data,
        )

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Any,
        config: Optional[ModelConfig] = None,
    ) -> Any:
        cfg = config or ModelConfig(model_name=self.default_model)
        model = cfg.model_name or self.default_model
        api_key = self._get_api_key(cfg)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Convert Pydantic or dict schema to JSON schema
        json_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema
        payload = {
            "model": model,
            "messages": messages,
            "temperature": cfg.temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_output",
                    "strict": True,
                    "schema": json_schema,
                },
            },
        }

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"OpenAI request timed out: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"OpenAI network error: {e}", provider=self.provider_name) from e

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.json() if resp.headers.get("content-type") == "application/json" else {"error": {"message": resp.text}})

        data = resp.json()
        raw_text = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw_text)

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)
        return parsed

    async def stream_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        cfg = config or ModelConfig(model_name=self.default_model)
        model = cfg.model_name or self.default_model
        api_key = self._get_api_key(cfg)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": cfg.temperature,
        }

        async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    raise self._map_http_error(response.status_code, {"error": {"message": err_body.decode()}})

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                yield delta
                        except Exception:
                            continue

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        model = model_id or self.default_model
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
        input_cost = (Decimal(usage.prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal("1000000")) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._api_key
        if not key:
            return False
        headers = {"Authorization": f"Bearer {key}"}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=headers)
                return resp.status_code == 200
        except Exception:
            return False
