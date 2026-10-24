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


class GeminiAdapter(BaseAIProviderAdapter):
    """
    Google Gemini Provider Adapter (Gemini 1.5 Pro, Flash).
    Implements DOC-67 and DOC-68 with 1M-2M token massive context window.
    """

    provider_name = "gemini"
    default_model = "gemini-1.5-flash"
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    PRICING = {
        "gemini-1.5-flash": {"input": Decimal("0.075"), "output": Decimal("0.30")},
        "gemini-1.5-pro": {"input": Decimal("1.25"), "output": Decimal("5.00")},
    }

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", "")

    def _get_api_key(self, config: Optional[ModelConfig] = None) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        return self._api_key

    def _map_http_error(self, status_code: int, error_data: Dict[str, Any]) -> AIProviderError:
        err = error_data.get("error", {})
        msg = err.get("message", "Gemini API Error")
        status_str = err.get("status", "")

        if status_code in (401, 403) or status_str in ("PERMISSION_DENIED", "UNAUTHENTICATED"):
            return AIProviderAuthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code == 429 or status_str == "RESOURCE_EXHAUSTED":
            return AIProviderRateLimitError(msg, provider=self.provider_name, status_code=status_code)
        if "context" in msg.lower() or "token limit" in msg.lower():
            return AIProviderContextLengthError(msg, provider=self.provider_name, status_code=status_code)
        if status_code >= 500:
            return AIProviderServerError(msg, provider=self.provider_name, status_code=status_code)
        return AIProviderError(msg, provider=self.provider_name, status_code=status_code)

    def _convert_messages(self, messages: List[Dict[str, str]]) -> tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        system_instruction = None
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": content}]})
        return system_instruction, contents

    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        cfg = config or ModelConfig(model_name=self.default_model)
        model = cfg.model_name or self.default_model
        api_key = self._get_api_key(cfg)

        system_instruction, contents = self._convert_messages(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "topP": cfg.top_p,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        url = f"{self.base_url}/{model}:generateContent"

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini request timed out: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini network error: {e}", provider=self.provider_name) from e

        latency_ms = int((time.time() - start_time) * 1000)

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.json() if resp.headers.get("content-type") == "application/json" else {"error": {"message": resp.text}})

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise AIProviderError("Gemini returned empty candidates", provider=self.provider_name)

        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        usage_meta = data.get("usageMetadata", {})

        usage = TokenUsage(
            prompt_tokens=usage_meta.get("promptTokenCount", 0),
            completion_tokens=usage_meta.get("candidatesTokenCount", 0),
            total_tokens=usage_meta.get("totalTokenCount", 0),
        )

        return TextResponse(
            content=text,
            finish_reason=candidates[0].get("finishReason", "STOP").lower(),
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

        system_instruction, contents = self._convert_messages(messages)
        json_schema = schema.model_json_schema() if hasattr(schema, "model_json_schema") else schema

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = system_instruction

        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        url = f"{self.base_url}/{model}:generateContent"

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as e:
            raise AIProviderTimeoutError(f"Gemini timeout: {e}", provider=self.provider_name) from e
        except httpx.RequestError as e:
            raise AIProviderServerError(f"Gemini connection error: {e}", provider=self.provider_name) from e

        if resp.status_code != 200:
            raise self._map_http_error(resp.status_code, resp.json() if resp.headers.get("content-type") == "application/json" else {"error": {"message": resp.text}})

        data = resp.json()
        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(raw_text)

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)
        return parsed

    async def stream_text(
        self,
        messages: List[Dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        # For simplicity and uniform streaming interface, yield text
        resp = await self.generate_text(messages, config)
        yield resp.content

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=True,
            max_context_window=1000000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["gemini-1.5-flash"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal("1000000")) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self, api_key: Optional[str] = None) -> bool:
        key = api_key or self._api_key
        if not key:
            return False
        url = f"{self.base_url}?key={key}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                return resp.status_code == 200
        except Exception:
            return False
