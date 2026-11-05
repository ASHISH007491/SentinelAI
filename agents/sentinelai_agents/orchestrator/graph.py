"""LangGraph orchestrator skeleton: routing, state passing, per-agent tracing.

Phase 2 wires this to echo agents; Phase 3 swaps in the real agents.
"""
from __future__ import annotations

from sentinelai_agents.contracts.base import AgentInput, AgentOutput, Workflow

# Map each workflow to the ordered agents it runs through.
WORKFLOW_ROUTES: dict[Workflow, list[str]] = {
    Workflow.VULN: ["detection", "prioritisation", "advisor", "report"],
    Workflow.PHISHING: ["phishing_detection", "advisor", "report"],
    Workflow.CODE_REVIEW: ["code_review", "advisor", "report"],
}


def run_workflow(inp: AgentInput) -> list[AgentOutput]:
    """Placeholder sequential runner. Replace with a compiled LangGraph StateGraph."""
    route = WORKFLOW_ROUTES[inp.workflow]
    return [AgentOutput(agent=name, summary=f"stub: {name}") for name in route]
