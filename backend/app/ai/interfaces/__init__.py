"""Abstract contracts (clean-architecture boundaries) for the AI platform.

Concrete implementations in ai/llm, ai/prompts, ai/state, ai/workflows depend on
these; nothing here depends on a concrete implementation.
"""
from app.ai.interfaces.agent import Agent
from app.ai.interfaces.llm import LLMProvider
from app.ai.interfaces.prompt import PromptRenderer
from app.ai.interfaces.state_store import StateStore
from app.ai.interfaces.step import Step
from app.ai.interfaces.workflow import Workflow

__all__ = ["Agent", "LLMProvider", "PromptRenderer", "StateStore", "Step", "Workflow"]
