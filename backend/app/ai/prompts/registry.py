"""A simple in-process registry of named prompt templates."""
from __future__ import annotations

from app.ai.core.errors import PromptError
from app.ai.prompts.template import PromptTemplate


class PromptRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}

    def register(self, name: str, template: str) -> PromptTemplate:
        if name in self._templates:
            raise PromptError(f"Prompt '{name}' already registered")
        tpl = PromptTemplate(template, name=name)
        self._templates[name] = tpl
        return tpl

    def get(self, name: str) -> PromptTemplate:
        if name not in self._templates:
            raise PromptError(f"Unknown prompt '{name}'")
        return self._templates[name]

    def names(self) -> list[str]:
        return sorted(self._templates)


# Process-wide default registry.
prompt_registry = PromptRegistry()
