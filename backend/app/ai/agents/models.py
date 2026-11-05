"""Structured, JSON-serialisable agent I/O and metrics."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.ai.models.messages import TokenUsage
from app.ai.types.aliases import JSON, Metadata
from app.ai.types.enums import StepStatus


class AgentRequest(BaseModel):
    """Generic input to an agent. Subclasses validate/interpret `inputs`."""
    run_id: str = ""
    inputs: JSON = Field(default_factory=dict)
    artefact_text: str = ""
    artefacts: list[str] = Field(default_factory=list)
    metadata: Metadata = Field(default_factory=dict)


class AgentMetrics(BaseModel):
    latency_ms: float = 0.0
    retries: int = 0
    tool_calls: int = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)
    success: bool = True


class AgentErrorInfo(BaseModel):
    code: str
    message: str
    type: str


class AgentResult(BaseModel):
    """The single, JSON-only return type of every agent run."""
    agent_id: str
    agent_name: str
    version: str = "1.0.0"
    status: StepStatus = StepStatus.COMPLETED
    output: JSON = Field(default_factory=dict)
    error: AgentErrorInfo | None = None
    metrics: AgentMetrics = Field(default_factory=AgentMetrics)

    def to_json(self) -> JSON:
        """Return a pure-JSON dict (enums/sub-models flattened)."""
        return self.model_dump(mode="json")
