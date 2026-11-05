"""LLM providers implementing the platform LLMProvider contract.

OpenAIProvider and OllamaProvider both speak the OpenAI chat-completions API
(Ollama exposes an OpenAI-compatible endpoint at /v1), so they share one
implementation with different defaults. OfflineProvider is a deterministic,
network-free provider used as the safe default and in tests.
"""
from __future__ import annotations

from collections.abc import Iterator

from app.ai.core.errors import LLMError
from app.ai.core.logging import get_logger
from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage

logger = get_logger(__name__)


class OfflineProvider:
    """Deterministic provider: echoes the last user message. No network, always available."""

    name = "offline"

    def __init__(self, model: str = "offline") -> None:
        self.model = model

    @property
    def available(self) -> bool:
        return True

    def _echo(self, request: LLMRequest) -> str:
        last = next((m.content for m in reversed(request.messages) if m.role.value == "user"), "")
        return f"(offline:{request.model or self.model}) {last}".strip()

    def generate(self, request: LLMRequest) -> LLMResponse:
        text = self._echo(request)
        return LLMResponse(text=text, model=request.model or self.model, usage=TokenUsage())

    def stream(self, request: LLMRequest) -> Iterator[str]:
        for word in self._echo(request).split(" "):
            yield word + " "


class OpenAIProvider:
    """Calls an OpenAI-compatible chat-completions endpoint via the openai SDK."""

    name = "openai"
    default_base_url: str | None = None  # SDK default (https://api.openai.com/v1)

    def __init__(self, model: str, *, api_key: str = "", base_url: str | None = None) -> None:
        self.model = model
        self.base_url = base_url or self.default_base_url
        self._client = None
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key or "not-needed", base_url=self.base_url)
        except Exception as exc:  # SDK missing
            logger.warning("%s unavailable (%s)", self.name, exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _messages(self, request: LLMRequest) -> list[dict]:
        msgs: list[dict] = []
        if request.system:
            msgs.append({"role": "system", "content": request.system})
        msgs += [{"role": m.role.value, "content": m.content} for m in request.messages]
        return msgs

    def generate(self, request: LLMRequest) -> LLMResponse:
        if not self._client:
            raise LLMError(f"{self.name} provider not available")
        resp = self._client.chat.completions.create(
            model=request.model or self.model,
            messages=self._messages(request),
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        choice = resp.choices[0]
        usage = TokenUsage(
            prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0,
            completion_tokens=getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0,
        )
        return LLMResponse(text=choice.message.content or "", model=resp.model, usage=usage,
                           finish_reason=choice.finish_reason or "stop")

    def stream(self, request: LLMRequest) -> Iterator[str]:
        if not self._client:
            raise LLMError(f"{self.name} provider not available")
        stream = self._client.chat.completions.create(
            model=request.model or self.model,
            messages=self._messages(request),
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


class OllamaProvider(OpenAIProvider):
    """Local Ollama via its OpenAI-compatible endpoint (no API key required)."""

    name = "ollama"
    default_base_url = "http://localhost:11434/v1"

    def __init__(self, model: str, *, api_key: str = "ollama", base_url: str | None = None) -> None:
        super().__init__(model, api_key=api_key or "ollama", base_url=base_url)
