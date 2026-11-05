"""Recommendation Engine (Prompt 064).

Turns prioritised findings into actionable, de-duplicated recommendations classified by
horizon (immediate / short-term / long-term), priority, impact, effort and estimated
risk reduction. Every recommendation carries reasoning.
"""
from __future__ import annotations

from app.ai.advisor.models import (
    PrioritisedFinding,
    Recommendation,
    RiskLevel,
    severity_weight,
)

_HORIZON = {
    RiskLevel.CRITICAL: "immediate", RiskLevel.HIGH: "immediate",
    RiskLevel.MEDIUM: "short_term", RiskLevel.LOW: "long_term",
    RiskLevel.INFORMATIONAL: "long_term",
}
_IMPACT = {RiskLevel.CRITICAL: "high", RiskLevel.HIGH: "high", RiskLevel.MEDIUM: "medium",
           RiskLevel.LOW: "low", RiskLevel.INFORMATIONAL: "low"}
# Systemic long-term improvements, keyed by the finding source that triggers them.
_SYSTEMIC = {
    "code_review": ("Adopt secure-coding practices",
                    "Introduce SAST in CI and developer secure-coding training.", "high"),
    "phishing_verdict": ("Strengthen email authentication",
                         "Enforce SPF/DKIM/DMARC and run phishing-awareness training.", "medium"),
    "prioritisation": ("Establish risk-based patching",
                       "Prioritise patching by EPSS/KEV, not CVSS alone.", "medium"),
}


class RecommendationEngine:
    def recommend(self, prioritised: list[PrioritisedFinding]) -> list[Recommendation]:
        recs: list[Recommendation] = []
        seen_actions: set[str] = set()

        for i, f in enumerate(prioritised):
            action = self._action(f)
            key = action.strip().lower()
            if key in seen_actions:
                recs[self._index_of(recs, key)].related.append(f.title)
                continue
            seen_actions.add(key)
            reduction = round(severity_weight(f.risk_level) * f.confidence, 3)
            recs.append(Recommendation(
                id=f"rec-{i}", title=f"Remediate: {f.title}", action=action,
                horizon=_HORIZON[f.risk_level], priority=f.risk_level,
                impact=_IMPACT[f.risk_level], effort=self._effort(f), risk_reduction=reduction,
                reasoning=f"{f.risk_level.value.title()} risk ({f.rationale}); "
                          "acting reduces exposure.",
                related=[f.title],
            ))

        for source, (title, action, effort) in _SYSTEMIC.items():
            if any(f.source == source for f in prioritised) and action.lower() not in seen_actions:
                seen_actions.add(action.lower())
                recs.append(Recommendation(
                    id=f"rec-sys-{source}", title=title, action=action, horizon="long_term",
                    priority=RiskLevel.MEDIUM, impact="medium", effort=effort,
                    risk_reduction=0.3,
                    reasoning="Systemic improvement addressing the root cause of findings.",
                ))
        return recs

    @staticmethod
    def _index_of(recs: list[Recommendation], key: str) -> int:
        return next(i for i, r in enumerate(recs) if r.action.strip().lower() == key)

    @staticmethod
    def _action(f: PrioritisedFinding) -> str:
        return f.recommendation.strip() or "Review and remediate the identified issue."

    @staticmethod
    def _effort(f: PrioritisedFinding) -> str:
        if f.source == "code_review":
            return "medium"
        if f.cve:
            return "low"      # usually a patch
        return "medium"
