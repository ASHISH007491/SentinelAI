"""Persistence + recovery for WorkflowState.

A StateRepository checkpoints workflow state by run_id. Two implementations:
in-memory (tests/dev) and file-backed (durable). `recover()` reloads a checkpoint
and resets interrupted agents so the workflow can resume from where it stopped.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from app.ai.core.errors import StateError
from app.ai.core.logging import get_logger
from app.ai.state.workflow_state import WorkflowState

logger = get_logger(__name__)


@runtime_checkable
class StateRepository(Protocol):
    def save(self, state: WorkflowState) -> None: ...
    def load(self, run_id: str) -> WorkflowState | None: ...
    def delete(self, run_id: str) -> None: ...
    def list_runs(self) -> list[str]: ...


class InMemoryStateRepository:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def save(self, state: WorkflowState) -> None:
        self._data[state.run_id] = state.to_json()

    def load(self, run_id: str) -> WorkflowState | None:
        raw = self._data.get(run_id)
        return WorkflowState.from_json(raw) if raw is not None else None

    def delete(self, run_id: str) -> None:
        self._data.pop(run_id, None)

    def list_runs(self) -> list[str]:
        return sorted(self._data)


class FileStateRepository:
    """Durable JSON checkpoints, one file per run_id."""

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        safe = run_id.replace("/", "_")
        return self.directory / f"{safe}.json"

    def save(self, state: WorkflowState) -> None:
        # Atomic write: tmp file then replace, so a crash never leaves a partial file.
        path = self._path(state.run_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(state.to_json(), encoding="utf-8")
        tmp.replace(path)

    def load(self, run_id: str) -> WorkflowState | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            return WorkflowState.from_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise StateError(f"Corrupt checkpoint for run '{run_id}': {exc}") from exc

    def delete(self, run_id: str) -> None:
        self._path(run_id).unlink(missing_ok=True)

    def list_runs(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.json"))


def recover(repository: StateRepository, run_id: str) -> WorkflowState:
    """Load a checkpoint and prepare it for resumption.

    Interrupted (still-running) agents are reset so they re-execute; completed and
    failed agents are preserved. Raises StateError if no checkpoint exists.
    """
    state = repository.load(run_id)
    if state is None:
        raise StateError(f"No checkpoint to recover for run '{run_id}'")
    state.mark_recovered()
    logger.info(
        "recovered run=%s completed=%d failed=%d",
        run_id, len(state.completed), len(state.failed),
    )
    return state
