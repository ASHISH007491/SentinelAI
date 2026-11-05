"""Agent base class and shared execution context."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.agents.schemas import AgentResult
from app.core.llm_client import LLMClient, Usage


@dataclass
class AgentContext:
    """Carries everything an agent needs plus accumulated state across the pipeline."""
    workflow: str
    artefact_text: str = ""
    artefact_names: list[str] = field(default_factory=list)
    llm: LLMClient = field(default_factory=LLMClient)
    # Findings flow forward through the pipeline (detection -> prioritisation -> ...).
    findings: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    def record_usage(self, u: Usage) -> None:
        self.usage.prompt_tokens += u.prompt_tokens
        self.usage.completion_tokens += u.completion_tokens


class Agent(ABC):
    name: str = "agent"

    @abstractmethod
    def run(self, ctx: AgentContext) -> AgentResult: ...
