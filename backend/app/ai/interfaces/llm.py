"""LLM provider contract."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.ai.models.messages import LLMRequest, LLMResponse


@runtime_checkable
class LLMProvider(Protocol):
    """Anything that can turn an LLMRequest into an LLMResponse."""

    @property
    def available(self) -> bool:
        """True if the provider can make real model calls."""
        ...

    def generate(self, request: LLMRequest) -> LLMResponse:
        ...
