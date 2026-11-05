# SentinelAI — Agent Registry (Phase 2, Prompt 016)

A thread-safe, singleton registry where agents register themselves and are
discovered at runtime. Lives at `backend/app/ai/agents/registry.py`.

## Capabilities

| Need | API |
|------|-----|
| Dynamic registration | `register(cls, ...)` (direct), `@register_agent(...)` (decorator) |
| Agent discovery | `names()`, `discover(capability=, enabled_only=)`, `find_by_capability()` |
| Agent metadata | `descriptor(id)` → `AgentDescriptor` (id, name, version, description, caps, deps, enabled, health, metadata) |
| Health status | `health(id)`, `set_health(id, status)`, `health_check(id)` (invokes the agent's `health_check()`) |
| Dependencies | `descriptor(id).dependencies`, `missing_dependencies(id)`, `resolution_order()` (topological sort + cycle detection) |
| Capabilities | `descriptor(id).capabilities`, capability index for O(1) lookup |
| Version | `descriptor(id).version` |
| Enable / Disable | `enable(id)`, `disable(id)` (disabled agents can't be created) |
| Reload | `reload(id, reimport=False)` — re-derive descriptor from the class, optionally re-import its module |
| Instantiate | `create(id, **kwargs)` — builds an instance via the registered class/factory |

## Design

- **Singleton** — `AgentRegistry.instance()` / `get_agent_registry()` returns one
  shared, lazily-created instance (double-checked locking). `AgentRegistry()` can
  still be constructed directly for isolated tests.
- **Fast lookups** — agents are stored in a dict (`id → entry`, O(1)) plus a
  capability index (`capability → set[id]`, O(1)).
- **Thread-safe** — every read and write is guarded by a re-entrant lock; agent
  construction happens outside the lock. Verified with a 50-thread concurrent
  registration test.

## Usage

```python
from app.ai.agents import BaseAgent, AgentConfig, register_agent, get_agent_registry

@register_agent(capabilities=["scan", "detect"], dependencies=[])
class DetectionAgent(BaseAgent):
    config = AgentConfig(id="detection", name="Detection", version="1.2.0")

    @classmethod
    def health_check(cls):
        from app.ai.agents import AgentHealth
        return AgentHealth.HEALTHY

    def execute(self, request):
        return {"findings": []}

reg = get_agent_registry()
reg.find_by_capability("scan")          # ["detection"]
reg.descriptor("detection").version     # "1.2.0"
reg.health_check("detection")           # AgentHealth.HEALTHY
agent = reg.create("detection")          # an instance, ready to .run(...)
reg.disable("detection")                 # create() now raises until re-enabled
```

Registration derives id/name/version/description from the agent's `AgentConfig`
when present, so a class only needs its `config` plus optional `capabilities` /
`dependencies` (class attributes or `register()` kwargs).

## Dependency resolution

`resolution_order(agent_ids=None)` returns agents ordered so each appears **after**
its dependencies (Kahn's algorithm over the dependency graph, deterministic/
alphabetical among ready nodes). It raises `DependencyCycleError` on a cycle and
`AgentError` on an unknown agent — giving the orchestrator a safe execution order.

```python
reg.resolution_order()   # e.g. ['detection', 'prioritisation', 'advisor', 'report']
```

## Tests

`backend/tests/ai/test_agent_registry.py` — 15 tests: registration + discovery +
metadata, duplicate rejection + replace, capability lookup, instantiation,
enable/disable gating, reload (descriptor refresh + preserved enabled state),
**hot-reload via `reimport=True` against a real module on disk**, health check
(classmethod + fallback), missing-dependency detection, **topological
`resolution_order` + cycle detection + subset ordering**, the decorator + singleton
identity, and 50-thread concurrent registration.

```
cd backend && pytest tests/ai/test_agent_registry.py -q
```

## Notes

- `reload(reimport=True)` re-imports the agent's module to pick up code changes —
  useful for a plugin/hot-reload flow; default `reimport=False` just refreshes the
  descriptor from the current class.
- The registry stores classes/factories, not live singletons — `create()` returns a
  fresh instance each call (agents are cheap and stateless per run).
- Not yet populated by the running pipeline; agents register onto it as they are
  (re)built on the platform (tracked).
