"""Small orchestration components: retry, failure, metrics, logging, state.

All are pure orchestration helpers — no domain/cybersecurity logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.agents.models import AgentResult
from app.ai.core.logging import get_logger
from app.ai.orchestrator.models import OrchestratorRequest
from app.ai.state.workflow_state import FileRef, UserRef, WorkflowState
from app.ai.types.enums import StepStatus

logger = get_logger(__name__)


@dataclass
class ExecContext:
    """Cross-cutting execution context threaded through the executor."""
    session_id: str = ""
    project_id: int | None = None
    deadline: float | None = None          # time.monotonic() budget; None = no budget
    memory: Any = None                     # MemoryService (optional)
    state_repo: Any = None                 # StateRepository for checkpoints (optional)

# Failures that must NOT be retried (deterministic — retrying won't help).
NON_RETRYABLE_CODES = {
    "ai_validation_error",
    "ai_tool_validation_error",
    "ai_tool_permission_denied",
    "ai_configuration_error",
}


class RetryManager:
    """Decides whether a failed agent result should be retried."""

    def __init__(self, max_retries: int = 1) -> None:
        self.max_retries = max_retries

    def should_retry(self, result: AgentResult, attempt: int) -> bool:
        if result.status is not StepStatus.FAILED:
            return False
        if attempt > self.max_retries:
            return False
        code = result.error.code if result.error else "ai_agent_error"
        return code not in NON_RETRYABLE_CODES


class FailureHandler:
    """Decides how the run proceeds after an agent fails."""

    def __init__(self, *, fail_fast: bool = True) -> None:
        self.fail_fast = fail_fast

    def on_failure(self, agent_id: str, *, optional: bool) -> str:
        """Return 'continue' (skip), or 'abort' (stop the run)."""
        if optional:
            return "continue"
        return "abort" if self.fail_fast else "continue"


class MetricsCollector:
    """Aggregates run metrics from the workflow state."""

    @staticmethod
    def from_state(state: WorkflowState, *, retries: int, levels: int, total_ms: float):
        from app.ai.orchestrator.models import OrchestratorMetrics
        return OrchestratorMetrics(
            total_ms=round(total_ms, 2),
            agents_run=len(state.completed),
            agents_failed=len(state.failed),
            retries=retries,
            levels=levels,
            tokens=state.usage,
        )


class ExecutionLogger:
    """Structured, run-scoped logging of orchestration events."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    def event(self, message: str, **fields) -> None:
        logger.info("orchestrator %s rid=%s %s", message, self.run_id,
                    " ".join(f"{k}={v}" for k, v in fields.items()))


class StateManager:
    """Creates and mutates the shared WorkflowState for a run."""

    @staticmethod
    def new(request: OrchestratorRequest) -> WorkflowState:
        state = WorkflowState(run_id=request.run_id)
        state.user = UserRef(id=request.user_id)
        state.project.id = request.project_id
        state.files = [FileRef(name=a) for a in request.artefacts]
        state.metadata["params"] = dict(request.params)
        return state

    @staticmethod
    def start(state: WorkflowState, agent_id: str) -> None:
        state.start_agent(agent_id)

    @staticmethod
    def complete(state: WorkflowState, agent_id: str, result: AgentResult) -> None:
        state.complete_agent(agent_id, output=result.output, latency_ms=result.metrics.latency_ms)
        state.usage = state.usage + result.metrics.tokens

    @staticmethod
    def fail(
        state: WorkflowState, agent_id: str, result: AgentResult, *, optional: bool = False
    ) -> None:
        message = result.error.message if result.error else "unknown error"
        if agent_id in state.running:
            state.running.remove(agent_id)
        if agent_id not in state.failed:
            state.failed.append(agent_id)
        state.execution_ms[agent_id] = result.metrics.latency_ms
        state.usage = state.usage + result.metrics.tokens
        note = f"{agent_id}: {message}"
        if optional:
            state.add_warning(note, agent=agent_id)
        else:
            state.add_error(note, agent=agent_id)
