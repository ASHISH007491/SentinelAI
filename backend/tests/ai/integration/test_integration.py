"""Tests for the live-app integration: LLM bridge + reporting service (fakes, no DB)."""
from app.ai.integration import LLMClientProvider
from app.ai.models.messages import LLMMessage, LLMRequest
from app.ai.types.enums import LLMRole
from app.services.reporting_service import REPORT_AGENT_NAME, build_run_report


# --- LLM bridge --------------------------------------------------------------
class _Usage:
    prompt_tokens = 11
    completion_tokens = 4


class _Resp:
    text = "ok"
    usage = _Usage()
    model = "fake-model"


class _FakeClient:
    available = True

    def __init__(self):
        self.last = None

    def complete(self, prompt, *, system=None, max_tokens=1024):
        self.last = {"prompt": prompt, "system": system, "max_tokens": max_tokens}
        return _Resp()


def test_bridge_maps_request_and_usage():
    client = _FakeClient()
    provider = LLMClientProvider(client)
    assert provider.available is True
    req = LLMRequest(messages=[LLMMessage(role=LLMRole.USER, content="hi")], system="sys")
    resp = provider.generate(req)
    assert resp.text == "ok" and resp.model == "fake-model"
    assert resp.usage.prompt_tokens == 11 and resp.usage.completion_tokens == 4
    assert client.last["system"] == "sys" and client.last["prompt"] == "hi"


# --- reporting service (DB faked) -------------------------------------------
class _Out:
    def __init__(self, agent_name, output):
        self.agent_name = agent_name
        self.output = output


class _Run:
    id = 7

    def __init__(self, outputs):
        self.agent_outputs = outputs


class _FakeDB:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_build_run_report_consolidates_findings():
    run = _Run([
        _Out("detection", {"findings": [
            {"title": "SQLi in login", "severity": "high", "confidence": 0.9,
             "recommendation": "Use parameterised queries", "cwe": "CWE-89"}]}),
        _Out("prioritisation", {"findings": [
            {"title": "CVE-2021-44228", "severity": "critical", "confidence": 0.97,
             "recommendation": "Patch now", "cve": "CVE-2021-44228"}]}),
    ])
    db = _FakeDB()
    row = build_run_report(db, run)
    assert row.agent_name == REPORT_AGENT_NAME
    report = row.output["report"]
    assert report["severity_counts"]["critical"] == 1
    assert report["findings"][0]["severity"] == "critical"   # sorted critical-first
    assert len(report["recommendations"]) == 2
    assert "Most urgent" in report["executive_summary"]
    assert row.output["summary"] == report["executive_summary"]   # frontend-compatible


def test_build_run_report_handles_no_findings():
    db = _FakeDB()
    row = build_run_report(db, _Run([_Out("detection", {"summary": "clean"})]))
    assert row.output["findings"] == []
    assert "No actionable findings" in row.output["report"]["executive_summary"]
