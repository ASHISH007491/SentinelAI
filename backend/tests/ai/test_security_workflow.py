"""Tests for the concrete LangGraph security workflow."""
import threading
import time

import pytest

from app.ai.agents import AgentConfig, AgentRegistry, BaseAgent
from app.ai.orchestrator.models import OrchestratorRequest
from app.ai.workflows.security_workflow import CancellationToken, SecurityWorkflow


def _agent(aid, caps, *, fn=None, fail=False, slow=0.0):
    def execute(self, request):
        if slow:
            time.sleep(slow)
        if fail:
            from app.ai.core.errors import AgentError
            raise AgentError("boom")
        return fn(request) if fn else {"agent": aid}
    return type(f"A_{aid}", (BaseAgent,), {
        "config": AgentConfig(id=aid, name=aid, max_retries=0),
        "capabilities": caps, "execute": execute,
    })


def _registry(*classes):
    r = AgentRegistry()
    for c in classes:
        r.register(c)
    return r


def _full_registry(**kw):
    return _registry(
        _agent("detection", ["scan"], **kw),
        _agent("prioritisation", ["scan"]),
        _agent("advisor", ["advise"]),
        _agent("report", ["report"]),
    )


# --- full pipeline order + outputs ---
def test_pipeline_runs_all_stages_in_order():
    wf = SecurityWorkflow(_full_registry())
    res = wf.run(OrchestratorRequest(capabilities=["scan", "advise", "report"]))
    assert res.status == "completed"
    assert set(res.outputs) == {"detection", "prioritisation", "advisor", "report"}
    assert res.trace == [
        "receive", "validate", "determine_intent", "select_agents", "execute_agents",
        "collect_results", "security_advisor", "report_generator", "return_response",
    ]
    assert "execute_agents" in res.stage_metrics  # execution metrics captured


# --- conditional routing: invalid request -> error terminal ---
def test_invalid_request_routes_to_error():
    wf = SecurityWorkflow(_full_registry())
    res = wf.run(OrchestratorRequest())  # nothing specified
    assert res.status == "failed"
    assert "return_error" in res.trace
    assert "execute_agents" not in res.trace
    assert res.errors


# --- conditional routing: no capable agents -> error ---
def test_no_agents_routes_to_error():
    wf = SecurityWorkflow(_registry(_agent("x", ["other"])))
    res = wf.run(OrchestratorRequest(capabilities=["missing"]))
    assert res.status == "failed"
    assert "return_error" in res.trace


# --- parallel execution of independent analysis agents ---
def test_parallel_analysis_execution():
    threads = set()
    lock = threading.Lock()

    def rec(request):
        with lock:
            threads.add(threading.get_ident())
        time.sleep(0.1)
        return {}

    reg = _registry(
        _agent("a", ["scan"], fn=rec),
        _agent("b", ["scan"], fn=rec),
        _agent("c", ["scan"], fn=rec),
    )
    wf = SecurityWorkflow(reg)
    t0 = time.perf_counter()
    res = wf.run(OrchestratorRequest(capabilities=["scan"]))
    elapsed = time.perf_counter() - t0
    assert res.status == "completed"
    assert elapsed < 0.25 and len(threads) >= 2   # ran concurrently


# --- recovery/degrade: a failed analysis agent doesn't kill the pipeline ---
def test_agent_failure_degrades_but_continues():
    reg = _registry(
        _agent("bad", ["scan"], fail=True),
        _agent("advisor", ["advise"]),
        _agent("report", ["report"]),
    )
    wf = SecurityWorkflow(reg)
    res = wf.run(OrchestratorRequest(capabilities=["scan", "advise", "report"]))
    assert res.status == "degraded"
    assert "advisor" in res.outputs and "report" in res.outputs  # later stages still ran
    assert any("bad" in e for e in res.errors)


# --- cancellation ---
def test_cancellation_stops_execution():
    token = CancellationToken()
    token.cancel()  # pre-cancelled
    wf = SecurityWorkflow(_full_registry(slow=0.2))
    res = wf.run(OrchestratorRequest(capabilities=["scan", "advise", "report"]), cancel=token)
    assert res.status == "cancelled"
    assert "detection" not in res.outputs  # analysis never launched


# --- timeout budget (deterministic: 2 levels, budget trips before level 2) ---
def test_run_timeout_budget_degrades_deterministically():
    # 'first' runs (level 0, ~0.1s), pushing the clock past the 0.05s budget;
    # 'second' depends on 'first' so it's level 1 — and must be skipped.
    first = _agent("first", ["scan"], slow=0.1)
    second = type("A_second", (BaseAgent,), {
        "config": AgentConfig(id="second", name="second", max_retries=0),
        "capabilities": ["scan"], "dependencies": ["first"],
        "execute": lambda self, r: {"agent": "second"},
    })
    wf = SecurityWorkflow(_registry(first, second), run_timeout_s=0.05)
    res = wf.run(OrchestratorRequest(capabilities=["scan"]))
    assert res.status == "degraded"
    assert "first" in res.outputs          # level 0 completed
    assert "second" not in res.outputs     # level 1 skipped by the budget
    assert any("timeout" in w.lower() for w in res.warnings)


# --- mid-run cancellation: cancel fires while level 0 is running ---
def test_cancellation_during_run():
    token = CancellationToken()
    first = _agent("first", ["scan"], slow=0.15)
    second = type("A_second2", (BaseAgent,), {
        "config": AgentConfig(id="second", name="second", max_retries=0),
        "capabilities": ["scan"], "dependencies": ["first"],
        "execute": lambda self, r: {"agent": "second"},
    })
    wf = SecurityWorkflow(_registry(first, second))
    # cancel shortly after the run starts (while 'first' is still running)
    threading.Timer(0.05, token.cancel).start()
    res = wf.run(OrchestratorRequest(capabilities=["scan"]), cancel=token)
    assert res.status == "cancelled"
    assert "second" not in res.outputs     # next level never launched after cancel


# --- recovery: execute_agents stage raising fires its on_error -> return_error ---
def test_stage_exception_triggers_on_error_recovery():
    from app.ai.orchestrator.models import ExecutionPlan, PlanStep
    from app.ai.orchestrator.planner import Planner

    class _GhostPlanner(Planner):
        # Returns a plan referencing an unregistered agent, so execute_agents'
        # registry.create("ghost") raises inside the stage -> on_error edge fires.
        def plan(self, intent, request):
            return ExecutionPlan(steps=[PlanStep(agent_id="ghost")], levels=[["ghost"]])

    wf = SecurityWorkflow(_full_registry(), planner=_GhostPlanner(_full_registry()))
    res = wf.run(OrchestratorRequest(capabilities=["scan"]))
    assert res.status == "failed"
    assert "return_error" in res.trace          # recovery edge fired
    assert "execute_agents" in res.trace        # the stage that raised


# --- visual graph ---
def test_to_mermaid_shows_pipeline_and_conditionals():
    wf = SecurityWorkflow(_full_registry())
    m = wf.to_mermaid()
    assert "flowchart TD" in m
    assert "execute_agents" in m and "security_advisor" in m and "report_generator" in m
    assert "-. ok .-> determine_intent" in m
    assert "-. invalid .-> return_error" in m


# --- real LangGraph compilation ---
def test_compiles_to_langgraph():
    pytest.importorskip("langgraph")
    wf = SecurityWorkflow(_full_registry())
    graph = wf.to_langgraph()
    assert graph is not None  # compiled without error
