"""AI pipeline: run the app/ai specialist agents for a live run (the real engine).

Maps each workflow to its specialist agent(s), feeds the uploaded artefact in, and
converts every agent's structured output into the findings shape the web UI renders.
This is what makes the running product use the same multi-agent engine the dissertation
evaluates. Driven by whatever LLMProvider is supplied (Ollama locally, or Anthropic).
"""
from __future__ import annotations

import json
import time

from app.ai.agents.models import AgentRequest, AgentResult
from app.ai.agents.specialists import (
    CodeReviewAgent,
    IndicatorExtractionAgent,
    PhishingVerdictAgent,
    PrioritisationAgent,
)

_EXT_LANG = {"py": "python", "js": "javascript", "ts": "typescript", "java": "java",
             "go": "go", "rb": "ruby", "php": "php", "c": "c", "cpp": "cpp"}


def _row(result: AgentResult, findings: list[dict], summary: str, data: dict | None = None) -> dict:
    return {
        "agent_name": result.agent_id,   # stable id (code_review, phishing_verdict, ...)
        "output": {"agent": result.agent_id, "summary": summary,
                   "findings": findings, "data": data or {}},
        "prompt_tokens": result.metrics.tokens.prompt_tokens,
        "completion_tokens": result.metrics.tokens.completion_tokens,
        "latency_ms": result.metrics.latency_ms,
    }


def _parse_cves(text: str) -> list[dict]:
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return []
    if isinstance(data, dict):
        data = data.get("vulnerabilities") or data.get("cves") or []
    if isinstance(data, list):
        return [d for d in data if isinstance(d, dict) and (d.get("cve_id") or d.get("id"))]
    return []


def _guess_lang(names: list[str]) -> str:
    for n in names:
        ext = n.rsplit(".", 1)[-1].lower() if "." in n else ""
        if ext in _EXT_LANG:
            return _EXT_LANG[ext]
    return "python"


def run_ai_agents(workflow: str, text: str, names: list[str], provider) -> list[dict]:
    """Run the specialist agent(s) for a workflow, return AgentOutput row dicts."""
    if workflow == "phishing":
        return _run_phishing(text, provider)
    if workflow == "code_review":
        return _run_code(text, names, provider)
    return _run_vuln(text, provider)


def _run_vuln(text: str, provider) -> list[dict]:
    cves = _parse_cves(text)
    started = time.perf_counter()
    res = PrioritisationAgent(llm=provider).run(AgentRequest(inputs={"cves": cves}))
    order = (res.output or {}).get("order", []) if isinstance(res.output, dict) else []
    by_id = {c.get("cve_id") or c.get("id"): c for c in cves}
    findings = []
    for rank, cid in enumerate(order[:10], 1):
        row = by_id.get(cid, {})
        findings.append({
            "title": cid, "cve": cid, "severity": _sev(row),
            "cvss": float(row.get("cvss", 0) or 0), "component": "scan",
            "recommendation": f"Patch priority #{rank}"
            + (" — actively exploited (KEV)." if row.get("kev") else "."),
        })
    _ = started
    return [_row(res, findings, f"Prioritised {len(order)} vulnerabilities.",
                 {"order": order})]


def _sev(row: dict) -> str:
    if row.get("kev"):
        return "critical"
    cvss = float(row.get("cvss", 0) or 0)
    return "high" if cvss >= 9 else "medium" if cvss >= 7 else "low"


def _run_phishing(text: str, provider) -> list[dict]:
    ext = IndicatorExtractionAgent(llm=provider).run(
        AgentRequest(inputs={"sender": "", "subject": "", "headers": {}, "body": text}))
    ind = ext.output if isinstance(ext.output, dict) else {}
    ver = PhishingVerdictAgent(llm=provider).run(
        AgentRequest(inputs={"indicators": ind, "subject": "", "sender": ""}))
    out = ver.output if isinstance(ver.output, dict) else {}
    findings = []
    if out.get("is_phish"):
        conf = float(out.get("confidence", 0) or 0)
        findings.append({
            "title": "Phishing indicators detected",
            "severity": "high" if conf >= 0.7 else "medium",
            "cvss": 0.0, "component": "email",
            "recommendation": ("Quarantine the message, alert the recipient, "
                               "and block the sender domain."),
        })
    return [
        _row(ext, [], "Extracted phishing indicators.", ind),
        _row(ver, findings, str(out.get("rationale", "Phishing verdict.")), out),
    ]


def _run_code(text: str, names: list[str], provider) -> list[dict]:
    res = CodeReviewAgent(llm=provider).run(
        AgentRequest(inputs={"language": _guess_lang(names), "code": text}))
    out = res.output if isinstance(res.output, dict) else {}
    findings = []
    if out.get("vulnerable"):
        cwe = out.get("cwe")
        findings.append({
            "title": "Vulnerable code" + (f" ({cwe})" if cwe else ""), "cve": None,
            "severity": "high", "cvss": 0.0, "component": names[0] if names else "code",
            "recommendation": str(out.get("fix") or "Remediate per secure-coding guidance."),
        })
    return [_row(res, findings, str(out.get("rationale", "Code review complete.")), out)]
