"""Tests for the Tool Manager and the future-tool interfaces."""
import time

import pytest
from pydantic import BaseModel

from app.ai.core.errors import ToolDisabledError, ToolNotFoundError, ToolValidationError
from app.ai.tools import BaseTool, ToolManager, register_builtin_interfaces


class AddTool(BaseTool):
    name = "add"
    description = "Add two integers"
    version = "2.0.0"
    tags = ["math"]

    class Input(BaseModel):
        a: int
        b: int

    def _run(self, params):
        return {"sum": params.a + params.b}


class SlowTool(BaseTool):
    name = "slow"
    timeout_s = 0.1

    class Input(BaseModel):
        pass

    def _run(self, params):
        time.sleep(0.5)
        return {}


@pytest.fixture()
def manager():
    m = ToolManager()
    m.register(AddTool())
    return m


# --- registration / discovery / metadata ---
def test_register_and_metadata(manager):
    assert "add" in manager and manager.names() == ["add"]
    md = manager.metadata("add")
    assert md.version == "2.0.0" and md.tags == ["math"]
    assert "a" in md.input_schema["properties"] and "b" in md.input_schema["properties"]


def test_duplicate_registration_rejected(manager):
    from app.ai.core.errors import ToolError
    with pytest.raises(ToolError):
        manager.register(AddTool())
    manager.register(AddTool(), replace=True)  # replace allowed


def test_unknown_tool_raises(manager):
    with pytest.raises(ToolNotFoundError):
        manager.run("ghost", {})


# --- execution + input validation ---
def test_run_success(manager):
    result = manager.run("add", {"a": 2, "b": 3})
    assert result.success and result.output == {"sum": 5}
    assert result.latency_ms >= 0


def test_input_validation_error(manager):
    with pytest.raises(ToolValidationError):
        manager.run("add", {"a": "not-an-int", "b": 1})


# --- enable / disable ---
def test_disable_blocks_execution(manager):
    manager.disable("add")
    assert manager.is_enabled("add") is False
    with pytest.raises(ToolDisabledError):
        manager.run("add", {"a": 1, "b": 1})
    manager.enable("add")
    assert manager.run("add", {"a": 1, "b": 1}).success


# --- timeout ---
def test_timeout_returns_failed_result():
    m = ToolManager()
    m.register(SlowTool())
    result = m.run("slow", {})
    assert result.success is False and result.code == "ai_tool_timeout"


# --- execution logging ---
def test_execution_logging_records_keys_not_values(manager):
    manager.run("add", {"a": 1, "b": 2})
    manager.run("add", {"a": 9, "b": 9})
    log = manager.executions(name="add")
    assert len(log) == 2
    assert log[0].arg_keys == ["a", "b"]      # keys only
    assert log[0].success is True
    # values are never stored in the log (safety)
    assert all(not hasattr(e, "args") for e in log)


# --- future tool interfaces ---
def test_future_interfaces_registered_disabled_and_documented():
    m = ToolManager()
    register_builtin_interfaces(m)
    assert set(m.names()) == {
        "database", "filesystem", "threat_intel", "cve_search", "knowledge_search"
    }
    for name in m.names():
        assert m.is_enabled(name) is False              # disabled (not implemented)
        assert m.metadata(name).input_schema["properties"]  # has a documented input schema


def test_future_interface_run_reports_not_implemented():
    m = ToolManager()
    register_builtin_interfaces(m)
    m.enable("cve_search")
    result = m.run("cve_search", {"query": "log4j"})
    assert result.success is False and result.code == "tool_not_implemented"


# --- per-agent tool permissions ---
def test_open_access_by_default(manager):
    # No policy for this agent -> may use any enabled tool.
    assert manager.permissions("analyst") is None
    assert manager.run("add", {"a": 1, "b": 1}, agent_id="analyst").success
    # No agent_id at all -> also open.
    assert manager.run("add", {"a": 1, "b": 1}).success


def test_grant_restricts_to_allowlist():
    m = ToolManager()
    m.register(AddTool())

    class MulTool(BaseTool):
        name = "mul"

        class Input(BaseModel):
            a: int
            b: int

        def _run(self, params):
            return {"prod": params.a * params.b}

    m.register(MulTool())

    m.grant("limited", "add")            # now restricted to {"add"}
    assert m.permissions("limited") == {"add"}
    assert m.run("add", {"a": 2, "b": 3}, agent_id="limited").success

    from app.ai.core.errors import ToolPermissionError
    with pytest.raises(ToolPermissionError):
        m.run("mul", {"a": 2, "b": 3}, agent_id="limited")


def test_revoke_removes_permission(manager):
    manager.grant("limited", "add")
    assert manager.can_use("limited", "add") is True
    manager.revoke("limited", "add")
    assert manager.can_use("limited", "add") is False
    from app.ai.core.errors import ToolPermissionError
    with pytest.raises(ToolPermissionError):
        manager.run("add", {"a": 1, "b": 1}, agent_id="limited")


def test_grant_unknown_tool_rejected(manager):
    with pytest.raises(ToolNotFoundError):
        manager.grant("limited", "ghost")
