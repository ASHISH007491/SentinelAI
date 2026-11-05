"""Phase 3 end-to-end demo: a real request through the real orchestrator, real
specialist agents, and dispatcher — with a deterministic fake LLM standing in for
the network call, so the trace is reproducible offline (no API keys required).

Prints the full trace (intent, agents invoked, tokens, latency) and the
aggregated output, demonstrating the orchestrator -> dispatcher -> specialist
agent -> response pipeline end-to-end.

Run as: python -m app.ai.orchestrator.demo "prioritise these CVEs"
"""
from __future__ import annotations

import asyncio
import json
import sys

from app.ai.agents import AgentRegistry
from app.ai.agents.specialists import (
    CodeReviewAgent,
    IndicatorExtractionAgent,
    PrioritisationAgent,
)
from app.ai.models.messages import LLMResponse, TokenUsage
from app.ai.orchestrator import Orchestrator, OrchestratorRequest


class _FakeProvider:
    """Deterministic, offline stand-in for a real LLM backend, used only so this
    demo's trace is reproducible without network access or API keys."""

    available = True

    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, request) -> LLMResponse:  # noqa: ARG002 - protocol requires the param
        return LLMResponse(
            text=self._reply, usage=TokenUsage(prompt_tokens=42, completion_tokens=18)
        )


_SAMPLE_CVES = [
    {"cve_id": "CVE-2024-0001", "cvss": 7.5, "epss": 0.94, "kev": True,
     "exploit_available": True, "description": "Actively exploited RCE"},
    {"cve_id": "CVE-2024-0002", "cvss": 9.8, "epss": 0.02, "kev": False,
     "exploit_available": False, "description": "Critical CVSS, no known exploitation"},
]

_CAPABILITY_HINTS = {
    "prioritise": ("priorit", "cve", "patch", "rank"),
    "code_review": ("code", "review", "cwe", "vulnerab"),
    "extract_indicators": ("phish", "email", "indicator"),
}


def _guess_capability(query: str) -> str:
    """Tiny local keyword mapping, standing in for real NLP intent detection so
    this demo can run offline. The orchestrator's own IntentClassifier does real
    LLM-based classification when a live LLM service is configured."""
    q = query.lower()
    for cap, hints in _CAPABILITY_HINTS.items():
        if any(h in q for h in hints):
            return cap
    return "prioritise"


def _build_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(
        lambda **kw: PrioritisationAgent(
            llm=_FakeProvider(json.dumps({
                "order": ["CVE-2024-0001", "CVE-2024-0002"],
                "rationale": {"CVE-2024-0001": "KEV + high EPSS outranks raw CVSS"},
            })),
            **kw,
        ),
        id="prioritise", name="Vulnerability Prioritisation Agent",
        capabilities=["prioritise"],
    )
    registry.register(
        lambda **kw: CodeReviewAgent(
            llm=_FakeProvider(json.dumps({
                "vulnerable": True, "cwe": "CWE-89", "confidence": 0.87,
                "rationale": "string-built SQL query", "fix": "use parameterised queries",
            })),
            **kw,
        ),
        id="code_review", name="Secure Code Review Agent",
        capabilities=["code_review"],
    )
    registry.register(
        lambda **kw: IndicatorExtractionAgent(
            llm=_FakeProvider(json.dumps({
                "urls": ["http://secure-login.example-verify.com"],
                "sender_domain": "example-verify.com", "auth_pass": False,
                "urgency": True, "credential_request": True,
                "signals": ["urgency", "spoofed-domain"],
            })),
            **kw,
        ),
        id="extract_indicators", name="Indicator Extraction Agent",
        capabilities=["extract_indicators"],
    )
    return registry


def _params_for(capability: str) -> dict:
    if capability == "prioritise":
        return {"cves": _SAMPLE_CVES}
    if capability == "code_review":
        return {"language": "python",
                "code": 'cur.execute(f"SELECT * FROM users WHERE id={user_id}")'}
    return {"body": "Your account will be suspended, verify now.",
            "sender": "support@example-verify.com"}


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('usage: python -m app.ai.orchestrator.demo "<request text>"')
        return 2

    request_text = argv[1]
    capability = _guess_capability(request_text)

    registry = _build_registry()
    orch = Orchestrator(registry=registry)
    request = OrchestratorRequest(
        query=request_text, capabilities=[capability], params=_params_for(capability),
    )
    result = asyncio.run(orch.execute(request))

    print(f"query:      {request_text!r}")
    print(f"intent:     capabilities={result.intent.capabilities} source={result.intent.source}")
    print(f"status:     {result.status.value}")
    print(f"agents run: {result.metrics.agents_run} "
          f"(failed={result.metrics.agents_failed}, retries={result.metrics.retries})")
    print(f"latency:    {result.metrics.total_ms:.1f}ms "
          f"tokens={result.metrics.tokens.total_tokens}")
    print(f"trace:      {result.trace}")
    print("output:")
    print(json.dumps(result.outputs, indent=2))

    return 0 if result.status.value != "failed" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
