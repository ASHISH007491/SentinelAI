"""Dataset loaders + real-feed adapters for the three evaluation tracks.

Loaders read frozen, normalized sample files committed under ``samples/`` so every
run is reproducible and fully offline (a hard requirement for the harness). To scale
up to the full public feeds, drop the real files in and use the adapters below to
convert them into the same normalized format the loaders consume.

Sources (public, free) the adapters target:
  - CVSS/CVE   : NVD JSON 2.0 feeds (nvd.nist.gov)
  - EPSS       : FIRST EPSS daily CSV (first.org/epss)
  - KEV        : CISA Known Exploited Vulnerabilities JSON (cisa.gov)
  - Phishing   : Nazario / SpamAssassin public corpora (synthetic stand-ins here)
  - Code       : OWASP Benchmark / NIST Juliet (synthetic stand-ins here)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from eval.datasets.types import CodeCase, CVECase, EmailCase

SAMPLES = Path(__file__).resolve().parent / "samples"
FULL = Path(__file__).resolve().parent / "full"


def _pick(full_name: str, sample_name: str) -> Path:
    """Prefer an ingested full dataset over the frozen sample.

    Falls back to the committed sample if the full file is missing, empty, or
    unreadable, so the offline CLI/tests never crash when only samples are present.
    """
    full = FULL / full_name
    try:
        if full.exists() and full.stat().st_size > 0:
            return full
    except OSError:
        pass
    return SAMPLES / sample_name


# --- loaders (offline, normalized) ------------------------------------------
def load_cves(path: Path | None = None) -> list[CVECase]:
    raw = json.loads((path or _pick("cve_full.json", "cve_sample.json")).read_text())
    return [CVECase.model_validate(r) for r in raw]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_emails(path: Path | None = None) -> list[EmailCase]:
    rows = _read_jsonl(path or _pick("emails_full.jsonl", "phishing_sample.jsonl"))
    return [EmailCase.model_validate(r) for r in rows]


def load_code(path: Path | None = None) -> list[CodeCase]:
    rows = _read_jsonl(path or _pick("code_full.jsonl", "code_sample.jsonl"))
    return [CodeCase.model_validate(r) for r in rows]


# --- real-feed adapters: full public feeds -> normalized CVECase ------------
def adapt_epss_csv(path: Path) -> dict[str, float]:
    """Parse a FIRST EPSS daily CSV (header line then ``cve,epss,percentile``)."""
    scores: dict[str, float] = {}
    lines = [ln for ln in path.read_text().splitlines() if ln and not ln.startswith("#")]
    reader = csv.DictReader(lines)
    for row in reader:
        cve = (row.get("cve") or "").strip()
        if cve:
            scores[cve] = float(row.get("epss", 0.0) or 0.0)
    return scores


def adapt_kev_json(path: Path) -> set[str]:
    """Parse the CISA KEV catalogue JSON -> set of known-exploited CVE ids."""
    data = json.loads(path.read_text())
    return {v["cveID"] for v in data.get("vulnerabilities", []) if v.get("cveID")}


def _nvd_base_score(metrics: dict) -> float | None:
    """Pull a CVSS base score from an NVD 2.0 `metrics` block.

    Prefers CVSS v3.1, then v3.0, then v2 — matching how NVD layers its scores.
    Returns None when a record carries no score (rejected/awaiting-analysis CVEs).
    """
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key) or []
        if entries:
            data = entries[0].get("cvssData", {})
            score = data.get("baseScore")
            if score is not None:
                return float(score)
    return None


def adapt_nvd_json(path: Path) -> tuple[dict[str, float], dict[str, str]]:
    """Parse a raw NVD JSON 2.0 feed -> ({cve_id: cvss_base}, {cve_id: description}).

    Handles the real feed shape: ``vulnerabilities[].cve`` with ``id``, ``metrics``
    and English ``descriptions``. Records without a CVSS score are skipped so they
    don't pollute the ranking with a fabricated 0.0.
    """
    data = json.loads(path.read_text())
    cvss: dict[str, float] = {}
    descriptions: dict[str, str] = {}
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        cve_id = cve.get("id")
        if not cve_id:
            continue
        score = _nvd_base_score(cve.get("metrics", {}))
        if score is None:
            continue                       # no score yet -> not usable ground truth
        cvss[cve_id] = score
        for d in cve.get("descriptions", []):
            if d.get("lang") == "en":
                descriptions[cve_id] = d.get("value", "")
                break
    return cvss, descriptions


def enrich_from_feeds(
    nvd_path: Path, epss_path: Path, kev_path: Path
) -> list[CVECase]:
    """One-call pipeline: raw NVD + EPSS + KEV feeds -> normalized CVECases.

    This is the bridge from the full public feeds to the harness. Download the three
    files, point this at them, and Track A runs on real data with no other changes.
    """
    cvss, descriptions = adapt_nvd_json(nvd_path)
    epss = adapt_epss_csv(epss_path)
    kev = adapt_kev_json(kev_path)
    return merge_cve_signals(cvss, epss=epss, kev=kev, descriptions=descriptions)


def merge_cve_signals(
    cvss: dict[str, float],
    *,
    epss: dict[str, float] | None = None,
    kev: set[str] | None = None,
    descriptions: dict[str, str] | None = None,
) -> list[CVECase]:
    """Combine per-CVE CVSS with EPSS + KEV feeds into normalized CVECases.

    Lets the dissertation swap the frozen sample for the full public feeds without
    touching any downstream harness/agent code.
    """
    epss = epss or {}
    kev = kev or set()
    descriptions = descriptions or {}
    cases: list[CVECase] = []
    for cve_id, base in cvss.items():
        cases.append(
            CVECase(
                cve_id=cve_id,
                cvss=base,
                epss=epss.get(cve_id, 0.0),
                kev=cve_id in kev,
                exploit_available=cve_id in kev,
                description=descriptions.get(cve_id, ""),
            )
        )
    return cases


if __name__ == "__main__":
    import sys
    if "--sample" in sys.argv:
        cases = load_cves()
        if cases:
            case = cases[0]
            print(f"CVE Sample: {case.cve_id}")
            print(f"  CVSS: {case.cvss}")
            print(f"  EPSS: {case.epss}")
            print(f"  KEV: {case.kev}")
            print(f"  Description: {case.description[:80]}...")
    else:
        print("Usage: python -m eval.datasets.loaders --sample")
