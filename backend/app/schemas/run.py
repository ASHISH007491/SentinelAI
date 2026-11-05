"""Run I/O schemas."""
from datetime import datetime

from pydantic import BaseModel

from app.models.run import RunStatus, WorkflowType
from app.schemas.agent_output import AgentOutputRead
from app.schemas.artefact import ArtefactRead


class RunCreate(BaseModel):
    workflow: WorkflowType
    architecture: str = "multi"  # "multi" | "single"


class RunRead(BaseModel):
    id: int
    workflow: WorkflowType
    status: RunStatus
    architecture: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RunDetail(RunRead):
    completed_at: datetime | None = None
    artefacts: list[ArtefactRead] = []
    agent_outputs: list[AgentOutputRead] = []
