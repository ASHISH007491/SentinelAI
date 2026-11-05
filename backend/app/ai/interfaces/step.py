"""A single unit of work within a workflow."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.state.base import BaseState


class Step(ABC):
    """One node in a workflow. Reads from and writes to shared state."""

    name: str = "step"

    @abstractmethod
    def run(self, state: BaseState) -> BaseState:
        """Execute the step, returning the (possibly updated) state."""
        ...
