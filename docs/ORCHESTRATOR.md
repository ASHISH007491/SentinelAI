# SentinelAI — Orchestrator (Phase 3 Implementation)

The coordination layer that turns a request into agent calls. It **performs no domain
analysis** — it understands intent, plans, dispatches agents over shared state, handles
failures, and returns one consolidated JSON response. Built on the AI platform; lives
at `backend/app/ai/orchestrator/`.

## Components (one class each)

| Component | File | Role |
|-----------|------|------|
| `Orchestrator` | `orchestrator.py` | Public async entrypoint; ties everything together |
| `WorkflowExecutor` | `executor.py` | Runs the plan level-by-level (parallel within a level) |
| `StateManager` | `components.py` | Creates/mutates the shared `WorkflowState` |
| `AgentDispatcher` | `dispatcher.py` | Instantiates + runs one agent (async + retry) |
| `ResponseCollector` | `collector.py` | Consolidates state → `OrchestratorResult` |
| `FailureHandler` | `components.py` | Decides continue/abort on a failure |
| `RetryManager` | `components.py` | Decides whether a failed result is retryable |
| `ExecutionLogger` | `components.py` | Structured, run-scoped logging |
| `MetricsCollector` | `components.py` | Aggregates run metrics |
| `IntentClassifier` | `intent.py` | Request → structured `Intent` (LLM or deterministic) |
| `Planner` | `planner.py` | Intent → dependency-ordered, parallelisable `ExecutionPlan` |

## The six methods (`Orchestrator`)

- `validate_request(request)` — reject empty/under-specified requests.
- `route(request) -> (Intent, ExecutionPlan)` — classify intent, select + order agents.
- `async run_agents(plan, request, state, log) -> bool` — execute the plan.
- `merge_results(run_id, state, intent, metrics, aborted) -> OrchestratorResult`.
- `handle_errors(request, intent, exc) -> OrchestratorResult` — unexpected failures → JSON.
- `async execute(request) -> OrchestratorResult` — the pipeline entrypoint.

## Pipeline

```
validate → route (classify intent → plan) → run_agents (levels, parallel) → merge_results
                                                   │
                                       failure → retry / skip-optional / abort
```

- **Async**: agents (synchronous `BaseAgent`s) run in worker threads, so independent
  agents in the same dependency level run **concurrently** (`asyncio.gather`). Verified
  by a test: three 0.1 s agents finish in < 0.25 s on multiple threads.
- **Dependency ordering**: the Planner pulls in transitive dependencies from the Agent
  Registry and lays agents out in levels (Kahn by layer); each level runs in parallel,
  levels run in order.
- **Selection**: explicit `agents` list > `capabilities`/`workflow` > LLM-classified
  intent over the registry's capability vocabulary (deterministic offline fallback).

## Result contract (JSON-only)

`OrchestratorResult{run_id, status, intent, outputs{agent_id→output}, errors, warnings,
trace, metrics{total_ms, agents_run, agents_failed, retries, levels, tokens}}` →
`.to_json()`.

**Status semantics:** `completed` (all required agents succeeded) · `degraded` (some
agents failed but partial output returned — optional failures become *warnings*) ·
`failed` (no capable agents, or a required agent aborted the run).

## Failure, retry, timeout

- **Two-layer retry**: each agent retries its own transient errors (`BaseAgent`); the
  Orchestrator's `RetryManager` re-dispatches a *failed* result when retryable (never
  for validation/permission/config errors).
- **Failure policy**: optional agent fails → skipped + warning; required agent fails
  (fail-fast) → run aborts → `failed`; otherwise `degraded` with partial outputs.
- **Per-agent timeouts** inherited from the agent/LLM layers — one slow/failed agent
  never crashes the run.
- **Per-run timeout budget** (`run_timeout_s`): before each level the executor checks a
  wall-clock deadline; on breach it stops scheduling, records a warning, and returns a
  `degraded` result with whatever completed.

## Memory & persistence (injected)

When a `MemoryService` is injected, the Orchestrator:

- **Recalls** recent session conversation into `state.metadata["recalled_context"]`.
- **Writes execution history** (scope `EXECUTION`) per agent and a run summary — so a
  session accumulates a queryable history of what ran.

When a `StateRepository` is injected, state is **checkpointed after each level**, making
runs resumable. All memory/checkpoint writes are best-effort (never break a run).

## Tool permissions (injected)

When a `ToolManager` is injected, the dispatcher **grants each agent exactly the tools it
declares** (`tools_required` class attribute) on the shared manager before running it —
so an agent can only use its allow-listed tools.

## Dependency injection & extensibility

Every collaborator is constructor-injectable (`registry`, `llm_service`, `tool_manager`,
`intent_classifier`, `planner`, `retry_manager`, `failure_handler`); platform defaults
are used otherwise. **Adding a new agent requires zero Orchestrator changes** — it's
discovered through the registry by capability + dependencies (open/closed).

## Tests

`backend/tests/ai/orchestrator/test_orchestrator.py` — 9 async tests: request
validation, capability routing + dependency ordering, end-to-end JSON result, no-agents
failure, required-failure abort, optional-failure degrade, dispatcher retry, **parallel
execution of independent agents**, and explicit-agent override.

```
cd backend && pytest tests/ai/orchestrator -q
```

## Notes

- No cybersecurity logic — capability tags are generic strings; the Orchestrator imports
  no specialised agent.
- Added a `usage` field (token-sum reducer) to `WorkflowState` so the Orchestrator can
  aggregate per-agent token cost.
- Not yet exposed via `/api/v1` and the specialised agents aren't built on the platform
  yet — those are the next Phase 3 steps. This is the orchestration brain they plug into.
