"""ReportBuilder: consolidate specialist-agent outputs into one SecurityReport.

This is the analyst-facing output stage and the home of the folded-in 'security advisor':
each finding carries a grounded, rule-derived remediation recommendation, and the report
opens with an executive summary that prioritises the most urgent actions. No free-text
LLM advice — recommendations are deterministic functions of the structured findings, so
they are reproducible and testable.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from app.ai.reporting.models import (
    Finding,
    SecurityReport,
    Severity,
    severity_rank,
)
from app.ai.types.aliases import JSON


class ReportBuilder:
    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self._findings: list[Finding] = []

    # -- vulnerability prioritisation -> findings -------------------------
    def add_vulnerabilities(self, order: list[str], cve_rows: list[JSON], *,
                            top: int = 5) -> ReportBuilder:
        by_id = {c.get("cve_id"): c for c in cve_rows}
        for rank, cve_id in enumerate(order[:top], 1):
            row = by_id.get(cve_id, {})
            sev = self._cve_severity(row)
            kev = bool(row.get("kev"))
            self._findings.append(Finding(
                id=f"vuln-{cve_id}", source="prioritisation", title=cve_id, severity=sev,
                confidence=float(row.get("epss", 0.0) or 0.0),
                summary=f"Patch priority #{rank}. {row.get('description', '')}".strip(),
                recommendation=(
                    f"Patch now (rank #{rank}) — actively exploited (CISA KEV)."
                    if kev else f"Schedule patch (rank #{rank}) by severity/EPSS."
                ),
                evidence={k: row.get(k) for k in ("cvss", "epss", "kev", "exploit_available")},
            ))
        return self

    @staticmethod
    def _cve_severity(row: JSON) -> Severity:
        if row.get("kev"):
            return Severity.CRITICAL
        epss = float(row.get("epss", 0.0) or 0.0)
        cvss = float(row.get("cvss", 0.0) or 0.0)
        if epss >= 0.7 or cvss >= 9.0:
            return Severity.HIGH
        if cvss >= 7.0:
            return Severity.MEDIUM
        return Severity.LOW

    # -- phishing -> findings (only actionable / positive) ----------------
    def add_phishing(self, email_id: str, output: JSON) -> ReportBuilder:
        if not output.get("is_phish"):
            return self
        conf = float(output.get("confidence", 0.0) or 0.0)
        self._findings.append(Finding(
            id=f"phish-{email_id}", source="phishing_verdict", title=f"Phishing email {email_id}",
            severity=Severity.HIGH if conf >= 0.7 else Severity.MEDIUM, confidence=conf,
            summary=str(output.get("rationale", "Suspected phishing.")),
            recommendation=("Quarantine the message, alert the recipient, "
                            "and block the sender domain."),
            evidence={"indicators": output.get("indicators", {})},
        ))
        return self

    # -- code review -> findings (only vulnerable) ------------------------
    def add_code(self, snippet_id: str, output: JSON) -> ReportBuilder:
        if not output.get("vulnerable"):
            return self
        cwe = output.get("cwe")
        fix = str(output.get("fix") or "").strip()
        self._findings.append(Finding(
            id=f"code-{snippet_id}", source="code_review",
            title=f"Vulnerable code {snippet_id}" + (f" ({cwe})" if cwe else ""),
            severity=Severity.HIGH, confidence=float(output.get("confidence", 0.0) or 0.0),
            summary=str(output.get("rationale", "Potential vulnerability.")),
            recommendation=fix or "Remediate following secure-coding guidance for the CWE.",
            evidence={"cwe": cwe},
        ))
        return self

    # -- generic findings (e.g. from the live agent pipeline) -------------
    def add_findings(self, source: str, findings: list[JSON]) -> ReportBuilder:
        """Consume arbitrary finding dicts (title/severity/recommendation/...) so the
        reporting layer can summarise outputs from any agent pipeline."""
        for i, f in enumerate(findings):
            rec = str(f.get("recommendation") or "").strip() or "Review and remediate."
            self._findings.append(Finding(
                id=f"{source}-{i}", source=source, title=str(f.get("title", "finding")),
                severity=self._coerce_severity(f.get("severity")),
                confidence=float(f.get("confidence", 0.0) or 0.0),
                summary=str(f.get("evidence") or f.get("explanation") or ""),
                recommendation=rec,
                evidence={k: f.get(k) for k in ("cve", "cvss", "component", "rule", "line")
                          if f.get(k) is not None},
            ))
        return self

    @staticmethod
    def _coerce_severity(value: object) -> Severity:
        try:
            return Severity(str(value).lower())
        except ValueError:
            return Severity.INFO

    # -- assemble ---------------------------------------------------------
    def build(self) -> SecurityReport:
        findings = sorted(
            self._findings,
            key=lambda f: (-severity_rank(f.severity), -f.confidence),
        )
        counts = Counter(f.severity.value for f in findings)
        recs = [f"[{f.severity.value}] {f.title}: {f.recommendation}" for f in findings]
        return SecurityReport(
            run_id=self.run_id,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            findings=findings,
            severity_counts=dict(counts),
            recommendations=recs,
            executive_summary=self._summary(findings, counts),
        )

    @staticmethod
    def _summary(findings: list[Finding], counts: Counter) -> str:
        if not findings:
            return "No actionable findings were identified."
        parts = [
            f"{counts[s.value]} {s.value}"
            for s in Severity if counts.get(s.value)
        ]
        head = f"{len(findings)} finding(s): " + ", ".join(parts) + "."
        top = findings[0]
        return f"{head} Most urgent: {top.title} — {top.recommendation}"
