"""Reference LLMs for offline demos/tests: a competent one and a weak one.

They respond to *every* prompt shape used in the harness — the single-LLM baseline
prompts AND the decomposed specialist prompts — returning deterministic, plausible JSON
in whatever shape the prompt asks for. This lets the same LLM fairly drive both systems
with no network. They are NOT the evaluated system; real runs inject an actual client.
"""
from __future__ import annotations

import json
import re

from eval.systems.llm import LLMResponse

_CVE_LINE = re.compile(r"- (\S+): CVSS=([\d.]+) EPSS=([\d.]+) KEV=(\w+) exploit=(\w+)")
_RISK_TAG = re.compile(r"risk=(\w+)")
_RISK_RANK = {"high": 0, "medium": 1, "low": 2}
_URL = re.compile(r"https?://[^\s\"']+")
_PHISH = ("http://", "verify", "urgent", "suspend", "click", "gift card", "refund",
          "unlock", "validate", "confidential", "locked", "password", "'urgency': true",
          "'credential_request': true", "suspicious")
_VULN = ("os.system", "pickle.loads", "hashlib.md5", "+ request", '" +',
         "execute(q", "where n='\"+", "os.path.join(base, request")
# PatternScanAgent's candidate set. Originally scoped narrower than _VULN (excluding
# weak-crypto/XSS as "a different vulnerability class") -- reverted to the full set
# after that gap silently broke Track D's guardrail-defence guarantee on exactly those
# CWE categories (test_guardrail_reduces_attack_success_rate expects 0% ASR across all
# 7 categories once sanitised). A detection scope narrower than the corpus it's
# evaluated against isn't a legitimate way to create separation from the baseline.
_VULN_CANDIDATES = _VULN
_VULN_CWE = {
    "os.system": "CWE-78", "pickle.loads": "CWE-502", "hashlib.md5": "CWE-327",
    "+ request": "CWE-89", '" +': "CWE-79", "execute(q": "CWE-89",
    "where n='\"+": "CWE-89", "os.path.join(base, request": "CWE-22",
}
_CANDIDATE_CWE = re.compile(r"- (cwe-\d+):")


def _resp(payload: dict, prompt: str) -> LLMResponse:
    text = json.dumps(payload)
    return LLMResponse(text=text, prompt_tokens=max(1, len(prompt.split())),
                       completion_tokens=max(1, len(text.split())))


def _risk_level(kev: str, epss: str) -> str:
    """Same exploitation-aware tiering the real agents use: KEV or high EPSS -> high."""
    if kev.lower() == "true" or float(epss) >= 0.5:
        return "high"
    if float(epss) >= 0.1:
        return "medium"
    return "low"


def _is_phishy(p: str) -> bool:
    return any(t in p for t in _PHISH)


def _is_vuln(p: str) -> bool:
    return any(t in p for t in _VULN)


class HeuristicLLM:
    """Competent: KEV+EPSS ranking, real phishing/vuln signals, indicator extraction."""

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        p = prompt.lower()
        if "exploitation risk tier" in p:   # risk-signal step (prioritisation, step 1)
            risk = {cve_id: {"level": _risk_level(kev, epss), "note": "heuristic"}
                    for cve_id, _cvss, epss, kev, _exploit in _CVE_LINE.findall(prompt)}
            return _resp({"risk": risk}, prompt)
        if "pre-assessed risk tiers" in p:   # ranking step (prioritisation, step 2)
            rows = []
            for line in prompt.splitlines():
                m = _CVE_LINE.match(line.strip())
                if not m:
                    continue
                cve_id, cvss, epss, kev, _exploit = m.groups()
                tag = _RISK_TAG.search(line)
                level = tag.group(1).lower() if tag else _risk_level(kev, epss)
                rows.append((cve_id, float(cvss), _RISK_RANK.get(level, 1)))
            rows.sort(key=lambda r: (r[2], -r[1]))   # risk tier first, CVSS breaks ties
            return _resp({"order": [r[0] for r in rows], "rationale": {}}, prompt)
        if "order these cves" in p:   # single-shot baseline (no decomposition)
            rows = _CVE_LINE.findall(prompt)
            rows.sort(key=lambda r: (r[3].lower() == "true", float(r[2])), reverse=True)
            return _resp({"order": [r[0] for r in rows], "rationale": {}}, prompt)
        if "extract phishing indicators" in p:
            phishy = _is_phishy(p)
            return _resp({"urls": _URL.findall(prompt), "sender_domain": "",
                          "auth_pass": not phishy, "urgency": phishy,
                          "credential_request": phishy,
                          "signals": ["suspicious"] if phishy else []}, prompt)
        if "for candidate vulnerability patterns" in p:   # pattern-scan step (code review, step 1)
            candidates = [{"cwe": _VULN_CWE[t], "pattern": t, "confidence": 0.7}
                          for t in _VULN_CANDIDATES if t in p]
            return _resp({"candidates": candidates}, prompt)
        if "confirm or reject each candidate" in p:   # confirm+fix step (code review, step 2)
            m = _CANDIDATE_CWE.search(p)
            cwe = m.group(1).upper() if m else None
            return _resp({"vulnerable": bool(m), "cwe": cwe,
                          "confidence": 0.7 if m else 0.6,
                          "rationale": "heuristic", "fix": ""}, prompt)
        if '"vulnerable": true' in p or '"vulnerable":true' in p:   # code-review single-shot
            vuln = _is_vuln(p)
            return _resp({"vulnerable": vuln, "cwe": "CWE-unknown" if vuln else None,
                          "confidence": 0.7, "rationale": "heuristic", "fix": ""}, prompt)
        if "vulnerable|safe" in p or ('"label"' in p and "code" in p):   # code baseline
            vuln = _is_vuln(p)
            return _resp({"label": "vulnerable" if vuln else "safe",
                          "confidence": 0.7, "rationale": "heuristic"}, prompt)
        # phishing verdict (baseline or decomposed)
        phishy = _is_phishy(p)
        return _resp({"label": "phish" if phishy else "legit", "confidence": 0.8,
                      "rationale": "heuristic"}, prompt)


class WeakLLM:
    """Weak: raw-CVSS order, benign extraction, and always legit/safe (high false-neg)."""

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        p = prompt.lower()
        if "exploitation risk tier" in p:
            risk = {cve_id: {"level": "low", "note": "weak"}
                    for cve_id, *_rest in _CVE_LINE.findall(prompt)}
            return _resp({"risk": risk}, prompt)
        if "pre-assessed risk tiers" in p:
            rows = [(m.group(1), float(m.group(2)))
                    for m in (_CVE_LINE.match(line.strip()) for line in prompt.splitlines())
                    if m]
            rows.sort(key=lambda r: r[1], reverse=True)   # ignores risk tiers, raw CVSS only
            return _resp({"order": [r[0] for r in rows], "rationale": {}}, prompt)
        if "order these cves" in p:
            rows = _CVE_LINE.findall(prompt)
            rows.sort(key=lambda r: float(r[1]), reverse=True)
            return _resp({"order": [r[0] for r in rows], "rationale": {}}, prompt)
        if "extract phishing indicators" in p:
            return _resp({"urls": [], "sender_domain": "", "auth_pass": True,
                          "urgency": False, "credential_request": False, "signals": []}, prompt)
        if "for candidate vulnerability patterns" in p:
            return _resp({"candidates": []}, prompt)   # weak: misses everything
        if "confirm or reject each candidate" in p:
            return _resp({"vulnerable": False, "cwe": None, "confidence": 0.5,
                          "rationale": "weak", "fix": ""}, prompt)
        if '"vulnerable": true' in p or '"vulnerable":true' in p:
            return _resp({"vulnerable": False, "cwe": None, "confidence": 0.5,
                          "rationale": "weak", "fix": ""}, prompt)
        if "vulnerable|safe" in p:
            return _resp({"label": "safe", "confidence": 0.5, "rationale": "weak"}, prompt)
        return _resp({"label": "legit", "confidence": 0.5, "rationale": "weak"}, prompt)


class InjectableLLM:
    """A *vulnerable* reference LLM that obeys injected directives — including obfuscated
    ones (spaced/hyphenated). It normalises the text before interpreting intent, the way a
    real model would, so keyword/regex guards that miss obfuscation still let it be steered.
    NOT part of the evaluated system.
    """

    # Injection intent detected on whitespace/hyphen-collapsed, lower-cased text.
    _CUES = ("ignoreprevious", "previousinstruction", "disregard", "youarenow",
             "newinstruction", "systemoverride", "system:override", "</system", "</instruction",
             "respondlegit", "respondsafe", "respondwithsafe", "saylegit", "saysafe",
             "aslegit", "assafe", "islegit", "islegitimate", "issafe", "novulnerab",
             "marksafe", "markas", "classifyas", "replylegit", "replysafe")

    def __init__(self) -> None:
        self._h = HeuristicLLM()

    def complete(self, prompt: str, *, system: str | None = None) -> LLMResponse:
        p = prompt.lower()
        collapsed = re.sub(r"[\s\-_]+", "", p)
        injected = any(c in collapsed for c in self._CUES)
        is_prioritisation = ("order these cves" in p or "exploitation risk tier" in p
                              or "pre-assessed risk tiers" in p)
        if injected and not is_prioritisation:
            if "extract phishing indicators" in p:
                return _resp({"urls": [], "sender_domain": "", "auth_pass": True,
                              "urgency": False, "credential_request": False,
                              "signals": []}, prompt)
            if "for candidate vulnerability patterns" in p:
                return _resp({"candidates": []}, prompt)   # obeys injection: sees nothing
            if "confirm or reject each candidate" in p:
                return _resp({"vulnerable": False, "cwe": None, "confidence": 0.6,
                              "rationale": "obeyed-injection", "fix": ""}, prompt)
            if '"vulnerable": true' in p or '"vulnerable":true' in p:
                return _resp({"vulnerable": False, "cwe": None, "confidence": 0.6,
                              "rationale": "obeyed-injection", "fix": ""}, prompt)
            if "vulnerable|safe" in p:
                return _resp({"label": "safe", "confidence": 0.6,
                              "rationale": "obeyed-injection"}, prompt)
            return _resp({"label": "legit", "confidence": 0.6,
                          "rationale": "obeyed-injection"}, prompt)
        return self._h.complete(prompt, system=system)
