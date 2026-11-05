"""SingleLLMBaseline — the experimental control: one LLM, one prompt, no orchestration.

It implements the same SystemUnderTest protocol as the multi-agent system, so the
harness scores both on identical inputs. Output parsing degrades gracefully: if the
model will not emit JSON, the verdict is inferred from the prose rather than aborting.
"""
from __future__ import annotations

import time

from eval.datasets.types import CodeCase, CVECase, EmailCase
from eval.systems.contracts import Ranking, Usage, Verdict
from eval.systems.llm import LLMClient, LLMResponse
from eval.systems.structured import extract_soft, infer_positive
from pydantic import BaseModel, Field


class _RankReply(BaseModel):
    order: list[str] = Field(default_factory=list)
    rationale: dict[str, object] = Field(default_factory=dict)


class _VerdictReply(BaseModel):
    label: str
    confidence: float = 0.0
    rationale: str = ""


def _usage(responses: list[LLMResponse], started: float, *, agents: int = 1) -> Usage:
    return Usage(
        prompt_tokens=sum(r.prompt_tokens for r in responses),
        completion_tokens=sum(r.completion_tokens for r in responses),
        latency_s=time.perf_counter() - started,
        agents_invoked=agents,
        llm_calls=len(responses),
    )


class SingleLLMBaseline:
    name = "single_llm_baseline"

    def __init__(self, llm: LLMClient, *, retries: int = 2) -> None:
        self._llm = llm
        self._retries = retries

    # -- Track A ----------------------------------------------------------
    def prioritise(self, cves: list[CVECase]) -> Ranking:
        started = time.perf_counter()
        listing = "\n".join(
            f"- {c.cve_id}: CVSS={c.cvss} EPSS={c.epss} KEV={c.kev} "
            f"exploit={c.exploit_available} :: {c.description}"
            for c in cves
        )
        prompt = (
            "Order these CVEs from most to least urgent to patch, prioritising real-world "
            "exploitation (EPSS) and known-exploited status (KEV) over severity.\n"
            f"{listing}\n\n"
            'Reply with ONLY a JSON object: {"order": [cve_id, ...], "rationale": {cve_id: reason}}'
        )
        value, responses, _ = extract_soft(
            self._llm, prompt, _RankReply,
            system="You are a vulnerability triage assistant.", retries=self._retries)
        order = self._normalise_order([c.cve_id for c in cves], value.order if value else [])
        rationale = value.rationale if value else {}
        return Ranking(order=order, rationale=rationale, usage=_usage(responses, started))

    @staticmethod
    def _normalise_order(known: list[str], proposed: list[str]) -> list[str]:
        known_set = set(known)
        seen: set[str] = set()
        out: list[str] = []
        for x in proposed:
            if x in known_set and x not in seen:
                out.append(x)
                seen.add(x)
        out.extend(c for c in known if c not in seen)
        return out

    # -- Track B ----------------------------------------------------------
    def investigate_email(self, email: EmailCase) -> Verdict:
        started = time.perf_counter()
        prompt = (
            "Classify this email as 'phish' or 'legit'.\n"
            f"From: {email.sender}\nSubject: {email.subject}\n"
            f"Headers: {email.headers}\nBody: {email.body}\n\n"
            'Reply with ONLY a JSON object: {"label": "phish|legit", "confidence": 0-1, '
            '"rationale": "..."}'
        )
        return self._verdict(prompt, positive_label="phish", started=started)

    # -- Track C ----------------------------------------------------------
    def review_code(self, code: CodeCase) -> Verdict:
        started = time.perf_counter()
        prompt = (
            f"Review this {code.language} code. Is it vulnerable? Answer 'vulnerable' or 'safe'.\n"
            f"```{code.language}\n{code.code}\n```\n\n"
            'Reply with ONLY a JSON object: {"label": "vulnerable|safe", "confidence": 0-1, '
            '"rationale": "..."}'
        )
        return self._verdict(prompt, positive_label="vulnerable", started=started)

    def _verdict(self, prompt: str, *, positive_label: str, started: float) -> Verdict:
        value, responses, last_text = extract_soft(
            self._llm, prompt, _VerdictReply,
            system="You are a security analyst.", retries=self._retries)
        if value is not None:
            positive = value.label.strip().lower() == positive_label
            confidence = max(0.0, min(1.0, float(value.confidence)))
            rationale = value.rationale
        else:
            positive = infer_positive(last_text, positive_label)   # graceful prose fallback
            confidence = 0.3
            rationale = "inferred from unstructured reply"
        return Verdict(positive=positive, confidence=confidence, rationale=rationale,
                       usage=_usage(responses, started))
