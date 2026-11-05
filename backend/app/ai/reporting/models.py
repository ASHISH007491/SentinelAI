"""Structured report types: one source of truth, two views (JSON + markdown)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.ai.types.aliases import JSON


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


_RANK = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


def severity_rank(sev: Severity) -> int:
    return _RANK[sev]


class Finding(BaseModel):
    """A single actionable item produced by an agent, with a remediation recommendation."""

    id: str
    source: str                       # agent id that produced it
    title: str
    severity: Severity = Severity.INFO
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    recommendation: str = ""          # the grounded 'advisor' action
    evidence: JSON = Field(default_factory=dict)


class SecurityReport(BaseModel):
    run_id: str = ""
    generated_at: str = ""
    findings: list[Finding] = Field(default_factory=list)
    severity_counts: dict[str, int] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)
    executive_summary: str = ""

    def to_json(self) -> JSON:
        return self.model_dump(mode="json")

    def to_markdown(self) -> str:
        lines = [
            "# SentinelAI Security Report",
            f"Run: {self.run_id or 'n/a'} · Generated: {self.generated_at or 'n/a'}",
            "",
            "## Executive summary",
            self.executive_summary or "No findings.",
            "",
            f"## Findings ({len(self.findings)})",
        ]
        for f in self.findings:
            lines += [
                f"### [{f.severity.value.upper()}] {f.title}",
                f"- Source: {f.source} · Confidence: {f.confidence:.2f}",
                f"- {f.summary}" if f.summary else "",
                f"- **Recommended action:** {f.recommendation}"
                if f.recommendation else "",
                "",
            ]
        if self.recommendations:
            lines.append("## Prioritised recommendations")
            lines += [f"{i}. {r}" for i, r in enumerate(self.recommendations, 1)]
        return "\n".join(line for line in lines if line is not None)
