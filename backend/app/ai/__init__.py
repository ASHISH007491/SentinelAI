"""SentinelAI AI platform.

Reusable, agent-agnostic infrastructure that every future AI agent and workflow
builds on: configuration, typed contracts, LLM access, prompt templating, shared
state, error handling, and workflow orchestration. Contains no business logic and
no cybersecurity agents — those compose these primitives.

Layering (clean architecture, dependencies point inward):
    types  <-  models  <-  interfaces  <-  {llm, prompts, state, utils, workflows}
    core (config/errors/logging) is depended on by all.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
