"""AI platform configuration and loader.

Reads from the application settings (which load env / .env) and exposes a focused,
immutable AIConfig. Keeping AI config separate from the web app's Settings means AI
code depends only on what it needs.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel

from app.ai.core.errors import ConfigurationError
from app.ai.types.enums import Provider
from app.core.config import settings


class AIConfig(BaseModel):
    provider: Provider
    model: str
    api_key: str = ""
    base_url: str = ""
    max_tokens: int = 1024
    temperature: float = 0.0
    request_timeout_s: float = 60.0

    model_config = {"frozen": True}


def _detect_provider(api_key: str, base_url: str) -> Provider:
    if not api_key:
        return Provider.OFFLINE
    if base_url:
        return Provider.OPENAI_COMPATIBLE
    return Provider.ANTHROPIC


@lru_cache(maxsize=1)
def load_ai_config() -> AIConfig:
    """Build the AIConfig from application settings. Cached for the process."""
    api_key = settings.llm_api_key or ""
    base_url = getattr(settings, "llm_base_url", "") or ""
    model = settings.llm_model
    if not model:
        raise ConfigurationError("LLM_MODEL is not configured")
    return AIConfig(
        provider=_detect_provider(api_key, base_url),
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
