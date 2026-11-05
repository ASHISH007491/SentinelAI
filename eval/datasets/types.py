"""Typed dataset case models + ground-truth helpers for the evaluation tracks.

Every track loads a list of these typed cases with a ground-truth label, so the
harness can score multi-agent vs. single-agent output on identical inputs. All data
is public or synthetic — no real personal email is ever stored (keeps the ethics
answers clean).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Track(str, Enum):
    VULN = "vuln"            # Track A: vulnerability prioritisation
    PHISHING = "phishing"    # Track B: phishing investigation
    CODE = "code"            # Track C: secure-code review


# --- Track A: vulnerability prioritisation -----------------------------------
class CVECase(BaseModel):
    """A single CVE with the public signals used to derive a patch-priority order."""

    cve_id: str
    cvss: float = Field(ge=0.0, le=10.0)        # CVSS v3 base score
    epss: float = Field(ge=0.0, le=1.0)         # FIRST EPSS exploitation probability
    kev: bool = False                            # present in CISA KEV catalogue
    exploit_available: bool = False             # public exploit known
    description: str = ""

    def priority_score(self) -> float:
        """Ground-truth-ish urgency: exploitation probability dominates, KEV/exploit
        add weight, CVSS breaks ties. This is the *reference* ordering Track A scores
        an agent against (and against raw-CVSS as a baseline)."""
        score = self.epss
        if self.kev:
            score += 1.0           # known-exploited beats everything else
        if self.exploit_available:
            score += 0.25
        return score + self.cvss / 100.0


# --- Track B: phishing investigation -----------------------------------------
class EmailLabel(str, Enum):
    PHISH = "phish"
    LEGIT = "legit"


class EmailCase(BaseModel):
    id: str
    subject: str = ""
    sender: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""
    label: EmailLabel                            # ground truth
    source: str = "synthetic"


# --- Track C: secure-code review ---------------------------------------------
class CodeCase(BaseModel):
    id: str
    language: str = "python"
    code: str
    vulnerable: bool                             # ground truth
    cwe: str | None = None                       # e.g. "CWE-89"
    source: str = "synthetic"


def cve_ground_truth_order(cases: list[CVECase]) -> list[str]:
    """Reference patch order: highest priority_score first, cve_id as a stable tiebreak."""
    return [c.cve_id for c in sorted(cases, key=lambda c: (-c.priority_score(), c.cve_id))]


def cvss_baseline_order(cases: list[CVECase]) -> list[str]:
    """Naive non-AI baseline: order by raw CVSS only (what Track A aims to beat)."""
    return [c.cve_id for c in sorted(cases, key=lambda c: (-c.cvss, c.cve_id))]
