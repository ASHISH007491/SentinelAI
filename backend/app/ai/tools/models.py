"""DTOs for tool metadata, results, and execution logs."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.ai.types.aliases import JSON


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ToolMetadata(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0.0"
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    input_schema: JSON = Field(default_factory=dict)  # JSON Schema of the tool's input


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: JSON = Field(default_factory=dict)
    error: str | None = None
    code: str | None = None
    latency_ms: float = 0.0


class ToolExecution(BaseModel):
    tool: str
    success: bool
    latency_ms: float = 0.0
    error: str | None = None
    arg_keys: list[str] = Field(default_factory=list)  # keys only — never values (safety)
    at: datetime = Field(default_factory=_now)
