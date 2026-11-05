"""GuardedSystem: wrap any SystemUnderTest with the prompt-injection guardrail.

Sanitises the untrusted fields of each case (email body/subject, code, CVE descriptions)
before delegating to the inner system, so injected directives are stripped before they
ever reach an agent prompt. Lets the harness measure attack-success-rate for the *same*
system with the defence on vs off (Track D).
"""
from __future__ import annotations

from eval.datasets.types import CodeCase, CVECase, EmailCase  # noqa: E402
from eval.systems.bridge import PromptGuard  # re-exported below
from eval.systems.contracts import Ranking, Verdict
from eval.systems.llm import LLMClient  # noqa: F401  (typing parity)


class GuardedSystem:
    def __init__(self, inner, guard: PromptGuard | None = None) -> None:
        self._inner = inner
        self._guard = guard or PromptGuard()

    @property
    def name(self) -> str:
        return f"guarded_{self._inner.name}"

    def _clean(self, text: str) -> str:
        return self._guard.sanitise(text).clean_text

    def prioritise(self, cves: list[CVECase]) -> Ranking:
        cleaned = [c.model_copy(update={"description": self._clean(c.description)}) for c in cves]
        return self._inner.prioritise(cleaned)

    def investigate_email(self, email: EmailCase) -> Verdict:
        cleaned = email.model_copy(update={
            "body": self._clean(email.body), "subject": self._clean(email.subject)})
        return self._inner.investigate_email(cleaned)

    def review_code(self, code: CodeCase) -> Verdict:
        return self._inner.review_code(code.model_copy(update={"code": self._clean(code.code)}))
