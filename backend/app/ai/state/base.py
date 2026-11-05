"""BaseState: the shared object threaded through a workflow's steps.

Agent-specific workflows subclass this to add typed fields. The base provides an
inputs bag, an artefacts list, a scratchpad for intermediate values, and an
append-only trace plus accumulated token usage.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.models.messages import TokenUsage
from app.ai.types.aliases import JSON, Metadata


class BaseState(BaseModel):
    run_id: str = ""
    inputs: JSON = Field(default_factory=dict)
    artefacts: list[str] = Field(default_factory=list)
    scratchpad: Metadata = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)

    def note(self, message: str) -> None:
        """Append a human-readable line to the execution trace."""
        self.trace.append(message)

    def add_usage(self, usage: TokenUsage) -> None:
        self.usage = self.usage + usage

    model_config = {"arbitrary_types_allowed": True}
