"""Thin LLM wrapper with cost/usage logging and a graceful offline fallback.

When LLM_API_KEY is set and the `anthropic` SDK is installed, calls the Anthropic
Messages API. Otherwise `available` is False and agents fall back to deterministic,
rule-based behaviour so the system still works (and tests run) without a key.

This is the single choke point for all model calls — both the multi-agent system
and the single-agent baseline go through it, which keeps token-cost accounting fair.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger("sentinelai.llm")


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class LLMResponse:
    text: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""


class LLMClient:
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self.model = model or settings.llm_model
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self._client = None
        if self.api_key:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as exc:  # SDK missing or init failed — fall back.
                logger.warning("LLM disabled (%s); using offline fallback.", exc)

    @property
    def available(self) -> bool:
        return self._client is not None

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> LLMResponse:
        """Return a completion. Raises only on hard API errors; callers may catch."""
        if not self._client:
            return LLMResponse(text="", model="offline")

        msg = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system or "You are a precise security analysis assistant.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
        usage = Usage(
            prompt_tokens=msg.usage.input_tokens,
            completion_tokens=msg.usage.output_tokens,
        )
        logger.info("llm_call model=%s total_tokens=%d", self.model, usage.total_tokens)
        return LLMResponse(text=text, usage=usage, model=self.model)
