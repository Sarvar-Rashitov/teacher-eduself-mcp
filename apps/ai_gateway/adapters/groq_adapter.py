import os
import time
import json
from decimal import Decimal
from typing import AsyncIterator, Type, Optional, Any
import httpx

from apps.ai_gateway.base import (
    BaseAIAdapter,
    ModelConfig,
    TokenUsage,
    TextResponse,
    ProviderCapabilities,
    T,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderServerError,
    AIProviderTimeoutError,
    AIProviderContextLengthError,
    AIProviderContentFilterError,
    AIProviderError,
)


class GroqAdapter(BaseAIAdapter):
    provider_name = "groq"
    default_model = "llama-3.3-70b-versatile"
    ACTIVE_FALLBACK_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

    PRICING_PER_1M = {
        "llama-3.3-70b-versatile": {"input": Decimal("0.59"), "output": Decimal("0.79")},
        "mixtral-8x7b-32768": {"input": Decimal("0.24"), "output": Decimal("0.24")},
        "openai/gpt-oss-120b": {"input": Decimal("0.15"), "output": Decimal("0.60")},
        "openai/gpt-oss-20b": {"input": Decimal("0.075"), "output": Decimal("0.30")},
        "qwen/qwen3.8-27b": {"input": Decimal("0.80"), "output": Decimal("4.00")},
    }

    def __init__(self, api_key: Optional[str] = None, http_client: Optional[httpx.AsyncClient] = None):
        self._default_api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self._http_client = http_client

    def _get_api_key(self, config: Optional[ModelConfig]) -> str:
        if config and config.api_key_override:
            return config.api_key_override
        return self._default_api_key

    def _map_http_error(self, exc: Exception) -> AIProviderError:
        if isinstance(exc, httpx.TimeoutException):
            return AIProviderTimeoutError("Groq request timed out", provider=self.provider_name)
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            text = exc.response.text
            if status in (401, 403):
                return AIProviderAuthError(f"Groq Auth failed: {text}", provider=self.provider_name, status_code=status)
            elif status == 429:
                return AIProviderRateLimitError(f"Groq Rate limit exceeded: {text}", provider=self.provider_name, status_code=status)
            elif status >= 500:
                return AIProviderServerError(f"Groq Server error: {text}", provider=self.provider_name, status_code=status)
            return AIProviderError(f"Groq Error ({status}): {text}", provider=self.provider_name, status_code=status)
        return AIProviderError(str(exc), provider=self.provider_name)

    async def _post_chat_completion(
        self,
        client: httpx.AsyncClient,
        payload: dict[str, Any],
        headers: dict[str, str],
        initial_model: str,
    ) -> tuple[dict[str, Any], str]:
        models_to_try = [initial_model]
        if self._http_client is None:
            if initial_model in ("llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"):
                models_to_try = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
            else:
                for fallback in self.ACTIVE_FALLBACK_MODELS:
                    if fallback not in models_to_try:
                        models_to_try.append(fallback)

        last_error = None
        for current_model in models_to_try:
            payload["model"] = current_model
            try:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json(), current_model
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 404) and any(
                    sig in e.response.text for sig in ["decommissioned", "model_not_found", "does not exist"]
                ):
                    last_error = e
                    continue
                raise e
            except Exception as e:
                raise e
        raise last_error or httpx.HTTPStatusError("All models failed", request=None, response=None)

    async def generate_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> TextResponse:
        cfg = config or ModelConfig()
        model = cfg.model_override or self.default_model
        api_key = self._get_api_key(cfg)

        payload = {
            "model": model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        start_time = time.perf_counter()
        try:
            client = self._http_client or httpx.AsyncClient(timeout=cfg.timeout_seconds)
            try:
                data, used_model = await self._post_chat_completion(client, payload, headers, model)
            finally:
                if self._http_client is None:
                    await client.aclose()
        except Exception as e:
            raise self._map_http_error(e)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        choice = data["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice.get("finish_reason", "stop")

        usage_raw = data.get("usage", {})
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )

        return TextResponse(
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=latency_ms,
            model_id=used_model,
            provider=self.provider_name,
        )

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: Type[T],
        config: Optional[ModelConfig] = None,
    ) -> T:
        cfg = config or ModelConfig()
        model = cfg.model_override or self.default_model
        api_key = self._get_api_key(cfg)

        schema_json = json.dumps(schema.model_json_schema())
        has_schema_instruction = any("conforming to this schema" in m.get("content", "") for m in messages)
        adapted_messages = list(messages)
        if not has_schema_instruction:
            adapted_messages.append({
                "role": "user",
                "content": f"Return strictly valid JSON conforming to this schema:\n{schema_json}",
            })

        payload = {
            "model": model,
            "messages": adapted_messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            client = self._http_client or httpx.AsyncClient(timeout=cfg.timeout_seconds)
            try:
                data, _ = await self._post_chat_completion(client, payload, headers, model)
            finally:
                if self._http_client is None:
                    await client.aclose()
        except Exception as e:
            raise self._map_http_error(e)

        content = data["choices"][0]["message"]["content"]
        return schema.model_validate_json(content)

    async def stream_text(
        self,
        messages: list[dict[str, str]],
        config: Optional[ModelConfig] = None,
    ) -> AsyncIterator[str]:
        res = await self.generate_text(messages, config)
        yield res.content

    def get_capabilities(self, model_id: str) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            max_context_window=128000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: str) -> Decimal:
        pricing = self.PRICING_PER_1M.get(model_id, self.PRICING_PER_1M["llama-3.3-70b-versatile"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal(1_000_000)) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal(1_000_000)) * pricing["output"]
        return round(input_cost + output_cost, 6)

    async def health_check(self) -> bool:
        if not self._default_api_key:
            return False
        try:
            res = await self.generate_text([{"role": "user", "content": "ping"}], ModelConfig(max_tokens=5, timeout_seconds=5.0))
            return bool(res.content)
        except Exception:
            return False
