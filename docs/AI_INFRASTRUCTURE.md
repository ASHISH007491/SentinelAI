# SentinelAI — AI Infrastructure (Phase 2, Prompt 011)

Reusable, agent-agnostic AI platform that every future agent and workflow builds on.
It contains **no business logic and no cybersecurity agents** — only the primitives
they compose. Lives at `backend/app/ai/`.

## Design

Clean architecture; dependencies point inward. Inner layers never import outer ones.

```
            ┌─────────── core (config · errors · logging) ───────────┐
            │   depended on by everything                            │
  types  ◄─ models ◄─ interfaces ◄─ { llm · prompts · state · utils · workflows }
 (enums,   (pydantic   (Protocols/    (concrete implementations)
  aliases)  contracts)  ABCs)
```

- **types** — primitive enums (`LLMRole`, `Provider`, `StepStatus`) and aliases (`JSON`, `Metadata`).
- **models** — Pydantic contracts: `LLMMessage`, `LLMRequest`, `LLMResponse`, `TokenUsage`, `StepResult`, `WorkflowResult`.
- **interfaces** — the boundaries: `LLMProvider`, `PromptRenderer`, `StateStore`, `Step`, `Workflow`.
- **core** — `AIConfig` + `load_ai_config()`, the `AIError` hierarchy, and a namespaced `get_logger`.
- **llm** — `LLMClient`, a provider-agnostic implementation of `LLMProvider`.
- **prompts** — `PromptTemplate` + `PromptRegistry`.
- **state** — `BaseState` (threaded through a workflow) + `InMemoryStateStore`.
- **utils** — `extract_json`, `retry`, `estimate_tokens`, `Timer`.
- **workflows** — `SequentialWorkflow` (pure Python), a lazy LangGraph runner, and `WorkflowRegistry`.

## LLM access (free-tier friendly)

`LLMClient` reads `AIConfig` and supports three providers, chosen automatically:

| Condition | Provider | Use |
|-----------|----------|-----|
| no `LLM_API_KEY` | `offline` | returns empty completions → callers use deterministic fallbacks. Runs/tests need no key. |
| key set, no base URL | `anthropic` | Anthropic native (`claude-*`). |
| key + `LLM_BASE_URL` set | `openai_compatible` | any OpenAI-compatible endpoint — **Groq, Gemini, OpenRouter** (free tiers). |

Example `.env` for a free Groq key:
```
LLM_API_KEY=<groq key>
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
```

Every call goes through one method and records `TokenUsage`, so cost accounting is
consistent across all agents and the single-agent baseline.

## Usage sketch (how an agent will use this)

```python
from app.ai.interfaces.step import Step
from app.ai.state.base import BaseState
from app.ai.workflows import SequentialWorkflow

class MyStep(Step):
    name = "example"
    def run(self, state: BaseState) -> BaseState:
        state.note("did work")
        return state

workflow = SequentialWorkflow("demo", [MyStep()])
result = workflow.run(BaseState(run_id="r1"))   # -> WorkflowResult with per-step timing + usage
```

A `SequentialWorkflow` isolates each step's failure, records per-step latency and
token usage, and stops on the first failure. The LangGraph runner
(`ai/workflows/langgraph_runner.build_state_graph`) offers the same Step semantics
compiled to a `StateGraph` when branching/checkpointing is needed; LangGraph is
imported lazily, so the platform runs and tests without it installed.

## Tests

`backend/tests/ai/` — 19 unit tests across config, types/models, errors, prompts,
state/utils, the offline LLM client, and workflows. Run:
```
cd backend && pytest tests/ai -q
```

## What this is not

No agents, no prompts with security content, no orchestration of real analysis —
those are Phase 2 prompts 012+ (one agent at a time), each composed from these
primitives.
