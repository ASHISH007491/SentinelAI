"""Collaborator protocols — the Orchestrator depends on these, not concretes."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.ai.orchestrator.models import ExecutionPlan, Intent, OrchestratorRequest


@runtime_checkable
class IntentClassifierProtocol(Protocol):
    def classify(self, request: OrchestratorRequest) -> Intent: ...


@runtime_checkable
class PlannerProtocol(Protocol):
    def plan(self, intent: Intent, request: OrchestratorRequest) -> ExecutionPlan: ...
