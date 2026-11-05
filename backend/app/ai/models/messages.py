"""LLM request/response domain models."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.types.aliases import Metadata
from app.ai.types.enums import LLMRole


class LLMMessage(BaseModel):
    role: LLMRole
    content: str


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )


class LLMRequest(BaseModel):
    messages: list[LLMMessage]
    system: str | None = None
    model: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.0
    metadata: Metadata = Field(default_factory=dict)


class LLMResponse(BaseModel):
    text: str
    model: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    finish_reason: str = "stop"
    metadata: Metadata = Field(default_factory=dict)
