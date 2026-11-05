"""Shared state that flows through a workflow + a pluggable state store."""
from app.ai.state.base import BaseState
from app.ai.state.persistence import (
    FileStateRepository,
    InMemoryStateRepository,
    StateRepository,
    recover,
)
from app.ai.state.store import InMemoryStateStore
from app.ai.state.workflow_state import (
    FileRef,
    Message,
    Note,
    ProjectRef,
    Recommendation,
    ReportRef,
    UserRef,
    WorkflowState,
    WorkflowStatus,
)

__all__ = [
    "BaseState",
    "FileRef",
    "FileStateRepository",
    "InMemoryStateRepository",
    "InMemoryStateStore",
    "Message",
    "Note",
    "ProjectRef",
    "Recommendation",
    "ReportRef",
    "StateRepository",
    "UserRef",
    "WorkflowState",
    "WorkflowStatus",
    "recover",
]
