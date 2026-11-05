"""SecurityAdvisor (Prompt 062): the final reasoning consumer.

Ingests the other agents' outputs and produces a unified, explainable SecurityAssessment
— prioritised risks, an explainable 0-100 posture score, actionable recommendations, and
executive / technical / business summaries. It performs NO scanning, detection or review;
it only consumes findings. Async + dependency-injected.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.ai.advisor.models import (
    AgentFinding,
    RiskLevel,
    SecurityAssessment,
    coerce_risk,
)
from app.ai.advisor.prioritisation import RiskPrioritisationEngine
from app.ai.advisor.recommendations import RecommendationEngine
from app.ai.advisor.scoring import SecurityScoreEngine
from app.ai.types.aliases import JSON


def _posture(score: int) -> str:
    if score >= 90:
        return "Strong"
    if score >= 70:
        return "Moderate"
    if score >= 50:
        return "Weak"
    return "Critical exposure"


class SecurityAdvisor:
    def __init__(self, *, prioritiser: RiskPrioritisationEngine | None = None,
                 scorer: SecurityScoreEngine | None = None,
                 recommender: RecommendationEngine | None = None) -> None:
        self._prioritiser = prioritiser or RiskPrioritisationEngine()
        self._scorer = scorer or SecurityScoreEngine()
        self._recommender = recommender or RecommendationEngine()

    @staticmethod
    def normalise(agent_outputs: list[JSON]) -> list[AgentFinding]:
        """Flatten each agent's findings into normalised AgentFindings."""
        findings: list[AgentFinding] = []
        for out in agent_outputs:
            source = str(out.get("agent_name") or out.get("agent") or "unknown")
            payload = out.get("output", out)
            for f in (payload.get("findings") or []):
                ev = f.get("evidence") or {}
                cvss = float(f.get("cvss", 0) or 0)
                exploit = 1.0 if ev.get("kev") else 0.6 if ev.get("exploit_available") \
                    else min(1.0, cvss / 10.0)
                findings.append(AgentFinding(
                    source=source, title=str(f.get("title", "finding")),
                    severity=coerce_risk(f.get("severity")), cvss=cvss,
                    cve=f.get("cve"), exploitability=exploit,
                    confidence=float(f.get("confidence", 0.5) or 0.5),
                    asset_criticality=float(f.get("asset_criticality", 0.5) or 0.5),
                    business_impact=str(f.get("business_impact", "")),
                    recommendation=str(f.get("recommendation", "")),
                    description=str(f.get("evidence") or f.get("description") or ""),
                ))
        return findings

    async def assess(self, agent_outputs: list[JSON], *, run_id: str = "") -> SecurityAssessment:
        findings = self.normalise(agent_outputs)
        prioritised = self._prioritiser.prioritise(findings)
        score = self._scorer.score(prioritised)
        recommendations = self._recommender.recommend(prioritised)
        posture = _posture(score.overall)

        counts = {lvl: sum(1 for p in prioritised if p.risk_level is lvl) for lvl in RiskLevel}
        crit_high = counts[RiskLevel.CRITICAL] + counts[RiskLevel.HIGH]
        top = prioritised[0] if prioritised else None
        immediate = [r for r in recommendations if r.horizon == "immediate"]

        exec_summary = (
            f"Security posture: {posture} ({score.overall}/100). "
            f"{len(prioritised)} finding(s), {crit_high} critical/high. "
            + (f"Top priority: {top.title} — {top.recommendation or 'remediate'}. "
               if top else "No actionable findings. ")
            + f"{len(immediate)} immediate action(s) recommended."
        )
        technical_summary = "; ".join(
            f"{counts[lvl]} {lvl.value}" for lvl in RiskLevel if counts[lvl]
        ) or "no findings"
        business_impact = next(
            (p.title for p in prioritised
             if p.risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)),
            "No material business impact identified.",
        )
        if crit_high:
            business_impact = (f"{crit_high} high-severity issue(s) could lead to breach, "
                               f"data loss or service disruption if unaddressed.")

        return SecurityAssessment(
            run_id=run_id,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            posture=posture, score=score, prioritised=prioritised,
            recommendations=recommendations, executive_summary=exec_summary,
            technical_summary=f"Findings by risk: {technical_summary}.",
            business_impact=business_impact,
        )
