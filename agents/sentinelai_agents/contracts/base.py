"""Typed I/O contracts so every agent is independently testable (Phase 1 deliverable).

Both the multi-agent system and the single-agent baseline implement the same
AgentInput -> AgentOutput contract, which keeps the comparison fair.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Workflow(str, Enum):
    VULN = "vuln"            # vulnerability analysis & prioritisation
    PHISHING = "phishing"    # phishing detection
    CODE_REVIEW = "code_review"


class AgentInput(BaseModel):
    run_id: str
    workflow: Workflow
    payload: dict = Field(default_factory=dict)


class Finding(BaseModel):
    title: str
    severity: str
    explanation: str
    confidence: float = 0.0


class AgentOutput(BaseModel):
    agent: str
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
