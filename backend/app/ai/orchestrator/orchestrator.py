"""Orchestrator: the AI brain that coordinates agents (no domain analysis).

Public async entrypoint `execute()` runs the pipeline: validate -> route -> run_agents
-> merge_results, with error handling, logging, and metrics. Every collaborator is
injectable (DI); platform defaults are used when not provided.
"""
from __future__ import annotations

import logging
import time
import uuid

from app.ai.agents.registry import AgentRegistry, get_agent_registry
from app.ai.core.errors import RequestValidationError
from app.ai.orchestrator.collector import ResponseCollector
from app.ai.orchestrator.components import (
    ExecContext,
    ExecutionLogger,
    FailureHandler,
    MetricsCollector,
    RetryManager,
    StateManager,
)
from app.ai.orchestrator.dispatcher import AgentDispatcher
from app.ai.orchestrator.executor import WorkflowExecutor
from app.ai.orchestrator.intent import IntentClassifier
from app.ai.orchestrator.models import (
    ExecutionPlan,
    Intent,
    OrchestratorRequest,
    OrchestratorResult,
    OrchestratorStatus,
)
from app.ai.orchestrator.planner import Planner

logger = logging.getLogger("sentinelai.orchestrator")


class Orchestrator:
    def __init__(
        self,
        *,
        registry: AgentRegistry | None = None,
        llm_service=None,
        tool_manager=None,
        intent_classifier: IntentClassifier | None = None,
        planner: Planner | None = None,
        retry_manager: RetryManager | None = None,
        failure_handler: FailureHandler | None = None,
        memory=None,
        state_repo=None,
        run_timeout_s: float = 0.0,
    ) -> None:
        self.registry = registry or get_agent_registry()
        self.llm_service = llm_service
        self.intent = intent_classifier or IntentClassifier(llm_service, self.registry)
        self.planner = planner or Planner(self.registry)
        retry = retry_manager or RetryManager()
        self.dispatcher = AgentDispatcher(
            self.registry, retry_manager=retry, tool_manager=tool_manager)
        self.executor = WorkflowExecutor(
            self.dispatcher, failure_handler=failure_handler or FailureHandler())
        self.memory = memory
        self.state_repo = state_repo
        self.run_timeout_s = run_timeout_s

    # ------------------------------------------------------------------ #
    # Public entrypoint
    # ------------------------------------------------------------------ #
    async def execute(self, request: OrchestratorRequest) -> OrchestratorResult:
        self.validate_request(request)
        if not request.run_id:
            request.run_id = uuid.uuid4().hex
        log = ExecutionLogger(request.run_id)
        started = time.perf_counter()
        log.event("started", session=request.session_id)

        intent, plan = self.route(request)
        if not plan.steps:
            return self._empty_result(request, intent, "no capable agents for request")

        state = StateManager.new(request)
        self._recall(request, state)
        deadline = time.monotonic() + self.run_timeout_s if self.run_timeout_s > 0 else None
        ctx = ExecContext(
            session_id=request.session_id, project_id=request.project_id,
            deadline=deadline, memory=self.memory, state_repo=self.state_repo,
        )
        try:
            ok = await self.executor.execute(plan, request, state, log, ctx)
        except Exception as exc:  # unexpected orchestration failure
            return self.handle_errors(request, intent, exc)

        total_ms = (time.perf_counter() - started) * 1000
        metrics = MetricsCollector.from_state(
            state, retries=self.dispatcher.retries_used, levels=len(plan.levels), total_ms=total_ms)
        result = self.merge_results(request.run_id, state, intent, metrics, aborted=not ok)
        self._store_history(request, result)
        log.event("finished", status=result.status.value, agents=result.metrics.agents_run)
        return result

    # ------------------------------------------------------------------ #
    # Named operations
    # ------------------------------------------------------------------ #
    def validate_request(self, request: OrchestratorRequest) -> None:
        if request is None:
            raise RequestValidationError("request is required")
        if not (request.agents or request.capabilities or request.workflow or request.query):
            raise RequestValidationError(
                "request must specify agents, capabilities, workflow, or a query"
            )

    def route(self, request: OrchestratorRequest) -> tuple[Intent, ExecutionPlan]:
        """Understand intent and select/order the required agents."""
        intent = self.intent.classify(request)
        plan = self.planner.plan(intent, request)
        return intent, plan

    async def run_agents(self, plan: ExecutionPlan, request: OrchestratorRequest,
                         state, log: ExecutionLogger, ctx: ExecContext | None = None) -> bool:
        return await self.executor.execute(
            plan, request, state, log, ctx or ExecContext(session_id=request.session_id))

    def merge_results(
        self, run_id: str, state, intent: Intent, metrics, *, aborted: bool
    ) -> OrchestratorResult:
        return ResponseCollector.collect(run_id, state, intent, metrics, aborted=aborted)

    def handle_errors(
        self, request: OrchestratorRequest, intent: Intent, exc: Exception
    ) -> OrchestratorResult:
        code = getattr(exc, "code", "ai_orchestrator_error")
        return OrchestratorResult(
            run_id=request.run_id,
            status=OrchestratorStatus.FAILED,
            intent=intent,
            errors=[str(exc)],
            metadata={"error_code": code},
        )

    # ------------------------------------------------------------------ #
    def _recall(self, request: OrchestratorRequest, state) -> None:
        """Pull recent session context from the Memory Service (best-effort)."""
        if self.memory is None or not request.session_id:
            return
        try:
            recent = self.memory.conversation(request.session_id, limit=10)
            state.metadata["recalled_context"] = [m.text for m in recent][-5:]
        except Exception:  # memory is optional
            logger.debug("memory recall failed (non-fatal)", exc_info=True)

    def _store_history(self, request: OrchestratorRequest, result) -> None:
        """Persist a run summary to execution history (best-effort)."""
        if self.memory is None or not request.session_id:
            return
        try:
            from app.models.memory import MemoryScope
            self.memory.remember(
                request.session_id,
                {"run_id": result.run_id, "status": result.status.value,
                 "agents_run": result.metrics.agents_run},
                scope=MemoryScope.EXECUTION, project_id=request.project_id,
            )
        except Exception:
            logger.debug("run-history store failed (non-fatal)", exc_info=True)

    def _empty_result(
        self, request: OrchestratorRequest, intent: Intent, reason: str
    ) -> OrchestratorResult:
        return OrchestratorResult(
            run_id=request.run_id,
            status=OrchestratorStatus.FAILED,
            intent=intent,
            warnings=[reason],
        )
