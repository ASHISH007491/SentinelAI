"""AI platform exception hierarchy.

All platform errors derive from AIError so callers can catch the whole family.
Each carries a stable `code` for structured logging and API mapping.
"""
from __future__ import annotations


class AIError(Exception):
    """Base class for all AI platform errors."""

    code: str = "ai_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.message = message
        if code is not None:
            self.code = code
        super().__init__(message)


class ConfigurationError(AIError):
    code = "ai_configuration_error"


class LLMError(AIError):
    code = "ai_llm_error"


class LLMTimeoutError(LLMError):
    code = "ai_llm_timeout"


class PromptError(AIError):
    code = "ai_prompt_error"


class PromptValidationError(PromptError):
    code = "ai_prompt_validation_error"


class StateError(AIError):
    code = "ai_state_error"


class WorkflowError(AIError):
    code = "ai_workflow_error"


class OrchestratorError(AIError):
    code = "ai_orchestrator_error"


class RequestValidationError(OrchestratorError):
    code = "ai_request_validation_error"


class ParsingError(AIError):
    code = "ai_parsing_error"


class ValidationError(AIError):
    code = "ai_validation_error"


class AgentError(AIError):
    code = "ai_agent_error"


class AgentTimeoutError(AgentError):
    code = "ai_agent_timeout"


class DependencyCycleError(AgentError):
    code = "ai_agent_dependency_cycle"


class RateLimitError(LLMError):
    code = "ai_rate_limited"


class ToolError(AIError):
    code = "ai_tool_error"


class ToolNotFoundError(ToolError):
    code = "ai_tool_not_found"


class ToolValidationError(ToolError):
    code = "ai_tool_validation_error"


class ToolDisabledError(ToolError):
    code = "ai_tool_disabled"


class ToolPermissionError(ToolError):
    code = "ai_tool_permission_error"


class ToolTimeoutError(ToolError):
    code = "ai_tool_timeout"
