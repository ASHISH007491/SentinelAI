"""Single-agent baseline: one prompt/agent with the same toolkit performs all tasks.

This is the experimental control that makes the dissertation's claims falsifiable.
"""
from __future__ import annotations

from sentinelai_agents.agents.base import Agent
from sentinelai_agents.contracts.base import AgentInput, AgentOutput


class SingleAgentBaseline(Agent):
    name = "single_agent_baseline"

    def run(self, inp: AgentInput) -> AgentOutput:
        return AgentOutput(agent=self.name, summary="stub: single-agent baseline")
