"""AgentOutput response schema."""
from datetime import datetime

from pydantic import BaseModel


class AgentOutputRead(BaseModel):
    id: int
    agent_name: str
    output: dict
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
