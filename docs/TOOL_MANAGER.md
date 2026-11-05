# SentinelAI — Tool Manager (Phase 2, Prompt 018)

Lets AI agents use tools **safely**: registration, enable/disable, input validation,
timeout, execution logging, and metadata. Interfaces for the five future tools are
included, but **no cybersecurity functionality yet**. Lives at `backend/app/ai/tools/`.

## A tool

A tool subclasses `BaseTool`, declares a Pydantic `Input` (validation + JSON-schema
metadata) and identity, and implements `_run`. It never handles validation, timeout,
or logging — the manager does:

```python
from pydantic import BaseModel
from app.ai.tools import BaseTool

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
```

## ToolManager

```python
from app.ai.tools import ToolManager
m = ToolManager()
m.register(AddTool())
m.run("add", {"a": 2, "b": 3})        # ToolResult(success=True, output={"sum": 5})
```

| Feature | API |
|---------|-----|
| Register tool | `register(tool, enabled=, replace=)`, `unregister(name)` |
| Enable / disable | `enable(name)`, `disable(name)`, `is_enabled(name)` |
| Validate inputs | automatic via the tool's Pydantic `Input` → `ToolValidationError` |
| Timeout | per-tool `timeout_s` (or `run(..., timeout_s=)`); soft, thread-based |
| Execution logging | `executions(name=)` → `ToolExecution` records |
| Tool metadata | `metadata(name)`, `list_metadata()` → name, version, enabled, tags, JSON-schema |
| Discovery | `names()`, `name in manager` |

### Per-agent permissions (tool allow-lists)

Agents can be restricted to a subset of tools:

```python
m.grant("phishing_agent", "knowledge_search", "threat_intel")  # allow-list
m.run("database", {...}, agent_id="phishing_agent")            # -> ToolPermissionError
m.permissions("phishing_agent")   # {"knowledge_search", "threat_intel"}
m.revoke("phishing_agent", "threat_intel")
```

An agent with **no** policy (or `agent_id=None`) has open access to any enabled tool;
once it's granted any tool, it's restricted to its allow-list. `run(..., agent_id=)`
enforces this before execution, raising `ToolPermissionError` on denial.

### Safety model

- **Pre-condition failures raise**: unknown tool (`ToolNotFoundError`), disabled tool
  (`ToolDisabledError`), bad input (`ToolValidationError`), permission denied
  (`ToolPermissionError`).
- **Execution failures don't crash the agent**: errors inside `_run` (including
  timeout and not-implemented) return a structured `ToolResult(success=False, error,
  code)` instead of propagating.
- **Logs store argument *keys* only, never values** — sensitive inputs aren't recorded.
- Thread-safe (re-entrant lock); soft timeout via a worker thread.

`get_tool_manager()` returns a process-wide default manager.

## Future tool interfaces (interface-only)

`register_builtin_interfaces(manager)` registers five tools **disabled** (not yet
implemented). Each has a documented input schema for discovery; calling one returns
`ToolResult(success=False, code="tool_not_implemented")`.

| Tool | Input | Purpose (future) |
|------|-------|------------------|
| `database` | query, params, limit | read-only datastore query |
| `filesystem` | path, mode | sandboxed file read/list/stat |
| `threat_intel` | indicator, indicator_type | indicator lookup in TI feeds |
| `cve_search` | query, max_results | CVE search |
| `knowledge_search` | query, top_k | RAG over the knowledge base |

These are interfaces only — the cybersecurity behaviour is implemented in a later phase.

## Tests

`backend/tests/ai/test_tool_manager.py` — 10 tests: registration + metadata,
duplicate rejection, unknown tool, successful run, input validation, enable/disable
gating, timeout → failed result, execution logging (keys not values), and the future
interfaces (registered, disabled, documented, not-implemented on run).

```
cd backend && pytest tests/ai/test_tool_manager.py -q
```
