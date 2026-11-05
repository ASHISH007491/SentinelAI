"""Workflow contract: orchestrates steps over shared state."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models.results import WorkflowResult
from app.ai.state.base import BaseState


class Workflow(ABC):
    name: str = "workflow"

    @abstractmethod
    def run(self, state: BaseState) -> WorkflowResult:
        ...
