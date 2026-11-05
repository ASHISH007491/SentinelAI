"""Exercises the real LangGraph runner. Skips if langgraph isn't installed."""
import pytest

pytest.importorskip("langgraph")

from app.ai.interfaces.step import Step  # noqa: E402
from app.ai.state.base import BaseState  # noqa: E402
from app.ai.workflows.langgraph_runner import build_state_graph  # noqa: E402


class _Echo(Step):
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, state: BaseState) -> BaseState:
        state.note(f"ran {self.name}")
        return state


def test_langgraph_compiles_and_runs_in_order():
    graph = build_state_graph([_Echo("alpha"), _Echo("beta")])
    final = graph.invoke(BaseState(run_id="r1"))
    # LangGraph returns the final state (dict-like or model); normalise to trace list.
    trace = final["trace"] if isinstance(final, dict) else final.trace
    assert trace == ["ran alpha", "ran beta"]
