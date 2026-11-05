"""phishing_detection agent — stub for the runnable skeleton (real logic in Phase 3)."""
from __future__ import annotations

from sentinelai_agents.agents.base import Agent
from sentinelai_agents.contracts.base import AgentInput, AgentOutput


class PhishingDetectionAgent(Agent):
    name = "phishing_detection"

    def run(self, inp: AgentInput) -> AgentOutput:
        return AgentOutput(agent=self.name, summary="stub: phishing_detection")
