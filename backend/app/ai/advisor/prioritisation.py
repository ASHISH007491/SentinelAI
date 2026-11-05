"""Risk Prioritisation Engine (Prompt 063).

Ranks findings using severity, CVSS, exploitability, asset criticality and confidence
into a single composite risk score, then buckets into Critical..Informational. Explains
every ranking and removes duplicate findings.
"""
from __future__ import annotations

from app.ai.advisor.models import (
    AgentFinding,
    PrioritisedFinding,
    RiskLevel,
    severity_weight,
)

# Composite weights (sum to 1.0).
_W_SEVERITY, _W_CVSS, _W_EXPLOIT, _W_ASSET, _W_CONF = 0.40, 0.20, 0.20, 0.10, 0.10


def _bucket(score: float) -> RiskLevel:
    if score >= 0.80:
        return RiskLevel.CRITICAL
    if score >= 0.60:
        return RiskLevel.HIGH
    if score >= 0.40:
        return RiskLevel.MEDIUM
    if score >= 0.20:
        return RiskLevel.LOW
    return RiskLevel.INFORMATIONAL


class RiskPrioritisationEngine:
    def prioritise(self, findings: list[AgentFinding]) -> list[PrioritisedFinding]:
        deduped = self._dedupe(findings)
        out: list[PrioritisedFinding] = []
        for f in deduped:
            score = (
                _W_SEVERITY * severity_weight(f.severity)
                + _W_CVSS * (f.cvss / 10.0)
                + _W_EXPLOIT * f.exploitability
                + _W_ASSET * f.asset_criticality
                + _W_CONF * f.confidence
            )
            out.append(PrioritisedFinding(
                source=f.source, title=f.title, risk_level=_bucket(score),
                risk_score=round(score, 4), severity=f.severity, cvss=f.cvss, cve=f.cve,
                confidence=f.confidence, recommendation=f.recommendation,
                rationale=self._rationale(f, score),
            ))
        out.sort(key=lambda p: p.risk_score, reverse=True)
        return out

    @staticmethod
    def _dedupe(findings: list[AgentFinding]) -> list[AgentFinding]:
        """Keep the strongest instance of each duplicate (by CVE, else title)."""
        best: dict[str, AgentFinding] = {}
        for f in findings:
            key = (f.cve or f.title).strip().lower()
            cur = best.get(key)
            if cur is None or severity_weight(f.severity) > severity_weight(cur.severity):
                best[key] = f
        return list(best.values())

    @staticmethod
    def _rationale(f: AgentFinding, score: float) -> str:
        bits = [f"severity={f.severity.value}"]
        if f.cvss:
            bits.append(f"CVSS={f.cvss}")
        if f.exploitability >= 0.5:
            bits.append("exploitable")
        if f.asset_criticality >= 0.7:
            bits.append("critical asset")
        bits.append(f"confidence={f.confidence:.0%}")
        return f"risk {score:.2f} from " + ", ".join(bits)
