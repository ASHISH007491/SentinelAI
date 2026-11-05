"""Planner: turn an Intent + request into a dependency-ordered ExecutionPlan.

Selects agents by explicit id or capability, pulls in their transitive dependencies
from the registry, and lays them out in parallelisable levels (Kahn by layer).
Raises on cycles via the registry's resolution check. No domain logic.
"""
from __future__ import annotations

from app.ai.core.errors import OrchestratorError
from app.ai.orchestrator.models import ExecutionPlan, Intent, OrchestratorRequest, PlanStep


class Planner:
    def __init__(self, registry) -> None:
        self._registry = registry

    def plan(self, intent: Intent, request: OrchestratorRequest) -> ExecutionPlan:
        selected = self._select(intent, request)
        if not selected:
            return ExecutionPlan()
        closure = self._with_dependencies(selected)
        levels = self._levels(closure)
        optional = set(request.optional_agents)
        steps = [
            PlanStep(agent_id=aid, optional=aid in optional,
                     depends_on=self._deps(aid, closure))
            for aid in [a for lvl in levels for a in lvl]
        ]
        return ExecutionPlan(steps=steps, levels=levels)

    # -- selection -----------------------------------------------------------
    def _select(self, intent: Intent, request: OrchestratorRequest) -> set[str]:
        if request.agents:
            return {a for a in request.agents if a in self._registry}
        caps = request.capabilities or intent.capabilities
        if not caps and intent.workflow:
            caps = [intent.workflow]
        selected: set[str] = set()
        for cap in caps:
            selected.update(self._registry.find_by_capability(cap))
        return selected

    def _with_dependencies(self, selected: set[str]) -> set[str]:
        closure = set(selected)
        frontier = list(selected)
        while frontier:
            aid = frontier.pop()
            for dep in self._registry.descriptor(aid).dependencies:
                if dep in self._registry and dep not in closure:
                    closure.add(dep)
                    frontier.append(dep)
        return closure

    def _deps(self, agent_id: str, closure: set[str]) -> list[str]:
        return [d for d in self._registry.descriptor(agent_id).dependencies if d in closure]

    # -- leveling (Kahn by layer) -------------------------------------------
    def _levels(self, ids: set[str]) -> list[list[str]]:
        deps = {aid: set(self._deps(aid, ids)) for aid in ids}
        levels: list[list[str]] = []
        resolved: set[str] = set()
        remaining = set(ids)
        while remaining:
            ready = sorted(aid for aid in remaining if deps[aid] <= resolved)
            if not ready:
                raise OrchestratorError(f"Dependency cycle among agents: {sorted(remaining)}")
            levels.append(ready)
            resolved.update(ready)
            remaining.difference_update(ready)
        return levels
