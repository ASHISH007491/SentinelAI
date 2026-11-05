"""Tests for the reporting/output layer (deterministic, no LLM)."""
from app.ai.reporting import ReportBuilder, SecurityReport, Severity


def _cves():
    return [
        {"cve_id": "CVE-A", "cvss": 10.0, "epss": 0.97, "kev": True, "exploit_available": True,
         "description": "Log4Shell"},
        {"cve_id": "CVE-B", "cvss": 9.8, "epss": 0.10, "kev": False, "exploit_available": False,
         "description": "dormant"},
        {"cve_id": "CVE-C", "cvss": 5.0, "epss": 0.02, "kev": False, "exploit_available": False,
         "description": "low"},
    ]


def test_kev_cve_is_critical_and_advised_to_patch_now():
    rep = ReportBuilder("run1").add_vulnerabilities(["CVE-A", "CVE-B", "CVE-C"], _cves()).build()
    a = next(f for f in rep.findings if f.title == "CVE-A")
    assert a.severity is Severity.CRITICAL
    assert "Patch now" in a.recommendation and "KEV" in a.recommendation


def test_severity_mapping_tiers():
    rep = ReportBuilder().add_vulnerabilities(["CVE-A", "CVE-B", "CVE-C"], _cves()).build()
    sev = {f.title: f.severity for f in rep.findings}
    assert sev["CVE-A"] is Severity.CRITICAL    # KEV
    assert sev["CVE-B"] is Severity.HIGH         # cvss>=9
    assert sev["CVE-C"] is Severity.LOW          # low everything


def test_phishing_and_code_only_when_actionable():
    b = ReportBuilder("r")
    b.add_phishing("e1", {"is_phish": True, "confidence": 0.9, "rationale": "spoofed"})
    b.add_phishing("e2", {"is_phish": False, "confidence": 0.8})        # benign -> no finding
    b.add_code("c1", {"vulnerable": True, "cwe": "CWE-89", "confidence": 0.95,
                      "rationale": "sqli", "fix": "Use parameterised queries"})
    b.add_code("c2", {"vulnerable": False})                            # safe -> no finding
    rep = b.build()
    ids = {f.id for f in rep.findings}
    assert ids == {"phish-e1", "code-c1"}
    code = next(f for f in rep.findings if f.id == "code-c1")
    assert code.recommendation == "Use parameterised queries"          # advisor = the fix


def test_report_sorted_counts_and_summary():
    b = ReportBuilder("r").add_vulnerabilities(["CVE-A", "CVE-B", "CVE-C"], _cves())
    b.add_phishing("e1", {"is_phish": True, "confidence": 0.9, "rationale": "x"})
    rep = b.build()
    # sorted by severity desc -> critical first
    assert rep.findings[0].severity is Severity.CRITICAL
    assert rep.severity_counts["critical"] == 1
    assert "Most urgent" in rep.executive_summary
    assert len(rep.recommendations) == len(rep.findings)


def test_markdown_and_json_views():
    rep = ReportBuilder("run1").add_vulnerabilities(["CVE-A"], _cves()).build()
    md = rep.to_markdown()
    assert "# SentinelAI Security Report" in md and "Recommended action" in md
    j = rep.to_json()
    assert j["run_id"] == "run1" and isinstance(j["findings"], list)


def test_empty_report_is_clean():
    rep = ReportBuilder("r").build()
    assert rep.findings == [] and "No actionable findings" in rep.executive_summary
    assert isinstance(rep, SecurityReport)
