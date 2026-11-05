"""Prompt rendering contract."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.ai.types.aliases import PromptVariables


@runtime_checkable
class PromptRenderer(Protocol):
    def render(self, variables: PromptVariables) -> str:
        ...
