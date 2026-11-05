"""BaseAgent: the reusable foundation every SentinelAI agent inherits from.

Design goals: dependency injection (LLM, prompts, tools, clock all overridable),
a strict lifecycle, resilient execution (per-attempt timeout + retry on transient
errors), built-in metrics, and a single JSON-only return type (AgentResult). Built
to scale to 50+ agents — concrete agents implement only `execute()` (and optionally
override the other hooks).

Lifecycle (orchestrated by `run()`):
    initialize -> validate -> execute (timeout+retry) -> post_process -> cleanup
Any exception is funnelled through `handle_error()` into a failed AgentResult.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from app.ai.agents.config import AgentConfig
from app.ai.agents.models import (
    AgentErrorInfo,
    AgentMetrics,
    AgentRequest,
    AgentResult,
)
from app.ai.agents.tools import ToolRegistry
from app.ai.core.errors import (
    AgentTimeoutError,
    ConfigurationError,
    LLMError,
    ValidationError,
)
from app.ai.core.logging import get_logger
from app.ai.interfaces.llm import LLMProvider
from app.ai.llm.client import build_default_client
from app.ai.models.messages import LLMMessage, LLMRequest, LLMResponse, TokenUsage
from app.ai.prompts.registry import PromptRegistry, prompt_registry
from app.ai.types.aliases import JSON, PromptVariables
from app.ai.types.enums import LLMRole, StepStatus


class _MeteredLLM:
    """Wraps an LLMProvider so every generate() call records tokens on the agent.

    Centralising accounting here means tokens are counted whether a subclass calls
    `self.generate(...)` or `self.llm.generate(...)` directly — no sharp edge.
    """

    def __init__(self, inner: LLMProvider, sink: BaseAgent) -> None:
        self._inner = inner
        self._sink = sink

    @property
    def available(self) -> bool:
        return self._inner.available

    def generate(self, request: LLMRequest) -> LLMResponse:
        resp = self._inner.generate(request)
        self._sink._record_tokens(resp.usage)
        return resp


class BaseAgent(ABC):
    #: Subclasses set this class attribute (or pass `config=` at construction).
    config: AgentConfig
    #: Exceptions that should trigger a retry (validation errors never retry).
    retryable_errors: tuple[type[Exception], ...] = (LLMError,)

    def __init__(
        self,
        config: AgentConfig | None = None,
        *,
        llm: LLMProvider | None = None,
        prompts: PromptRegistry | None = None,
        tools: ToolRegistry | None = None,
    ) -> None:
        resolved = config or getattr(type(self), "config", None)
        if resolved is None:
            raise ConfigurationError(f"{type(self).__name__} requires an AgentConfig")
        self.config = resolved
        # Dependency injection with sensible platform defaults.
        self.llm: LLMProvider = _MeteredLLM(llm or build_default_client(), self)
        self.prompts: PromptRegistry = prompts or prompt_registry
        self.tools: ToolRegistry = tools or ToolRegistry()
        self.logger = get_logger(self.config.id)
        self._initialized = False
        self._metrics = AgentMetrics()

    # ------------------------------------------------------------------ #
    # Lifecycle hooks (override as needed; sensible defaults provided)
    # ------------------------------------------------------------------ #
    def initialize(self) -> None:
        """Prepare the agent. Verifies declared prompts are registered."""
        for name in self.config.prompt_names:
            if name not in self.prompts.names():
                raise ConfigurationError(
                    f"Prompt '{name}' not registered for agent '{self.config.id}'"
                )
        self.logger.info("initialize id=%s v=%s", self.config.id, self.config.version)

    def validate(self, request: AgentRequest) -> None:
        """Validate input. Raise ValidationError on bad input. Override to extend."""
        if request is None:
            raise ValidationError("request is required")

    @abstractmethod
    def execute(self, request: AgentRequest) -> JSON:
        """Core agent logic. Return a JSON-serialisable dict."""

    def post_process(self, output: JSON) -> JSON:
        """Transform/normalise raw output. Default ensures a dict."""
        if not isinstance(output, dict):
            return {"result": output}
        return output

    def handle_error(self, exc: Exception, metrics: AgentMetrics | None = None) -> AgentResult:
        """Convert any exception into a failed, JSON-only AgentResult."""
        m = metrics or self._metrics
        m.success = False
        code = getattr(exc, "code", "ai_agent_error")
        self.logger.warning("agent_error id=%s code=%s msg=%s", self.config.id, code, exc)
        return AgentResult(
            agent_id=self.config.id,
            agent_name=self.config.name,
            version=self.config.version,
            status=StepStatus.FAILED,
            error=AgentErrorInfo(code=code, message=str(exc), type=type(exc).__name__),
            metrics=m,
        )

    def cleanup(self) -> None:  # noqa: B027 - intentional no-op hook for subclasses
        """Release resources. Default no-op; never raises out of run()."""

    # ------------------------------------------------------------------ #
    # Public entrypoint (template method)
    # ------------------------------------------------------------------ #
    def run(self, request: AgentRequest) -> AgentResult:
        self._metrics = AgentMetrics()
        started = time.perf_counter()
        try:
            if not self._initialized:
                self.initialize()
                self._initialized = True
            self.validate(request)
            raw = self._execute_with_policy(request)
            output = self.post_process(raw)
            self._metrics.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return AgentResult(
                agent_id=self.config.id,
                agent_name=self.config.name,
                version=self.config.version,
                status=StepStatus.COMPLETED,
                output=output,
                metrics=self._metrics,
            )
        except Exception as exc:  # noqa: BLE001 - funnel everything to JSON
            self._metrics.latency_ms = round((time.perf_counter() - started) * 1000, 2)
            return self.handle_error(exc, self._metrics)
        finally:
            try:
                self.cleanup()
            except Exception:  # noqa: BLE001
                self.logger.exception("cleanup failed id=%s", self.config.id)

    # ------------------------------------------------------------------ #
    # Helpers for subclasses
    # ------------------------------------------------------------------ #
    def generate(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 1024
    ) -> LLMResponse:
        """Call the injected LLM and accumulate token metrics."""
        return self.llm.generate(
            LLMRequest(
                messages=[LLMMessage(role=LLMRole.USER, content=prompt)],
                system=system,
                model=self.config.model,
                max_tokens=max_tokens,
            )
        )

    def render_prompt(self, name: str, variables: PromptVariables | None = None) -> str:
        return self.prompts.get(name).render(variables or {})

    def use_tool(self, name: str, **kwargs) -> JSON:
        result = self.tools.get(name).run(**kwargs)
        self._metrics.tool_calls += 1
        return result

    def _record_tokens(self, usage: TokenUsage) -> None:
        self._metrics.tokens = self._metrics.tokens + usage

    # ------------------------------------------------------------------ #
    # Internal: retry + timeout policy
    # ------------------------------------------------------------------ #
    def _execute_with_policy(self, request: AgentRequest) -> JSON:
        attempts = max(1, self.config.max_retries + 1)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._execute_with_timeout(request)
            except ValidationError:
                raise  # never retry validation
            except self.retryable_errors as exc:
                last = exc
                self._metrics.retries += 1
                self.logger.warning("retry id=%s attempt=%d/%d: %s",
                                     self.config.id, attempt + 1, attempts, exc)
                if attempt < attempts - 1:
                    time.sleep(self.config.retry_backoff_s * (attempt + 1))
        assert last is not None
        raise last

    def _execute_with_timeout(self, request: AgentRequest) -> JSON:
        timeout = self.config.timeout_s
        if timeout is None or timeout <= 0:
            return self.execute(request)
        # Soft timeout: stop waiting after `timeout`s. The worker thread cannot be
        # force-killed, which is acceptable for I/O-bound LLM calls.
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.execute, request)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout as exc:
                raise AgentTimeoutError(
                    f"agent '{self.config.id}' exceeded {timeout}s"
                ) from exc
