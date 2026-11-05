"""Tests for the LangGraph workflow engine (built-in executor; offline)."""
import pytest

from app.ai.core.errors import WorkflowError
from app.ai.workflows import END, ExecutionMonitor, WorkflowBuilder


# --- build + linear execution + state management ---
def test_linear_workflow_runs_and_merges_state():
    b = WorkflowBuilder("linear")
    b.add_node("inc", lambda s: {"n": s.get("n", 0) + 1})
    b.add_node("double", lambda s: {"n": s["n"] * 2})
    b.set_entry("inc").add_edge("inc", "double").add_edge("double", END)
    result = b.build().run({"n": 3})
    assert result.status == "completed"
    assert result.state["n"] == 8                       # (3+1)*2
    assert [e.node for e in result.events] == ["inc", "double"]


# --- node registration validation ---
def test_duplicate_node_and_bad_targets_rejected():
    b = WorkflowBuilder("v")
    b.add_node("a", lambda s: {})
    with pytest.raises(WorkflowError):
        b.add_node("a", lambda s: {})                   # duplicate
    b.set_entry("a").add_edge("a", "ghost")
    with pytest.raises(WorkflowError):
        b.build()                                       # unknown edge target


def test_build_requires_entry():
    b = WorkflowBuilder("v").add_node("a", lambda s: {})
    with pytest.raises(WorkflowError):
        b.build()


# --- conditional routing ---
def test_conditional_routing():
    b = WorkflowBuilder("router")
    b.add_node("classify", lambda s: {"kind": "high" if s["score"] > 50 else "low"})
    b.add_node("high_path", lambda s: {"path": "HIGH"})
    b.add_node("low_path", lambda s: {"path": "LOW"})
    b.set_entry("classify")
    b.add_conditional_edges("classify", lambda s: s["kind"],
                            {"high": "high_path", "low": "low_path"})
    b.add_edge("high_path", END).add_edge("low_path", END)
    wf = b.build()
    assert wf.run({"score": 90}).state["path"] == "HIGH"
    assert wf.run({"score": 10}).state["path"] == "LOW"


# --- retry logic ---
def test_retry_then_success():
    calls = {"n": 0}

    def flaky(s):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    b = WorkflowBuilder("retry")
    b.add_node("flaky", flaky, retries=2, retry_backoff_s=0)
    b.set_entry("flaky").add_edge("flaky", END)
    result = b.build().run({})
    assert result.status == "completed" and result.state["ok"] is True
    statuses = [e.status for e in result.events]
    assert statuses == ["retried", "retried", "success"]


# --- error recovery routing ---
def test_error_recovery_routes_to_recovery_node():
    def boom(s):
        raise RuntimeError("explode")

    b = WorkflowBuilder("recover")
    b.add_node("risky", boom, retries=0, on_error="recover")
    b.add_node("recover", lambda s: {"recovered": True})
    b.set_entry("risky").add_edge("recover", END)
    result = b.build().run({})
    assert result.status == "completed"
    assert result.state["recovered"] is True
    assert result.events[0].status == "failed"


def test_failure_without_recovery():
    def boom(s):
        raise RuntimeError("explode")

    b = WorkflowBuilder("fail")
    b.add_node("risky", boom)
    b.set_entry("risky").add_edge("risky", END)
    result = b.build().run({})
    assert result.status == "failed" and "explode" in result.error


# --- execution monitoring ---
def test_execution_monitor_receives_live_events():
    seen = []
    monitor = ExecutionMonitor(on_event=lambda e: seen.append(e.node))
    b = WorkflowBuilder("mon")
    b.add_node("a", lambda s: {}).add_node("b", lambda s: {})
    b.set_entry("a").add_edge("a", "b").add_edge("b", END)
    b.build().run({}, monitor=monitor)
    assert seen == ["a", "b"]
    assert len(monitor.events) == 2


# --- infinite-loop guard ---
def test_max_steps_guard():
    b = WorkflowBuilder("loop")
    b.add_node("a", lambda s: {}).add_node("b", lambda s: {})
    b.set_entry("a").add_edge("a", "b").add_edge("b", "a")  # cycle
    result = b.build().run({}, max_steps=10)
    assert result.status == "failed" and "max_steps" in result.error


# --- visualization ---
def test_to_mermaid_includes_nodes_and_routing():
    b = WorkflowBuilder("viz")
    b.add_node("classify", lambda s: {})
    b.add_node("a", lambda s: {}).add_node("b", lambda s: {})
    b.set_entry("classify")
    b.add_conditional_edges("classify", lambda s: "a", {"a": "a", "b": "b"})
    b.add_edge("a", END).add_edge("b", END)
    mermaid = b.to_mermaid()
    assert "flowchart TD" in mermaid
    assert "START --> classify" in mermaid
    assert "-. a .-> a" in mermaid and "-. b .-> b" in mermaid


# --- real LangGraph compilation ---
def test_compiles_to_langgraph():
    pytest.importorskip("langgraph")
    b = WorkflowBuilder("lg")
    b.add_node("a", lambda s: {"hit_a": True})
    b.add_node("b", lambda s: {"hit_b": True})
    b.set_entry("a").add_edge("a", "b").add_edge("b", END)
    graph = b.build().to_langgraph()
    out = graph.invoke({})
    assert out["hit_a"] and out["hit_b"]


# --- node-level timeout (covers hangs, not just exceptions) ---
def test_node_timeout_triggers_recovery():
    import time as _t

    def hang(s):
        _t.sleep(0.5)
        return {}

    b = WorkflowBuilder("timeout")
    b.add_node("slow", hang, timeout_s=0.1, on_error="recover")
    b.add_node("recover", lambda s: {"recovered": True})
    b.set_entry("slow").add_edge("recover", END)
    result = b.build().run({})
    assert result.status == "completed"
    assert result.state["recovered"] is True
    assert result.events[0].status == "failed"
    assert "exceeded" in (result.events[0].error or "")


def test_node_timeout_with_retry_then_success():
    import time as _t
    calls = {"n": 0}

    def sometimes_slow(s):
        calls["n"] += 1
        if calls["n"] == 1:
            _t.sleep(0.5)      # first attempt times out
        return {"ok": True}

    b = WorkflowBuilder("t2")
    b.add_node("n", sometimes_slow, timeout_s=0.1, retries=1, retry_backoff_s=0)
    b.set_entry("n").add_edge("n", END)
    result = b.build().run({})
    assert result.status == "completed" and result.state["ok"] is True
    assert [e.status for e in result.events] == ["retried", "success"]


# --- runtime trace visualization ---
def test_to_mermaid_runtime_trace_highlights_path():
    def boom(s):
        raise RuntimeError("x")

    b = WorkflowBuilder("trace")
    b.add_node("a", lambda s: {})
    b.add_node("b", boom, on_error="rec")
    b.add_node("rec", lambda s: {})
    b.set_entry("a").add_edge("a", "b").add_edge("rec", END)
    wf = b.build()
    result = wf.run({})
    mermaid = wf.to_mermaid(result)
    assert "classDef executed" in mermaid and "classDef failed" in mermaid
    assert "class b failed;" in mermaid          # b failed
    # a and rec executed successfully
    assert "a" in mermaid and "rec executed" in mermaid
