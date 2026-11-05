"""MultiAgentSystem: the orchestrated, decomposed system under test.

Coordinates the app/ai specialist agents (phishing = extract -> verdict; plus
code-review and prioritisation) and exposes the same SystemUnderTest protocol as the
baseline, so the harness scores them head-to-head on identical inputs. Usage is summed
across every agent call, so Track E reflects the real cost of decomposition.
"""
from __future__ import annotations

from eval.datasets.types import CodeCase, CVECase, EmailCase  # noqa: E402

# Import the bridge first: it puts backend/ on sys.path so ``app.ai`` resolves.
from eval.systems.bridge import EvalLLMProvider
from eval.systems.contracts import Ranking, Usage, Verdict
from eval.systems.llm import LLMClient

from app.ai.agents.models import AgentRequest, AgentResult  # noqa: E402  (needs path shim)
from app.ai.agents.specialists import (  # noqa: E402
    CodeReviewAgent,
    IndicatorExtractionAgent,
    PatternScanAgent,
    PhishingVerdictAgent,
    PrioritisationAgent,
    RiskSignalAgent,
)


def _usage(result: AgentResult, *, agents: int = 1) -> Usage:
    m = result.metrics
    return Usage(
        prompt_tokens=m.tokens.prompt_tokens,
        completion_tokens=m.tokens.completion_tokens,
        latency_s=m.latency_ms / 1000.0,
        agents_invoked=agents,
        llm_calls=m.retries + 1,
    )


class MultiAgentSystem:
    name = "multi_agent"

    def __init__(self, llm: LLMClient, *, timeout_s: float | None = None) -> None:
        provider = EvalLLMProvider(llm)

        def _mk(cls):
            # Optionally raise the per-agent soft timeout (slow local models).
            cfg = cls.config.model_copy(update={"timeout_s": timeout_s}) if timeout_s else None
            return cls(config=cfg, llm=provider)

        self._risk = _mk(RiskSignalAgent)
        self._prioritiser = _mk(PrioritisationAgent)
        self._extractor = _mk(IndicatorExtractionAgent)
        self._verdict = _mk(PhishingVerdictAgent)
        self._scanner = _mk(PatternScanAgent)
        self._reviewer = _mk(CodeReviewAgent)

    def prioritise(self, cves: list[CVECase]) -> Ranking:
        rows = [c.model_dump() for c in cves]
        risk_res = self._risk.run(AgentRequest(inputs={"cves": rows}))
        risk_out = risk_res.output if isinstance(risk_res.output, dict) else {}
        rank_res = self._prioritiser.run(
            AgentRequest(inputs={"cves": rows, "risk": risk_out.get("risk", {})}))
        out = rank_res.output if isinstance(rank_res.output, dict) else {}
        order = out.get("order") or [c.cve_id for c in cves]
        usage = _usage(risk_res) + _usage(rank_res)   # two agents, llm_calls summed
        return Ranking(order=order, rationale=out.get("rationale", {}), usage=usage)

    def investigate_email(self, email: EmailCase) -> Verdict:
        ext = self._extractor.run(AgentRequest(inputs={
            "sender": email.sender, "subject": email.subject,
            "headers": email.headers, "body": email.body}))
        ver = self._verdict.run(AgentRequest(inputs={
            "indicators": ext.output, "subject": email.subject, "sender": email.sender}))
        out = ver.output if isinstance(ver.output, dict) else {}
        usage = _usage(ext) + _usage(ver)   # two agents, llm_calls summed
        return Verdict(positive=bool(out.get("is_phish", False)),
                       confidence=float(out.get("confidence", 0.0)),
                       rationale=str(out.get("rationale", "")), usage=usage)

    def review_code(self, code: CodeCase) -> Verdict:
        scan_res = self._scanner.run(AgentRequest(inputs={
            "language": code.language, "code": code.code}))
        scan_out = scan_res.output if isinstance(scan_res.output, dict) else {}
        review_res = self._reviewer.run(AgentRequest(inputs={
            "language": code.language, "code": code.code,
            "candidates": scan_out.get("candidates", [])}))
        out = review_res.output if isinstance(review_res.output, dict) else {}
        usage = _usage(scan_res) + _usage(review_res)   # two agents, llm_calls summed
        return Verdict(positive=bool(out.get("vulnerable", False)),
                       confidence=float(out.get("confidence", 0.0)),
                       rationale=str(out.get("rationale", "")), usage=usage)
