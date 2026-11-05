"""Tests for the Security Advisor (aggregation, prioritisation, scoring, recommendations)."""
import asyncio

from app.ai.advisor import (
    RecommendationEngine,
    RiskLevel,
    RiskPrioritisationEngine,
    SecurityAdvisor,
    SecurityScoreEngine,
)


def _outputs():
    return [
        {"agent_name": "prioritisation", "output": {"findings": [
            {"title": "CVE-2021-44228", "severity": "critical", "cvss": 10.0,
             "cve": "CVE-2021-44228", "confidence": 0.97, "recommendation": "Patch now",
             "evidence": {"kev": True, "exploit_available": True}},
            {"title": "CVE-2015-1635", "severity": "low", "cvss": 10.0,
             "cve": "CVE-2015-1635", "confidence": 0.4, "recommendation": "Schedule patch",
             "evidence": {"kev": False}},
        ]}},
        {"agent_name": "code_review", "output": {"findings": [
            {"title": "SQL injection (CWE-89)", "severity": "high", "cvss": 0.0,
             "confidence": 0.9, "recommendation": "Use parameterised queries"},
        ]}},
    ]


def _assess():
    return asyncio.run(SecurityAdvisor().assess(_outputs(), run_id="r1"))


# --- prioritisation ---------------------------------------------------------
def test_prioritisation_ranks_kev_critical_first():
    a = _assess()
    assert a.prioritised[0].cve == "CVE-2021-44228"
    assert a.prioritised[0].risk_level is RiskLevel.CRITICAL
    # KEV/exploit + high confidence beats a dormant high-CVSS low-severity item
    assert a.prioritised[0].risk_score > a.prioritised[-1].risk_score


def test_deduplicates_findings():
    dupes = [{"agent_name": "prioritisation", "output": {"findings": [
        {"title": "X", "cve": "CVE-1", "severity": "high", "recommendation": "fix"},
        {"title": "X", "cve": "CVE-1", "severity": "critical", "recommendation": "fix"},
    ]}}]
    a = asyncio.run(SecurityAdvisor().assess(dupes))
    assert len(a.prioritised) == 1
    assert a.prioritised[0].severity is RiskLevel.CRITICAL   # dedupe keeps the strongest


# --- scoring ----------------------------------------------------------------
def test_score_is_explainable_and_penalised():
    a = _assess()
    assert 0 <= a.score.overall <= 100
    assert a.score.overall < 100                    # findings deduct points
    assert "overall" in a.score.explanation and a.score.explanation["overall"]
    assert a.score.code_security < 100              # code finding hit that domain


def test_clean_input_scores_100():
    a = asyncio.run(SecurityAdvisor().assess([]))
    assert a.score.overall == 100 and a.posture == "Strong"
    assert "No actionable findings" in a.executive_summary


# --- recommendations --------------------------------------------------------
def test_recommendations_have_reasoning_and_horizon():
    a = _assess()
    assert a.recommendations
    assert all(r.reasoning for r in a.recommendations)      # every rec justified
    assert any(r.horizon == "immediate" for r in a.recommendations)
    # the critical CVE's own fix text is used
    assert any("Patch now" in r.action for r in a.recommendations)


def test_systemic_long_term_recommendation_added_for_code():
    a = _assess()
    assert any(r.horizon == "long_term" and "secure-coding" in r.action.lower()
               for r in a.recommendations)


# --- summaries + DI ---------------------------------------------------------
def test_summaries_present_and_json_serialisable():
    a = _assess()
    assert a.executive_summary and a.technical_summary and a.business_impact
    assert a.posture in ("Strong", "Moderate", "Weak", "Critical exposure")
    j = a.to_json()
    assert j["run_id"] == "r1" and isinstance(j["prioritised"], list)


def test_dependency_injection():
    adv = SecurityAdvisor(prioritiser=RiskPrioritisationEngine(),
                          scorer=SecurityScoreEngine(),
                          recommender=RecommendationEngine())
    a = asyncio.run(adv.assess(_outputs()))
    assert a.score.overall < 100


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
