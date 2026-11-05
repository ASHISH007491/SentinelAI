"""Generic step/workflow result models (agent-agnostic)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.models.messages import TokenUsage
from app.ai.types.aliases import JSON
from app.ai.types.enums import StepStatus


class StepResult(BaseModel):
    name: str
    status: StepStatus = StepStatus.COMPLETED
    output: JSON = Field(default_factory=dict)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    error: str | None = None


class WorkflowResult(BaseModel):
    workflow: str
    status: StepStatus = StepStatus.COMPLETED
    steps: list[StepResult] = Field(default_factory=list)
    output: JSON = Field(default_factory=dict)

    @property
    def total_usage(self) -> TokenUsage:
        total = TokenUsage()
        for step in self.steps:
            total = total + step.usage
        return total
