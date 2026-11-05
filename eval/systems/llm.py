"""Injectable LLM seam: a minimal protocol + a deterministic fake for offline tests.

Real runs inject a concrete client (OpenAI/Anthropic/Ollama via the app's LLM layer);
tests inject FakeLLM so the whole harness is reproducible without network or API keys.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse: ...


def _approx_tokens(text: str) -> int:
    # cheap, deterministic stand-in for a tokenizer (good enough for relative cost).
    return max(1, len(text.split()))


class FakeLLM:
    """Deterministic scriptable LLM for tests.

    Pass either a list of replies (returned in order, last one repeats) or a callable
    mapping prompt -> reply. Records every prompt it saw for assertions.
    """

    def __init__(self, replies: list[str] | Callable[[str], str]) -> None:
        self._replies = replies
        self._i = 0
        self.prompts: list[str] = []

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        self.prompts.append(prompt)
        if callable(self._replies):
            text = self._replies(prompt)
        else:
            idx = min(self._i, len(self._replies) - 1)
            text = self._replies[idx]
            self._i += 1
        full_prompt = f"{system}\n{prompt}" if system else prompt
        return LLMResponse(
            text=text,
            prompt_tokens=_approx_tokens(full_prompt),
            completion_tokens=_approx_tokens(text),
        )
