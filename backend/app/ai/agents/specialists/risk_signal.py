"""RiskSignalAgent: step 1 of the prioritisation pipeline (independent risk-tier assessment).

Assesses each CVE's exploitation risk tier (high/medium/low) on its own, before the
PrioritisationAgent uses that pre-assessment to finalise the patch order. This is what
makes multi-agent prioritisation architecturally distinct from the single-LLM baseline's
one-shot ranking (see prioritisation.py) rather than a relabelled copy of it.
"""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json

_SYSTEM = "You are a vulnerability risk assessor. Reply with JSON only."
_LEVELS = ("high", "medium", "low")


class RiskSignalAgent(BaseAgent):
    config = AgentConfig(
        id="risk_signal",
        name="Risk Signal Agent",
        description="Independently assesses each CVE's exploitation risk tier before ranking.",
        version="1.0.0",
    )
    capabilities = ["assess_risk"]
    dependencies: list[str] = []
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        cves = request.inputs.get("cves", [])  # type: ignore[attr-defined]
        listing = "\n".join(
            f"- {c.get('cve_id')}: CVSS={c.get('cvss')} EPSS={c.get('epss')} "
            f"KEV={c.get('kev')} exploit={c.get('exploit_available')} :: {c.get('description', '')}"
            for c in cves
        )
        prompt = (
            "Assess the exploitation risk tier (high/medium/low) for each CVE below, "
            "independently of any final patch order. "
            'Reply with ONLY a JSON object: {"risk": {cve_id: {"level": "high|medium|low", '
            '"note": "..."}}}.\n'
            f"{listing}"
        )
        data, _ = ask_json(self.generate, prompt, system=_SYSTEM)
        risk = (data or {}).get("risk")
        if not isinstance(risk, dict):
            risk = {}
        out: dict[str, dict[str, str]] = {}
        for c in cves:
            cid = c.get("cve_id")
            entry = risk.get(cid)
            if not isinstance(entry, dict):
                entry = {}
            level = str(entry.get("level", "medium")).strip().lower()
            if level not in _LEVELS:
                level = "medium"
            out[cid] = {"level": level, "note": str(entry.get("note", ""))}
        return {"risk": out}
