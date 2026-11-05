"""Prioritisation agent: rank findings by exploitation-aware urgency.

EPSS/KEV-aware, not severity-alone: a known-exploited (KEV) or high-EPSS finding
outranks a higher-CVSS one that nobody exploits -- the premise of the dissertation's
Track A. Deterministic and explainable; when no exploitation signals are present it
reduces to the classic severity-then-CVSS order (backward compatible).
"""
from __future__ import annotations

import argparse
import json

from app.agents.base import Agent, AgentContext
from app.agents.schemas import AgentResult, Finding

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


# EPSS >= 10% chance of exploitation in 30 days is the commonly-used "actionable" bar.
# Below it we do NOT let EPSS override severity: a missing/negligible EPSS must not
# outrank a critical finding (absence of evidence is not evidence of safety).
_EPSS_SIGNIFICANT = 0.1


def priority_key(f: Finding) -> tuple:
    """Ascending sort key -- most urgent first.

    Tiers: KEV -> public exploit -> *significant* EPSS -> severity -> CVSS -> confidence.
    Findings whose EPSS is unknown/negligible fall through to the classic
    severity-then-CVSS ordering rather than being ranked on a near-zero probability.
    """
    epss_significant = f.epss >= _EPSS_SIGNIFICANT
    return (
        0 if f.kev else 1,
        0 if f.exploit_available else 1,
        0 if epss_significant else 1,
        -f.epss if epss_significant else 0.0,
        _SEVERITY_RANK.get(f.severity, 4),
        -f.cvss,
        -f.confidence,
    )


def rationale_for(f: Finding, rank: int) -> str:
    if f.kev:
        return f"#{rank}: known-exploited (CISA KEV) -- patch first despite CVSS {f.cvss:g}."
    if f.exploit_available:
        return f"#{rank}: public exploit available; EPSS {f.epss:.2f}."
    if f.epss >= 0.5:
        return f"#{rank}: high exploitation probability (EPSS {f.epss:.2f}), above CVSS alone."
    if f.epss > 0.0:
        return (
            f"#{rank}: low exploitation probability (EPSS {f.epss:.2f}); "
            f"ranked by {f.severity}/CVSS {f.cvss:g}."
        )
    return f"#{rank}: no known exploitation; ranked by {f.severity}/CVSS {f.cvss:g}."


class PrioritisationAgent(Agent):
    name = "prioritisation"

    def run(self, ctx: AgentContext) -> AgentResult:
        ranked = sorted(ctx.findings, key=priority_key)
        ctx.findings = ranked
        counts: dict[str, int] = {}
        rationales: list[str] = []
        for i, f in enumerate(ranked, start=1):
            counts[f.severity] = counts.get(f.severity, 0) + 1
            rationales.append(rationale_for(f, i))
        top = ranked[0].title if ranked else "no findings"
        kev_count = sum(1 for f in ranked if f.kev)
        return AgentResult(
            agent=self.name,
            findings=ranked,
            summary=(
                f"Prioritised {len(ranked)} finding(s); "
                f"{kev_count} known-exploited; top risk: {top}"
            ),
            data={"severity_counts": counts, "order": [f.title for f in ranked],
                  "rationale": rationales, "kev_count": kev_count},
        )


def _severity_from_cvss(cvss: float) -> str:
    if cvss >= 9.0:
        return "critical"
    if cvss >= 7.0:
        return "high"
    if cvss >= 4.0:
        return "medium"
    if cvss > 0.0:
        return "low"
    return "info"


def _load_findings(path: str) -> list[Finding]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        Finding(
            title=item.get("description") or item.get("cve_id", "unknown"),
            cve=item.get("cve_id"),
            cvss=item.get("cvss", 0.0),
            epss=item.get("epss", 0.0),
            kev=item.get("kev", False),
            exploit_available=item.get("exploit_available", False),
            severity=_severity_from_cvss(item.get("cvss", 0.0)),
        )
        for item in raw
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rank CVE findings by exploitation-aware urgency (EPSS/KEV-aware)."
    )
    parser.add_argument("--input", required=True, help="Path to a JSON file of CVE findings.")
    args = parser.parse_args()

    ctx = AgentContext(workflow="prioritisation", findings=_load_findings(args.input))
    result = PrioritisationAgent().run(ctx)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
