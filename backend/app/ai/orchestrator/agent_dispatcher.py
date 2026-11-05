"""Agent Dispatcher: discover, validate, run, retry, and collect agent executions.

A production dispatcher over the Agent Registry. Discovers agents (by capability or
explicit id), validates availability (registered + enabled + healthy + dependencies +
version), starts and runs them — in parallel for a batch — collects structured outputs,
retries transient failures, and logs every dispatch. Supports dynamic registration
(via the registry), versioning (`min_version`), health checks, and future plugins
(plugin agents/tools register into the same registry / tool manager).

No domain logic — agents are referenced purely by id/capability.

Concurrency is bounded by ``max_concurrency``; retries use capped exponential backoff
with optional full jitter (``_backoff_delay``). The orchestrator's dispatcher adapter
delegates single-run mechanics to :meth:`AgentDispatcher.run_once`.
"""
from __future__ import annotations

import asyncio
import random
import time

from pydantic import BaseModel, Field

from app.ai.agents.models import AgentRequest, AgentResult
from app.ai.agents.registry import AgentHealth, AgentRegistry, get_agent_registry
from app.ai.core.logging import get_logger
from app.ai.orchestrator.components import RetryManager
from app.ai.types.aliases import JSON
from app.ai.types.enums import StepStatus

logger = get_logger(__name__)


def _version_key(version: str) -> tuple:
    parts = []
    for piece in version.split("."):
        parts.append((0, int(piece)) if piece.isdigit() else (1, piece))
    return tuple(parts)


class AgentAvailability(BaseModel):
    agent_id: str
    registered: bool = False
    enabled: bool = False
    health: str = AgentHealth.UNKNOWN.value
    version: str = ""
    missing_dependencies: list[str] = Field(default_factory=list)
    available: bool = False
    reason: str = ""


class DispatchResult(BaseModel):
    agent_id: str
    version: str = ""
    status: str  # completed | failed | skipped | unavailable
    output: JSON = Field(default_factory=dict)
    error: str | None = None
    attempts: int = 0
    latency_ms: float = 0.0
    health: str = AgentHealth.UNKNOWN.value


class DispatchReport(BaseModel):
    results: list[DispatchResult] = Field(default_factory=list)
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    total_ms: float = 0.0

    @property
    def outputs(self) -> dict[str, JSON]:
        return {r.agent_id: r.output for r in self.results if r.status == "completed"}

    def to_json(self) -> JSON:
        return self.model_dump(mode="json")


class AgentDispatcher:
    def __init__(
        self,
        registry: AgentRegistry | None = None,
        *,
        tool_manager=None,
        retry_manager: RetryManager | None = None,
        retry_backoff_s: float = 0.0,
        retry_backoff_cap_s: float = 30.0,
        retry_jitter: bool = True,
        max_concurrency: int = 8,
        health_check: bool = True,
    ) -> None:
        self.registry = registry or get_agent_registry()
        self.tools = tool_manager
        self.retry = retry_manager or RetryManager()
        self.retry_backoff_s = retry_backoff_s
        self.retry_backoff_cap_s = retry_backoff_cap_s
        self.retry_jitter = retry_jitter
        self.max_concurrency = max(1, max_concurrency)
        self.health_check = health_check

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff, capped, with optional full jitter."""
        if not self.retry_backoff_s:
            return 0.0
        raw = self.retry_backoff_s * (2 ** (attempt - 1))
        delay = min(raw, self.retry_backoff_cap_s)
        if self.retry_jitter:
            delay = random.uniform(0.0, delay)
        return delay

    # -- discovery -----------------------------------------------------------
    def discover(self, *, capability: str | None = None, agents: list[str] | None = None,
                 available_only: bool = False) -> list[str]:
        if agents is not None:
            ids = [a for a in agents if a in self.registry]
        elif capability is not None:
            ids = self.registry.find_by_capability(capability)
        else:
            ids = self.registry.names()
        if available_only:
            ids = [a for a in ids if self.validate(a).available]
        return sorted(ids)

    # -- availability validation --------------------------------------------
    def validate(self, agent_id: str, *, min_version: str | None = None) -> AgentAvailability:
        if agent_id not in self.registry:
            return AgentAvailability(agent_id=agent_id, reason="not registered")
        desc = self.registry.descriptor(agent_id)
        if self.health_check:
            health = self.registry.health_check(agent_id).value
        else:
            health = desc.health.value
        missing = self.registry.missing_dependencies(agent_id)

        reason = ""
        ok = True
        if not desc.enabled:
            ok, reason = False, "disabled"
        elif missing:
            ok, reason = False, f"missing dependencies: {missing}"
        elif health == AgentHealth.UNHEALTHY.value:
            ok, reason = False, "unhealthy"
        elif min_version and _version_key(desc.version) < _version_key(min_version):
            ok, reason = False, f"version {desc.version} < {min_version}"

        return AgentAvailability(
            agent_id=agent_id, registered=True, enabled=desc.enabled, health=health,
            version=desc.version, missing_dependencies=missing, available=ok, reason=reason,
        )

    # -- single dispatch (sync core) ----------------------------------------
    def dispatch(self, agent_id: str, request: AgentRequest, *,
                 min_version: str | None = None) -> DispatchResult:
        avail = self.validate(agent_id, min_version=min_version)
        if not avail.available:
            status = "unavailable" if not avail.registered else "skipped"
            logger.info("dispatch skip agent=%s reason=%s", agent_id, avail.reason)
            return DispatchResult(agent_id=agent_id, version=avail.version, status=status,
                                  error=avail.reason, health=avail.health)

        started = time.perf_counter()
        attempts = 0
        last: AgentResult | None = None
        while True:
            attempts += 1
            last = self.run_once(agent_id, request)
            if last.status is StepStatus.COMPLETED or not self.retry.should_retry(last, attempts):
                break
            logger.info("dispatch retry agent=%s attempt=%d", agent_id, attempts)
            delay = self._backoff_delay(attempts)
            if delay:
                time.sleep(delay)

        latency = round((time.perf_counter() - started) * 1000, 2)
        if last.status is StepStatus.COMPLETED:
            return DispatchResult(agent_id=agent_id, version=avail.version, status="completed",
                                  output=last.output, attempts=attempts, latency_ms=latency,
                                  health=avail.health)
        return DispatchResult(agent_id=agent_id, version=avail.version, status="failed",
                              error=last.error.message if last.error else "failed",
                              attempts=attempts, latency_ms=latency, health=avail.health)

    def run_once(self, agent_id: str, request: AgentRequest) -> AgentResult:
        """Create the agent, grant its declared tools, and run it once (no retry).

        The single source of truth for agent execution mechanics; the orchestrator's
        dispatcher adapter delegates here.
        """
        agent = self.registry.create(agent_id)
        if self.tools is not None:
            required = getattr(agent, "tools_required", None)
            if required:
                try:
                    self.tools.grant(agent_id, *required)
                except Exception as exc:  # unknown tool shouldn't crash dispatch
                    logger.warning("tool grant failed agent=%s: %s", agent_id, exc)
        return agent.run(request)

    # -- parallel batch ------------------------------------------------------
    async def dispatch_many(
        self, agent_ids: list[str], request: AgentRequest, *,
        parallel: bool = True, min_version: str | None = None,
    ) -> DispatchReport:
        started = time.perf_counter()
        if parallel:
            sem = asyncio.Semaphore(self.max_concurrency)

            async def _run(aid: str) -> DispatchResult:
                async with sem:  # bound in-flight agents to max_concurrency
                    res = await asyncio.to_thread(
                        self.dispatch, aid, request, min_version=min_version
                    )
                return res

            results = await asyncio.gather(*(_run(aid) for aid in agent_ids))
        else:
            results = []
            for aid in agent_ids:
                results.append(
                    await asyncio.to_thread(self.dispatch, aid, request, min_version=min_version)
                )
        return self._report(list(results), started)

    def dispatch_batch(
        self, agent_ids: list[str], request: AgentRequest, **kwargs
    ) -> DispatchReport:
        """Synchronous convenience wrapper around dispatch_many."""
        return asyncio.run(self.dispatch_many(agent_ids, request, **kwargs))

    @staticmethod
    def _report(results: list[DispatchResult], started: float) -> DispatchReport:
        return DispatchReport(
            results=results,
            succeeded=sum(1 for r in results if r.status == "completed"),
            failed=sum(1 for r in results if r.status == "failed"),
            skipped=sum(1 for r in results if r.status in ("skipped", "unavailable")),
            total_ms=round((time.perf_counter() - started) * 1000, 2),
        )
