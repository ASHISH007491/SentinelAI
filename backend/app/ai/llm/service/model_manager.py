"""Resolve which model/provider/temperature an agent should use.

Resolution order (highest first):
  1. programmatic override registered via `register(agent_id, spec)`
  2. per-agent environment overrides: LLM_MODEL__<AGENT>, LLM_PROVIDER__<AGENT>,
     LLM_TEMPERATURE__<AGENT>
  3. global defaults from application settings (env / .env)
This lets different agents use different models, switched purely via env vars.
"""
from __future__ import annotations

import os

from pydantic import BaseModel

from app.core.config import settings


class ModelSpec(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    api_key: str = ""
    base_url: str = ""

    model_config = {"frozen": True}


def _default_provider() -> str:
    explicit = (getattr(settings, "llm_provider", "") or "").strip()
    if explicit:
        return explicit
    if not settings.llm_api_key:
        return "offline"
    if getattr(settings, "llm_base_url", ""):
        return "openai"  # OpenAI-compatible base URL
    return "openai"


class ModelManager:
    def __init__(self) -> None:
        self._overrides: dict[str, ModelSpec] = {}

    def register(self, agent_id: str, spec: ModelSpec) -> None:
        self._overrides[agent_id] = spec

    def default_spec(self) -> ModelSpec:
        return ModelSpec(
            provider=_default_provider(),
            model=settings.llm_model,
            temperature=float(getattr(settings, "llm_temperature", 0.0) or 0.0),
            api_key=settings.llm_api_key or "",
            base_url=getattr(settings, "llm_base_url", "") or "",
        )

    def resolve(self, agent_id: str | None = None) -> ModelSpec:
        if agent_id and agent_id in self._overrides:
            return self._overrides[agent_id]
        spec = self.default_spec()
        if not agent_id:
            return spec
        key = agent_id.upper().replace("-", "_")
        provider = os.environ.get(f"LLM_PROVIDER__{key}", spec.provider)
        model = os.environ.get(f"LLM_MODEL__{key}", spec.model)
        temp = os.environ.get(f"LLM_TEMPERATURE__{key}")
        return spec.model_copy(update={
            "provider": provider,
            "model": model,
            "temperature": float(temp) if temp is not None else spec.temperature,
        })
