"""Maps workflow -> ordered agent pipeline, and a single-agent baseline."""
from __future__ import annotations

from app.agents.advisor import AdvisorAgent
from app.agents.base import Agent
from app.agents.detection import CodeReviewAgent, DetectionAgent, PhishingDetectionAgent
from app.agents.prioritisation import PrioritisationAgent
from app.agents.report import ReportAgent

WORKFLOW_PIPELINES: dict[str, list[Agent]] = {
    "vuln": [DetectionAgent(), PrioritisationAgent(), AdvisorAgent(), ReportAgent()],
    "phishing": [PhishingDetectionAgent(), PrioritisationAgent(), AdvisorAgent(), ReportAgent()],
    "code_review": [CodeReviewAgent(), PrioritisationAgent(), AdvisorAgent(), ReportAgent()],
}


def pipeline_for(workflow: str) -> list[Agent]:
    return WORKFLOW_PIPELINES.get(workflow, WORKFLOW_PIPELINES["vuln"])
