"""Unit tests for the real agent pipeline (offline / rule-based path, no API key)."""
from app.agents.advisor import AdvisorAgent
from app.agents.base import AgentContext
from app.agents.detection import DetectionAgent
from app.agents.prioritisation import PrioritisationAgent
from app.agents.report import ReportAgent
from app.core.llm_client import LLMClient

VULNERABLE = """
import os
def run(cmd):
    os.system(cmd)
rows = db.execute("SELECT * FROM items WHERE name = '" + term + "'")
app.run(debug=True)
# tracking CVE-2024-3094
"""


def _ctx(text=VULNERABLE):
    # No API key -> LLMClient.available is False -> deterministic rule-based path.
    return AgentContext(
        workflow="vuln",
        artefact_text=text,
        artefact_names=["app.py"],
        llm=LLMClient(api_key=""),
    )


def test_detection_finds_known_patterns():
    ctx = _ctx()
    result = DetectionAgent().run(ctx)
    titles = " ".join(f.title.lower() for f in result.findings)
    assert "command execution" in titles
    assert "sql injection" in titles
    assert "debug mode" in titles
    assert any(f.cve == "CVE-2024-3094" for f in result.findings)


def test_prioritisation_orders_critical_first():
    ctx = _ctx()
    DetectionAgent().run(ctx)
    result = PrioritisationAgent().run(ctx)
    severities = [f.severity for f in result.findings]
    # critical/high must come before medium/low
    rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    assert severities == sorted(severities, key=lambda s: rank[s])
    assert result.data["severity_counts"]


def test_advisor_and_report_produce_output():
    ctx = _ctx()
    DetectionAgent().run(ctx)
    PrioritisationAgent().run(ctx)
    advisor = AdvisorAgent().run(ctx)
    report = ReportAgent().run(ctx)
    assert advisor.summary
    assert report.data["total_findings"] == len(ctx.findings)
    assert report.data["findings"]


def test_clean_artefact_has_no_findings():
    ctx = _ctx(text="print('hello world')\nx = 1 + 1\n")
    result = DetectionAgent().run(ctx)
    assert result.findings == []
