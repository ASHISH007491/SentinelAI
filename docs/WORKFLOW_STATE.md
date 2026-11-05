# SentinelAI — Shared Workflow State (Phase 2, Prompt 015)

The single Pydantic state object threaded through a LangGraph run. Every agent reads
from and writes to it. Fully serialisable, persistable, and recoverable. No agent
logic — only state and the transitions over it. Lives at `backend/app/ai/state/`.

## What it tracks (`WorkflowState`)

| Field | Type | Purpose |
|-------|------|---------|
| `user` | `UserRef` | current user (id, email) |
| `project` | `ProjectRef` | current project (id, name) |
| `files` | `list[FileRef]` | uploaded files |
| `running` / `completed` / `failed` | `list[str]` | agent lifecycle |
| `current_step` | `str \| None` | the agent in progress (for recovery) |
| `outputs` | `dict[str, JSON]` | per-agent output |
| `execution_ms` | `dict[str, float]` | per-agent timing (+ `total_execution_ms`) |
| `conversation` | `list[Message]` | conversation context |
| `recommendations` | `list[Recommendation]` | advisor recommendations |
| `reports` | `list[ReportRef]` | generated reports |
| `errors` / `warnings` | `list[Note]` | diagnostics |
| `status` | `WorkflowStatus` | pending / running / completed / failed / recovered |
| `created_at` / `updated_at` | `datetime` | bookkeeping |

## Transitions

```python
from app.ai.state import WorkflowState

s = WorkflowState(run_id="run-1")
s.start_agent("detection")
s.complete_agent("detection", output={"findings": []}, latency_ms=120)
s.start_agent("prioritisation")
s.fail_agent("prioritisation", "schema error")   # records an error note
s.add_recommendation("Patch xz", priority="P0")
s.add_report("Executive Summary", kind="executive")
s.finish()        # -> FAILED (because an agent failed), else COMPLETED
```

`pending_agents(expected)` returns the agents in `expected` that haven't run yet
(not completed, failed, or running) — the basis for resuming.

## Serialization

`state.to_json()` / `WorkflowState.from_json(data)` round-trip the entire state
(including timestamps, nested models, outputs) via Pydantic.

## Persistence

A `StateRepository` checkpoints state by `run_id`:

- `InMemoryStateRepository` — tests/dev.
- `FileStateRepository(dir)` — durable JSON, one file per run, **atomic writes**
  (temp file + `replace`) so a crash never leaves a partial checkpoint.

```python
from app.ai.state import FileStateRepository
repo = FileStateRepository("var/checkpoints")
repo.save(state)                 # checkpoint after each step
repo.list_runs()                 # ["run-1", ...]
state = repo.load("run-1")
```

## Recovery

```python
from app.ai.state import recover
state = recover(repo, "run-1")
```

`recover()` loads the last checkpoint and calls `mark_recovered()`: still-`running`
(interrupted) agents are cleared so they re-execute, while `completed`/`failed`
progress is preserved, status becomes `RECOVERED`, and a warning is recorded. The
orchestrator then resumes from `pending_agents(expected)`.

## Tests

`backend/tests/ai/test_workflow_state.py` — 9 tests: lifecycle transitions, finish
status, pending computation, JSON round-trip, in-memory + file repositories, and
recovery of an interrupted run. Run:

```
cd backend && pytest tests/ai/test_workflow_state.py -q
```

## Notes

- `WorkflowState` is a plain Pydantic model and can be used directly as a LangGraph
  state schema. It complements the lightweight `BaseState` (used by the simple
  `SequentialWorkflow`); use `WorkflowState` when you need the full run picture.
- Persistence/recovery aren't wired into the running pipeline yet — that happens when
  the orchestrator is rebuilt on the platform (deliberately deferred, tracked).
