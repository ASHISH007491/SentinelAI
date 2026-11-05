"""BaseTool: the contract every tool implements.

A tool declares a Pydantic `Input` model (for validation + JSON-schema metadata),
identity (name/description/version/tags), and a `_run` that does the work. The
ToolManager wraps `_run` with validation, timeout, and logging — tools never need
to implement those concerns themselves.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ValidationError

from app.ai.core.errors import ToolValidationError
from app.ai.tools.models import ToolMetadata
from app.ai.types.aliases import JSON


class _EmptyInput(BaseModel):
    pass


class BaseTool(ABC):
    name: str = "tool"
    description: str = ""
    version: str = "1.0.0"
    tags: list[str] = []
    timeout_s: float = 30.0
    Input: type[BaseModel] = _EmptyInput

    def validate(self, args: JSON) -> BaseModel:
        try:
            return self.Input(**(args or {}))
        except ValidationError as exc:
            raise ToolValidationError(f"Invalid input for tool '{self.name}': {exc}") from exc

    @abstractmethod
    def _run(self, params: BaseModel) -> JSON:
        """Execute the tool with validated params. Return a JSON-serialisable dict."""

    def metadata(self, *, enabled: bool = True) -> ToolMetadata:
        return ToolMetadata(
            name=self.name,
            description=self.description,
            version=self.version,
            enabled=enabled,
            tags=list(self.tags),
            input_schema=self.Input.model_json_schema(),
        )
