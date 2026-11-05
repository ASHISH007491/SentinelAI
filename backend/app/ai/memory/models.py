"""DTOs returned by the Memory Service (decoupled from the ORM model)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.ai.types.aliases import JSON
from app.models.memory import MemoryScope


class MemoryItem(BaseModel):
    id: int
    session_id: str
    scope: MemoryScope
    role: str | None = None
    key: str | None = None
    content: JSON = Field(default_factory=dict)
    importance: float = 0.0
    is_summary: bool = False
    created_at: datetime | None = None
    expires_at: datetime | None = None

    @property
    def text(self) -> str:
        return str(self.content.get("text", "")) if isinstance(self.content, dict) else ""


class Summary(BaseModel):
    session_id: str
    scope: MemoryScope
    text: str
    compressed_count: int
