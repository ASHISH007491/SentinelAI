"""Detection agent: surface security findings from the uploaded artefact.

With an LLM available it asks the model to extract findings as JSON. Without one,
it runs a deterministic rule-based scan over the artefact text so the system stays
functional (and unit tests are reproducible) offline.
"""
from __future__ import annotations

import json
import re

from app.agents.base import Agent, AgentContext
from app.agents.schemas import AgentResult, Finding

# (regex, title, severity, cvss, rule, recommendation)
_RULES: list[tuple[str, str, str, float, str, str]] = [
    (r"os\.system\s*\(", "OS command execution from user input", "critical", 9.1, "CWE-78",
     "Avoid os.system; use subprocess with an argument list and validate input."),
    (r"eval\s*\(|exec\s*\(", "Dangerous dynamic code execution", "critical", 8.8, "CWE-95",
     "Remove eval/exec; parse input explicitly."),
    (r"SELECT\s.+\+\s|execute\s*\(\s*[\"'].*\+",
     "Possible SQL injection via string concatenation", "high", 8.2, "CWE-89",
     "Use parameterised queries instead of string concatenation."),
    (r"(password|passwd|secret|api[_-]?key|token)\s*=\s*[\"'][^\"']{6,}",
     "Hardcoded secret", "high", 7.5, "CWE-798",
     "Move secrets to environment variables or a secrets manager."),
    (r"debug\s*=\s*True", "Debug mode enabled", "medium", 5.3, "CWE-489",
     "Disable debug in production; it exposes the interactive debugger."),
    (r"verify\s*=\s*False|InsecureRequestWarning|ssl\._create_unverified",
     "TLS verification disabled", "high", 7.4, "CWE-295",
     "Enable certificate verification for all outbound TLS."),
    (r"md5\s*\(|hashlib\.md5|sha1\s*\(", "Weak cryptographic hash", "medium", 5.9, "CWE-327",
     "Use SHA-256 or stronger for security-sensitive hashing."),
    (r"pickle\.loads?\s*\(", "Insecure deserialization", "high", 8.1, "CWE-502",
     "Avoid pickle for untrusted data; use JSON or a safe schema."),
]

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,7}")


class DetectionAgent(Agent):
    name = "detection"
    _rules: list[tuple[str, str, str, float, str, str]] = _RULES

    def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.llm.available:
            findings = self._detect_with_llm(ctx)
            if findings is not None:
                ctx.findings = findings
                return AgentResult(agent=self.name, findings=findings,
                                   summary=f"LLM detected {len(findings)} finding(s)")
        findings = self._detect_with_rules(ctx)
        ctx.findings = findings
        return AgentResult(agent=self.name, findings=findings,
                           summary=f"Rule-based scan found {len(findings)} finding(s)")

    # --- offline path -----------------------------------------------------
    def _detect_with_rules(self, ctx: AgentContext) -> list[Finding]:
        text = ctx.artefact_text or ""
        lines = text.splitlines()
        findings: list[Finding] = []
        for pattern, title, sev, cvss, rule, rec in self._rules:
            rx = re.compile(pattern, re.IGNORECASE)
            for i, line in enumerate(lines, start=1):
                if rx.search(line):
                    findings.append(Finding(
                        title=title, severity=sev, cvss=cvss, rule=rule, line=i,
                        component=ctx.artefact_names[0] if ctx.artefact_names else "artefact",
                        evidence=line.strip()[:200], recommendation=rec, confidence=0.7,
                    ))
                    break  # one finding per rule keeps output readable
        # Surface any CVE identifiers referenced in the artefact.
        for cve in sorted(set(_CVE_RE.findall(text))):
            findings.append(Finding(
                title=f"Referenced vulnerability {cve}", severity="high", cvss=7.5, cve=cve,
                component=ctx.artefact_names[0] if ctx.artefact_names else "artefact",
                recommendation="Confirm affected versions and apply the vendor patch.",
                confidence=0.6,
            ))
        return findings

    # --- LLM path ---------------------------------------------------------
    def _llm_instructions(self) -> str:
        return (
            "Analyse the artefact below for security vulnerabilities. Return ONLY a JSON array; "
            "each item: {title, severity (critical|high|medium|low|info), cvss (0-10), component, "
            "cve (or null), recommendation, evidence}. Artefact:\n\n"
        )

    def _detect_with_llm(self, ctx: AgentContext) -> list[Finding] | None:
        prompt = self._llm_instructions() + ctx.artefact_text[:12000]
        try:
            resp = ctx.llm.complete(prompt, max_tokens=1500)
            ctx.record_usage(resp.usage)
            raw = resp.text[resp.text.find("[") : resp.text.rfind("]") + 1]
            items = json.loads(raw)
            return [
                Finding(
                    title=str(it.get("title", "Finding")),
                    severity=str(it.get("severity", "info")).lower(),
                    cvss=float(it.get("cvss", 0) or 0),
                    component=str(it.get("component", "")),
                    cve=it.get("cve") or None,
                    evidence=str(it.get("evidence", ""))[:200],
                    recommendation=str(it.get("recommendation", "")),
                    confidence=0.8,
                )
                for it in items
                if isinstance(it, dict)
            ]
        except Exception:
            return None  # fall back to rules on any parse/API failure


_PHISHING_RULES: list[tuple[str, str, str, float, str, str]] = [
    (r"gift\s?card|wire\s+transfer|reimburse\s+you",
     "Gift-card / wire-transfer request", "critical", 8.5, "PHISH-BEC",
     "Classic business-email-compromise pattern; verify the request out-of-band before acting."),
    (r"verify\s+(your\s+)?account|account\s+(has\s+been\s+)?(locked|suspended)|"
     r"unlock\s+(your\s+)?account",
     "Account-verification / lockout pressure", "high", 7.0, "PHISH-URGENCY",
     "Do not use the link in the email; log in via the service's known URL directly."),
    (r"click\s+(here|below)|verify\s+(now|within)|pay\s+now|update\s+(your\s+)?(card|payment)",
     "Urgent call-to-action link", "high", 6.5, "PHISH-CTA",
     "Treat unsolicited urgent links as suspicious; hover/inspect the real destination first."),
    (r"confidential|do\s+not\s+(tell|discuss|forward)|keep\s+this\s+between\s+us",
     "Secrecy / confidentiality pressure", "medium", 5.5, "PHISH-SECRECY",
     "Legitimate requests rarely demand secrecy from colleagues; verify via a separate channel."),
    (r"spf=fail|dkim=fail|dkim=none",
     "Failed sender authentication (SPF/DKIM)", "high", 7.5, "PHISH-AUTH",
     "Sender authentication failed; treat the message as unverified regardless of display name."),
    (r"\b[a-z]+[0-9][a-z-]*\.(com|net|org|support|info)\b",
     "Possible lookalike domain (digit-substituted brand name)", "high", 7.0, "PHISH-LOOKALIKE",
     "Compare the domain character-by-character against the real brand domain "
     "(digits often substitute for letters, e.g. 0-for-o, 1-for-l)."),
]


class PhishingDetectionAgent(DetectionAgent):
    """Phishing detection: email-specific rules (urgency, credential/payment requests,
    lookalike domains, failed sender authentication) -- distinct from the code-security
    rules DetectionAgent/CodeReviewAgent use, since email text isn't source code."""
    name = "phishing_detection"
    _rules = _PHISHING_RULES

    def _llm_instructions(self) -> str:
        return (
            "Analyse the email below for phishing indicators. Return ONLY a JSON array; "
            "each item: {title, severity (critical|high|medium|low|info), cvss (0-10), component, "
            "cve (null), recommendation, evidence}. Flag urgency/pressure language, suspicious or "
            "lookalike links/domains, credential or payment requests, and failed sender "
            "authentication (SPF/DKIM). Email:\n\n"
        )


class CodeReviewAgent(DetectionAgent):
    name = "code_review"


_AGENTS: dict[str, type[DetectionAgent]] = {
    "detection": DetectionAgent,
    "phishing_detection": PhishingDetectionAgent,
    "code_review": CodeReviewAgent,
}


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(
        description="Run a detection-family agent (rule-based, offline) over an artefact file."
    )
    parser.add_argument("--agent", choices=sorted(_AGENTS), default="detection",
                         help="Which agent to run.")
    parser.add_argument("--input", required=True, help="Path to the artefact file.")
    args = parser.parse_args()

    path = Path(args.input)
    ctx = AgentContext(workflow=args.agent, artefact_text=path.read_text(encoding="utf-8"),
                        artefact_names=[path.name])
    result = _AGENTS[args.agent]().run(ctx)
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
