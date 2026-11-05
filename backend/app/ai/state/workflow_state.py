"""Shared workflow state threaded through a LangGraph run.

A single Pydantic model that every agent reads from and writes to. It tracks the
user/project context, uploaded files, agent lifecycle (running/completed/failed),
outputs, timing, conversation, recommendations, reports, and errors/warnings.
Fully serialisable (JSON) and persistable, which enables workflow recovery.

No agent logic lives here — only state and the transitions over it.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field

from app.ai.models.messages import TokenUsage
from app.ai.types.aliases import JSON, Metadata


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- LangGraph reducers: merge concurrent updates instead of overwriting ---
def _merge_unique(left: list, right: list) -> list:
    """Union of two lists preserving order (for agent-name lists)."""
    out = list(left)
    for item in right:
        if item not in out:
            out.append(item)
    return out


def _merge_dict(left: dict, right: dict) -> dict:
    return {**left, **right}


def _extend(left: list, right: list) -> list:
    return [*left, *right]


def _sum_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return left + right


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RECOVERED = "recovered"


# --- reference sub-models ---------------------------------------------------
class UserRef(BaseModel):
    id: int | None = None
    email: str = ""


class ProjectRef(BaseModel):
    id: int | None = None
    name: str = ""


class FileRef(BaseModel):
    name: str
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    path: str = ""


class Message(BaseModel):
    role: str  # system | user | assistant
    content: str
    agent: str | None = None
    at: datetime = Field(default_factory=_now)


class Recommendation(BaseModel):
    title: str
    priority: str = "P2"  # P0 | P1 | P2
    detail: str = ""


class ReportRef(BaseModel):
    id: int | None = None
    title: str
    kind: str = "executive"  # executive | technical
    path: str = ""


class Note(BaseModel):
    message: str
    agent: str | None = None
    at: datetime = Field(default_factory=_now)


# --- the workflow state -----------------------------------------------------
class WorkflowState(BaseModel):
    run_id: str
    status: WorkflowStatus = WorkflowStatus.PENDING

    # Context
    user: UserRef = Field(default_factory=UserRef)
    project: ProjectRef = Field(default_factory=ProjectRef)
    files: list[FileRef] = Field(default_factory=list)

    # Agent lifecycle
    running: Annotated[list[str], _merge_unique] = Field(default_factory=list)
    completed: Annotated[list[str], _merge_unique] = Field(default_factory=list)
    failed: Annotated[list[str], _merge_unique] = Field(default_factory=list)
    current_step: str | None = None

    # Results
    outputs: Annotated[dict[str, JSON], _merge_dict] = Field(default_factory=dict)
    execution_ms: Annotated[dict[str, float], _merge_dict] = Field(default_factory=dict)
    conversation: Annotated[list[Message], _extend] = Field(default_factory=list)
    recommendations: Annotated[list[Recommendation], _extend] = Field(default_factory=list)
    reports: Annotated[list[ReportRef], _extend] = Field(default_factory=list)
    errors: Annotated[list[Note], _extend] = Field(default_factory=list)
    warnings: Annotated[list[Note], _extend] = Field(default_factory=list)

    # Bookkeeping
    metadata: Metadata = Field(default_factory=dict)
    usage: Annotated[TokenUsage, _sum_usage] = Field(default_factory=TokenUsage)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # ---- transitions -------------------------------------------------------
    def touch(self) -> None:
        self.updated_at = _now()

    def start_agent(self, name: str) -> None:
        if name not in self.running:
            self.running.append(name)
        self.current_step = name
        self.status = WorkflowStatus.RUNNING
        self.touch()

    def complete_agent(
        self, name: str, output: JSON | None = None, latency_ms: float = 0.0
    ) -> None:
        self._remove_running(name)
        if name not in self.completed:
            self.completed.append(name)
        if output is not None:
            self.outputs[name] = output
        self.execution_ms[name] = latency_ms
        self.touch()

    def fail_agent(self, name: str, error: str, latency_ms: float = 0.0) -> None:
        self._remove_running(name)
        if name not in self.failed:
            self.failed.append(name)
        self.execution_ms[name] = latency_ms
        self.add_error(error, agent=name)
        self.touch()

    def _remove_running(self, name: str) -> None:
        if name in self.running:
            self.running.remove(name)

    def add_message(self, role: str, content: str, *, agent: str | None = None) -> None:
        self.conversation.append(Message(role=role, content=content, agent=agent))
        self.touch()

    def add_recommendation(self, title: str, *, priority: str = "P2", detail: str = "") -> None:
        self.recommendations.append(Recommendation(title=title, priority=priority, detail=detail))
        self.touch()

    def add_report(
        self, title: str, *, kind: str = "executive", path: str = "", id: int | None = None
    ) -> None:
        self.reports.append(ReportRef(id=id, title=title, kind=kind, path=path))
        self.touch()

    def add_error(self, message: str, *, agent: str | None = None) -> None:
        self.errors.append(Note(message=message, agent=agent))
        self.touch()

    def add_warning(self, message: str, *, agent: str | None = None) -> None:
        self.warnings.append(Note(message=message, agent=agent))
        self.touch()

    def finish(self) -> None:
        self.status = WorkflowStatus.FAILED if self.failed else WorkflowStatus.COMPLETED
        self.current_step = None
        self.touch()

    # ---- queries / recovery ------------------------------------------------
    @property
    def total_execution_ms(self) -> float:
        return round(sum(self.execution_ms.values()), 2)

    def pending_agents(self, expected: list[str]) -> list[str]:
        done = set(self.completed) | set(self.failed) | set(self.running)
        return [a for a in expected if a not in done]

    def mark_recovered(self) -> None:
        """Reset interrupted (still-running) agents so they can be re-executed."""
        self.running.clear()
        self.current_step = None
        self.status = WorkflowStatus.RECOVERED
        self.add_warning("workflow recovered from checkpoint")
        self.touch()

    # ---- serialization -----------------------------------------------------
    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, data: str) -> WorkflowState:
        return cls.model_validate_json(data)
