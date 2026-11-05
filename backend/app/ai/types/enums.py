"""Enumerations shared across the AI platform."""
from __future__ import annotations

import enum


class LLMRole(str, enum.Enum):
    """Role of a message in an LLM conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Provider(str, enum.Enum):
    """Supported LLM backends."""
    ANTHROPIC = "anthropic"
    OPENAI_COMPATIBLE = "openai_compatible"  # Groq, Gemini (compat), OpenRouter, ...
    OFFLINE = "offline"  # deterministic fallback, no network


class StepStatus(str, enum.Enum):
    """Lifecycle status of a workflow step or run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
