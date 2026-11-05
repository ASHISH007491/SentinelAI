"""Cost tracking with a per-model price table (USD per 1K tokens)."""
from __future__ import annotations

from threading import Lock

from app.ai.models.messages import TokenUsage

# (input_per_1k, output_per_1k). Local models (Ollama) are free. Extend as needed.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.0025, 0.01),
    "gpt-4o-mini": (0.00015, 0.0006),
    "claude-sonnet-4-6": (0.003, 0.015),
    "llama-3.1-8b-instant": (0.0, 0.0),
}


class CostTracker:
    def __init__(self, prices: dict[str, tuple[float, float]] | None = None) -> None:
        self.prices = prices or dict(DEFAULT_PRICES)
        self._lock = Lock()
        self.total_cost = 0.0
        self.by_model: dict[str, float] = {}

    def price_of(self, model: str, usage: TokenUsage) -> float:
        rate_in, rate_out = self.prices.get(model, (0.0, 0.0))
        return (usage.prompt_tokens / 1000) * rate_in + (usage.completion_tokens / 1000) * rate_out

    def record(self, model: str, usage: TokenUsage) -> float:
        cost = self.price_of(model, usage)
        with self._lock:
            self.total_cost += cost
            self.by_model[model] = self.by_model.get(model, 0.0) + cost
        return cost
