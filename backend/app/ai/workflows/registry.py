"""Registry mapping workflow names to factory callables."""
from __future__ import annotations

from collections.abc import Callable

from app.ai.core.errors import WorkflowError
from app.ai.interfaces.workflow import Workflow

WorkflowFactory = Callable[[], Workflow]


class WorkflowRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, WorkflowFactory] = {}

    def register(self, name: str, factory: WorkflowFactory) -> None:
        if name in self._factories:
            raise WorkflowError(f"Workflow '{name}' already registered")
        self._factories[name] = factory

    def create(self, name: str) -> Workflow:
        if name not in self._factories:
            raise WorkflowError(f"Unknown workflow '{name}'")
        return self._factories[name]()

    def names(self) -> list[str]:
        return sorted(self._factories)


workflow_registry = WorkflowRegistry()
