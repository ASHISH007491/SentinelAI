"""ResponseCollector: consolidate shared state into an OrchestratorResult."""
from __future__ import annotations

from app.ai.orchestrator.models import (
    Intent,
    OrchestratorMetrics,
    OrchestratorResult,
    OrchestratorStatus,
)
from app.ai.state.workflow_state import WorkflowState


class ResponseCollector:
    @staticmethod
    def collect(run_id: str, state: WorkflowState, intent: Intent,
                metrics: OrchestratorMetrics, *, aborted: bool) -> OrchestratorResult:
        timed_out = bool(state.metadata.get("timed_out"))
        if aborted or (state.failed and not state.completed):
            status = OrchestratorStatus.FAILED
        elif state.failed or timed_out:
            status = OrchestratorStatus.DEGRADED
        else:
            status = OrchestratorStatus.COMPLETED
        trace = [f"ok:{a}" for a in state.completed] + [f"fail:{a}" for a in state.failed]
        return OrchestratorResult(
            run_id=run_id,
            status=status,
            intent=intent,
            outputs=dict(state.outputs),
            errors=[n.message for n in state.errors],
            warnings=[n.message for n in state.warnings],
            trace=trace,
            metrics=metrics,
        )
