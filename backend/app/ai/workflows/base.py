"""SequentialWorkflow: run an ordered list of Steps over shared state.

Pure Python (no external deps) so it always runs and is fully unit-testable. A
LangGraph-backed runner with identical semantics lives in `langgraph_runner.py`
for when graph features (branching, checkpoints) are needed.
"""
from __future__ import annotations

from app.ai.core.errors import WorkflowError
from app.ai.core.logging import get_logger
from app.ai.interfaces.step import Step
from app.ai.models.messages import TokenUsage
from app.ai.models.results import StepResult, WorkflowResult
from app.ai.state.base import BaseState
from app.ai.types.enums import StepStatus
from app.ai.utils.timing import Timer

logger = get_logger(__name__)


class SequentialWorkflow:
    def __init__(self, name: str, steps: list[Step]) -> None:
        if not steps:
            raise WorkflowError("A workflow needs at least one step")
        self.name = name
        self.steps = steps

    def run(self, state: BaseState) -> WorkflowResult:
        result = WorkflowResult(workflow=self.name, status=StepStatus.RUNNING)
        for step in self.steps:
            usage_before = state.usage.total_tokens
            with Timer() as timer:
                try:
                    state = step.run(state)
                    status, error = StepStatus.COMPLETED, None
                except Exception as exc:  # isolate step failures
                    logger.exception("step '%s' failed", step.name)
                    status, error = StepStatus.FAILED, str(exc)
            delta = max(0, state.usage.total_tokens - usage_before)
            result.steps.append(
                StepResult(
                    name=step.name,
                    status=status,
                    latency_ms=round(timer.elapsed_ms, 2),
                    error=error,
                    usage=TokenUsage(completion_tokens=delta),
                )
            )
            if status is StepStatus.FAILED:
                result.status = StepStatus.FAILED
                return result

        result.status = StepStatus.COMPLETED
        result.output = {"trace": state.trace, "scratchpad": state.scratchpad}
        return result
