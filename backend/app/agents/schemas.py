"""Typed agent I/O contracts. Shared by every agent and the single-agent baseline."""
from __future__ import annotations

from pydantic import BaseModel, Field

Severity = str  # one of: critical | high | medium | low | info


class Finding(BaseModel):
    title: str
    severity: Severity = "info"
    cvss: float = 0.0
    epss: float = 0.0            # FIRST EPSS exploitation probability (0-1)
    kev: bool = False            # present in CISA KEV catalogue (known-exploited)
    exploit_available: bool = False
    component: str = ""
    cve: str | None = None
    rule: str | None = None
    line: int | None = None
    evidence: str = ""
    recommendation: str = ""
    confidence: float = 0.5


class AgentResult(BaseModel):
    agent: str
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
