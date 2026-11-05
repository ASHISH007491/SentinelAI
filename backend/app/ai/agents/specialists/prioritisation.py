"""PrioritisationAgent: rank CVEs by patch urgency with justification."""
from __future__ import annotations

from app.ai.agents.base import BaseAgent
from app.ai.agents.config import AgentConfig
from app.ai.core.errors import LLMError
from app.ai.types.aliases import JSON
from app.ai.utils.json_parse import ask_json

_SYSTEM = "You are a vulnerability triage assistant. Reply with JSON only."


class PrioritisationAgent(BaseAgent):
    config = AgentConfig(
        id="prioritisation",
        name="Vulnerability Prioritisation Agent",
        description="Ranks CVEs by real-world patch urgency (EPSS/KEV/CVSS).",
        version="1.0.0",
    )
    capabilities = ["prioritise"]
    dependencies: list[str] = []
    retryable_errors = (LLMError,)

    def execute(self, request: JSON) -> JSON:  # type: ignore[override]
        cves = request.inputs.get("cves", [])  # type: ignore[attr-defined]
        # Optional pre-assessment from an upstream RiskSignalAgent: {cve_id: {"level": ...}}.
        # When present, ranking is decomposed (assess tier, then finalise order by tier);
        # when absent, this collapses to the original single-shot ranking prompt.
        risk = request.inputs.get("risk")  # type: ignore[attr-defined]

        def _line(c: dict) -> str:
            base = (f"- {c.get('cve_id')}: CVSS={c.get('cvss')} EPSS={c.get('epss')} "
                    f"KEV={c.get('kev')} exploit={c.get('exploit_available')}")
            if risk:
                level = risk.get(c.get("cve_id"), {}).get("level", "unknown")
                base += f" risk={level.upper()}"
            return base + f" :: {c.get('description', '')}"

        listing = "\n".join(_line(c) for c in cves)
        if risk:
            prompt = (
                "Finalise the CVE patch order using the pre-assessed risk tiers below as the "
                "primary signal, breaking ties within a tier by CVSS. "
                'Reply with ONLY a JSON object: {"order": [cve_id, ...], '
                '"rationale": {cve_id: reason}}.\n'
                f"{listing}"
            )
        else:
            prompt = (
                "Order these CVEs from most to least urgent to patch, prioritising real-world "
                "exploitation (EPSS) and known-exploited status (KEV) over raw severity. "
                'Reply with ONLY a JSON object: {"order": [cve_id, ...], '
                '"rationale": {cve_id: reason}}.\n'
                f"{listing}"
            )
        data, _ = ask_json(self.generate, prompt, system=_SYSTEM)
        data = data or {}
        known = [c.get("cve_id") for c in cves]
        order = self._normalise_order(known, data.get("order") or [])
        return {"order": order, "rationale": data.get("rationale", {})}

    @staticmethod
    def _normalise_order(known: list[str], proposed: list[str]) -> list[str]:
        known_set = set(known)
        seen: set[str] = set()
        out: list[str] = []
        for x in proposed:
            if x in known_set and x not in seen:
                out.append(x)
                seen.add(x)
        out.extend(c for c in known if c not in seen)
        return out
