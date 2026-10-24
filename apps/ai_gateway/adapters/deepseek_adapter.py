import os
from decimal import Decimal
from typing import Optional
from .openai_adapter import OpenAIAdapter
from ..base import ProviderCapabilities, TokenUsage


class DeepSeekAdapter(OpenAIAdapter):
    """
    DeepSeek Provider Adapter (DeepSeek-V3, DeepSeek-R1).
    Implements DOC-67 with ultra-low cost ($0.14/1M input) and open chain-of-thought reasoning.
    Uses OpenAI-compatible protocol.
    """

    provider_name = "deepseek"
    default_model = "deepseek-chat"
    base_url = "https://api.deepseek.com/v1"

    PRICING = {
        "deepseek-chat": {"input": Decimal("0.14"), "output": Decimal("0.28")},
        "deepseek-reasoner": {"input": Decimal("0.55"), "output": Decimal("2.19")},
    }

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""))

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
        input_cost = (Decimal(usage.prompt_tokens) / Decimal("1000000")) * pricing["input"]
        output_cost = (Decimal(usage.completion_tokens) / Decimal("1000000")) * pricing["output"]
        return round(input_cost + output_cost, 6)
