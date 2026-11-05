"""prioritisation agent — stub for the runnable skeleton (real logic in Phase 3)."""
from __future__ import annotations

from sentinelai_agents.agents.base import Agent
from sentinelai_agents.contracts.base import AgentInput, AgentOutput


class PrioritisationAgent(Agent):
    name = "prioritisation"

    def run(self, inp: AgentInput) -> AgentOutput:
        return AgentOutput(agent=self.name, summary="stub: prioritisation")
