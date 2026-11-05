"""Tests for the production Agent Dispatcher."""
import threading
import time

from app.ai.agents import AgentConfig, AgentHealth, AgentRegistry, AgentRequest, BaseAgent
from app.ai.orchestrator.agent_dispatcher import AgentDispatcher


def _agent(aid, *, caps=None, deps=None, version="1.0.0", fn=None,
           fail=False, health=None, slow=0.0):
    def execute(self, request):
        if slow:
            time.sleep(slow)
        if fail:
            from app.ai.core.errors import AgentError
            raise AgentError("boom")
        return fn(request) if fn else {"agent": aid}
    attrs = {
        "config": AgentConfig(id=aid, name=aid, version=version, max_retries=0),
        "capabilities": caps or [], "dependencies": deps or [], "execute": execute,
    }
    if health is not None:
        attrs["health_check"] = classmethod(lambda cls, _h=health: _h)
    return type(f"A_{aid}", (BaseAgent,), attrs)


def _registry(*classes):
    r = AgentRegistry()
    for c in classes:
        r.register(c)
    return r


def _req():
    return AgentRequest(run_id="r1")


# --- discovery ---
def test_discover_by_capability_and_explicit():
    reg = _registry(_agent("a", caps=["x"]), _agent("b", caps=["x"]), _agent("c", caps=["y"]))
    d = AgentDispatcher(reg)
    assert d.discover(capability="x") == ["a", "b"]
    assert d.discover(agents=["a", "ghost"]) == ["a"]
    assert d.discover() == ["a", "b", "c"]


# --- availability validation: registered, enabled, health, deps, version ---
def test_validate_unregistered():
    av = AgentDispatcher(_registry()).validate("ghost")
    assert av.available is False and av.registered is False


def test_validate_disabled():
    reg = _registry(_agent("a", caps=["x"]))
    reg.disable("a")
    av = AgentDispatcher(reg).validate("a")
    assert av.available is False and av.reason == "disabled"


def test_validate_unhealthy():
    reg = _registry(_agent("a", caps=["x"], health=AgentHealth.UNHEALTHY))
    av = AgentDispatcher(reg).validate("a")
    assert av.available is False and av.reason == "unhealthy"


def test_validate_missing_dependency():
    reg = _registry(_agent("a", caps=["x"], deps=["missing"]))
    av = AgentDispatcher(reg).validate("a")
    assert av.available is False and "missing dependencies" in av.reason


def test_validate_version_too_low():
    reg = _registry(_agent("a", caps=["x"], version="1.2.0"))
    av = AgentDispatcher(reg).validate("a", min_version="2.0.0")
    assert av.available is False and "version" in av.reason
    assert AgentDispatcher(reg).validate("a", min_version="1.0.0").available is True


# --- single dispatch: success, failure, skip ---
def test_dispatch_success_records_version_and_health():
    reg = _registry(_agent("a", caps=["x"], version="3.1.0", health=AgentHealth.HEALTHY))
    res = AgentDispatcher(reg).dispatch("a", _req())
    assert res.status == "completed" and res.output == {"agent": "a"}
    assert res.version == "3.1.0" and res.health == "healthy" and res.attempts == 1


def test_dispatch_failure():
    reg = _registry(_agent("bad", caps=["x"], fail=True))
    res = AgentDispatcher(reg).dispatch("bad", _req())
    assert res.status == "failed" and res.error


def test_dispatch_unavailable_skips():
    reg = _registry(_agent("a", caps=["x"]))
    reg.disable("a")
    res = AgentDispatcher(reg).dispatch("a", _req())
    assert res.status == "skipped"


# --- retry ---
def test_dispatch_retries_transient():
    state = {"n": 0}

    def flaky(request):
        state["n"] += 1
        if state["n"] < 2:
            from app.ai.core.errors import LLMError
            raise LLMError("transient")
        return {"ok": True}

    reg = _registry(_agent("flaky", caps=["x"], fn=flaky))
    res = AgentDispatcher(reg, retry_backoff_s=0).dispatch("flaky", _req())
    assert res.status == "completed" and res.attempts == 2


# --- parallel batch + collect outputs ---
def test_dispatch_many_parallel_collects_outputs():
    threads = set()
    lock = threading.Lock()

    def rec(request):
        with lock:
            threads.add(threading.get_ident())
        time.sleep(0.1)
        return {}

    reg = _registry(
        _agent("a", caps=["x"], fn=rec),
        _agent("b", caps=["x"], fn=rec),
        _agent("c", caps=["x"], fn=rec),
    )
    d = AgentDispatcher(reg)
    t0 = time.perf_counter()
    report = d.dispatch_batch(["a", "b", "c"], _req())
    elapsed = time.perf_counter() - t0
    assert report.succeeded == 3 and report.failed == 0
    assert set(report.outputs) == {"a", "b", "c"}
    assert elapsed < 0.25 and len(threads) >= 2   # genuinely parallel


# --- bounded concurrency ---
def test_dispatch_many_respects_max_concurrency():
    state = {"current": 0, "peak": 0}
    lock = threading.Lock()

    def busy(request):
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        return {}

    reg = _registry(*[_agent(c, caps=["x"], fn=busy) for c in "abcd"])
    d = AgentDispatcher(reg, max_concurrency=2)
    report = d.dispatch_batch(["a", "b", "c", "d"], _req())
    assert report.succeeded == 4
    assert state["peak"] <= 2   # never more than max_concurrency in flight


# --- backoff (capped + jitter) ---
def test_backoff_delay_capped_and_jittered():
    d = AgentDispatcher(_registry(), retry_backoff_s=1.0, retry_backoff_cap_s=4.0)
    # no jitter: exponential, then capped at 4.0
    d.retry_jitter = False
    assert [d._backoff_delay(n) for n in (1, 2, 3, 10)] == [1.0, 2.0, 4.0, 4.0]
    # jitter on: always within [0, capped]
    d.retry_jitter = True
    assert all(0.0 <= d._backoff_delay(5) <= 4.0 for _ in range(50))
    # disabled when backoff is 0
    assert AgentDispatcher(_registry())._backoff_delay(3) == 0.0


def test_dispatch_many_mixed_results():
    reg = _registry(
        _agent("ok", caps=["x"]),
        _agent("bad", caps=["x"], fail=True),
        _agent("disabled", caps=["x"]),
    )
    reg.disable("disabled")
    report = AgentDispatcher(reg).dispatch_batch(["ok", "bad", "disabled"], _req())
    assert report.succeeded == 1 and report.failed == 1 and report.skipped == 1
    j = report.to_json()
    assert j["succeeded"] == 1
