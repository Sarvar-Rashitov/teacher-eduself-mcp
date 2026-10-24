import os
from decimal import Decimal
from typing import Optional
from .openai_adapter import OpenAIAdapter
from ..base import ProviderCapabilities, TokenUsage


class GroqAdapter(OpenAIAdapter):
    """
    Groq LPU Provider Adapter (Llama 3.3 70B, Mixtral).
    Implements DOC-67 with ultra-fast inference (>300 tokens/sec) for live interactive classroom quizzes.
    Uses OpenAI-compatible protocol.
    """

    provider_name = "groq"
    default_model = "llama-3.3-70b-versatile"
    base_url = "https://api.groq.com/openai/v1"

    PRICING = {
        "llama-3.3-70b-versatile": {"input": Decimal("0.59"), "output": Decimal("0.79")},
        "mixtral-8x7b-32768": {"input": Decimal("0.24"), "output": Decimal("0.24")},
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key or os.getenv("GROQ_API_KEY", ""))

    def get_capabilities(self, model_id: Optional[str] = None) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_outputs=True,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
            max_context_window=128000,
        )

    def estimate_cost(self, usage: TokenUsage, model_id: Optional[str] = None) -> Decimal:
        model = model_id or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["llama-3.3-70b-versatile"])
        input_cost = (Decimal(usage.prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal("1000000")) * pricing["output"]
        return round(input_cost + output_cost, 6)
