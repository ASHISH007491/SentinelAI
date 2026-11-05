"""Ingest the full public corpora into normalized datasets under ``datasets/full/``.

Downstream loaders auto-prefer ``full/`` files when present, so once you ingest the real
feeds the whole harness runs on real, scaled data with no other changes.

Where to get each (all free):
  CVEs      : FIRST EPSS daily CSV (first.org/epss) + CISA KEV JSON (cisa.gov/kev)
              [optional CVSS map: JSON {cve_id: cvss} from an NVD export]
  Emails    : Nazario phishing corpus + SpamAssassin ham (public research corpora)
  Code      : OWASP Benchmark / NIST Juliet, described by a CSV manifest (file,vulnerable,cwe)

Examples (from the repo root):
  python -m eval.datasets.ingest cves --epss epss.csv --kev kev.json --limit 2000
  python -m eval.datasets.ingest emails --phish ./nazario --ham ./spamassassin_ham --limit 1000
  python -m eval.datasets.ingest code --manifest ./benchmark/manifest.csv
"""
from __future__ import annotations

import argparse
import csv
import email
import json
import logging
from email import policy
from pathlib import Path

from eval.datasets.loaders import adapt_epss_csv, adapt_kev_json, merge_cve_signals
from eval.datasets.types import CodeCase, EmailCase, EmailLabel

logger = logging.getLogger("sentinelai.eval.ingest")

FULL = Path(__file__).resolve().parent / "full"


def _write_json(name: str, rows: list) -> Path:
    FULL.mkdir(exist_ok=True)
    path = FULL / name
    path.write_text(json.dumps(rows, indent=2))
    return path


def _write_jsonl(name: str, rows: list) -> Path:
    FULL.mkdir(exist_ok=True)
    path = FULL / name
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def ingest_cves(epss_csv: str, kev_json: str, cvss_json: str | None = None,
                limit: int | None = None) -> int:
    if not cvss_json:
        raise SystemExit(
            "ingest cves requires --cvss (a {cve_id: baseScore} JSON export from NVD); "
            "without it there is no real CVSS score to ingest, only a fabricated 0.0"
        )
    epss = adapt_epss_csv(Path(epss_csv))
    kev = adapt_kev_json(Path(kev_json))
    cvss_src = json.loads(Path(cvss_json).read_text())
    ids = list(epss)
    if limit:
        ids = sorted(ids, key=lambda c: epss[c], reverse=True)[:limit]  # keep the riskiest
    cvss_map = {cid: float(cvss_src[cid]) for cid in ids if cid in cvss_src}
    cases = merge_cve_signals(cvss_map, epss=epss, kev=kev)
    _write_json("cve_full.json", [c.model_dump() for c in cases])
    return len(cases)


def _email_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_content()
                except Exception:  # noqa: BLE001
                    logger.debug("email part decode failed; skipping part", exc_info=True)
                    continue
        return ""
    try:
        return msg.get_content()
    except Exception:  # noqa: BLE001
        logger.debug("email body decode failed; returning empty body", exc_info=True)
        return ""


def _parse_email(path: Path, label: str) -> EmailCase:
    try:
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        subject = str(msg.get("subject", "") or "")
        sender = str(msg.get("from", "") or "")
        body = _email_body(msg)
    except Exception:  # noqa: BLE001 - malformed message -> treat as plain text
        subject, sender, body = "", "", path.read_text(errors="replace")
    return EmailCase(id=path.stem, subject=subject[:300], sender=sender[:200],
                     body=(body or "")[:20000], label=EmailLabel(label), source=path.parent.name)


def ingest_emails(phish_dir: str, ham_dir: str, limit: int | None = None) -> int:
    rows: list[dict] = []
    for directory, label in ((phish_dir, "phish"), (ham_dir, "legit")):
        n = 0
        for f in sorted(Path(directory).glob("**/*")):
            if not f.is_file():
                continue
            rows.append(_parse_email(f, label).model_dump())
            n += 1
            if limit and n >= limit:
                break
    _write_jsonl("emails_full.jsonl", rows)
    return len(rows)


def ingest_code(manifest_csv: str, limit: int | None = None) -> int:
    base = Path(manifest_csv).parent
    rows: list[dict] = []
    reader = csv.DictReader(Path(manifest_csv).read_text().splitlines())
    for i, r in enumerate(reader):
        if limit and i >= limit:
            break
        code = r.get("code", "")
        if r.get("file"):
            try:
                code = (base / r["file"]).read_text(errors="replace")
            except OSError:
                continue
        vulnerable = str(r.get("vulnerable", "")).strip().lower() in ("1", "true", "yes")
        rows.append(CodeCase(
            id=r.get("id") or r.get("file") or f"code-{i}",
            language=r.get("language", "java"), code=code[:20000],
            vulnerable=vulnerable, cwe=(r.get("cwe") or None), source="manifest",
        ).model_dump())
    _write_jsonl("code_full.jsonl", rows)
    return len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest full public corpora for SentinelAI eval")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cves")
    c.add_argument("--epss", required=True)
    c.add_argument("--kev", required=True)
    c.add_argument("--cvss")
    c.add_argument("--limit", type=int)
    e = sub.add_parser("emails")
    e.add_argument("--phish", required=True)
    e.add_argument("--ham", required=True)
    e.add_argument("--limit", type=int)
    k = sub.add_parser("code")
    k.add_argument("--manifest", required=True)
    k.add_argument("--limit", type=int)
    a = ap.parse_args()

    if a.cmd == "cves":
        print(f"ingested {ingest_cves(a.epss, a.kev, a.cvss, a.limit)} CVEs -> full/cve_full.json")
    elif a.cmd == "emails":
        print(f"ingested {ingest_emails(a.phish, a.ham, a.limit)} emails -> full/emails_full.jsonl")
    else:
        print(f"ingested {ingest_code(a.manifest, a.limit)} snippets -> full/code_full.jsonl")


if __name__ == "__main__":
    main()
