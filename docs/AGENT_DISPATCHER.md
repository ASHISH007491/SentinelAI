# SentinelAI — Agent Dispatcher (Phase 3)

A production dispatcher over the Agent Registry: discover agents, validate availability,
run them (in parallel for a batch), collect structured outputs, retry transient
failures, and log every dispatch. No domain logic — agents are referenced by id or
capability. Lives at `backend/app/ai/orchestrator/agent_dispatcher.py`.

## Responsibilities → API

| Responsibility | API |
|----------------|-----|
| **Discover agents** | `discover(capability=, agents=, available_only=)` |
| **Validate availability** | `validate(agent_id, min_version=)` → `AgentAvailability` |
| **Start execution / run agent** | `dispatch(agent_id, request)` → `DispatchResult` |
| **Run agents in parallel** | `await dispatch_many(ids, request, parallel=True)` / `dispatch_batch(...)` |
| **Collect outputs** | `DispatchReport.outputs` (`agent_id → output`) + per-agent results |
| **Retry failures** | `RetryManager` + capped exponential backoff with full jitter (`_backoff_delay`) |
| **Log execution** | structured logs on skip/retry/grant per dispatch |

Batch runs are bounded by `max_concurrency` (default 8) via an `asyncio.Semaphore`, so a
large fan-out throttles instead of saturating the thread pool. Backoff is configurable:
`retry_backoff_s` (base), `retry_backoff_cap_s` (ceiling, default 30s), `retry_jitter`.

## Availability validation

`validate()` checks, in order, and reports the first failing `reason`:

1. **registered** (in the registry — dynamic registration)
2. **enabled** (not disabled)
3. **dependencies** satisfied (`missing_dependencies` empty)
4. **health** (runs the agent's `health_check()` — not `unhealthy`)
5. **version** ≥ `min_version` (semantic comparison)

Only an `available` agent is run; otherwise `dispatch` returns `skipped` / `unavailable`.

## Result contracts (JSON)

```python
DispatchResult{agent_id, version, status, output, error, attempts, latency_ms, health}
# status: completed | failed | skipped | unavailable

DispatchReport{results[], succeeded, failed, skipped, total_ms}
report.outputs   # {agent_id: output} for completed agents
```

## Usage

```python
from app.ai.orchestrator.agent_dispatcher import AgentDispatcher
from app.ai.agents.models import AgentRequest

d = AgentDispatcher(registry, tool_manager=tools)         # DI; defaults to the singleton registry
ids = d.discover(capability="scan", available_only=True)  # discovery + availability filter
report = d.dispatch_batch(ids, AgentRequest(run_id="r1")) # parallel run + collect
report.outputs                                            # {agent_id: output}

# single, with a minimum version requirement
result = d.dispatch("detection", AgentRequest(run_id="r1"), min_version="2.0.0")
```

## Supported

- **Dynamic Registration** — works with whatever is registered in the Agent Registry;
  newly registered agents are immediately discoverable/dispatchable.
- **Versioning** — `DispatchResult.version` is recorded; `min_version` gates execution.
- **Health Checks** — `validate()` invokes the agent's `health_check()`; unhealthy
  agents are skipped (can be disabled via `health_check=False`).
- **Future Plugins** — plugin agents register into the same registry and are dispatched
  with no dispatcher changes; plugin tools are granted per-agent via the Tool Manager
  (`tools_required`).

## Tests

`backend/tests/ai/orchestrator/test_agent_dispatcher.py` — 12 tests: discovery
(capability/explicit/all), availability validation (unregistered, disabled, unhealthy,
missing-dependency, version-too-low), dispatch success (version + health recorded),
failure, skip-when-unavailable, retry-on-transient, **parallel batch with output
collection** (genuine concurrency), and mixed success/fail/skip reporting.

```
cd backend && pytest tests/ai/orchestrator/test_agent_dispatcher.py -q
```

## Notes

- Parallelism: synchronous agents run in worker threads (`asyncio.to_thread` +
  `gather`), so a batch executes concurrently while remaining easy to call from sync
  code (`dispatch_batch`).
- **Single source of truth for "run one agent".** The orchestrator's adapter
  (`dispatcher.py`) now delegates its create-agent + tool-grant + run mechanics to this
  dispatcher's `run_once()`, so there is one implementation, not two. The adapter only
  adds the `OrchestratorRequest → AgentRequest` mapping and the executor's async retry
  loop. Not yet exposed via `/api/v1`.
