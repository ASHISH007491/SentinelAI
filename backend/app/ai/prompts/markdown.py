"""Parse Markdown prompt files: YAML frontmatter (metadata) + Jinja2 body."""
from __future__ import annotations

import yaml
from pydantic import BaseModel, Field

from app.ai.core.errors import PromptError


class PromptTest(BaseModel):
    """An embedded render test: render with `vars`, assert output contains text."""
    vars: dict = Field(default_factory=dict)
    expect_contains: str = ""


class PromptMetadata(BaseModel):
    name: str
    version: str = "1.0.0"
    description: str = ""
    variables: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    model: str | None = None
    tests: list[PromptTest] = Field(default_factory=list)


class MarkdownPrompt(BaseModel):
    metadata: PromptMetadata
    body: str


_DELIM = "---"


def parse_markdown(text: str) -> MarkdownPrompt:
    """Split `--- yaml ---` frontmatter from the Jinja2 body."""
    stripped = text.lstrip("﻿").lstrip()
    if not stripped.startswith(_DELIM):
        raise PromptError("Prompt is missing YAML frontmatter (expected leading '---')")
    parts = stripped.split(_DELIM, 2)
    if len(parts) < 3:
        raise PromptError("Malformed frontmatter (expected opening and closing '---')")
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as exc:
        raise PromptError(f"Invalid YAML frontmatter: {exc}") from exc
    if not isinstance(data, dict):
        raise PromptError("Frontmatter must be a YAML mapping")
    try:
        metadata = PromptMetadata(**data)
    except Exception as exc:
        raise PromptError(f"Invalid prompt metadata: {exc}") from exc
    return MarkdownPrompt(metadata=metadata, body=parts[2].strip() + "\n")


def to_markdown(prompt: MarkdownPrompt) -> str:
    """Serialise a MarkdownPrompt back to frontmatter + body."""
    front = yaml.safe_dump(
        prompt.metadata.model_dump(exclude_defaults=True), sort_keys=False
    ).strip()
    return f"{_DELIM}\n{front}\n{_DELIM}\n\n{prompt.body.strip()}\n"
