"""Tests for the evaluation datasets: offline loading, labels, and ground-truth order."""
from pathlib import Path

import pytest
from eval.datasets.loaders import (
    adapt_epss_csv,
    adapt_kev_json,
    adapt_nvd_json,
    enrich_from_feeds,
    load_code,
    load_cves,
    load_emails,
    merge_cve_signals,
)
from eval.datasets.types import (
    CVECase,
    cve_ground_truth_order,
    cvss_baseline_order,
)

SAMPLES = Path(__file__).resolve().parents[1] / "datasets" / "samples"


def test_load_cves_offline_and_typed():
    cves = load_cves()
    assert len(cves) >= 20
    assert all(isinstance(c, CVECase) for c in cves)
    assert all(0.0 <= c.epss <= 1.0 and 0.0 <= c.cvss <= 10.0 for c in cves)


def test_emails_balanced_and_labelled():
    emails = load_emails()
    labels = [e.label.value for e in emails]
    assert len(emails) >= 20
    assert set(labels) == {"phish", "legit"}
    assert labels.count("phish") >= 8 and labels.count("legit") >= 8
    assert all(e.source == "synthetic" for e in emails)


def test_code_cases_have_cwe_when_vulnerable():
    code = load_code()
    assert len(code) >= 12
    assert {c.vulnerable for c in code} == {True, False}
    assert all(c.cwe for c in code if c.vulnerable)
    assert all(c.cwe is None for c in code if not c.vulnerable)


def test_ground_truth_order_beats_naive_cvss():
    cves = load_cves()
    gt = cve_ground_truth_order(cves)
    cvss = cvss_baseline_order(cves)
    assert set(gt) == set(cvss) and len(gt) == len(cves)
    assert gt != cvss


def test_kev_outranks_higher_cvss_without_exploitation():
    exploited = CVECase(cve_id="CVE-A", cvss=7.5, epss=0.9, kev=True)
    dormant = CVECase(cve_id="CVE-B", cvss=10.0, epss=0.05, kev=False)
    assert cve_ground_truth_order([dormant, exploited]) == ["CVE-A", "CVE-B"]


def test_adapt_epss_and_kev_and_merge(tmp_path: Path):
    epss_csv = tmp_path / "epss.csv"
    epss_csv.write_text("#model_version\ncve,epss,percentile\nCVE-X,0.80,0.99\nCVE-Y,0.01,0.10\n")
    kev_json = tmp_path / "kev.json"
    kev_json.write_text('{"vulnerabilities":[{"cveID":"CVE-X"}]}')

    epss = adapt_epss_csv(epss_csv)
    kev = adapt_kev_json(kev_json)
    assert epss == {"CVE-X": 0.80, "CVE-Y": 0.01}
    assert kev == {"CVE-X"}

    cases = merge_cve_signals({"CVE-X": 9.8, "CVE-Y": 9.8}, epss=epss, kev=kev)
    by_id = {c.cve_id: c for c in cases}
    assert by_id["CVE-X"].kev is True and by_id["CVE-X"].epss == 0.80
    assert by_id["CVE-Y"].kev is False
    assert cve_ground_truth_order(cases)[0] == "CVE-X"


def test_adapt_nvd_json_prefers_v31_and_extracts_english():
    cvss, desc = adapt_nvd_json(SAMPLES / "nvd_sample.json")
    assert cvss["CVE-2021-44228"] == 10.0
    assert cvss["CVE-2014-0160"] == 5.0
    assert "Log4Shell" in desc["CVE-2021-44228"]


def test_adapt_nvd_json_skips_unscored_records():
    cvss, _ = adapt_nvd_json(SAMPLES / "nvd_sample.json")
    assert "CVE-2099-99999" not in cvss


def test_enrich_from_feeds_end_to_end(tmp_path: Path):
    epss_csv = tmp_path / "epss.csv"
    epss_csv.write_text("cve,epss,percentile\nCVE-2014-0160,0.94,0.99\nCVE-2021-44228,0.97,0.99\n")
    kev_json = tmp_path / "kev.json"
    kev_json.write_text('{"vulnerabilities":[{"cveID":"CVE-2021-44228"}]}')

    cases = enrich_from_feeds(SAMPLES / "nvd_sample.json", epss_csv, kev_json)
    by_id = {c.cve_id: c for c in cases}
    assert by_id["CVE-2021-44228"].cvss == 10.0
    assert by_id["CVE-2021-44228"].kev is True
    assert by_id["CVE-2014-0160"].epss == 0.94 and by_id["CVE-2014-0160"].kev is False
    assert all(isinstance(c, CVECase) for c in cases)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
