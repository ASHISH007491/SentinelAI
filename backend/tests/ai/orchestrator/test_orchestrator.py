"""Tests for the Orchestrator (async; fake agents; no domain logic)."""
import asyncio
import threading
import time

import pytest

from app.ai.agents import AgentConfig, AgentRegistry, AgentRequest, BaseAgent
from app.ai.core.errors import RequestValidationError
from app.ai.orchestrator import Orchestrator, OrchestratorRequest, OrchestratorStatus


class _FakeLLM:
    available = True
    def generate(self, request):
        from app.ai.models.messages import LLMResponse
        return LLMResponse(text="ok")


def _agent(agent_id, *, caps=None, deps=None, fn=None, fail=False,
           error_code="ai_agent_error", slow=0.0):
    def execute(self, request: AgentRequest):
        if slow:
            time.sleep(slow)
        if fail:
            from app.ai.core.errors import AgentError
            raise AgentError("boom", code=error_code)
        return (fn(request) if fn else {"agent": agent_id})
    return type(f"Agent_{agent_id}", (BaseAgent,), {
        "config": AgentConfig(id=agent_id, name=agent_id),
        "capabilities": caps or [],
        "dependencies": deps or [],
        "execute": execute,
    })


def _registry(*agent_classes):
    r = AgentRegistry()
    for cls in agent_classes:
        r.register(cls)
    return r


def _run(coro):
    return asyncio.run(coro)


# --- validation ---
def test_validate_request_rejects_empty():
    orch = Orchestrator(registry=AgentRegistry())
    with pytest.raises(RequestValidationError):
        orch.validate_request(OrchestratorRequest())


# --- routing / agent selection by capability + dependency order ---
def test_route_selects_and_orders_by_dependency():
    reg = _registry(
        _agent("detection", caps=["scan"]),
        _agent("advisor", caps=["advise"], deps=["detection"]),
    )
    orch = Orchestrator(registry=reg)
    intent, plan = orch.route(OrchestratorRequest(capabilities=["scan", "advise"]))
    # detection must precede advisor (dependency), expressed as levels
    assert plan.levels[0] == ["detection"]
    assert "advisor" in plan.levels[1]


# --- end-to-end execute returns structured JSON ---
def test_execute_completed_collects_outputs():
    reg = _registry(_agent("a", caps=["x"]), _agent("b", caps=["x"]))
    orch = Orchestrator(registry=reg)
    result = _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    assert result.status is OrchestratorStatus.COMPLETED
    assert set(result.outputs) == {"a", "b"}
    j = result.to_json()
    assert j["status"] == "completed" and j["metrics"]["agents_run"] == 2


def test_execute_no_agents_fails_gracefully():
    orch = Orchestrator(registry=AgentRegistry())
    result = _run(orch.execute(OrchestratorRequest(capabilities=["nope"])))
    assert result.status is OrchestratorStatus.FAILED
    assert result.warnings


# --- failure handling: required vs optional ---
def test_required_failure_aborts_and_fails():
    reg = _registry(_agent("bad", caps=["x"], fail=True))
    orch = Orchestrator(registry=reg)
    result = _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    assert result.status is OrchestratorStatus.FAILED
    assert result.errors


def test_optional_failure_degrades_but_continues():
    reg = _registry(
        _agent("ok", caps=["x"]),
        _agent("flaky", caps=["x"], fail=True),
    )
    orch = Orchestrator(registry=reg)
    req = OrchestratorRequest(capabilities=["x"], optional_agents=["flaky"])
    result = _run(orch.execute(req))
    assert result.status is OrchestratorStatus.DEGRADED
    assert "ok" in result.outputs
    assert any("flaky" in w for w in result.warnings)  # optional failure -> warning


# --- retry on transient failure ---
def test_retry_then_success():
    state = {"n": 0}

    def flaky_fn(request):
        state["n"] += 1
        if state["n"] < 2:
            from app.ai.core.errors import LLMError
            raise LLMError("transient")
        return {"n": state["n"]}

    # max_retries=0 on the agent so its own retry doesn't mask the failure;
    # the orchestrator's dispatcher is what retries here.
    cls = _agent("flaky", caps=["x"], fn=flaky_fn)
    cls.config = AgentConfig(id="flaky", name="flaky", max_retries=0)
    reg = _registry(cls)
    orch = Orchestrator(registry=reg)  # RetryManager default max_retries=1
    result = _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    assert result.status is OrchestratorStatus.COMPLETED
    assert result.metrics.retries == 1


# --- async parallelism: independent agents run concurrently ---
def test_independent_agents_run_in_parallel():
    seen_threads = set()
    lock = threading.Lock()

    def record(request):
        with lock:
            seen_threads.add(threading.get_ident())
        time.sleep(0.1)
        return {}

    reg = _registry(
        _agent("a", caps=["x"], fn=record),
        _agent("b", caps=["x"], fn=record),
        _agent("c", caps=["x"], fn=record),
    )
    orch = Orchestrator(registry=reg)
    t0 = time.perf_counter()
    result = _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    elapsed = time.perf_counter() - t0
    assert result.status is OrchestratorStatus.COMPLETED
    # 3 x 0.1s sequential would be ~0.3s; parallel should be well under
    assert elapsed < 0.25
    assert len(seen_threads) >= 2  # ran on multiple threads


# --- explicit agent list overrides capability selection ---
def test_explicit_agent_list():
    reg = _registry(_agent("only", caps=["x"]), _agent("other", caps=["x"]))
    orch = Orchestrator(registry=reg)
    result = _run(orch.execute(OrchestratorRequest(agents=["only"])))
    assert set(result.outputs) == {"only"}


# --- memory integration: recall + execution history ---
def _memory_service():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401
    from app.ai.memory import MemoryService
    from app.db.session import Base
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    return MemoryService(sessionmaker(bind=engine))


def test_memory_recall_and_history():
    from app.models.memory import MemoryScope
    mem = _memory_service()
    mem.add_message("sess-1", "user", "previous context")
    reg = _registry(_agent("a", caps=["x"]))
    orch = Orchestrator(registry=reg, memory=mem)
    result = _run(orch.execute(OrchestratorRequest(session_id="sess-1", capabilities=["x"])))
    assert result.status is OrchestratorStatus.COMPLETED
    # execution history was written (one per agent + one run summary)
    exec_records = mem.recall("sess-1", scope=MemoryScope.EXECUTION)
    assert len(exec_records) >= 2
    assert any(r.content.get("agent") == "a" for r in exec_records)
    assert any("run_id" in r.content for r in exec_records)


# --- per-run timeout budget -> degraded ---
def test_run_timeout_budget_degrades():
    import time as _t

    def slow_fn(request):
        _t.sleep(0.2)
        return {}

    # level 0 = fast 'first'; level 1 = 'second' (depends on first) won't be scheduled
    reg = _registry(
        _agent("first", caps=["x"], fn=slow_fn),
        _agent("second", caps=["x"], deps=["first"]),
    )
    orch = Orchestrator(registry=reg, run_timeout_s=0.05)  # budget under the first agent's time
    result = _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    assert result.status is OrchestratorStatus.DEGRADED
    assert "second" not in result.outputs                 # not scheduled after budget breach
    assert any("timeout" in w.lower() for w in result.warnings)


# --- per-agent tool allow-list granting ---
def test_tool_allowlist_granted_to_agent():
    from pydantic import BaseModel

    from app.ai.tools import BaseTool, ToolManager

    class NoopTool(BaseTool):
        name = "noop"
        class Input(BaseModel):
            pass
        def _run(self, params):
            return {}

    tm = ToolManager()
    tm.register(NoopTool())

    cls = _agent("user", caps=["x"])
    cls.tools_required = ["noop"]
    reg = _registry(cls)
    orch = Orchestrator(registry=reg, tool_manager=tm)
    _run(orch.execute(OrchestratorRequest(capabilities=["x"])))
    # the dispatcher granted exactly the declared tools to this agent
    assert tm.permissions("user") == {"noop"}
