"""A Run is one orchestrated job over an uploaded artefact for a given workflow."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.agent_output import AgentOutput
    from app.models.artefact import Artefact
    from app.models.evaluation import EvaluationRecord
    from app.models.user import User


class WorkflowType(str, enum.Enum):
    VULN = "vuln"
    PHISHING = "phishing"
    CODE_REVIEW = "code_review"


class RunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    workflow: Mapped[WorkflowType] = mapped_column(Enum(WorkflowType))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.QUEUED)
    # "multi" (LangGraph) or "single" (baseline) — the experimental variable.
    architecture: Mapped[str] = mapped_column(default="multi")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    owner: Mapped[User] = relationship(back_populates="runs")
    artefacts: Mapped[list[Artefact]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    agent_outputs: Mapped[list[AgentOutput]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    evaluation: Mapped[EvaluationRecord | None] = relationship(
        back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
