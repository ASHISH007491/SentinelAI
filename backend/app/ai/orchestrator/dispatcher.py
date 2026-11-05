"""AgentDispatcher: instantiate and run a single agent, with retry + timeout.

Async-friendly: the (synchronous) agent runs in a worker thread so independent agents
can be dispatched concurrently. Tools are granted to the agent via the Tool Manager
allow-list when one is provided. No domain logic.

This is the orchestrator-facing adapter: it maps an ``OrchestratorRequest`` to an
``AgentRequest`` and exposes the async, retry-looped ``dispatch`` the executor needs.
The single-run mechanics (create agent + grant declared tools + run) are delegated to
the standalone :class:`~app.ai.orchestrator.agent_dispatcher.AgentDispatcher`, so there
is exactly one implementation of "run one agent".
"""
from __future__ import annotations

import asyncio

from app.ai.agents.models import AgentRequest, AgentResult
from app.ai.core.logging import get_logger
from app.ai.orchestrator.agent_dispatcher import AgentDispatcher as CoreDispatcher
from app.ai.orchestrator.components import RetryManager
from app.ai.orchestrator.models import OrchestratorRequest

logger = get_logger(__name__)


class AgentDispatcher:
    def __init__(self, registry, *, retry_manager: RetryManager | None = None,
                 tool_manager=None) -> None:
        self._registry = registry
        self._retry = retry_manager or RetryManager()
        self._tools = tool_manager
        # Single source of truth for agent creation + tool granting + run.
        self._core = CoreDispatcher(registry, tool_manager=tool_manager)
        self.retries_used = 0

    def build_agent_request(self, agent_id: str, request: OrchestratorRequest) -> AgentRequest:
        return AgentRequest(
            run_id=request.run_id,
            inputs=dict(request.params),
            artefact_text=request.artefact_text,
            artefacts=list(request.artefacts),
            metadata={"agent_id": agent_id, "session_id": request.session_id},
        )

    async def dispatch(self, agent_id: str, request: OrchestratorRequest) -> AgentResult:
        agent_request = self.build_agent_request(agent_id, request)
        attempt = 0
        while True:
            attempt += 1
            result = await asyncio.to_thread(self._run_once, agent_id, agent_request)
            if not self._retry.should_retry(result, attempt):
                return result
            self.retries_used += 1
            logger.info("dispatch retry agent=%s attempt=%d", agent_id, attempt)

    def _run_once(self, agent_id: str, agent_request: AgentRequest) -> AgentResult:
        return self._core.run_once(agent_id, agent_request)
