"""A minimal, safe prompt template.

Uses str.format_map with a guard so missing variables raise a clear PromptError
rather than a bare KeyError. Implements the PromptRenderer protocol.
"""
from __future__ import annotations

import string

from app.ai.core.errors import PromptError
from app.ai.types.aliases import PromptVariables


class _SafeDict(dict):
    def __missing__(self, key: str):  # noqa: D401
        raise KeyError(key)


class PromptTemplate:
    def __init__(self, template: str, *, name: str = "prompt") -> None:
        self.template = template
        self.name = name
        # Pre-compute referenced field names for validation.
        self.variables = {
            field for _, field, _, _ in string.Formatter().parse(template) if field
        }

    def render(self, variables: PromptVariables | None = None) -> str:
        variables = variables or {}
        try:
            return self.template.format_map(_SafeDict(variables))
        except KeyError as exc:
            raise PromptError(f"Missing variable {exc} for prompt '{self.name}'") from exc
