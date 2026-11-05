"""Concrete security workflow (the SentinelAI pipeline) built on the Workflow Engine.

Pipeline:
    receive -> validate -> determine_intent -> select_agents -> execute_agents
            -> collect_results -> security_advisor -> report_generator -> return_response

Conditional routing sends invalid requests / no-capable-agents to a terminal error
node. Analysis agents in a dependency level run in parallel (threads); the advisor and
report stages run sequentially after. Supports a CancellationToken, a per-run timeout
budget, recovery (stage on_error -> error node), retry (per agent), shared dict state,
execution metrics, and a visual graph (Mermaid / LangGraph). No domain logic — agents
are selected purely by capability.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pydantic import BaseModel, Field

from app.ai.agents.models import AgentRequest
from app.ai.core.logging import get_logger
from app.ai.orchestrator.intent import IntentClassifier
from app.ai.orchestrator.models import OrchestratorRequest
from app.ai.orchestrator.planner import Planner
from app.ai.types.aliases import JSON
from app.ai.types.enums import StepStatus
from app.ai.workflows.engine import END, ExecutionMonitor, WorkflowBuilder

logger = get_logger(__name__)


class CancellationToken:
    """A thread-safe flag the workflow checks between stages/levels."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


class SecurityWorkflowResult(BaseModel):
    run_id: str
    status: str  # completed | degraded | failed | cancelled
    outputs: dict[str, JSON] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    stage_metrics: dict[str, float] = Field(default_factory=dict)  # stage -> ms
    agents_run: int = 0
    total_ms: float = 0.0
    trace: list[str] = Field(default_factory=list)

    def to_json(self) -> JSON:
        return self.model_dump(mode="json")


class SecurityWorkflow:
    def __init__(
        self,
        registry,
        *,
        intent_classifier: IntentClassifier | None = None,
        planner: Planner | None = None,
        advisor_capability: str = "advise",
        report_capability: str = "report",
        run_timeout_s: float = 0.0,
        stage_timeout_s: float = 0.0,
    ) -> None:
        self.registry = registry
        self.intent = intent_classifier or IntentClassifier(None, registry)
        self.planner = planner or Planner(registry)
        self.advisor_capability = advisor_capability
        self.report_capability = report_capability
        self.run_timeout_s = run_timeout_s
        self.stage_timeout_s = stage_timeout_s
        self._graph = self._build()

    # ------------------------------------------------------------------ #
    # Public
    # ------------------------------------------------------------------ #
    def run(
        self, request: OrchestratorRequest, *, cancel: CancellationToken | None = None
    ) -> SecurityWorkflowResult:
        if not request.run_id:
            import uuid
            request.run_id = uuid.uuid4().hex
        state: JSON = {
            "_request": request,
            "_cancel": cancel,
            "_deadline": time.monotonic() + self.run_timeout_s if self.run_timeout_s > 0 else None,
            "outputs": {},
            "errors": [],
            "warnings": [],
            "status": None,
        }
        monitor = ExecutionMonitor()
        started = time.perf_counter()
        run_result = self._graph.run(state, monitor=monitor)
        total_ms = (time.perf_counter() - started) * 1000

        final = run_result.state
        stage_metrics: dict[str, float] = {}
        for ev in monitor.events:
            stage_metrics[ev.node] = round(ev.latency_ms, 2)
        return SecurityWorkflowResult(
            run_id=request.run_id,
            status=str(final.get("status")
                       or ("failed" if run_result.status == "failed" else "completed")),
            outputs=final.get("outputs", {}),
            errors=final.get("errors", []),
            warnings=final.get("warnings", []),
            stage_metrics=stage_metrics,
            agents_run=len(final.get("outputs", {})),
            total_ms=round(total_ms, 2),
            trace=[ev.node for ev in monitor.events],
        )

    def to_mermaid(self) -> str:
        return self._graph.to_mermaid()

    def to_langgraph(self):
        return self._graph.to_langgraph()

    # ------------------------------------------------------------------ #
    # Graph definition
    # ------------------------------------------------------------------ #
    def _build(self):
        b = WorkflowBuilder("security_pipeline")
        b.add_node("receive", self._receive)
        b.add_node("validate", self._validate)
        b.add_node("determine_intent", self._determine_intent)
        b.add_node("select_agents", self._select_agents)
        b.add_node("execute_agents", self._execute_agents,
                   on_error="return_error", timeout_s=self.stage_timeout_s)
        b.add_node("collect_results", self._collect_results)
        b.add_node("security_advisor", self._security_advisor, on_error="return_error")
        b.add_node("report_generator", self._report_generator, on_error="return_error")
        b.add_node("return_response", self._return_response)
        b.add_node("return_error", self._return_error)

        b.set_entry("receive")
        b.add_edge("receive", "validate")
        b.add_conditional_edges("validate", lambda s: s.get("route_valid", "ok"),
                                {"ok": "determine_intent", "invalid": "return_error"})
        b.add_edge("determine_intent", "select_agents")
        b.add_conditional_edges("select_agents", lambda s: s.get("route_agents", "has"),
                                {"has": "execute_agents", "none": "return_error"})
        b.add_edge("execute_agents", "collect_results")
        b.add_edge("collect_results", "security_advisor")
        b.add_edge("security_advisor", "report_generator")
        b.add_edge("report_generator", "return_response")
        b.add_edge("return_response", END)
        b.add_edge("return_error", END)
        return b.build()

    # ------------------------------------------------------------------ #
    # Stage implementations (state-in, updates-out; may mutate shared dict)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _receive(state: JSON) -> JSON:
        return {"received": True}

    @staticmethod
    def _validate(state: JSON) -> JSON:
        req: OrchestratorRequest = state["_request"]
        valid = bool(req.agents or req.capabilities or req.workflow or req.query)
        if not valid:
            state["errors"].append("request must specify agents, capabilities, workflow, or query")
            state["status"] = "failed"
        return {"route_valid": "ok" if valid else "invalid"}

    def _determine_intent(self, state: JSON) -> JSON:
        req = state["_request"]
        state["intent"] = self.intent.classify(req)
        return {"intent_source": state["intent"].source}

    def _select_agents(self, state: JSON) -> JSON:
        req = state["_request"]
        plan = self.planner.plan(state["intent"], req)
        state["plan"] = plan
        if not plan.steps:
            state["warnings"].append("no capable agents for request")
            state["status"] = "failed"
        return {"route_agents": "has" if plan.steps else "none", "n_agents": len(plan.steps)}

    def _execute_agents(self, state: JSON) -> JSON:
        """Run the analysis agents (everything except advisor/report) in parallel levels."""
        plan = state["plan"]
        special = {self.advisor_capability, self.report_capability}
        analysis_levels = [
            [a for a in level if not (set(self._caps(a)) & special)]
            for level in plan.levels
        ]
        self._run_levels([lvl for lvl in analysis_levels if lvl], state)
        return {}

    @staticmethod
    def _collect_results(state: JSON) -> JSON:
        return {"collected": len(state["outputs"])}

    def _security_advisor(self, state: JSON) -> JSON:
        self._run_capability(self.advisor_capability, state)
        return {}

    def _report_generator(self, state: JSON) -> JSON:
        self._run_capability(self.report_capability, state)
        return {}

    @staticmethod
    def _return_response(state: JSON) -> JSON:
        if state.get("cancelled"):
            status = "cancelled"
        elif state.get("timed_out"):
            status = "degraded"
        elif state["errors"]:
            status = "degraded"
        else:
            status = "completed"
        state["status"] = status
        return {"status": status}

    @staticmethod
    def _return_error(state: JSON) -> JSON:
        state["status"] = state.get("status") or "failed"
        return {"status": state["status"]}

    # ------------------------------------------------------------------ #
    # Agent execution helpers
    # ------------------------------------------------------------------ #
    def _caps(self, agent_id: str) -> list[str]:
        return self.registry.descriptor(agent_id).capabilities

    def _run_capability(self, capability: str, state: JSON) -> None:
        plan = state.get("plan")
        if plan is None:
            return
        ids = [a for a in plan.agent_ids if capability in self._caps(a)]
        if ids:
            self._run_levels([ids], state)

    def _run_levels(self, levels: list[list[str]], state: JSON) -> None:
        req: OrchestratorRequest = state["_request"]
        cancel: CancellationToken | None = state.get("_cancel")
        deadline = state.get("_deadline")
        for level in levels:
            if cancel is not None and cancel.cancelled:
                state["cancelled"] = True
                state["warnings"].append("workflow cancelled")
                return
            if deadline is not None and time.monotonic() >= deadline:
                state["timed_out"] = True
                state["warnings"].append("run timeout budget exceeded")
                return
            if not level:
                continue
            with ThreadPoolExecutor(max_workers=len(level)) as pool:
                results = list(pool.map(lambda aid: (aid, self._run_agent(aid, req)), level))
            for aid, result in results:
                if result.status is StepStatus.COMPLETED:
                    state["outputs"][aid] = result.output
                else:
                    msg = result.error.message if result.error else "failed"
                    state["errors"].append(f"{aid}: {msg}")

    def _run_agent(self, agent_id: str, request: OrchestratorRequest):
        agent = self.registry.create(agent_id)
        return agent.run(AgentRequest(
            run_id=request.run_id, inputs=dict(request.params),
            artefact_text=request.artefact_text, artefacts=list(request.artefacts),
        ))
