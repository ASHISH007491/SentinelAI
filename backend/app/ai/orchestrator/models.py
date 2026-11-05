"""Pydantic models for orchestrator I/O (JSON-only contracts)."""
from __future__ import annotations

import enum

from pydantic import BaseModel, Field

from app.ai.models.messages import TokenUsage
from app.ai.types.aliases import JSON, Metadata


class OrchestratorStatus(str, enum.Enum):
    COMPLETED = "completed"   # all required agents succeeded
    DEGRADED = "degraded"     # some agents failed; partial result returned
    FAILED = "failed"         # could not proceed / required agent aborted


class OrchestratorRequest(BaseModel):
    run_id: str = ""
    session_id: str = ""
    user_id: int | None = None
    project_id: int | None = None
    # Routing inputs (any one drives agent selection):
    query: str = ""                                  # free text -> intent
    workflow: str | None = None                      # explicit capability/workflow
    capabilities: list[str] = Field(default_factory=list)
    agents: list[str] = Field(default_factory=list)  # explicit agent ids (highest precedence)
    optional_agents: list[str] = Field(default_factory=list)
    # Payload passed to agents:
    artefact_text: str = ""
    artefacts: list[str] = Field(default_factory=list)
    params: JSON = Field(default_factory=dict)


class Intent(BaseModel):
    workflow: str = ""
    capabilities: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "fallback"  # explicit | llm | fallback


class PlanStep(BaseModel):
    agent_id: str
    optional: bool = False
    depends_on: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)
    levels: list[list[str]] = Field(default_factory=list)  # dependency layers (parallelisable)

    @property
    def agent_ids(self) -> list[str]:
        return [s.agent_id for s in self.steps]


class OrchestratorMetrics(BaseModel):
    total_ms: float = 0.0
    agents_run: int = 0
    agents_failed: int = 0
    retries: int = 0
    levels: int = 0
    tokens: TokenUsage = Field(default_factory=TokenUsage)


class OrchestratorResult(BaseModel):
    run_id: str
    status: OrchestratorStatus
    intent: Intent = Field(default_factory=Intent)
    outputs: dict[str, JSON] = Field(default_factory=dict)   # agent_id -> output
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    metrics: OrchestratorMetrics = Field(default_factory=OrchestratorMetrics)
    metadata: Metadata = Field(default_factory=dict)

    def to_json(self) -> JSON:
        return self.model_dump(mode="json")
