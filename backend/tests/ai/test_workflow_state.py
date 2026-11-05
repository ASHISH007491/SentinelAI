"""Tests for the shared LangGraph workflow state + persistence + recovery."""
import pytest

from app.ai.core.errors import StateError
from app.ai.state import (
    FileStateRepository,
    InMemoryStateRepository,
    UserRef,
    WorkflowState,
    WorkflowStatus,
    recover,
)


def _state() -> WorkflowState:
    s = WorkflowState(run_id="run-1")
    s.user = UserRef(id=1, email="a@b.com")
    s.project.name = "Payments"
    return s


# --- lifecycle / transitions ---
def test_agent_lifecycle_transitions():
    s = _state()
    s.start_agent("detection")
    assert s.running == ["detection"] and s.status is WorkflowStatus.RUNNING
    s.complete_agent("detection", output={"findings": []}, latency_ms=120)
    assert s.completed == ["detection"] and s.running == []
    assert s.outputs["detection"] == {"findings": []}

    s.start_agent("prioritisation")
    s.fail_agent("prioritisation", "boom", latency_ms=30)
    assert s.failed == ["prioritisation"]
    assert s.errors[-1].message == "boom" and s.errors[-1].agent == "prioritisation"
    assert s.total_execution_ms == 150.0


def test_collections_and_finish():
    s = _state()
    s.add_message("user", "hi", agent=None)
    s.add_recommendation("Patch xz", priority="P0", detail="CVE-2024-3094")
    s.add_report("Exec Summary", kind="executive")
    s.add_warning("low confidence", agent="advisor")
    s.complete_agent("report", latency_ms=5)
    s.finish()
    assert s.status is WorkflowStatus.COMPLETED
    assert len(s.conversation) == 1 and len(s.recommendations) == 1 and len(s.reports) == 1
    assert s.warnings[-1].agent == "advisor"


def test_finish_failed_when_any_agent_failed():
    s = _state()
    s.start_agent("a")
    s.fail_agent("a", "err")
    s.finish()
    assert s.status is WorkflowStatus.FAILED


def test_pending_agents():
    s = _state()
    s.start_agent("a")
    s.complete_agent("a")
    s.start_agent("b")  # still running
    assert s.pending_agents(["a", "b", "c", "d"]) == ["c", "d"]


# --- serialization ---
def test_serialization_round_trip():
    s = _state()
    s.start_agent("detection")
    s.complete_agent("detection", {"x": 1}, 10)
    s.add_recommendation("R")
    restored = WorkflowState.from_json(s.to_json())
    assert restored.run_id == "run-1"
    assert restored.completed == ["detection"]
    assert restored.outputs["detection"] == {"x": 1}
    assert restored.user.email == "a@b.com"


# --- persistence ---
def test_in_memory_repository():
    repo = InMemoryStateRepository()
    repo.save(_state())
    assert repo.list_runs() == ["run-1"]
    assert repo.load("run-1").run_id == "run-1"
    repo.delete("run-1")
    assert repo.load("run-1") is None


def test_file_repository_round_trip(tmp_path):
    repo = FileStateRepository(tmp_path)
    s = _state()
    s.start_agent("a")
    s.complete_agent("a", {"k": 1}, 7)
    repo.save(s)
    assert (tmp_path / "run-1.json").exists()
    loaded = repo.load("run-1")
    assert loaded.outputs["a"] == {"k": 1}
    assert repo.list_runs() == ["run-1"]


# --- recovery ---
def test_recovery_resets_interrupted_agents(tmp_path):
    repo = FileStateRepository(tmp_path)
    s = _state()
    s.start_agent("detection")
    s.complete_agent("detection", {}, 5)
    s.start_agent("prioritisation")  # interrupted mid-run (still "running")
    repo.save(s)

    recovered = recover(repo, "run-1")
    assert recovered.status is WorkflowStatus.RECOVERED
    assert recovered.running == []                       # interrupted agent cleared
    assert recovered.completed == ["detection"]          # progress preserved
    # prioritisation is pending again, ready to resume
    assert recovered.pending_agents(["detection", "prioritisation", "report"]) == [
        "prioritisation", "report",
    ]
    assert any("recovered" in w.message for w in recovered.warnings)


def test_recover_missing_run_raises():
    with pytest.raises(StateError):
        recover(InMemoryStateRepository(), "nope")
