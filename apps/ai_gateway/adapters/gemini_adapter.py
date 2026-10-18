"""
Google Gemini Provider Adapter Implementation.
Supports Gemini 1.5 Pro and Gemini 1.5 Flash with 1M+ context window and JSON output mode.
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


class GeminiAdapter(BaseAIAdapter):
    provider_name: str = "gemini"
    default_model: str = "gemini-1.5-flash"
    base_url: str = "https://generativelanguage.googleapis.com/v1beta/models"

    PRICING = {
        "gemini-1.5-flash": {"prompt": Decimal("0.075"), "completion": Decimal("0.30")},
        "gemini-1.5-pro": {"prompt": Decimal("1.25"), "completion": Decimal("5.00")},
    }

    def __init__(self, default_api_key: Optional[str] = None, http_client: Optional[httpx.Client] = None):
        key = default_api_key or getattr(settings, "GEMINI_API_KEY", "")
        super().__init__(default_api_key=key)
        self._client = http_client

    def _get_client(self, timeout: float = 30.0) -> httpx.Client:
        if self._client:
            return self._client
        return httpx.Client(timeout=timeout)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Converts OpenAI message format [{'role': 'user', 'content': '...'}] to Gemini contents."""
        gemini_contents = []
        for msg in messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            content = msg.get("content", "")
            gemini_contents.append({
                "role": role,
                "parts": [{"text": content}]
            })
        return gemini_contents

    def _handle_http_error(self, response: httpx.Response, raw_error: Any = None):
        status = response.status_code
        try:
            body = response.json()
            err_obj = body.get("error", {})
            err_msg = err_obj.get("message", response.text)
            err_status = err_obj.get("status", "")
        except Exception:
            err_msg = response.text
            err_status = ""

        if status == 429 or err_status == "RESOURCE_EXHAUSTED":
            raise AIProviderRateLimitError(f"Gemini rate limit exceeded: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (401, 403) or "API_KEY_INVALID" in err_msg or err_status == "PERMISSION_DENIED":
            raise AIProviderAuthError(f"Gemini authentication failed: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status == 400:
            if "context" in err_msg.lower() or "too long" in err_msg.lower():
                raise AIProviderContextLengthError(f"Gemini context overflow: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            elif "safety" in err_msg.lower() or "blocked" in err_msg.lower():
                raise AIProviderContentFilterError(f"Gemini content blocked: {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
            raise AIProviderError(f"Gemini bad request (400): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        elif status in (500, 502, 503, 504):
            raise AIProviderServerError(f"Gemini server error ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)
        else:
            raise AIProviderError(f"Gemini unexpected status ({status}): {err_msg}", provider=self.provider_name, status_code=status, raw_error=raw_error)

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
            raise AIProviderAuthError("Gemini API key is missing.", provider=self.provider_name)

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": self._convert_messages(messages),
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "topP": cfg.top_p,
            }
        }

        start_time = time.perf_counter()
        client = self._get_client(timeout=cfg.timeout_seconds)
        url = f"{self.base_url}/{model}:generateContent"

        try:
            resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        if resp.is_error:
            self._handle_http_error(resp)

        data = resp.json()
        candidate = data.get("candidates", [{}])[0]
        content_text = ""
        parts = candidate.get("content", {}).get("parts", [])
        if parts:
            content_text = parts[0].get("text", "")

        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        return TextResponse(
            content=content_text,
            finish_reason=candidate.get("finishReason", "STOP"),
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
            raise AIProviderAuthError("Gemini API key is missing.", provider=self.provider_name)

        is_pydantic = isinstance(schema, type) and issubclass(schema, BaseModel)

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": self._convert_messages(messages),
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "topP": cfg.top_p,
                "responseMimeType": "application/json",
            }
        }

        client = self._get_client(timeout=cfg.timeout_seconds)
        url = f"{self.base_url}/{model}:generateContent"

        try:
            resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini request timed out: {str(e)}", provider=self.provider_name, raw_error=e)
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini connection error: {str(e)}", provider=self.provider_name, raw_error=e)

        if resp.is_error:
            self._handle_http_error(resp)

        raw_parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        raw_text = raw_parts[0].get("text", "{}") if raw_parts else "{}"
        parsed_dict = json.loads(raw_text)

        if is_pydantic:
            return schema.model_validate(parsed_dict)
        return parsed_dict

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=1000000,  # 1M context window
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["gemini-1.5-flash"])
        prompt_cost = (Decimal(usage.prompt_tokens) / Decimal(1_000_000)) * pricing["prompt"]
        completion_cost = (Decimal(usage.completion_tokens) / Decimal(1_000_000)) * pricing["completion"]
        return (prompt_cost + completion_cost).quantize(Decimal("0.000001"))

    def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self.default_api_key
        if not key:
            return False
        headers = {"x-goog-api-key": key}
        try:
            client = self._get_client(timeout=5.0)
            resp = client.get("https://generativelanguage.googleapis.com/v1beta/models", headers=headers)
            return resp.status_code == 200
        except Exception:
            return False
