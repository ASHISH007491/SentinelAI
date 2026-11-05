"""Token counting. Uses tiktoken when available, else a ~4 chars/token heuristic."""
from __future__ import annotations

from app.ai.models.messages import LLMRequest
from app.ai.utils.tokens import estimate_tokens


class TokenCounter:
    def __init__(self, model: str | None = None) -> None:
        self.model = model
        self._encoding = None
        try:  # optional precise counting
            import tiktoken

            try:
                self._encoding = (
                    tiktoken.encoding_for_model(model) if model
                    else tiktoken.get_encoding("cl100k_base")
                )
            except Exception:
                self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoding = None

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is not None:
            return len(self._encoding.encode(text))
        return estimate_tokens(text)

    def count_request(self, request: LLMRequest) -> int:
        total = self.count(request.system or "")
        for message in request.messages:
            total += self.count(message.content)
        return total
