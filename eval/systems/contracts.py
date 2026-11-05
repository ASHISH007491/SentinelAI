"""The 'system under test' contract shared by the baseline and the multi-agent system.

Both architectures implement the same protocol over identical dataset inputs, which is
what makes the multi-agent-vs-baseline comparison fair (RQ1). The harness depends only
on this protocol — not on any concrete engine — so the two are swappable.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from eval.datasets.types import CodeCase, CVECase, EmailCase
from pydantic import BaseModel, Field, field_validator


class Usage(BaseModel):
    """Per-query cost — the Track E efficiency signal."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_s: float = 0.0
    agents_invoked: int = 0
    llm_calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            latency_s=self.latency_s + other.latency_s,
            agents_invoked=self.agents_invoked + other.agents_invoked,
            llm_calls=self.llm_calls + other.llm_calls,
        )


class Ranking(BaseModel):
    """Track A output: a patch-priority ordering of CVE ids + per-item justification."""

    order: list[str] = Field(default_factory=list)
    rationale: dict[str, str] = Field(default_factory=dict)
    usage: Usage = Field(default_factory=Usage)

    @field_validator("rationale", mode="before")
    @classmethod
    def _coerce_rationale(cls, value: object) -> dict[str, str]:
        # Real LLMs return rationale values as strings, lists, or nested dicts;
        # normalise everything to a string so the contract never breaks at runtime.
        if not isinstance(value, dict):
            return {}
        out: dict[str, str] = {}
        for key, val in value.items():
            if isinstance(val, str):
                out[str(key)] = val
            elif isinstance(val, (list, tuple)):
                out[str(key)] = ", ".join(str(x) for x in val)
            else:
                out[str(key)] = str(val)
        return out


class Verdict(BaseModel):
    """Track B/C output: a binary call (phish / vulnerable) with confidence + reason."""

    positive: bool                       # phish (Track B) or vulnerable (Track C)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""
    usage: Usage = Field(default_factory=Usage)


@runtime_checkable
class SystemUnderTest(Protocol):
    """Implemented by both SingleLLMBaseline and the multi-agent adapter."""

    name: str

    def prioritise(self, cves: list[CVECase]) -> Ranking: ...

    def investigate_email(self, email: EmailCase) -> Verdict: ...

    def review_code(self, code: CodeCase) -> Verdict: ...
