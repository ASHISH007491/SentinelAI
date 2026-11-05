"""Security Advisor data models (Pydantic v2).

The Advisor is a *consumer* — it never scans, detects, or reviews. It ingests the other
agents' findings and produces a unified, explainable assessment: prioritised risks,
recommendations with reasoning, explainable scores, and executive/technical summaries.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.ai.types.aliases import JSON


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


_SEVERITY_WEIGHT = {
    RiskLevel.CRITICAL: 1.0,
    RiskLevel.HIGH: 0.75,
    RiskLevel.MEDIUM: 0.5,
    RiskLevel.LOW: 0.25,
    RiskLevel.INFORMATIONAL: 0.1,
}


def coerce_risk(value: object) -> RiskLevel:
    try:
        return RiskLevel(str(value).lower())
    except ValueError:
        return RiskLevel.INFORMATIONAL


def severity_weight(level: RiskLevel) -> float:
    return _SEVERITY_WEIGHT[level]


class AgentFinding(BaseModel):
    """Normalised finding the Advisor consumes from any agent."""

    source: str = "unknown"                    # producing agent id
    title: str = "finding"
    severity: RiskLevel = RiskLevel.INFORMATIONAL
    cvss: float = Field(default=0.0, ge=0.0, le=10.0)
    cve: str | None = None
    exploitability: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    asset_criticality: float = Field(default=0.5, ge=0.0, le=1.0)
    business_impact: str = ""
    recommendation: str = ""
    description: str = ""


class PrioritisedFinding(BaseModel):
    source: str
    title: str
    risk_level: RiskLevel
    risk_score: float                          # 0..1 composite
    severity: RiskLevel
    cvss: float
    cve: str | None = None
    confidence: float
    recommendation: str = ""
    rationale: str = ""


class Recommendation(BaseModel):
    id: str
    title: str
    action: str
    horizon: str                               # immediate | short_term | long_term
    priority: RiskLevel
    impact: str                                # high | medium | low
    effort: str                                # high | medium | low
    risk_reduction: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""
    related: list[str] = Field(default_factory=list)


class SecurityScore(BaseModel):
    overall: int = Field(default=100, ge=0, le=100)
    vulnerability: int = Field(default=100, ge=0, le=100)
    phishing: int = Field(default=100, ge=0, le=100)
    code_security: int = Field(default=100, ge=0, le=100)
    threat_exposure: int = Field(default=100, ge=0, le=100)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    explanation: dict[str, str] = Field(default_factory=dict)


class SecurityAssessment(BaseModel):
    run_id: str = ""
    generated_at: str = ""
    posture: str = ""                          # human-readable overall posture
    score: SecurityScore = Field(default_factory=SecurityScore)
    prioritised: list[PrioritisedFinding] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    executive_summary: str = ""
    technical_summary: str = ""
    business_impact: str = ""

    def to_json(self) -> JSON:
        return self.model_dump(mode="json")
