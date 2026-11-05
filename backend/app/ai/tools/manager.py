"""ToolManager: register tools and run them safely.

Provides input validation, per-call timeout, enable/disable gating, execution
logging, and metadata/discovery. Thread-safe. Execution failures are returned as a
structured ToolResult (success=False) rather than raised, so an agent calling a tool
never crashes; pre-condition problems (unknown/disabled tool) raise explicitly.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from app.ai.core.errors import (
    ToolDisabledError,
    ToolError,
    ToolNotFoundError,
    ToolPermissionError,
    ToolTimeoutError,
)
from app.ai.core.logging import get_logger
from app.ai.tools.base import BaseTool
from app.ai.tools.models import ToolExecution, ToolMetadata, ToolResult
from app.ai.types.aliases import JSON

logger = get_logger(__name__)


class ToolManager:
    def __init__(self, *, max_log: int = 1000) -> None:
        self._lock = threading.RLock()
        self._tools: dict[str, BaseTool] = {}
        self._enabled: dict[str, bool] = {}
        self._log: list[ToolExecution] = []
        self._max_log = max_log
        # Per-agent allow-lists. An agent absent from this map may use ANY enabled
        # tool (open by default); once granted any tool, it is restricted to its set.
        self._permissions: dict[str, set[str]] = {}

    # -- registration --------------------------------------------------------
    def register(self, tool: BaseTool, *, enabled: bool = True, replace: bool = False) -> None:
        with self._lock:
            if tool.name in self._tools and not replace:
                raise ToolError(f"Tool '{tool.name}' already registered")
            self._tools[tool.name] = tool
            self._enabled[tool.name] = enabled
        logger.info("registered tool name=%s enabled=%s", tool.name, enabled)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)
            self._enabled.pop(name, None)

    # -- enable / disable ----------------------------------------------------
    def enable(self, name: str) -> None:
        with self._lock:
            self._require(name)
            self._enabled[name] = True

    def disable(self, name: str) -> None:
        with self._lock:
            self._require(name)
            self._enabled[name] = False

    def is_enabled(self, name: str) -> bool:
        with self._lock:
            self._require(name)
            return self._enabled[name]

    # -- per-agent permissions ----------------------------------------------
    def grant(self, agent_id: str, *tool_names: str) -> None:
        """Allow `agent_id` to use the named tools. Granting any tool switches the
        agent from open access to allow-list-only."""
        with self._lock:
            for name in tool_names:
                self._require(name)
            self._permissions.setdefault(agent_id, set()).update(tool_names)

    def revoke(self, agent_id: str, *tool_names: str) -> None:
        with self._lock:
            allowed = self._permissions.get(agent_id)
            if allowed is not None:
                allowed.difference_update(tool_names)

    def permissions(self, agent_id: str) -> set[str] | None:
        """Return the agent's allow-list, or None if it has open access."""
        with self._lock:
            allowed = self._permissions.get(agent_id)
            return set(allowed) if allowed is not None else None

    def can_use(self, agent_id: str | None, name: str) -> bool:
        with self._lock:
            if agent_id is None:
                return True
            allowed = self._permissions.get(agent_id)
            return allowed is None or name in allowed

        # -- discovery / metadata ------------------------------------------------
    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._tools)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._tools

    def metadata(self, name: str) -> ToolMetadata:
        with self._lock:
            tool = self._require(name)
            return tool.metadata(enabled=self._enabled[name])

    def list_metadata(self) -> list[ToolMetadata]:
        with self._lock:
            return [self._tools[n].metadata(enabled=self._enabled[n]) for n in sorted(self._tools)]

    # -- execution -----------------------------------------------------------
    def run(
        self,
        name: str,
        args: JSON | None = None,
        *,
        agent_id: str | None = None,
        timeout_s: float | None = None,
    ) -> ToolResult:
        with self._lock:
            tool = self._require(name)
            if not self._enabled[name]:
                raise ToolDisabledError(f"Tool '{name}' is disabled")
            if not self.can_use(agent_id, name):
                raise ToolPermissionError(
                    f"Agent '{agent_id}' is not permitted to use tool '{name}'"
                )
        # Validation errors raise (caller passed bad input).
        params = tool.validate(args or {})
        timeout = timeout_s if timeout_s is not None else tool.timeout_s

        started = time.perf_counter()
        try:
            output = self._with_timeout(tool, params, timeout)
            result = ToolResult(tool=name, success=True, output=output,
                                latency_ms=round((time.perf_counter() - started) * 1000, 2))
        except ToolTimeoutError as exc:
            result = ToolResult(tool=name, success=False, error=str(exc), code=exc.code,
                                latency_ms=round((time.perf_counter() - started) * 1000, 2))
        except Exception as exc:  # execution failures become structured results
            code = getattr(exc, "code", "tool_execution_error")
            code = "tool_not_implemented" if isinstance(exc, NotImplementedError) else code
            result = ToolResult(tool=name, success=False, error=str(exc) or type(exc).__name__,
                                code=code,
                                latency_ms=round((time.perf_counter() - started) * 1000, 2))
        self._record(name, result, list((args or {}).keys()))
        return result

    def _with_timeout(self, tool: BaseTool, params, timeout: float) -> JSON:
        if timeout is None or timeout <= 0:
            return tool._run(params)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(tool._run, params)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeout as exc:
                raise ToolTimeoutError(f"tool '{tool.name}' exceeded {timeout}s") from exc

    # -- logging -------------------------------------------------------------
    def executions(self, *, name: str | None = None) -> list[ToolExecution]:
        with self._lock:
            if name is None:
                return list(self._log)
            return [e for e in self._log if e.tool == name]

    def _record(self, name: str, result: ToolResult, arg_keys: list[str]) -> None:
        entry = ToolExecution(tool=name, success=result.success, latency_ms=result.latency_ms,
                              error=result.error, arg_keys=sorted(arg_keys))
        with self._lock:
            self._log.append(entry)
            if len(self._log) > self._max_log:
                self._log = self._log[-self._max_log:]
        logger.info("tool_exec name=%s success=%s ms=%.1f", name, result.success, result.latency_ms)

    # -- internals -----------------------------------------------------------
    def _require(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' is not registered")
        return tool


_default_manager = ToolManager()


def get_tool_manager() -> ToolManager:
    """Return the process-wide default ToolManager."""
    return _default_manager
