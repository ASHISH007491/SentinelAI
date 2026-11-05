"""WorkflowExecutor: run an ExecutionPlan over shared state, level by level.

Agents within a dependency level run concurrently (asyncio.gather). After each level
the executor checkpoints state (optional), records execution history to the Memory
Service (optional), and enforces a per-run timeout budget. A non-optional failure
under fail-fast aborts the remaining levels. No domain logic.
"""
from __future__ import annotations

import asyncio
import time

from app.ai.core.logging import get_logger
from app.ai.orchestrator.components import (
    ExecContext,
    ExecutionLogger,
    FailureHandler,
    StateManager,
)
from app.ai.orchestrator.dispatcher import AgentDispatcher
from app.ai.orchestrator.models import ExecutionPlan, OrchestratorRequest
from app.ai.state.workflow_state import WorkflowState
from app.ai.types.enums import StepStatus

logger = get_logger(__name__)


class WorkflowExecutor:
    def __init__(
        self, dispatcher: AgentDispatcher, *, failure_handler: FailureHandler | None = None
    ) -> None:
        self._dispatcher = dispatcher
        self._failure = failure_handler or FailureHandler()

    async def execute(self, plan: ExecutionPlan, request: OrchestratorRequest,
                      state: WorkflowState, log: ExecutionLogger, ctx: ExecContext) -> bool:
        """Run the plan. Returns False if it aborted on a required failure."""
        optional = {s.agent_id: s.optional for s in plan.steps}
        for level in plan.levels:
            if ctx.deadline is not None and time.monotonic() >= ctx.deadline:
                state.add_warning("run timeout budget exceeded")
                state.metadata["timed_out"] = True
                log.event("timeout_budget_exceeded")
                return True  # stop scheduling; collector marks the run degraded

            for aid in level:
                StateManager.start(state, aid)
            results = await asyncio.gather(
                *(self._dispatcher.dispatch(aid, request) for aid in level)
            )
            aborted = self._record_level(level, results, state, log, optional, ctx)
            self._checkpoint(state, ctx)
            if aborted:
                return False
        return True

    def _record_level(self, level, results, state, log, optional, ctx) -> bool:
        for aid, result in zip(level, results, strict=True):
            if result.status is StepStatus.COMPLETED:
                StateManager.complete(state, aid, result)
                log.event("agent_completed", agent=aid, ms=result.metrics.latency_ms)
                self._remember(ctx, aid, "completed")
            else:
                StateManager.fail(state, aid, result, optional=optional.get(aid, False))
                log.event("agent_failed", agent=aid,
                          code=result.error.code if result.error else "?")
                self._remember(ctx, aid, "failed")
                if self._failure.on_failure(aid, optional=optional.get(aid, False)) == "abort":
                    log.event("run_aborted", agent=aid)
                    return True
        return False

    @staticmethod
    def _checkpoint(state: WorkflowState, ctx: ExecContext) -> None:
        if ctx.state_repo is not None:
            try:
                ctx.state_repo.save(state)
            except Exception as exc:  # checkpointing must never break a run
                logger.warning("checkpoint failed: %s", exc)

    @staticmethod
    def _remember(ctx: ExecContext, agent_id: str, status: str) -> None:
        if ctx.memory is None or not ctx.session_id:
            return
        try:
            from app.models.memory import MemoryScope
            ctx.memory.remember(
                ctx.session_id, {"agent": agent_id, "status": status},
                scope=MemoryScope.EXECUTION, project_id=ctx.project_id,
            )
        except Exception as exc:  # memory is best-effort
            logger.warning("memory write failed: %s", exc)
