"""Common agent interface."""
from __future__ import annotations

from abc import ABC, abstractmethod

from sentinelai_agents.contracts.base import AgentInput, AgentOutput


class Agent(ABC):
    name: str = "agent"

    @abstractmethod
    def run(self, inp: AgentInput) -> AgentOutput: ...
