import pytest

from app.ai.core.errors import WorkflowError
from app.ai.interfaces.step import Step
from app.ai.models.messages import TokenUsage
from app.ai.state.base import BaseState
from app.ai.types.enums import StepStatus
from app.ai.workflows import SequentialWorkflow, WorkflowRegistry


class _Echo(Step):
    def __init__(self, name): self.name = name
    def run(self, state: BaseState) -> BaseState:
        state.note(f"ran {self.name}")
        state.add_usage(TokenUsage(completion_tokens=1))
        return state


class _Boom(Step):
    name = "boom"
    def run(self, state: BaseState) -> BaseState:
        raise RuntimeError("explode")


def test_sequential_runs_all_steps():
    wf = SequentialWorkflow("w", [_Echo("a"), _Echo("b")])
    result = wf.run(BaseState(run_id="r"))
    assert result.status is StepStatus.COMPLETED
    assert [s.name for s in result.steps] == ["a", "b"]
    assert result.total_usage.total_tokens == 2


def test_sequential_stops_on_failure():
    wf = SequentialWorkflow("w", [_Echo("a"), _Boom(), _Echo("c")])
    result = wf.run(BaseState())
    assert result.status is StepStatus.FAILED
    assert result.steps[-1].status is StepStatus.FAILED
    assert len(result.steps) == 2  # stopped at boom


def test_empty_workflow_rejected():
    with pytest.raises(WorkflowError):
        SequentialWorkflow("w", [])


def test_registry():
    reg = WorkflowRegistry()
    reg.register("w", lambda: SequentialWorkflow("w", [_Echo("a")]))
    assert reg.names() == ["w"]
    assert reg.create("w").run(BaseState()).status is StepStatus.COMPLETED
