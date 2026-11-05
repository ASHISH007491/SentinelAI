"""Track A premise: exploitation-aware prioritisation should override raw severity/CVSS."""
from app.agents.base import AgentContext
from app.agents.prioritisation import PrioritisationAgent
from app.agents.schemas import Finding
from app.core.llm_client import LLMClient


def _ctx(findings):
    ctx = AgentContext(workflow="vuln", llm=LLMClient(api_key=""))
    ctx.findings = findings
    return ctx


def test_kev_outranks_higher_cvss_without_exploitation():
    findings = [
        Finding(title="dormant-critical", severity="critical", cvss=10.0, epss=0.02, kev=False),
        Finding(title="exploited-medium", severity="medium", cvss=5.0, epss=0.90, kev=True),
    ]
    result = PrioritisationAgent().run(_ctx(findings))
    assert result.findings[0].title == "exploited-medium"      # KEV beats higher CVSS
    assert result.data["kev_count"] == 1
    assert "known-exploited" in result.data["rationale"][0]


def test_epss_breaks_ties_within_same_severity():
    findings = [
        Finding(title="low-epss", severity="high", cvss=8.0, epss=0.05),
        Finding(title="high-epss", severity="high", cvss=8.0, epss=0.85),
    ]
    result = PrioritisationAgent().run(_ctx(findings))
    assert [f.title for f in result.findings] == ["high-epss", "low-epss"]


def test_falls_back_to_severity_when_no_exploitation_signals():
    # All EPSS 0, no KEV -> classic severity-then-CVSS order preserved.
    findings = [
        Finding(title="med", severity="medium", cvss=6.0),
        Finding(title="crit", severity="critical", cvss=9.0),
        Finding(title="low", severity="low", cvss=3.0),
    ]
    result = PrioritisationAgent().run(_ctx(findings))
    assert [f.title for f in result.findings] == ["crit", "med", "low"]


def test_negligible_epss_does_not_outrank_critical_severity():
    """Regression: a near-zero EPSS must not promote a finding above a critical one.

    Absence of exploitation evidence is not evidence of safety -- findings with unknown
    or negligible EPSS fall through to severity/CVSS ordering.
    """
    findings = [
        Finding(title="critical-no-epss", severity="critical", cvss=9.1, epss=0.0),
        Finding(title="high-tiny-epss", severity="high", cvss=7.5, epss=0.0004),
    ]
    result = PrioritisationAgent().run(_ctx(findings))
    assert [f.title for f in result.findings] == ["critical-no-epss", "high-tiny-epss"]
