"""Round-trip tests for real-corpus ingestion (synthetic feeds, tmp output)."""
from pathlib import Path

import pytest
from eval.datasets import ingest, loaders


def _redirect(monkeypatch, tmp: Path):
    monkeypatch.setattr(ingest, "FULL", tmp)
    monkeypatch.setattr(loaders, "FULL", tmp)


def _feeds(tmp_path: Path) -> tuple[str, str, str]:
    (tmp_path / "epss.csv").write_text(
        "#model\ncve,epss,percentile\nCVE-2021-44228,0.97,0.99\nCVE-2000-0001,0.02,0.10\n")
    (tmp_path / "kev.json").write_text('{"vulnerabilities":[{"cveID":"CVE-2021-44228"}]}')
    (tmp_path / "cvss.json").write_text(
        '{"CVE-2021-44228": 10.0, "CVE-2000-0001": 3.1}')
    return (str(tmp_path / "epss.csv"), str(tmp_path / "kev.json"),
            str(tmp_path / "cvss.json"))


def test_ingest_cves_from_epss_kev_and_cvss(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    epss, kev, cvss = _feeds(tmp_path)
    n = ingest.ingest_cves(epss, kev, cvss)
    assert n == 2
    cves = loaders.load_cves()                      # auto-picks the ingested full set
    by = {c.cve_id: c for c in cves}
    assert by["CVE-2021-44228"].kev is True and by["CVE-2021-44228"].epss == 0.97
    assert by["CVE-2021-44228"].cvss == 10.0
    assert by["CVE-2000-0001"].kev is False


def test_ingest_cves_refuses_without_real_cvss(monkeypatch, tmp_path):
    """Integrity guard: never fabricate a 0.0 CVSS when no real score is supplied."""
    _redirect(monkeypatch, tmp_path)
    epss, kev, _ = _feeds(tmp_path)
    with pytest.raises(SystemExit):
        ingest.ingest_cves(epss, kev)


def test_ingest_emails_from_files(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    phish = tmp_path / "phish"
    ham = tmp_path / "ham"
    phish.mkdir()
    ham.mkdir()
    (phish / "p1.eml").write_text(
        "From: a@evil.com\nSubject: Verify now\n\nClick http://evil.com to verify.")
    (ham / "h1.eml").write_text("From: b@corp.com\nSubject: Lunch\n\nSee you at noon.")
    n = ingest.ingest_emails(str(phish), str(ham))
    assert n == 2
    emails = loaders.load_emails()
    labels = {e.label.value for e in emails}
    assert labels == {"phish", "legit"}
    phish_email = next(e for e in emails if e.label.value == "phish")
    assert "verify" in phish_email.body.lower()


def test_ingest_code_from_manifest(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    (tmp_path / "bad.java").write_text('String q="SELECT *"+u; st.execute(q);')
    (tmp_path / "good.java").write_text('PreparedStatement ps=c.prepareStatement("SELECT ?");')
    (tmp_path / "manifest.csv").write_text(
        "file,vulnerable,cwe,language\nbad.java,true,CWE-89,java\ngood.java,false,,java\n")
    n = ingest.ingest_code(str(tmp_path / "manifest.csv"))
    assert n == 2
    code = loaders.load_code()
    assert {c.vulnerable for c in code} == {True, False}
    vuln = next(c for c in code if c.vulnerable)
    assert vuln.cwe == "CWE-89"
