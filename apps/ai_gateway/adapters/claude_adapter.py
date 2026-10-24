import json
import os
import time
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, List, Optional
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


class ClaudeAdapter(BaseAIProviderAdapter):
    """
    Anthropic Claude Provider Adapter (Claude 3.5 Sonnet, Haiku).
    Implements DOC-67 and DOC-68 with high pedagogical reasoning and tool-based structure.
    """

    provider_name = "claude"
    default_model = "claude-3-5-sonnet-20241022"
    base_url = "https://api.anthropic.com/v1"

    PRICING = {
        "claude-3-5-sonnet-20241022": {"input": Decimal("3.00"), "output": Decimal("15.00")},
        "claude-3-5-haiku-20241022": {"input": Decimal("0.80"), "output": Decimal("4.00")},
    }

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        return self._api_key

    def _map_http_error(self, status_code: int, error_data: Dict[str, Any]) -> AIProviderError:
        err = error_data.get("error", {})
        err_type = err.get("type", "")
        msg = err.get("message", "Claude API Error")

        if status_code in (401, 403) or err_type == "authentication_error":
            return AIProviderAuthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code == 429 or err_type == "rate_limit_error":
            return AIProviderRateLimitError(msg, provider=self.provider_name, status_code=status_code)
        if "prompt is too long" in msg.lower() or "context length" in msg.lower():
            return AIProviderContextLengthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code >= 500 or err_type == "api_error":
            return AIProviderServerError(msg, provider=self.provider_name, status_code=status_code)
        return AIProviderError(msg, provider=self.provider_name, status_code=status_code)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple[Optional[str], List[Dict[str, str]]]:
        system_prompt = None
        filtered = []
        for m in messages:
            if m.get("role") == "system":
                system_prompt = m.get("content", "")
            else:
                filtered.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        return system_prompt, filtered

    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        cfg = config or ModelConfig(model_name=self.default_model)
        model = cfg.model_name or self.default_model
        api_key = self._get_api_key(cfg)

        system_prompt, formatted_msgs = self._convert_messages(messages)
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": formatted_msgs,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude request timed out: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude network error: {e}", provider=self.provider_name) from e

        latency_ms = int((time.time() - start_time) * 1000)

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.json() if resp.headers.get("content-type") == "application/json" else {"error": {"message": resp.text}})

        data = resp.json()
        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        raw_usage = data.get("usage", {})

        usage = TokenUsage(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
        )

        return TextResponse(
            content=text,
            finish_reason=data.get("stop_reason", "end_turn"),
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

        system_prompt, formatted_msgs = self._convert_messages(messages)
        json_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema

        # Tool-based structured output (Claude Tool Use)
        tool_def = {
            "name": "emit_structured_data",
            "description": "Outputs validated structured educational data",
            "input_schema": json_schema,
        }

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": model,
            "messages": formatted_msgs,
            "max_tokens": cfg.max_tokens,
            "tools": [tool_def],
            "tool_choice": {"type": "tool", "name": "emit_structured_data"},
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude timeout: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude connection error: {e}", provider=self.provider_name) from e

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.json() if resp.headers.get("content-type") == "application/json" else {"error": {"message": resp.text}})

        data = resp.json()
        tool_calls = [b for b in data.get("content", []) if b.get("type") == "tool_use"]
        if not tool_calls:
            # Fallback to text parsing
            raw_text = "".join(b.get("text", "") for b in data.get("content", []))
            parsed = json.loads(raw_text)
        else:
            parsed = tool_calls[0].get("input", {})

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)
        return parsed

    async def stream_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        resp = await self.generate_text(messages, config)
        yield resp.content

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=200000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["claude-3-5-sonnet-20241022"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal("1000000")) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._api_key
        return bool(key)
