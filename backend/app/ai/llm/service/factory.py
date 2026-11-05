"""Construct a provider from a ModelSpec."""
from __future__ import annotations

from app.ai.core.errors import ConfigurationError
from app.ai.interfaces.llm import LLMProvider
from app.ai.llm.service.model_manager import ModelSpec
from app.ai.llm.service.providers import OfflineProvider, OllamaProvider, OpenAIProvider


class LLMFactory:
    @staticmethod
    def create(spec: ModelSpec) -> LLMProvider:
        provider = spec.provider.lower()
        if provider == "offline":
            return OfflineProvider(model=spec.model)
        if provider == "openai":
            return OpenAIProvider(spec.model, api_key=spec.api_key, base_url=spec.base_url or None)
        if provider == "ollama":
            return OllamaProvider(spec.model, base_url=spec.base_url or None)
        raise ConfigurationError(f"Unknown LLM provider '{spec.provider}'")
