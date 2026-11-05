"""Report agent: compile the run into a structured deliverable."""
from __future__ import annotations

from datetime import datetime, timezone

from app.agents.base import Agent, AgentContext
from app.agents.schemas import AgentResult


class ReportAgent(Agent):
    name = "report"

    def run(self, ctx: AgentContext) -> AgentResult:
        findings = ctx.findings
        counts: dict[str, int] = {}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "workflow": ctx.workflow,
            "artefacts": ctx.artefact_names,
            "total_findings": len(findings),
            "severity_counts": counts,
            "findings": [f.model_dump() for f in findings],
            "tokens_used": ctx.usage.total_tokens,
        }
        return AgentResult(
            agent=self.name,
            summary=(
                f"Compiled report: {len(findings)} finding(s) "
                f"across {len(ctx.artefact_names)} artefact(s)"
            ),
            data=report,
        )
