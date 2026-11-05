"""Declarative configuration for an agent (identity + runtime policy)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Identity and execution policy for an agent instance.

    Subclasses provide a default via `BaseAgent.config`, and callers may override
    any field at construction time (dependency injection of configuration).
    """

    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"

    # Runtime policy
    model: str | None = None  # None -> platform default model
    timeout_s: float = 60.0  # soft timeout per execute() attempt; <=0 disables
    max_retries: int = 2  # additional attempts on retryable errors
    retry_backoff_s: float = 0.5

    # Prompt template names this agent expects to be registered.
    prompt_names: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}
