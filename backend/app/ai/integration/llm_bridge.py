"""Bridge the app's real LLMClient to the app/ai LLMProvider protocol.

Lets the app/ai specialist agents run inside the live application driven by the user's
configured model (Anthropic key in .env, etc.) — the seam for swapping the legacy
pipeline onto the app/ai engine. The agent layer depends only on the LLMProvider
protocol, so this adapter is all that's needed.
"""
from __future__ import annotations

from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage
from app.core.llm_client import LLMClient


class LLMClientProvider:
    """Adapts core.LLMClient (.complete) to app/ai LLMProvider (.generate)."""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    @property
    def available(self) -> bool:
        return self._client.available

    def generate(self, request: LLMRequest) -> LLMResponse:
        prompt = "\n".join(m.content for m in request.messages)
        resp = self._client.complete(
            prompt, system=request.system, max_tokens=request.max_tokens
        )
        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=resp.text,
            usage=TokenUsage(
                prompt_tokens=getattr(usage, "prompt_tokens", 0),
                completion_tokens=getattr(usage, "completion_tokens", 0),
            ),
            model=getattr(resp, "model", ""),
        )
