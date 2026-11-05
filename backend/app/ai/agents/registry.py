"""Thread-safe, singleton Agent Registry.

Agents register themselves (a class or factory) and the registry provides discovery,
metadata, health status, capability lookup, dependency checks, versioning, and
enable / disable / reload. Lookups are O(1) via dict + a capability index. All
mutating and reading operations are guarded by a re-entrant lock.
"""
from __future__ import annotations

import enum
import importlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from app.ai.core.errors import AgentError, DependencyCycleError
from app.ai.core.logging import get_logger
from app.ai.types.aliases import Metadata

logger = get_logger(__name__)


class AgentHealth(str, enum.Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class AgentDescriptor(BaseModel):
    """Discoverable metadata for a registered agent."""
    id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    enabled: bool = True
    health: AgentHealth = AgentHealth.UNKNOWN
    metadata: Metadata = Field(default_factory=dict)


@dataclass
class _Entry:
    descriptor: AgentDescriptor
    target: Callable[..., Any]  # class or factory producing an agent instance
    factory: Callable[..., Any] = field(repr=False, default=lambda: None)


class AgentRegistry:
    """Registry of agents. Use `AgentRegistry.instance()` for the shared singleton."""

    _singleton: AgentRegistry | None = None
    _singleton_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, _Entry] = {}
        self._by_capability: dict[str, set[str]] = {}

    # -- singleton -----------------------------------------------------------
    @classmethod
    def instance(cls) -> AgentRegistry:
        if cls._singleton is None:
            with cls._singleton_lock:
                if cls._singleton is None:
                    cls._singleton = cls()
        return cls._singleton

    # -- registration --------------------------------------------------------
    def register(
        self,
        target: Callable[..., Any] | None = None,
        /,
        *,
        id: str | None = None,
        name: str | None = None,
        version: str | None = None,
        description: str | None = None,
        capabilities: list[str] | None = None,
        dependencies: list[str] | None = None,
        metadata: Metadata | None = None,
        replace: bool = False,
    ) -> Any:
        """Register an agent. Usable directly or as a (parameterised) decorator."""
        if target is None:
            def _decorator(cls: Callable[..., Any]) -> Callable[..., Any]:
                self.register(
                    cls, id=id, name=name, version=version, description=description,
                    capabilities=capabilities, dependencies=dependencies,
                    metadata=metadata, replace=replace,
                )
                return cls
            return _decorator

        cfg = getattr(target, "config", None)
        rid = str(id or getattr(cfg, "id", None) or getattr(target, "__name__", "agent"))
        descriptor = AgentDescriptor(
            id=rid,
            name=name or getattr(cfg, "name", None) or rid,
            version=version or getattr(cfg, "version", "1.0.0"),
            description=description or getattr(cfg, "description", "") or "",
            capabilities=list(
                capabilities if capabilities is not None
                else getattr(target, "capabilities", [])
            ),
            dependencies=list(
                dependencies if dependencies is not None
                else getattr(target, "dependencies", [])
            ),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            if rid in self._entries and not replace:
                raise AgentError(f"Agent '{rid}' is already registered")
            self._drop_from_index(rid)
            self._entries[rid] = _Entry(descriptor=descriptor, target=target,
                                        factory=lambda **kw: target(**kw))
            for cap in descriptor.capabilities:
                self._by_capability.setdefault(cap, set()).add(rid)
        logger.info(
            "registered agent id=%s v=%s caps=%s",
            rid, descriptor.version, descriptor.capabilities,
        )
        return target

    def unregister(self, agent_id: str) -> None:
        with self._lock:
            self._entries.pop(agent_id, None)
            self._drop_from_index(agent_id)

    # -- discovery / metadata ------------------------------------------------
    def __contains__(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._entries

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._entries)

    def descriptor(self, agent_id: str) -> AgentDescriptor:
        with self._lock:
            return self._require(agent_id).descriptor.model_copy(deep=True)

    def discover(
        self, *, capability: str | None = None, enabled_only: bool = False
    ) -> list[AgentDescriptor]:
        with self._lock:
            ids = self._by_capability.get(capability, set()) if capability else set(self._entries)
            out = [self._entries[i].descriptor for i in ids if i in self._entries]
            if enabled_only:
                out = [d for d in out if d.enabled]
            return [d.model_copy(deep=True) for d in sorted(out, key=lambda d: d.id)]

    def find_by_capability(self, capability: str) -> list[str]:
        with self._lock:
            return sorted(self._by_capability.get(capability, set()))

    # -- instantiation -------------------------------------------------------
    def create(self, agent_id: str, **kwargs: Any) -> Any:
        with self._lock:
            entry = self._require(agent_id)
            if not entry.descriptor.enabled:
                raise AgentError(f"Agent '{agent_id}' is disabled")
            factory = entry.factory
        return factory(**kwargs)  # construct outside the lock

    # -- enable / disable / reload ------------------------------------------
    def enable(self, agent_id: str) -> None:
        with self._lock:
            self._require(agent_id).descriptor.enabled = True

    def disable(self, agent_id: str) -> None:
        with self._lock:
            self._require(agent_id).descriptor.enabled = False

    def reload(self, agent_id: str, *, reimport: bool = False) -> AgentDescriptor:
        """Re-derive an agent's descriptor from its class (optionally re-importing
        its module to pick up code changes). Preserves enabled state, resets health."""
        with self._lock:
            entry = self._require(agent_id)
            target = entry.target
            enabled = entry.descriptor.enabled
        if reimport and getattr(target, "__module__", None):
            module = importlib.reload(importlib.import_module(target.__module__))
            target = getattr(module, target.__name__, target)
        self.register(target, id=agent_id, replace=True)
        with self._lock:
            self._entries[agent_id].descriptor.enabled = enabled
            return self._entries[agent_id].descriptor.model_copy(deep=True)

    # -- health --------------------------------------------------------------
    def set_health(self, agent_id: str, status: AgentHealth) -> None:
        with self._lock:
            self._require(agent_id).descriptor.health = status

    def health(self, agent_id: str) -> AgentHealth:
        with self._lock:
            return self._require(agent_id).descriptor.health

    def health_check(self, agent_id: str) -> AgentHealth:
        """Invoke the agent's `health_check()` (class/staticmethod) if present."""
        with self._lock:
            target = self._require(agent_id).target
        checker = getattr(target, "health_check", None)
        if callable(checker):
            try:
                result = checker()
                status = result if isinstance(result, AgentHealth) else (
                    AgentHealth.HEALTHY if result else AgentHealth.UNHEALTHY
                )
            except Exception as exc:  # a failing check is itself unhealthy
                logger.warning("health_check failed id=%s: %s", agent_id, exc)
                status = AgentHealth.UNHEALTHY
        else:
            status = self.health(agent_id)
        self.set_health(agent_id, status)
        return status

    # -- dependencies --------------------------------------------------------
    def missing_dependencies(self, agent_id: str) -> list[str]:
        with self._lock:
            deps = self._require(agent_id).descriptor.dependencies
            return [d for d in deps if d not in self._entries]

    # -- dependency resolution ----------------------------------------------
    def resolution_order(self, agent_ids: list[str] | None = None) -> list[str]:
        """Return agents ordered so each appears after its dependencies.

        Uses Kahn's algorithm over the dependency graph (edges: dependency -> agent).
        Raises DependencyCycleError on a cycle, AgentError on a missing dependency.
        Only dependencies among the requested set are ordered; external missing
        dependencies are reported via missing_dependencies().
        """
        with self._lock:
            selected = list(agent_ids) if agent_ids is not None else list(self._entries)
            for aid in selected:
                self._require(aid)
            selected_set = set(selected)
            # Build in-degree + adjacency restricted to the selected set.
            deps: dict[str, list[str]] = {
                aid: [d for d in self._entries[aid].descriptor.dependencies if d in selected_set]
                for aid in selected
            }

        indegree = {aid: len(deps[aid]) for aid in selected}
        dependents: dict[str, list[str]] = {aid: [] for aid in selected}
        for aid, ds in deps.items():
            for d in ds:
                dependents[d].append(aid)

        # Deterministic order: process ready nodes alphabetically.
        ready = sorted(aid for aid in selected if indegree[aid] == 0)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(dependents[node]):
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    ready.append(dependent)
            ready.sort()

        if len(order) != len(selected):
            cyclic = sorted(set(selected) - set(order))
            raise DependencyCycleError(f"Dependency cycle among agents: {cyclic}")
        return order

    # -- internals -----------------------------------------------------------
    def _require(self, agent_id: str) -> _Entry:
        entry = self._entries.get(agent_id)
        if entry is None:
            raise AgentError(f"Agent '{agent_id}' is not registered")
        return entry

    def _drop_from_index(self, agent_id: str) -> None:
        for ids in self._by_capability.values():
            ids.discard(agent_id)


def get_agent_registry() -> AgentRegistry:
    """Return the process-wide singleton registry."""
    return AgentRegistry.instance()


def register_agent(**kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that registers an agent class on the singleton registry."""
    def _decorator(cls: Callable[..., Any]) -> Callable[..., Any]:
        AgentRegistry.instance().register(cls, **kwargs)
        return cls
    return _decorator
