"""Security Score Engine (Prompt 066).

Explainable 0-100 scores: an overall posture plus per-domain scores. Each finding
deducts points by risk level; every score carries a short explanation.
"""
from __future__ import annotations

from app.ai.advisor.models import PrioritisedFinding, RiskLevel, SecurityScore

_PENALTY = {RiskLevel.CRITICAL: 25, RiskLevel.HIGH: 12, RiskLevel.MEDIUM: 5,
            RiskLevel.LOW: 2, RiskLevel.INFORMATIONAL: 0}
_DOMAIN_SOURCES = {
    "vulnerability": {"prioritisation", "detection", "vuln"},
    "phishing": {"phishing_verdict", "phishing_detection", "indicator_extraction"},
    "code_security": {"code_review"},
    "threat_exposure": {"threat_intel", "threat_intelligence"},
}


def _score_for(findings: list[PrioritisedFinding]) -> tuple[int, str]:
    penalty = sum(_PENALTY[f.risk_level] for f in findings)
    value = max(0, 100 - penalty)
    counts = {lvl: sum(1 for f in findings if f.risk_level is lvl) for lvl in RiskLevel}
    parts = [f"{counts[lvl]} {lvl.value}" for lvl in RiskLevel if counts[lvl]]
    explanation = (f"{value}/100 — " + ", ".join(parts) + f" (−{penalty})") if parts \
        else f"{value}/100 — no findings"
    return value, explanation


class SecurityScoreEngine:
    def score(self, prioritised: list[PrioritisedFinding]) -> SecurityScore:
        overall, overall_exp = _score_for(prioritised)
        explanation = {"overall": overall_exp}
        domain_values: dict[str, int] = {}
        for domain, sources in _DOMAIN_SOURCES.items():
            subset = [f for f in prioritised if f.source in sources]
            val, exp = _score_for(subset)
            domain_values[domain] = val
            explanation[domain] = exp
        confidence = (sum(f.confidence for f in prioritised) / len(prioritised)
                      if prioritised else 1.0)
        return SecurityScore(
            overall=overall,
            vulnerability=domain_values["vulnerability"],
            phishing=domain_values["phishing"],
            code_security=domain_values["code_security"],
            threat_exposure=domain_values["threat_exposure"],
            confidence=round(confidence, 3),
            explanation=explanation,
        )
