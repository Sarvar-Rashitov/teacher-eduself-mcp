"""
Anthropic Claude Provider Adapter Implementation.
Supports Claude 3.5 Sonnet and Haiku with Tool-based structured output extraction and reasoning.
"""

import json
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union
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


class ClaudeAdapter(BaseAIAdapter):
    provider_name: str = "claude"
    default_model: str = "claude-3-5-sonnet"
    base_url: str = "https://api.anthropic.com/v1"
    anthropic_version: str = "2023-06-01"

    PRICING = {
        "claude-3-5-haiku": {"prompt": Decimal("0.80"), "completion": Decimal("4.00")},
        "claude-3-5-sonnet": {"prompt": Decimal("3.00"), "completion": Decimal("15.00")},
    }

    def __init__(self, default_api_key: Optional[str] = None, http_client: Optional[httpx.Client] = None):
        key = default_api_key or getattr(settings, "ANTHROPIC_API_KEY", "")
        super().__init__(default_api_key=key)
        self._client = http_client

    def _get_client(self, timeout: float = 30.0) -> httpx.Client:
        if self._client:
            return self._client
        return httpx.Client(timeout=timeout)

    def _split_system_messages(self, messages: List[Dict[str, str]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
        """Anthropic separates top-level system prompt from user/assistant messages."""
        system_parts = []
        chat_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            else:
                chat_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        return system_prompt, chat_messages

    def _handle_http_error(self, response: httpx.Response, raw_error: Any = None):
        status = response.status_code
        try:
            body = response.json()
            err_obj = body.get("error", {})
            err_msg = err_obj.get("message", response.text)
            err_type = err_obj.get("type", "")
        except Exception:
            err_msg = response.text
            err_type = ""

        if status == 429 or err_type == "rate_limit_error":
            raise AIProviderRateLimitError(f"Claude rate limit exceeded: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (401, 403) or err_type == "authentication_error":
            raise AIProviderAuthError(f"Claude authentication failed: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status == 400:
            if "prompt is too long" in err_msg.lower() or "context" in err_msg.lower():
                raise AIProviderContextLengthError(f"Claude context overflow: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            raise AIProviderError(f"Claude bad request (400): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (500, 502, 503, 504, 529):
            raise AIProviderServerError(f"Claude server error ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        else:
            raise AIProviderError(f"Claude unexpected status ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)

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
            raise AIProviderAuthError("Claude API key is missing.", provider=self.provider_name)

        system_prompt, chat_msgs = self._split_system_messages(messages)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": chat_msgs,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
        }
        if system_prompt:
            payload["system"] = system_prompt

        start_time = time.perf_counter()
        client = self._get_client(timeout=cfg.timeout_seconds)

        try:
            resp = client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if resp.is_error:
            self._handle_http_error(resp)

        data = resp.json()
        content_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content_text += block.get("text", "")

        usage_data = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_data.get("input_tokens", 0),
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
        )

        return TextResponse(
            content=content_text,
            finish_reason=data.get("stop_reason", "end_turn"),
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
            raise AIProviderAuthError("Claude API key is missing.", provider=self.provider_name)

        is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)
        json_schema = schema.model_json_schema() if is_pydantic else schema
        tool_name = "emit_structured_output"

        system_prompt, chat_msgs = self._split_system_messages(messages)

        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": chat_msgs,
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
            "top_p": cfg.top_p,
            "tools": [{
                "name": tool_name,
                "description": "Structured JSON schema output extraction",
                "input_schema": json_schema,
            }],
            "tool_choice": {"type": "tool", "name": tool_name},
        }
        if system_prompt:
            payload["system"] = system_prompt

        client = self._get_client(timeout=cfg.timeout_seconds)

        try:
            resp = client.post(f"{self.base_url}/messages", headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Claude request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Claude connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        if resp.is_error:
            self._handle_http_error(resp)

        data = resp.json()
        tool_input: Dict[str, Any] = {}
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool_name:
                tool_input = block.get("input", {})
                break

        if is_pydantic:
            return schema.model_validate(tool_input)
        return tool_input

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=200000,  # 200K tokens
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["claude-3-5-sonnet"])
        prompt_cost = (Decimal(usage.prompt_tokens) / Decimal(1_000_000)) * pricing["prompt"]
        completion_cost = (Decimal(usage.completion_tokens) / Decimal(1_000_000)) * pricing["completion"]
        return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))

    def health_check(self, api_key: Optional[str] = None) -> bool:
        # Anthropic doesn't have a simple GET /models without auth; send minimal ping
        key = api_key or self.default_api_key
        if not key:
            return False
        headers = {
            "x-api-key": key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        try:
            client = self._get_client(timeout=5.0)
            resp = client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json={
                    "model": "claude-3-5-haiku",
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                }
            )
            return resp.status_code == 200
        except Exception:
            return False
