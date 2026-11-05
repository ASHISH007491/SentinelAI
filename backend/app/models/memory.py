"""Memory records — durable store for the AI Memory Service (session-isolated)."""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class MemoryScope(str, enum.Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    CONVERSATION = "conversation"
    PROJECT = "project"
    EXECUTION = "execution"


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Session isolation: every read is scoped by session_id.
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    scope: Mapped[MemoryScope] = mapped_column(Enum(MemoryScope), index=True)
    mem_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)  # conversation role
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    is_summary: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # short-term TTL
