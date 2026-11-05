"""Reporting service: build a SecurityReport from a run's agent outputs.

Wires the app/ai Reporting layer (the 5th component) into the live application: after
the agent pipeline finishes, consolidate every agent's findings into one analyst report
(with grounded remediation recommendations) and persist it as a final agent output.
Best-effort — a reporting failure must never fail an otherwise-successful run.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.reporting import ReportBuilder
from app.models.agent_output import AgentOutput
from app.models.run import Run

REPORT_AGENT_NAME = "security_report"


def build_run_report(db: Session, run: Run) -> AgentOutput:
    """Consolidate run.agent_outputs[*].output['findings'] into one SecurityReport row."""
    builder = ReportBuilder(run_id=str(run.id))
    for out in run.agent_outputs:
        if out.agent_name == REPORT_AGENT_NAME:
            continue
        findings = (out.output or {}).get("findings") or []
        if findings:
            builder.add_findings(out.agent_name, findings)
    report = builder.build()
    report_json = report.to_json()
    row = AgentOutput(
        run_id=run.id,
        agent_name=REPORT_AGENT_NAME,
        # Frontend-compatible shape (agent/summary/findings) + the full report payload.
        output={
            "agent": REPORT_AGENT_NAME,
            "summary": report.executive_summary,
            "findings": report_json["findings"],
            "report": report_json,
        },
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=0.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
