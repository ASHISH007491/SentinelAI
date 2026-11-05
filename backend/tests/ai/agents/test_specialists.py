"""Offline tests for the concrete specialist agents (fake LLMProvider)."""
import json

from app.ai.agents.models import AgentRequest
from app.ai.agents.specialists import (
    CodeReviewAgent,
    IndicatorExtractionAgent,
    PhishingVerdictAgent,
    PrioritisationAgent,
    RiskSignalAgent,
)
from app.ai.models.messages import LLMRequest, LLMResponse, TokenUsage
from app.ai.types.enums import StepStatus


class FakeProvider:
    """Implements the LLMProvider protocol; returns scripted replies in order."""

    def __init__(self, replies):
        self._replies = replies
        self._i = 0
        self.calls = 0
        self.last_prompt = ""

    @property
    def available(self) -> bool:
        return True

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls += 1
        self.last_prompt = " ".join(m.content for m in request.messages)
        text = self._replies[min(self._i, len(self._replies) - 1)]
        self._i += 1
        return LLMResponse(text=text, usage=TokenUsage(prompt_tokens=5, completion_tokens=3))


def test_indicator_extraction_normalises_fields():
    reply = json.dumps({"urls": ["http://x"], "sender_domain": "x.com",
                        "auth_pass": False, "urgency": True,
                        "credential_request": True, "signals": ["urgent"]})
    agent = IndicatorExtractionAgent(llm=FakeProvider([reply]))
    res = agent.run(AgentRequest(inputs={"body": "verify now", "sender": "a@x.com"}))
    assert res.status is StepStatus.COMPLETED
    assert res.output["urgency"] is True and res.output["urls"] == ["http://x"]
    assert res.metrics.tokens.total_tokens == 8


def test_phishing_verdict_maps_label():
    reply = json.dumps({"label": "phish", "confidence": 0.9, "rationale": "spoofed"})
    agent = PhishingVerdictAgent(llm=FakeProvider([reply]))
    res = agent.run(AgentRequest(inputs={"indicators": {"auth_pass": False}}))
    assert res.output["is_phish"] is True and res.output["confidence"] == 0.9


def test_code_review_nulls_cwe_when_safe():
    reply = json.dumps({"vulnerable": False, "cwe": "null", "confidence": 0.8,
                        "rationale": "ok", "fix": ""})
    agent = CodeReviewAgent(llm=FakeProvider([reply]))
    res = agent.run(AgentRequest(inputs={"language": "python", "code": "x=1"}))
    assert res.output["vulnerable"] is False and res.output["cwe"] is None


def test_prioritisation_repairs_to_valid_permutation():
    reply = json.dumps({"order": ["CVE-2", "CVE-BOGUS"], "rationale": {}})
    cves = [{"cve_id": "CVE-1", "cvss": 9.0, "epss": 0.5, "kev": True,
             "exploit_available": True, "description": "a"},
            {"cve_id": "CVE-2", "cvss": 8.0, "epss": 0.9, "kev": True,
             "exploit_available": True, "description": "b"}]
    agent = PrioritisationAgent(llm=FakeProvider([reply]))
    res = agent.run(AgentRequest(inputs={"cves": cves}))
    assert sorted(res.output["order"]) == ["CVE-1", "CVE-2"]   # valid permutation
    assert res.output["order"][0] == "CVE-2"                    # model order respected


def test_risk_signal_assigns_and_defaults_tiers():
    # model rates CVE-1 high; omits CVE-2, which must default to medium (not crash)
    reply = json.dumps({"risk": {"CVE-1": {"level": "HIGH", "note": "kev"}}})
    cves = [{"cve_id": "CVE-1", "cvss": 9.0, "epss": 0.9, "kev": True,
             "exploit_available": True, "description": "a"},
            {"cve_id": "CVE-2", "cvss": 5.0, "epss": 0.1, "kev": False,
             "exploit_available": False, "description": "b"}]
    agent = RiskSignalAgent(llm=FakeProvider([reply]))
    res = agent.run(AgentRequest(inputs={"cves": cves}))
    risk = res.output["risk"]
    assert risk["CVE-1"]["level"] == "high"     # normalised to lower-case, in-range
    assert risk["CVE-2"]["level"] == "medium"   # missing entry defaults safely


def test_prioritisation_uses_upstream_risk_signal():
    # With a pre-assessment present, ranking is decomposed and the tiers reach the prompt.
    reply = json.dumps({"order": ["CVE-2", "CVE-1"], "rationale": {}})
    cves = [{"cve_id": "CVE-1", "cvss": 9.0, "epss": 0.2, "kev": False,
             "exploit_available": False, "description": "a"},
            {"cve_id": "CVE-2", "cvss": 6.0, "epss": 0.9, "kev": True,
             "exploit_available": True, "description": "b"}]
    provider = FakeProvider([reply])
    agent = PrioritisationAgent(llm=provider)
    res = agent.run(AgentRequest(inputs={
        "cves": cves, "risk": {"CVE-2": {"level": "high"}, "CVE-1": {"level": "low"}}}))
    assert res.output["order"] == ["CVE-2", "CVE-1"]
    # the risk tier must appear in the prompt the prioritiser actually sent
    sent = provider.last_prompt
    assert "risk=HIGH" in sent and "risk=LOW" in sent


def test_agents_survive_json_array_reply():
    # llama-family models sometimes return a bare JSON array instead of an object.
    # ask_json must treat that as a parse miss so callers fall back instead of
    # crashing with "'list' object has no attribute 'get'".
    arr = json.dumps([{"cwe": "CWE-89"}, {"cwe": "CWE-78"}])

    reviewer = CodeReviewAgent(llm=FakeProvider([arr, arr]))
    res = reviewer.run(AgentRequest(inputs={"language": "python", "code": "x=1"}))
    assert res.status is StepStatus.COMPLETED          # graceful fallback, no crash

    risk = RiskSignalAgent(llm=FakeProvider([arr, arr]))
    cves = [{"cve_id": "CVE-1", "cvss": 9.0, "epss": 0.9, "kev": True,
             "exploit_available": True, "description": "a"}]
    rres = risk.run(AgentRequest(inputs={"cves": cves}))
    assert rres.status is StepStatus.COMPLETED
    assert rres.output["risk"]["CVE-1"]["level"] == "medium"   # safe default


def test_agent_retries_on_bad_json_then_succeeds():
    # first reply unparseable -> retryable ParsingError -> second reply valid
    good = json.dumps({"vulnerable": True, "cwe": "CWE-89", "confidence": 0.9,
                       "rationale": "sqli", "fix": "parameterise"})
    provider = FakeProvider(["not json", good])
    agent = CodeReviewAgent(llm=provider)
    res = agent.run(AgentRequest(inputs={"language": "python", "code": "q"}))
    assert res.status is StepStatus.COMPLETED
    assert res.output["vulnerable"] is True and provider.calls == 2
