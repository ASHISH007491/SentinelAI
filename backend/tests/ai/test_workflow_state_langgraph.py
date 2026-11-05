"""Prove WorkflowState works as a real LangGraph state, including concurrent merges."""
import pytest

pytest.importorskip("langgraph")

from langgraph.graph import END, START, StateGraph  # noqa: E402

from app.ai.state import WorkflowState  # noqa: E402


def test_workflowstate_runs_in_langgraph_sequential():
    def detect(state: WorkflowState) -> dict:
        return {"completed": ["detection"], "outputs": {"detection": {"n": 1}},
                "execution_ms": {"detection": 10.0}}

    def report(state: WorkflowState) -> dict:
        return {"completed": ["report"], "outputs": {"report": {"ok": True}}}

    g = StateGraph(WorkflowState)
    g.add_node("detect", detect)
    g.add_node("report", report)
    g.add_edge(START, "detect")
    g.add_edge("detect", "report")
    g.add_edge("report", END)

    out = g.compile().invoke(WorkflowState(run_id="r1"))
    state = out if isinstance(out, WorkflowState) else WorkflowState.model_validate(out)
    assert state.completed == ["detection", "report"]
    assert state.outputs == {"detection": {"n": 1}, "report": {"ok": True}}


def test_parallel_fanout_merges_without_overwrite():
    # Two agents run in parallel and each append to the same fields. Reducers must
    # merge their updates rather than one overwriting the other.
    def agent_a(state: WorkflowState) -> dict:
        return {"completed": ["a"], "outputs": {"a": {"v": 1}},
                "warnings": [{"message": "from a"}]}

    def agent_b(state: WorkflowState) -> dict:
        return {"completed": ["b"], "outputs": {"b": {"v": 2}},
                "warnings": [{"message": "from b"}]}

    g = StateGraph(WorkflowState)
    g.add_node("a", agent_a)
    g.add_node("b", agent_b)
    g.add_edge(START, "a")
    g.add_edge(START, "b")   # fan-out: a and b run concurrently
    g.add_edge("a", END)
    g.add_edge("b", END)

    out = g.compile().invoke(WorkflowState(run_id="r2"))
    state = out if isinstance(out, WorkflowState) else WorkflowState.model_validate(out)
    assert sorted(state.completed) == ["a", "b"]          # both, not just one
    assert state.outputs == {"a": {"v": 1}, "b": {"v": 2}}
    assert {w.message for w in state.warnings} == {"from a", "from b"}
