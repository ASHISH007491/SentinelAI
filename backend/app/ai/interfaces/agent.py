"""Agent contract.

The platform-level interface every agent satisfies, independent of the concrete
BaseAgent implementation. Code that orchestrates agents can depend on this Protocol
rather than the base class, keeping the dependency pointing inward.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.ai.agents.config import AgentConfig
    from app.ai.agents.models import AgentRequest, AgentResult


@runtime_checkable
class Agent(Protocol):
    config: AgentConfig

    def run(self, request: AgentRequest) -> AgentResult:
        """Execute the agent and return a JSON-only result (never raises)."""
        ...
