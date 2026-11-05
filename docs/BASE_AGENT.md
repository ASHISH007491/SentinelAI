# SentinelAI — BaseAgent Framework (Phase 2, Prompt 012)

The reusable foundation every SentinelAI agent inherits from. Built on the AI
platform (Prompt 011), designed to scale to 50+ agents. Lives at
`backend/app/ai/agents/`.

## What you get

| Feature | Where |
|---------|-------|
| Agent ID / Name / Description / Version | `AgentConfig` |
| Timeout (soft, per attempt) | `AgentConfig.timeout_s` → enforced in `run()` |
| Retry logic (transient errors only) | `AgentConfig.max_retries` / `retry_backoff_s` |
| Logging | namespaced `sentinelai.ai.<id>` logger |
| Validation | `validate()` hook → `ValidationError` |
| Error handling | `handle_error()` → failed `AgentResult` |
| Metrics | `AgentMetrics` (latency, retries, tokens, tool_calls, success) |
| Structured output (JSON only) | `AgentResult` / `.to_json()` |
| Prompt loading | injected `PromptRegistry` + `render_prompt()` |
| Tool registration | `ToolRegistry` + `use_tool()` |
| Model selection | `AgentConfig.model` (falls back to platform default) |
| Dependency injection | `llm`, `prompts`, `tools` all constructor-injectable |

## Lifecycle

`run(request)` is the template method that orchestrates the hooks and always
returns a JSON-only `AgentResult` (never raises):

```
initialize → validate → execute (timeout + retry) → post_process → cleanup
                                   │
                          any exception → handle_error → failed AgentResult
```

Concrete agents implement **only** `execute()`; the other hooks have sensible
defaults you can override.

## Writing an agent

```python
from app.ai.agents import AgentConfig, AgentRequest, BaseAgent

class GreetAgent(BaseAgent):
    config = AgentConfig(
        id="greet", name="Greeter", version="1.0.0",
        model=None,            # None -> platform default model
        timeout_s=30, max_retries=1,
        prompt_names=["greeting"],   # verified at initialize()
    )

    def validate(self, request: AgentRequest) -> None:
        super().validate(request)
        if "name" not in request.inputs:
            from app.ai.core.errors import ValidationError
            raise ValidationError("'name' is required")

    def execute(self, request: AgentRequest) -> dict:
        prompt = self.render_prompt("greeting", {"name": request.inputs["name"]})
        resp = self.generate(prompt, system="Be warm and brief.")
        return {"message": resp.text}

# Dependency injection (e.g. for tests or a free provider):
result = GreetAgent(llm=my_llm, prompts=my_registry).run(
    AgentRequest(inputs={"name": "Sam"})
)
print(result.to_json())   # pure JSON: {agent_id, status, output, metrics, ...}
```

## Behaviour notes

- **JSON only.** Every run returns an `AgentResult`; `.to_json()` flattens enums and
  sub-models. Failures are *also* JSON (`status: "failed"`, populated `error`).
- **Retries** apply only to `retryable_errors` (default: `LLMError`). `ValidationError`
  is never retried.
- **Timeout** is soft: the worker thread can't be force-killed, so a runaway call
  stops being awaited but may finish in the background — fine for I/O-bound LLM calls.
- **Metrics** accumulate automatically when subclasses use `self.generate(...)` and
  `self.use_tool(...)`.

## Tests

`backend/tests/ai/test_base_agent.py` — 11 tests: happy path + JSON contract, token
metrics, validation→JSON, model selection, retry / no-retry-on-validation, timeout,
tools, prompt loading, missing-prompt config error, and lifecycle ordering. Run:

```
cd backend && pytest tests/ai -q
```

## Relationship to the existing agents

The older `backend/app/agents/*` (detection, prioritisation, …) predate this
framework and still power the running pipeline. Prompts 013+ implement the real
agents on top of `BaseAgent`, one at a time; the legacy package will be retired
once they are migrated.
