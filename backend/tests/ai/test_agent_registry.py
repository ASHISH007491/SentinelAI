"""Tests for the Agent Registry."""
import threading

import pytest

from app.ai.agents import (
    AgentConfig,
    AgentHealth,
    AgentRegistry,
    AgentRequest,
    BaseAgent,
    get_agent_registry,
    register_agent,
)
from app.ai.core.errors import AgentError


class _FakeLLM:
    available = True
    def generate(self, request):
        from app.ai.models.messages import LLMResponse
        return LLMResponse(text="ok")


class DetectionAgent(BaseAgent):
    config = AgentConfig(id="detection", name="Detection", version="1.2.0",
                         description="finds issues")
    capabilities = ["scan", "detect"]
    dependencies: list[str] = []

    @classmethod
    def health_check(cls):
        return AgentHealth.HEALTHY

    def execute(self, request: AgentRequest):
        return {"ok": True}


class AdvisorAgent(BaseAgent):
    config = AgentConfig(id="advisor", name="Advisor")
    capabilities = ["recommend"]
    dependencies = ["detection"]

    def execute(self, request: AgentRequest):
        return {}


@pytest.fixture()
def registry():
    r = AgentRegistry()
    r.register(DetectionAgent)
    r.register(AdvisorAgent)
    return r


# --- registration + discovery + metadata ---
def test_register_and_discover(registry):
    assert registry.names() == ["advisor", "detection"]
    d = registry.descriptor("detection")
    assert d.version == "1.2.0" and d.capabilities == ["scan", "detect"]
    assert d.description == "finds issues"


def test_duplicate_registration_rejected(registry):
    with pytest.raises(AgentError):
        registry.register(DetectionAgent)
    registry.register(DetectionAgent, replace=True)  # replace is allowed


def test_capability_lookup_is_fast_and_correct(registry):
    assert registry.find_by_capability("scan") == ["detection"]
    assert registry.find_by_capability("recommend") == ["advisor"]
    assert registry.find_by_capability("nope") == []
    caps = registry.discover(capability="detect")
    assert [d.id for d in caps] == ["detection"]


# --- instantiation ---
def test_create_instantiates_agent(registry):
    agent = registry.create("detection", llm=_FakeLLM())
    result = agent.run(AgentRequest(inputs={}))
    assert result.output == {"ok": True}


def test_create_unknown_raises(registry):
    with pytest.raises(AgentError):
        registry.create("ghost")


# --- enable / disable ---
def test_disable_blocks_creation(registry):
    registry.disable("detection")
    assert registry.descriptor("detection").enabled is False
    with pytest.raises(AgentError):
        registry.create("detection", llm=_FakeLLM())
    registry.enable("detection")
    assert registry.create("detection", llm=_FakeLLM()) is not None


# --- reload ---
def test_reload_refreshes_descriptor_and_keeps_enabled(registry):
    registry.disable("detection")
    DetectionAgent.capabilities = ["scan", "detect", "triage"]  # class changes
    desc = registry.reload("detection")
    assert "triage" in desc.capabilities
    assert desc.enabled is False  # preserved
    assert registry.find_by_capability("triage") == ["detection"]
    DetectionAgent.capabilities = ["scan", "detect"]  # restore


# --- health ---
def test_health_check_invokes_classmethod(registry):
    assert registry.health("detection") is AgentHealth.UNKNOWN
    assert registry.health_check("detection") is AgentHealth.HEALTHY
    assert registry.health("detection") is AgentHealth.HEALTHY
    # agent without a health_check falls back to stored health
    registry.set_health("advisor", AgentHealth.DEGRADED)
    assert registry.health_check("advisor") is AgentHealth.DEGRADED


# --- dependencies ---
def test_missing_dependencies(registry):
    assert registry.missing_dependencies("advisor") == []  # detection is registered
    registry.unregister("detection")
    assert registry.missing_dependencies("advisor") == ["detection"]


# --- decorator + singleton ---
def test_register_agent_decorator_uses_singleton():
    @register_agent(id="temp-agent", capabilities=["x"])
    class _Temp(BaseAgent):
        config = AgentConfig(id="temp-agent", name="Temp")
        def execute(self, request):
            return {}

    try:
        assert "temp-agent" in get_agent_registry()
        assert get_agent_registry() is AgentRegistry.instance()
    finally:
        get_agent_registry().unregister("temp-agent")


# --- thread safety ---
def test_concurrent_registration_is_thread_safe():
    r = AgentRegistry()

    def make(i):
        cfg = AgentConfig(id=f"a{i}", name=f"A{i}")
        cls = type(f"Agent{i}", (BaseAgent,), {"config": cfg,
              "execute": lambda self, request: {}, "capabilities": ["c"]})
        r.register(cls)

    threads = [threading.Thread(target=make, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(r.names()) == 50
    assert len(r.find_by_capability("c")) == 50


# --- dependency resolution (topological order + cycle detection) ---
def _mk(agent_id, deps):
    return type(
        f"Agent_{agent_id}",
        (BaseAgent,),
        {"config": AgentConfig(id=agent_id, name=agent_id),
         "dependencies": deps,
         "execute": lambda self, request: {}},
    )


def test_resolution_order_topological():
    r = AgentRegistry()
    r.register(_mk("report", ["advisor"]))
    r.register(_mk("advisor", ["detection", "prioritisation"]))
    r.register(_mk("detection", []))
    r.register(_mk("prioritisation", ["detection"]))
    order = r.resolution_order()
    # every dependency precedes its dependent
    assert order.index("detection") < order.index("prioritisation")
    assert order.index("prioritisation") < order.index("advisor")
    assert order.index("advisor") < order.index("report")


def test_resolution_order_detects_cycle():
    from app.ai.core.errors import DependencyCycleError
    r = AgentRegistry()
    r.register(_mk("a", ["b"]))
    r.register(_mk("b", ["a"]))
    with pytest.raises(DependencyCycleError):
        r.resolution_order()


def test_resolution_order_subset():
    r = AgentRegistry()
    r.register(_mk("detection", []))
    r.register(_mk("advisor", ["detection"]))
    r.register(_mk("report", ["advisor"]))
    assert r.resolution_order(["advisor", "detection"]) == ["detection", "advisor"]


# --- reload(reimport=True) against a real module on disk ---
def test_reload_reimport_picks_up_code_changes(tmp_path, monkeypatch):
    import importlib
    import sys

    mod_name = "sentinel_tmp_agent_mod"
    mod_file = tmp_path / f"{mod_name}.py"

    def write(caps):
        mod_file.write_text(
            "from app.ai.agents import BaseAgent, AgentConfig\n"
            "class TmpAgent(BaseAgent):\n"
            f"    config = AgentConfig(id='tmp', name='Tmp', version='1.0.0')\n"
            f"    capabilities = {caps!r}\n"
            "    def execute(self, request):\n"
            "        return {}\n",
            encoding="utf-8",
        )

    monkeypatch.syspath_prepend(str(tmp_path))
    write(["v1"])
    module = importlib.import_module(mod_name)
    try:
        reg = AgentRegistry()
        reg.register(module.TmpAgent)
        assert reg.descriptor("tmp").capabilities == ["v1"]

        # change the source on disk, then hot-reload
        write(["v1", "v2"])
        desc = reg.reload("tmp", reimport=True)
        assert desc.capabilities == ["v1", "v2"]
        assert reg.find_by_capability("v2") == ["tmp"]
    finally:
        sys.modules.pop(mod_name, None)
