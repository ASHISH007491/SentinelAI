# SentinelAI — Intent Detection (Phase 3)

Understands what a user request is asking for and turns it into actionable routing
data: **intent + confidence + required agents + workflow**. Rule-based and extensible;
optionally refined by an LLM. Supports **multiple intents** at once and **future
intents**. No domain logic — capabilities/workflows are generic strings. Lives at
`backend/app/ai/orchestrator/intent_detection.py`.

## Supported intents

| Intent | Signals (keywords / file types) | Workflow | Capabilities |
|--------|----------------------------------|----------|--------------|
| `upload_scan` | scan, vulnerability, sbom, sarif · `.sarif`/`.sbom` | vuln | scan, vuln |
| `upload_email` | email, phishing, spoof · `.eml`/`.msg` | phishing | phishing |
| `upload_source_code` | code, review, repository · `.py`/`.js`/`.ts`/… | code_review | code_review |
| `generate_report` | report, summary, export, executive | report | report |
| `view_dashboard` | dashboard, overview, status, metrics | dashboard | — |
| `security_question` | how, what, explain, advice, recommend | advisor | advise |
| `threat_intelligence` | threat, intel, cve, mitre, ioc, indicator | knowledge | knowledge, threat_intel |
| `unknown` | (fallback when nothing matches) | — | — |

**Multiple Requests** = the result contains more than one intent (`result.multiple`).

## How it scores

For each registered `IntentDefinition`:

- keyword present as a **whole word** (regex word-boundary, so "scandalous" does *not*
  match "scan") → **+1** (recorded in `matched`)
- uploaded file with a matching extension → **+2** (a file is a strong signal)
- explicit workflow hint equals the definition's workflow → **+4**

`confidence = min(1.0, 0.25 + 0.2 × score)`. Intents scoring above `min_confidence`
(default 0.3) are returned, sorted by confidence; the top one is `primary`. If nothing
matches, a single `unknown` intent (confidence 0) is returned.

### Optional LLM refinement

If an `llm_service` is injected, `detect()` asks it which intent types apply (from the
registered vocabulary only) and blends the answer with the rules: an intent confirmed
by both is **boosted** (+0.2, tagged `llm`); an LLM-only intent is **added** at moderate
confidence. It can never invent an intent outside the vocabulary, and any failure
(offline/parse error) silently falls back to the rule-based result. Without an
`llm_service`, detection is fully deterministic.

## Output

```python
from app.ai.orchestrator.intent_detection import IntentDetector

det = IntentDetector(registry=agent_registry)        # registry optional
result = det.detect("scan this sbom and generate a report", files=["x.sbom"])

result.multiple          # True
result.primary.type      # IntentType.UPLOAD_SCAN
result.primary.confidence
result.primary.workflow            # "vuln"
result.primary.capabilities        # ["scan", "vuln"]
result.primary.required_agents     # resolved from the registry by capability
result.to_json()
```

Each `DetectedIntent` carries `type`, `confidence`, `capabilities`, `required_agents`
(resolved from the registry when provided), `workflow`, and the `matched` signals.

## Extensibility (future intents)

`detector.register(IntentDefinition(...))` adds or overrides an intent — new intents
are pure config (keywords, extensions, capabilities, workflow), no code changes to the
detector. An injected `llm_service` can be used to refine/disambiguate on top of the
deterministic core.

## Tests

`backend/tests/ai/orchestrator/test_intent_detection.py` — 14 tests: each supported
intent, multi-intent detection + ordering, confidence + JSON contract, unknown
fallback, explicit-workflow dominance, registry-resolved required agents, definition
override/extensibility, and a check that all supported intents have definitions.

```
cd backend && pytest tests/ai/orchestrator/test_intent_detection.py -q
```

## Notes

- Deterministic core runs with no LLM/network — fully testable offline.
- Feeds the Orchestrator/Planner: `capabilities` → agents, `workflow` → pipeline.
- Complements the lighter `IntentClassifier` (Prompt 022); this is the richer,
  multi-intent, capability-mapping detector.
