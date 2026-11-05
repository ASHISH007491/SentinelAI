# SentinelAI — LLM Service (Phase 2, Prompt 013)

The central service every agent uses to talk to a model. Contains no agent logic.
Lives at `backend/app/ai/llm/service/`.

## Components

| Component | File | Responsibility |
|-----------|------|----------------|
| `LLMFactory` | `factory.py` | Build a provider from a `ModelSpec`. |
| `ModelManager` / `ModelSpec` | `model_manager.py` | Resolve which model/provider/temperature an agent uses (env + per-agent). |
| `PromptExecutor` | `executor.py` | Run a request through cache → rate limit → retry(timeout) → token/cost accounting. Streaming + JSON output. |
| `TokenCounter` | `token_counter.py` | Token counting (tiktoken if installed, else heuristic). |
| `ResponseCache` | `cache.py` | In-memory TTL cache for temperature-0 completions. |
| `RateLimiter` | `rate_limiter.py` | Token-bucket limiter (injectable clock). |
| `CostTracker` | `cost.py` | Per-model price table → USD cost, totals by model. |
| Providers | `providers.py` | `OpenAIProvider`, `OllamaProvider`, `OfflineProvider` (+ streaming). |
| `LLMService` | `service.py` | Facade composing all of the above. |

## Providers

- **OpenAI** — `OpenAIProvider`, OpenAI chat-completions via the `openai` SDK.
- **Ollama** — `OllamaProvider`, local models through Ollama's OpenAI-compatible
  endpoint (`http://localhost:11434/v1`, no API key).
- **Offline** — `OfflineProvider`, deterministic, network-free. The safe default so
  the service (and its tests) run with zero configuration.

## Switching models via environment variables

Global defaults come from settings (`.env`):
```
LLM_PROVIDER=openai          # offline | openai | ollama  (blank = auto-detect)
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=                # optional; e.g. http://localhost:11434/v1 for Ollama
LLM_API_KEY=sk-...
LLM_TEMPERATURE=0.0
```

Per-agent overrides (different models for different agents) — no code change:
```
LLM_PROVIDER__DETECTION=ollama
LLM_MODEL__DETECTION=llama3.1
LLM_TEMPERATURE__DETECTION=0.2
```
`ModelManager.resolve("detection")` merges these over the global defaults. You can
also register a `ModelSpec` programmatically (`mm.register("vuln", spec)`), which
takes highest precedence.

## Usage

```python
from app.ai.llm.service import LLMService

svc = LLMService()                              # offline by default
text  = svc.complete("Summarise the risk", agent_id="advisor").text
data  = svc.complete_json('Return {"score": int}', agent_id="prioritisation")
for chunk in svc.stream("Explain step by step", agent_id="advisor"):
    print(chunk, end="")
print(svc.total_cost_usd)                       # accumulated USD cost
```

Features available on every call: **retry** (transient errors), soft **timeout**,
**caching** (temperature-0 only), **rate limiting**, **cost tracking**, **token
counting**, **structured JSON output** (`json_output=True` / `complete_json`),
**temperature** configuration, and **streaming**.

## Tests

`backend/tests/ai/llm/` — 17 tests covering token counting, cache hit/TTL, rate
limiting, cost accumulation, the factory, env + programmatic model resolution,
executor (usage fill, cache, rate limit, JSON instruction), streaming, and the
service facade (per-agent routing, JSON parse, cost, streaming). All run offline.

```
cd backend && pytest tests/ai/llm -q
```

## Notes

- The cache only stores deterministic (temperature 0) responses.
- Timeout is soft (thread-based) — correct for I/O-bound model calls; see BASE_AGENT.md.
- This service supersedes the earlier `ai/llm/client.py`; agents migrate onto it as
  they are (re)built. No agent logic lives here.
